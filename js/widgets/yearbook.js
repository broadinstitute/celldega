import { AwsClient } from 'aws4fetch';
import * as d3 from 'd3';
import { OrthographicController, OrthographicView, ScatterplotLayer } from 'deck.gl';

import { ini_deck, set_views_prop } from '../deck-gl/core/deck_ist';
import { ini_background_layer } from '../deck-gl/layers/background_layer';
import { make_image_layers } from '../deck-gl/layers/image_layers';
import { ini_path_layer, toggle_path_layer_visibility, update_path_layer_data } from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  toggle_trx_layer_visibility,
  update_trx_layer_data,
} from '../deck-gl/layers/trx_layer';
import { options, set_options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_dimensions } from '../global_variables/image_dimensions';
import {
  set_image_format,
  set_image_info,
  set_image_layer_colors,
} from '../global_variables/image_info';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_cluster_metadata } from '../global_variables/meta_cluster';
import { set_meta_gene } from '../global_variables/meta_gene';
import { update_selected_genes } from '../global_variables/selected_genes';
import { create_obs_store } from '../obs_store/obs_store';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { get_scatter_data } from '../read_parquet/get_scatter_data';
import { objects_from_parquet } from '../read_parquet/objects_from_parquet';
import { make_bar_container, make_bar_graph } from '../ui/bar_plot';
import { visibleTiles } from '../vector_tile/visibleTiles';

const makeViewGrid = (rows, cols, width, height) => {
  const views = [];
  const spacing = 8;
  const usableWidth = Math.max(width - spacing * (cols + 1), width * 0.9);
  const usableHeight = Math.max(height - spacing * (rows + 1), height * 0.9);
  const cellWidth = usableWidth / cols;
  const cellHeight = usableHeight / rows;

  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const id = `cell-${r * cols + c}`;
      views.push(
        new OrthographicView({
          id,
          x: spacing + c * (cellWidth + spacing),
          y: spacing + r * (cellHeight + spacing),
          width: cellWidth,
          height: cellHeight,
        })
      );
    }
  }
  return { views, cellWidth, cellHeight };
};

const computeZoomForWindow = (windowSizeUm, viewportWidth) => {
  const safeWindow = windowSizeUm > 0 ? windowSizeUm : 20;
  const safeViewport = viewportWidth > 0 ? viewportWidth : 200;
  return Math.log2(safeViewport / safeWindow);
};

const getWindowSize = (model) => {
  const windowSize = model.get('window_size_um');
  if (windowSize !== undefined && windowSize !== null) return windowSize;
  return model.get('cell_size_um') || 20;
};

const shuffle = (array) => array.sort(() => Math.random() - 0.5);

const hashColor = (name) => {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const r = (hash >> 16) & 0xff;
  const g = (hash >> 8) & 0xff;
  const b = hash & 0xff;
  return [Math.abs(r), Math.abs(g), Math.abs(b)];
};

const create_yearbook_get_tile_data = (viz_state, base_get_tile_data) => {
  return async (params) => {
    const { index } = params || {};
    if (!index) return base_get_tile_data(params);

    const { x, y } = index;
    const tiles = viz_state.image_yearbook_tiles || [];

    // if we don't have a manifest yet, just pass through (good for debugging)
    if (!tiles.length) {
      return base_get_tile_data(params);
    }

    const has_tile = tiles.some((t) => t.x === x && t.y === y);

    if (!has_tile) {
      // tile outside our allowed range; skip
      return null;
    }

    return base_get_tile_data(params);
  };
};


export const render_yearbook = async ({ model, el }) => {
  const base_url = model.get('base_url');
  const token = model.get('token');
  const creds = model.get('creds');
  const segmentation = model.get('segmentation') || 'default';
  const maxTilesToView = model.get('max_tiles_to_view') || 50;

  const state = {
    aws: null,
    deck: null,
    imageLayerTemplates: [],
    imageLayerIds: new Set(),
    backgroundLayer: null,
    overlays: { path_layer: null, trx_layer: null },
    obs_store: create_obs_store(),
    cellPositions: new Map(),
    metaCell: { result: {}, attr: [] },
    capacity: 0,
    cellWidth: 0,
    cellHeight: 0,
    mounted: true,
    viz_state: null,
    showSegments: true,
    showTranscripts: true,
    barGraphs: null,
    geneSearch: null,
    globalZoom: null,
    viewTargets: new Map(),
  };

  set_options(token);

  if (creds && creds.accessKeyId) {
    state.aws = new AwsClient({
      accessKeyId: creds.accessKeyId,
      secretAccessKey: creds.secretAccessKey,
      sessionToken: creds.sessionToken,
      region: 'us-east-1',
      service: 's3',
    });
  }

  const controls = document.createElement('div');
  controls.className = 'celldega-yearbook-controls';
  el.appendChild(controls);

  const gridRoot = document.createElement('div');
  gridRoot.className = 'celldega-yearbook-grid';
  el.appendChild(gridRoot);

  const makeDeck = async () => {
    const rows = model.get('rows') || 2;
    const cols = model.get('cols') || 3;
    const width = model.get('width') || gridRoot.clientWidth || cols * 240;
    const height = model.get('height') || gridRoot.clientHeight || rows * 240;

    gridRoot.style.width = typeof width === 'number' ? `${width}px` : `${width}`;
    gridRoot.style.height = `${height}px`;

    const { views, cellWidth, cellHeight } = makeViewGrid(rows, cols, width, height);
    state.capacity = rows * cols;
    state.cellWidth = cellWidth;
    state.cellHeight = cellHeight;

    // ⬅️ back to per-view controller map (this is what ini_deck expects)
    const controller = views.reduce((acc, view) => {
      acc[view.id] = {
        type: OrthographicController,
        scrollZoom: true,
        dragPan: false,
        dragRotate: false,
        doubleClickZoom: true,
        keyboard: false,
      };
      return acc;
    }, {});

    const deck = ini_deck(gridRoot, width, height, '', controller);
    set_views_prop(deck, views);
    state.deck = deck;

    deck.setProps({
      views,
      // Only share zoom, keep each portrait locked to its own target
      onViewStateChange: ({ viewId, viewState }) => {
        if (!viewId || !viewState || !Number.isFinite(viewState.zoom)) return;
        if (!state.viewTargets.size) return;

        // whichever portrait you scroll in becomes the zoom source
        state.globalZoom = viewState.zoom;

        const syncedViewState = {};
        state.viewTargets.forEach((target, targetViewId) => {
          syncedViewState[targetViewId] = {
            target,
            zoom: state.globalZoom,
          };
        });

        deck.setProps({ viewState: syncedViewState });
      },
    });
  };

  const setupImagery = async () => {
    const viz_state = { img: {}, obs_store: state.obs_store };
    set_global_base_url(viz_state, base_url);
    viz_state.aws = state.aws;

    viz_state.genes = {
      trx_data: [],
      trx_names_array: [],
      color_dict_gene: {},
      selected_genes: [],
      top_gene_counts: [],
      meta_gene: {},
      gene_counts: [],
      g_nameMapping_inv: {},
      gene_names: [],
      trx_ini_radius: undefined,
      gene_text_box: '',
      trx_slider: document.createElement('input'),
      gene_search: document.createElement('div'),
    };
    viz_state.cats = {
      polygon_cell_names: [],
      dict_cell_cats: {},
      color_dict_cluster: {},
      selected_cats: [],
      cluster_counts: [],
      has_meta_cluster: false,
      meta_cluster: {},
      meta_cluster_attr: [],
      cell_exp_array: [],
      cell_names_array: [],
      cell_name_to_index_map: new Map(),
      has_meta_cell: false,
      meta_cell: {},
      meta_cell_attr: [],
    };

    await set_landscape_parameters(viz_state.img, base_url, state.aws);
    const imageInfo = viz_state.img.landscape_parameters.image_info;
    const imageNameForDim = imageInfo[0].name;

    viz_state.seg = { version: segmentation };

    set_image_format(viz_state.img, viz_state.img.landscape_parameters.image_format);
    set_image_info(viz_state.img, imageInfo);
    set_image_layer_colors(viz_state.img.image_layer_colors ?? {}, viz_state.img.image_info);

    await set_dimensions(viz_state, base_url, imageNameForDim);
    viz_state.dimensions = viz_state.dimensions || { width: 1, height: 1, tileSize: 1 };

    viz_state.vector_name_integer =
      viz_state.img.landscape_parameters?.use_int_index || false;

    await set_meta_gene(viz_state.genes, base_url, viz_state.seg.version, viz_state.aws);
    await set_cluster_metadata(viz_state);

    const layers = await make_image_layers(viz_state);

    // we can keep vector_yearbook_tiles for transcripts / polygons
    viz_state.vector_yearbook_tiles = [];

    // Let TileLayer handle image tile selection like in Landscape
    state.imageLayerTemplates = layers.map((layer) =>
      layer.clone({
        maxCacheSize: Math.max(state.capacity * 2, 12),
        refinementStrategy: 'best-available',
        // NOTE: do NOT override getTileData here
      })
    );


    state.imageLayerIds = new Set(state.imageLayerTemplates.map((layer) => layer.id));
    viz_state.cache = { cell: new Map(), trx: new Map() };
    viz_state.combo_data = { trx: [], cell: [] };
    viz_state.max_tiles_to_view = maxTilesToView;
    viz_state.close_up = true;
    viz_state.global_base_url = base_url;

    state.viz_state = viz_state;
    state.backgroundLayer = ini_background_layer(viz_state);
    state.overlays = {
      path_layer: ini_path_layer(viz_state),
      trx_layer: ini_trx_layer(viz_state),
    };
  };

  const loadCellPositions = async () => {
    if (state.cellPositions.size > 0) return state.cellPositions;

    const suffix = segmentation === 'default' ? '' : `_${segmentation}`;
    const url = `${base_url}/cell_metadata${suffix}.parquet`;
    const table = await get_arrow_table(url, options.fetch, state.aws);

    if (!table || !table.getChild) {
      return state.cellPositions;
    }

    const scatter = get_scatter_data(table);
    const names = table?.getChild('name')?.toArray?.() || [];
    const coordArray = scatter.attributes?.getPosition?.value || new Float64Array();
    const dim = scatter.attributes?.getPosition?.size || 2;

    names.forEach((name, i) => {
      const idx = i * dim;
      state.cellPositions.set(String(name), {
        x: coordArray[idx],
        y: coordArray[idx + 1],
        z: dim === 3 ? coordArray[idx + 2] : 0,
      });
    });
    return state.cellPositions;
  };

  const loadMetaCell = async () => {
    const bytes = model.get('meta_cell_parquet');
    if (bytes && bytes.byteLength > 0) {
      state.metaCell = await objects_from_parquet(bytes, 'cell_id');
    }
    return state.metaCell;
  };

  const buildControls = () => {
    controls.innerHTML = '';

    const buttonRow = document.createElement('div');
    buttonRow.className = 'celldega-yearbook-mode-buttons';

    const makeModeButton = (label, active, onClick) => {
      const btn = document.createElement('button');
      btn.textContent = label;
      btn.className = 'celldega-yearbook-button';
      btn.style.color = active ? '#3366cc' : 'gray';
      btn.onclick = () => {
        onClick(!active);
        btn.style.color = active ? 'gray' : '#3366cc';
        active = !active;
      };
      return btn;
    };

    const applyLayerVisibility = () => {
      if (!state.deck) return;
      const nextLayers = (state.deck.props.layers || []).map((layer) => {
        if (state.overlays.path_layer && layer.id === state.overlays.path_layer.id) {
          return state.overlays.path_layer;
        }
        if (state.overlays.trx_layer && layer.id === state.overlays.trx_layer.id) {
          return state.overlays.trx_layer;
        }
        return layer;
      });
      state.deck.setProps({ layers: nextLayers });
    };

    const imgButton = makeModeButton('IMG', true, (visible) => {
      const layers = (state.deck?.props?.layers || []).map((layer) => {
        if (
          layer.id?.startsWith('background-layer-') ||
          (layer.id && state.imageLayerIds.has(layer.id.replace(/-\d+$/, '')))
        ) {
          return layer.clone({ visible });
        }
        return layer;
      });
      state.deck?.setProps({ layers });
    });

    const cellButton = makeModeButton('CELL', state.showSegments, (visible) => {
      state.showSegments = visible;
      if (state.overlays.path_layer) {
        toggle_path_layer_visibility(state.overlays, visible);
      }
      applyLayerVisibility();
    });

    const trxButton = makeModeButton('TRX', state.showTranscripts, (visible) => {
      state.showTranscripts = visible;
      if (state.overlays.trx_layer) {
        toggle_trx_layer_visibility(state.overlays, visible);
      }
      applyLayerVisibility();
    });

    buttonRow.appendChild(imgButton);
    buttonRow.appendChild(cellButton);
    buttonRow.appendChild(trxButton);
    controls.appendChild(buttonRow);

    const searchRow = document.createElement('div');
    searchRow.className = 'celldega-yearbook-search-row';
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Search gene';
    searchInput.className = 'celldega-yearbook-search-input';
    const dataList = document.createElement('datalist');
    const listId = 'celldega-yearbook-genes';
    dataList.id = listId;
    searchInput.setAttribute('list', listId);
    searchInput.onchange = () => {
      const gene = searchInput.value.trim();
      if (gene === '') {
        update_selected_genes(state.viz_state.genes, [], state.obs_store);
      } else {
        update_selected_genes(state.viz_state.genes, [gene], state.obs_store);
      }
      ensureGeneColors();
      renderBars();
      if (state.deck) {
        state.deck.setProps({
          layers: state.deck.props.layers?.map((layer) =>
            layer.id === state.overlays.trx_layer.id ? state.overlays.trx_layer : layer
          ),
        });
      }
    };
    searchRow.appendChild(searchInput);
    searchRow.appendChild(dataList);

    const trxSlider = document.createElement('input');
    trxSlider.type = 'range';
    trxSlider.min = '0.2';
    trxSlider.max = '3';
    trxSlider.step = '0.1';
    trxSlider.value = '0.6';
    trxSlider.className = 'celldega-yearbook-range';
    trxSlider.addEventListener('input', (event) => {
      const value = parseFloat(event.target.value);
      state.overlays.trx_layer = state.overlays.trx_layer.clone({
        radiusMinPixels: value,
        radiusMaxPixels: value * 3,
      });
      applyLayerVisibility();
    });
    searchRow.appendChild(trxSlider);
    controls.appendChild(searchRow);

    state.geneSearch = { input: searchInput, dataList };

    (state.viz_state?.genes?.gene_names || []).forEach((gene) => {
      const option = document.createElement('option');
      option.value = `${gene}`;
      dataList.appendChild(option);
    });

    const barRow = document.createElement('div');
    barRow.className = 'celldega-yearbook-bars';
    const geneContainer = make_bar_container();
    geneContainer.classList.add('celldega-yearbook-bar');
    const geneSvg = d3.create('svg');
    const cellContainer = make_bar_container();
    cellContainer.classList.add('celldega-yearbook-bar');
    const cellSvg = d3.create('svg');
    barRow.appendChild(geneContainer);
    barRow.appendChild(cellContainer);
    controls.appendChild(barRow);

    state.barGraphs = {
      gene: { container: geneContainer, svg: geneSvg },
      cell: { container: cellContainer, svg: cellSvg },
    };
  };

  const getColorAttr = () => {
    const defaultClusterAttr =
      state.metaCell.attr.find((a) => a?.toLowerCase?.().includes('cluster')) || 'cluster';
    const colorAttrName = (model.get('cell_attr') || [])[0] || defaultClusterAttr;
    const colorAttrIdx = colorAttrName ? state.metaCell.attr.indexOf(colorAttrName) : -1;
    return { colorAttrName, colorAttrIdx };
  };

  const computeCandidates = (positionMap) => {
    const provided = model.get('cells') || [];
    if (provided.length > 0) {
      return provided.map((id) => String(id)).filter((id) => positionMap.has(id));
    }
    return Array.from(positionMap.keys());
  };

  const chooseCells = (positionMap, preferredIds = null) => {
    const { colorAttrIdx } = getColorAttr();

    const toCandidate = (id) => {
      const catValue = colorAttrIdx >= 0 ? state.metaCell.result?.[id]?.[colorAttrIdx] : undefined;
      const coords = positionMap.get(id);
      if (!coords) return null;
      return { id, catValue, ...coords };
    };

    const preferred = Array.isArray(preferredIds)
      ? preferredIds
          .map((id) => toCandidate(String(id)))
          .filter((c) => c && Number.isFinite(c.x) && Number.isFinite(c.y))
      : [];

    if (preferred.length > 0) {
      return preferred.slice(0, state.capacity);
    }

    const candidates = computeCandidates(positionMap)
      .map((id) => toCandidate(id))
      .filter((c) => c && Number.isFinite(c.x) && Number.isFinite(c.y));

    const shuffled = shuffle(candidates);
    return shuffled.slice(0, state.capacity);
  };

  const getTilesForCells = (selectedCells) => {
    if (!state.viz_state?.img?.landscape_parameters) return [];
    const { tile_size } = state.viz_state.img.landscape_parameters;
    const tiles = new Map();

    const windowSizeUm = getWindowSize(model);

    selectedCells.forEach((cell) => {
      const zoom = state.globalZoom ?? computeZoomForWindow(windowSizeUm, state.cellWidth);
      const zoomFactor = 2 ** zoom;
      const halfWidth = state.cellWidth / (2 * zoomFactor);
      const halfHeight = state.cellHeight / (2 * zoomFactor);
      const minX = cell.x - halfWidth;
      const maxX = cell.x + halfWidth;
      const minY = cell.y - halfHeight;
      const maxY = cell.y + halfHeight;

      visibleTiles(minX, maxX, minY, maxY, tile_size).forEach((tile) => {
        tiles.set(`${tile.tileX}_${tile.tileY}`, tile);
      });
    });

    return Array.from(tiles.values());
  };

  // Load all image tiles in the single contiguous x,y range that
  // covers *all* portrait windows.
  const getImageTilesForCells = (selectedCells, viz_state, deckZoom) => {
    const { tile_size } = viz_state.img.landscape_parameters;
    const tiles = new Map();

    if (!selectedCells.length) return [];

    // same window math you already use for vector tiles
    const zoomFactor = 2 ** deckZoom;
    const halfWidth = state.cellWidth / (2 * zoomFactor);
    const halfHeight = state.cellHeight / (2 * zoomFactor);

    let globalMinX = Infinity;
    let globalMaxX = -Infinity;
    let globalMinY = Infinity;
    let globalMaxY = -Infinity;

    selectedCells.forEach((cell) => {
      const minX = cell.x - halfWidth;
      const maxX = cell.x + halfWidth;
      const minY = cell.y - halfHeight;
      const maxY = cell.y + halfHeight;

      if (minX < globalMinX) globalMinX = minX;
      if (maxX > globalMaxX) globalMaxX = maxX;
      if (minY < globalMinY) globalMinY = minY;
      if (maxY > globalMaxY) globalMaxY = maxY;
    });

    if (!Number.isFinite(globalMinX)) return [];

    // convert overall bounds to tile indices (same grid as Landscape)
    const x0 = Math.floor(globalMinX / tile_size);
    const x1 = Math.floor(globalMaxX / tile_size);
    const y0 = Math.floor(globalMinY / tile_size);
    const y1 = Math.floor(globalMaxY / tile_size);

    for (let x = x0; x <= x1; x += 1) {
      for (let y = y0; y <= y1; y += 1) {
        tiles.set(`${x}_${y}`, { x, y });
      }
    }

    return Array.from(tiles.values());
  };



  const filterTranscriptsForWindows = (selectedCells) => {
    if (!state.viz_state) return;
    const windowSizeUm = getWindowSize(model);
    const halfWindow = Number.isFinite(windowSizeUm) && windowSizeUm > 0 ? windowSizeUm / 2 : 10;

    const bounds = selectedCells.map((cell) => ({
      minX: cell.x - halfWindow,
      maxX: cell.x + halfWindow,
      minY: cell.y - halfWindow,
      maxY: cell.y + halfWindow,
    }));

    if (bounds.length === 0) return;

    const names = state.viz_state.genes.trx_names_array || [];
    const filtered = [];
    const filteredNames = [];

    state.viz_state.combo_data.trx.forEach((trx, idx) => {
      const matches = bounds.some(
        (b) => trx && trx.x >= b.minX && trx.x <= b.maxX && trx.y >= b.minY && trx.y <= b.maxY
      );

      if (matches) {
        filtered.push(trx);
        filteredNames.push(names[idx] ?? trx.name ?? 'unknown');
      }
    });

    state.viz_state.combo_data.trx = filtered;
    state.viz_state.genes.trx_names_array = filteredNames;
    state.overlays.trx_layer = state.overlays.trx_layer.clone({ data: filtered });
  };

  const ensureGeneColors = () => {
    const { genes } = state.viz_state;
    genes.trx_names_array
      .map((name) => (name === undefined || name === null ? 'unknown' : `${name}`))
      .forEach((name) => {
        if (!genes.color_dict_gene[name]) {
          genes.color_dict_gene[name] = hashColor(name);
        }
      });

    const barColorDict = { ...genes.color_dict_gene };

    state.overlays.trx_layer = state.overlays.trx_layer.clone({
      data: state.viz_state.combo_data.trx,
      getPosition: (d) => [d.x, d.y],
      pickable: true,
      getFillColor: (d) => {
        const inst_gene = d.name || state.viz_state.genes.trx_names_array?.[d.index] || 'unknown';
        const inst_color = barColorDict[inst_gene] || hashColor(inst_gene);
        const inst_opacity =
          genes.selected_genes.length === 0 || genes.selected_genes.includes(inst_gene)
            ? 255
            : 20;
        const safeColor =
          Array.isArray(inst_color) && inst_color.length === 3 ? inst_color : hashColor(inst_gene);
        return [...safeColor, inst_opacity];
      },
      getRadius: 0.25,
      radiusMinPixels: 0.6,
      radiusMaxPixels: 2,
      updateTriggers: {
        getFillColor: [genes.selected_genes.join('-'), Object.keys(barColorDict).length],
      },
      onClick: (info) => {
        const inst_gene = info?.object?.name;
        if (!inst_gene) return;
        update_selected_genes(genes, [inst_gene], state.obs_store);
        ensureGeneColors();
        renderBars();
        if (state.deck) {
          state.deck.setProps({
            layers: state.deck.props.layers?.map((layer) =>
              layer.id === state.overlays.trx_layer.id ? state.overlays.trx_layer : layer
            ),
          });
        }
      },
    });
  };

  const refreshOverlays = async (selectedCells) => {
    if (!state.viz_state || selectedCells.length === 0) return;

    const deckZoom =
      state.globalZoom ?? computeZoomForWindow(getWindowSize(model), state.cellWidth);

    // vector tiles (unchanged)
      let tiles = getTilesForCells(selectedCells);
    if (tiles.length === 0) return;

    const max_tiles = state.viz_state.max_tiles_to_view || tiles.length;
    tiles = tiles.slice(0, max_tiles);

    // image tiles: single contiguous block
    state.viz_state.image_yearbook_tiles =
      getImageTilesForCells(selectedCells, state.viz_state, deckZoom);

    console.log('image_yearbook_tiles', state.viz_state.image_yearbook_tiles);

    // vector manifest (for your existing vector tile mechanism)
    state.viz_state.vector_yearbook_tiles = tiles;
    console.log('yearbook_tiles', tiles);

    const windowSizeUm = getWindowSize(model);
    const halfWindow = Number.isFinite(windowSizeUm) && windowSizeUm > 0 ? windowSizeUm / 2 : 10;

    await Promise.all([
      update_path_layer_data(base_url, tiles, state.overlays, state.viz_state),
      update_trx_layer_data(base_url, tiles, state.overlays, state.viz_state, (trx) => {
        return selectedCells.some(
          (cell) =>
            trx &&
            trx.x >= cell.x - halfWindow &&
            trx.x <= cell.x + halfWindow &&
            trx.y >= cell.y - halfWindow &&
            trx.y <= cell.y + halfWindow
        );
      }),
    ]);

    filterTranscriptsForWindows(selectedCells);

    const transcriptGenes = Array.from(new Set(state.viz_state.genes.trx_names_array || []))
      .filter((g) => g !== undefined && g !== null)
      .map((g) => `${g}`);
    const searchableGenes =
      transcriptGenes.length > 0
        ? transcriptGenes
        : (state.viz_state.genes.gene_names || []).map((g) => `${g}`);
    searchableGenes.sort();
    state.viz_state.genes.gene_names = searchableGenes;

    if (state.geneSearch) {
      state.geneSearch.dataList.innerHTML = '';
      state.viz_state.genes.gene_names.forEach((gene) => {
        const option = document.createElement('option');
        option.value = gene;
        state.geneSearch.dataList.appendChild(option);
      });
    }

    ensureGeneColors();

    toggle_path_layer_visibility(state.overlays, state.showSegments);
    toggle_trx_layer_visibility(state.overlays, state.showTranscripts);

    const geneCounts = state.viz_state.genes.trx_names_array.reduce((acc, gene) => {
      const safeGene = gene ? `${gene}` : 'unknown';
      acc[safeGene] = (acc[safeGene] || 0) + 1;
      return acc;
    }, {});
    const geneBars = Object.entries(geneCounts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
    state.obs_store.new_gene_bar_data.set(geneBars);

    const colorAttrName = (model.get('cell_attr') || [])[0] || 'cluster';
    const categoryCounts = selectedCells.reduce((acc, cell) => {
      const cat = cell.catValue ?? 'unknown';
      acc[cat] = (acc[cat] || 0) + 1;
      return acc;
    }, {});
    const cellBars = Object.entries(categoryCounts).map(([name, value]) => ({
      name: `${colorAttrName}: ${name}`,
      value,
    }));
    state.obs_store.new_cell_bar_data.set(cellBars);
  };

  const renderBars = () => {
    if (!state.barGraphs) return;

    const layersObj = state.overlays;
    const vizState = state.viz_state;
    const deckIst = state.deck;

    const geneBars = state.obs_store.new_gene_bar_data.get();
    const geneColorDict = vizState?.genes?.color_dict_gene || {};

    state.barGraphs.gene.container.innerHTML = '';
    state.barGraphs.cell.container.innerHTML = '';

    make_bar_graph(
      state.barGraphs.gene.container,
      (event, d) => {
        const inst_gene = d.name;
        update_selected_genes(vizState.genes, [inst_gene], vizState.obs_store);
        ensureGeneColors();
        toggle_trx_layer_visibility(layersObj, true);
        if (deckIst) {
          deckIst.setProps({
            layers: deckIst.props.layers?.map((layer) =>
              layer.id === layersObj.trx_layer.id ? layersObj.trx_layer : layer
            ),
          });
        }
      },
      state.barGraphs.gene.svg,
      geneBars,
      geneColorDict,
      deckIst,
      layersObj,
      vizState
    );

    const cellBars = state.obs_store.new_cell_bar_data.get();
    const cellColorDict = cellBars.reduce((acc, c) => {
      const cleanName = c.name || 'unknown';
      acc[cleanName] =
        acc[cleanName] ||
        state.viz_state.cats.color_dict_cluster?.[cleanName.replace(/^.*?:\s*/, '')] ||
        hashColor(cleanName);
      return acc;
    }, {});

    make_bar_graph(
      state.barGraphs.cell.container,
      () => {},
      state.barGraphs.cell.svg,
      cellBars,
      cellColorDict,
      deckIst,
      layersObj,
      vizState
    );
  };

  const renderCells = async (selectionIds = null) => {
    const cellSizeUm = getWindowSize(model);
    const {deck} = state;
    if (!deck) return;

    const selectedCells = chooseCells(state.cellPositions, selectionIds);
    const selectedIds = new Set(selectedCells.map((c) => c.id));
    const viewState = {};
    state.viewTargets.clear();

    selectedCells.forEach((cell, idx) => {
      const viewId = `cell-${idx}`;
      const zoomLevel = state.globalZoom ?? computeZoomForWindow(cellSizeUm, state.cellWidth);
      state.globalZoom = zoomLevel;
      const target = [cell.x, cell.y, cell.z || 0];
      viewState[viewId] = { target, zoom: zoomLevel };
      state.viewTargets.set(viewId, target);
    });

    const { colorAttrIdx } = getColorAttr();
    const scatterData = [];

    state.cellPositions.forEach((coords, id) => {
      const cellMeta = state.metaCell.result?.[id];
      const clusterValue =
        colorAttrIdx >= 0 && Array.isArray(cellMeta) ? cellMeta[colorAttrIdx] : cellMeta?.[colorAttrIdx];
      scatterData.push({
        position: [coords.x, coords.y, coords.z || 0],
        id,
        cluster: clusterValue ?? 'unknown',
        selected: selectedIds.has(id),
      });
    });

    const scatterLayer = new ScatterplotLayer({
      id: 'yearbook-centers',
      data: scatterData,
      pickable: true,
      getPosition: (d) => d.position,
      getFillColor: (d) => {
        const instCluster = d.cluster ?? 'unknown';
        const instColor =
          state.viz_state.cats.color_dict_cluster?.[instCluster] || hashColor(`${instCluster}`);
        const safeColor =
          Array.isArray(instColor) && instColor.length === 3 ? instColor : hashColor(`${instCluster}`);
        const alpha = d.selected ? 220 : 90;
        return [...safeColor, alpha];
      },
      getRadius: (d) => (d.selected ? Math.max(cellSizeUm / 12, 1.5) : Math.max(cellSizeUm / 60, 0.5)),
      radiusMinPixels: 0.4,
      radiusMaxPixels: 6,
    });

    await refreshOverlays(selectedCells);

    const backgroundLayers = selectedCells.map((_, idx) =>
      state.backgroundLayer.clone({
        id: `background-layer-${idx}`,
        viewId: `cell-${idx}`,
        viewportId: `cell-${idx}`,
      })
    );

    const imageLayers = selectedCells.flatMap((cell, idx) =>
      state.imageLayerTemplates.map((layer, layerIdx) =>
        layer.clone({
          id: `${layer.id}-portrait-${idx}-${layerIdx}`,
          viewId: `cell-${idx}`,
          viewportIds: [`cell-${idx}`],
          image_layers: layerIdx,
        })
      )
    );

    const layerStack = [
      ...backgroundLayers,
      ...imageLayers,
      ...(state.showSegments && state.overlays.path_layer ? [state.overlays.path_layer] : []),
      ...(state.showTranscripts && state.overlays.trx_layer ? [state.overlays.trx_layer] : []),
      scatterLayer,
    ];

    deck.setProps({
      viewState,
      layers: layerStack,
      getTooltip: (info) => {
        if (info?.layer?.id === 'trx-layer') {
          const gene = info?.object?.name || state.viz_state.genes.trx_names_array[info.index];
          return { text: `${gene || 'unknown'}`, position: info.coordinate, offset: [0, 0] };
        }
        if (info?.layer?.id === 'yearbook-centers') {
          return { text: `${info?.object?.id || ''}`, position: info.coordinate, offset: [0, 0] };
        }
        return null;
      },
    });

    model.set('displayed_cells', selectedCells.map((c) => c.id));
    model.save_changes();
    renderBars();
  };

  const updateYearbook = async ({ preserveSelection = false } = {}) => {
    if (!state.mounted) return;
    await Promise.all([loadCellPositions(), loadMetaCell()]);
    if (preserveSelection) {
      state.globalZoom = computeZoomForWindow(getWindowSize(model), state.cellWidth);
    } else {
      state.globalZoom = null;
    }
    const retained = preserveSelection ? model.get('displayed_cells') || [] : null;
    await renderCells(retained);
  };

  await makeDeck();
  await setupImagery();
  await loadMetaCell();
  buildControls();
  await updateYearbook();

  const listeners = [];
  const addListener = (name, fn) => {
    model.on(name, fn);
    listeners.push([name, fn]);
  };

  addListener('change:cells', updateYearbook);
  addListener('change:rows', async () => {
    state.deck?.finalize();
    await makeDeck();
    await setupImagery();
    await updateYearbook();
  });
  addListener('change:cols', async () => {
    state.deck?.finalize();
    await makeDeck();
    await setupImagery();
    await updateYearbook();
  });
  addListener('change:window_size_um', () => updateYearbook({ preserveSelection: true }));
  addListener('change:cell_size_um', () => updateYearbook({ preserveSelection: true }));

  return () => {
    state.mounted = false;
    listeners.forEach(([name, fn]) => model.off(name, fn));
    state.deck?.finalize();
  };
};
