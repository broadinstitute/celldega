import { OrthographicView, ScatterplotLayer } from 'deck.gl';
import { AwsClient } from 'aws4fetch';

import { ini_deck, set_views_prop } from '../deck-gl/core/deck_ist';
import { make_image_layers } from '../deck-gl/layers/image_layers';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_dimensions } from '../global_variables/image_dimensions';
import { set_global_base_url } from '../global_variables/global_base_url';
import {
  set_image_format,
  set_image_info,
  set_image_layer_colors,
} from '../global_variables/image_info';
import { options, set_options } from '../global_variables/fetch_options';
import { create_obs_store } from '../obs_store/obs_store';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { get_scatter_data } from '../read_parquet/get_scatter_data';
import { objects_from_parquet } from '../read_parquet/objects_from_parquet';
import { visibleTiles } from '../vector_tile/visibleTiles';
import { ini_path_layer, toggle_path_layer_visibility, update_path_layer_data } from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  toggle_trx_layer_visibility,
  update_trx_layer_data,
} from '../deck-gl/layers/trx_layer';

const makeViewGrid = (rows, cols, width, height) => {
  const views = [];
  const cellWidth = width / cols;
  const cellHeight = height / rows;

  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const id = `cell-${r * cols + c}`;
      views.push(
        new OrthographicView({
          id,
          x: c * cellWidth,
          y: r * cellHeight,
          width: cellWidth,
          height: cellHeight,
        })
      );
    }
  }
  return { views, cellWidth, cellHeight };
};

const computeZoomForCell = (cellSizeUm, viewportWidth) => {
  const safeCellSize = cellSizeUm > 0 ? cellSizeUm : 20;
  const safeViewport = viewportWidth > 0 ? viewportWidth : 200;
  return Math.log2(safeViewport / safeCellSize);
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

const rankCells = (cells, mode) => {
  if (mode === 'max') {
    return [...cells].sort((a, b) => (b.attrValue ?? -Infinity) - (a.attrValue ?? -Infinity));
  }
  if (mode === 'min') {
    return [...cells].sort((a, b) => (a.attrValue ?? Infinity) - (b.attrValue ?? Infinity));
  }
  if (mode === 'middle') {
    const sorted = [...cells].sort((a, b) => (a.attrValue ?? 0) - (b.attrValue ?? 0));
    const mid = Math.floor(sorted.length / 2);
    return shuffle(sorted.slice(Math.max(mid - 1, 0), Math.min(mid + 2, sorted.length)));
  }
  return shuffle([...cells]);
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
    imageLayers: [],
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

    const deck = ini_deck(gridRoot, width, height, '', {
      scrollZoom: false,
      dragPan: false,
      dragRotate: false,
      doubleClickZoom: false,
      keyboard: false,
    });
    set_views_prop(deck, views);
    state.deck = deck;
    deck.setProps({ views });
  };

  const setupImagery = async () => {
    const viz_state = { img: {}, obs_store: state.obs_store };
    set_global_base_url(viz_state, base_url);
    viz_state.aws = state.aws;

    await set_landscape_parameters(viz_state.img, base_url, state.aws);
    const imageInfo = viz_state.img.landscape_parameters.image_info;
    const imageNameForDim = imageInfo[0].name;

    set_image_format(viz_state.img, viz_state.img.landscape_parameters.image_format);
    set_image_info(viz_state.img, imageInfo);
    set_image_layer_colors(viz_state.img.image_layer_colors ?? {}, viz_state.img.image_info);

    await set_dimensions(viz_state, base_url, imageNameForDim);
    viz_state.dimensions = viz_state.dimensions || { width: 1, height: 1, tileSize: 1 };

    const layers = await make_image_layers(viz_state);
    const tunedLayers = layers.map((layer) =>
      layer.clone({
        maxCacheSize: Math.max(state.capacity * 2, 12),
        refinementStrategy: 'best-available',
      })
    );
    state.imageLayers = tunedLayers;
    state.deck?.setProps({ layers: tunedLayers });

    viz_state.seg = { version: segmentation };
    viz_state.cache = { cell: new Map(), trx: new Map() };
    viz_state.genes = {
      trx_data: [],
      trx_names_array: [],
      color_dict_gene: {},
      selected_genes: [],
      top_gene_counts: [],
    };
    viz_state.cats = {
      polygon_cell_names: [],
      dict_cell_cats: {},
      color_dict_cluster: {},
      selected_cats: [],
      cluster_counts: [],
    };
    viz_state.combo_data = { trx: [], cell: [] };
    viz_state.max_tiles_to_view = maxTilesToView;
    viz_state.close_up = true;
    viz_state.vector_name_integer = false;
    viz_state.global_base_url = base_url;

    state.viz_state = viz_state;
    state.overlays = {
      path_layer: ini_path_layer(viz_state),
      trx_layer: ini_trx_layer(viz_state.genes),
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

  const buildControls = (attributes) => {
    controls.innerHTML = '';

    const attrSelect = document.createElement('select');
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'auto/random';
    attrSelect.appendChild(emptyOption);
    attributes.forEach((attr) => {
      const opt = document.createElement('option');
      opt.value = attr;
      opt.textContent = attr;
      attrSelect.appendChild(opt);
    });
    attrSelect.value = model.get('selection_attribute') || '';
    attrSelect.onchange = () => {
      model.set('selection_attribute', attrSelect.value);
      model.save_changes();
      updateYearbook();
    };

    const addButton = (mode, label) => {
      const btn = document.createElement('button');
      btn.textContent = label;
      btn.onclick = () => {
        model.set('selection_mode', mode);
        model.save_changes();
        updateYearbook();
      };
      controls.appendChild(btn);
    };

    controls.appendChild(attrSelect);
    addButton('random', 'Random');
    addButton('max', 'Max');
    addButton('min', 'Min');
    addButton('middle', 'Middle');

    const toggles = document.createElement('div');
    toggles.className = 'celldega-yearbook-toggle-row';

    const makeToggle = (label, initial, onChange) => {
      const wrapper = document.createElement('label');
      wrapper.className = 'celldega-yearbook-toggle';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = initial;
      input.onchange = () => onChange(input.checked);
      const span = document.createElement('span');
      span.textContent = label;
      wrapper.appendChild(input);
      wrapper.appendChild(span);
      return wrapper;
    };

    toggles.appendChild(
      makeToggle('Segmentation', state.showSegments, (checked) => {
        state.showSegments = checked;
        if (state.overlays.path_layer) {
          toggle_path_layer_visibility(state.overlays, checked);
        }
        updateYearbook();
      })
    );

    toggles.appendChild(
      makeToggle('Transcripts', state.showTranscripts, (checked) => {
        state.showTranscripts = checked;
        if (state.overlays.trx_layer) {
          toggle_trx_layer_visibility(state.overlays, checked);
        }
        updateYearbook();
      })
    );

    controls.appendChild(toggles);
  };

  const computeCandidates = (positionMap) => {
    const provided = model.get('cells') || [];
    if (provided.length > 0) {
      return provided.map((id) => String(id)).filter((id) => positionMap.has(id));
    }
    return Array.from(positionMap.keys());
  };

  const chooseCells = (positionMap) => {
    const attrName = model.get('selection_attribute');
    const mode = model.get('selection_mode') || 'random';
    const attrIdx = attrName ? state.metaCell.attr.indexOf(attrName) : -1;

    const candidates = computeCandidates(positionMap)
      .map((id) => {
        const attrValue = attrIdx >= 0 ? state.metaCell.result?.[id]?.[attrIdx] : null;
        const numericValue = Number.isFinite(Number(attrValue)) ? Number(attrValue) : null;
        return { id, attrValue: numericValue ?? attrValue, ...positionMap.get(id) };
      })
      .filter((c) => Number.isFinite(c.x) && Number.isFinite(c.y));

    const hasNumericAttr = candidates.some((c) => typeof c.attrValue === 'number');
    const ranked = rankCells(candidates, attrIdx >= 0 && hasNumericAttr ? mode : 'random');
    return ranked.slice(0, state.capacity);
  };

  const getTilesForCells = (selectedCells) => {
    if (!state.viz_state?.img?.landscape_parameters) return [];
    const { tile_size } = state.viz_state.img.landscape_parameters;
    const tiles = new Map();

    selectedCells.forEach((cell) => {
      const zoom = computeZoomForCell(model.get('cell_size_um') || 20, state.cellWidth);
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

  const ensureGeneColors = () => {
    const { genes } = state.viz_state;
    genes.trx_names_array.forEach((name) => {
      if (!genes.color_dict_gene[name]) {
        genes.color_dict_gene[name] = hashColor(name);
      }
    });

    state.overlays.trx_layer = state.overlays.trx_layer.clone({
      getFillColor: (i, d) => {
        const inst_gene = genes.trx_names_array[d.index];
        const inst_color = genes.color_dict_gene[inst_gene] || hashColor(inst_gene);
        const inst_opacity =
          genes.selected_genes.length === 0 || genes.selected_genes.includes(inst_gene)
            ? 255
            : 5;
        return [...inst_color, inst_opacity];
      },
    });
  };

  const refreshOverlays = async (selectedCells) => {
    if (!state.viz_state || selectedCells.length === 0) return;
    const tiles = getTilesForCells(selectedCells);
    if (tiles.length === 0) return;

    await Promise.all([
      update_path_layer_data(base_url, tiles, state.overlays, state.viz_state),
      update_trx_layer_data(base_url, tiles, state.overlays, state.viz_state),
    ]);

    ensureGeneColors();

    toggle_path_layer_visibility(state.overlays, state.showSegments);
    toggle_trx_layer_visibility(state.overlays, state.showTranscripts);
  };

  const renderCells = async () => {
    const cellSizeUm = model.get('cell_size_um') || 20;
    const deck = state.deck;
    if (!deck) return;

    const selectedCells = chooseCells(state.cellPositions);
    const viewState = {};
    const scatterData = [];

    selectedCells.forEach((cell, idx) => {
      const viewId = `cell-${idx}`;
      viewState[viewId] = {
        target: [cell.x, cell.y, cell.z || 0],
        zoom: computeZoomForCell(cellSizeUm, state.cellWidth),
      };
      scatterData.push({ position: [cell.x, cell.y, cell.z || 0], id: cell.id });
    });

    const scatterLayer = new ScatterplotLayer({
      id: 'yearbook-centers',
      data: scatterData,
      getPosition: (d) => d.position,
      getFillColor: [255, 255, 0, 220],
      getRadius: Math.max(cellSizeUm / 6, 2),
      pickable: false,
    });

    await refreshOverlays(selectedCells);

    const layerStack = [
      ...state.imageLayers,
      ...(state.showSegments && state.overlays.path_layer ? [state.overlays.path_layer] : []),
      ...(state.showTranscripts && state.overlays.trx_layer ? [state.overlays.trx_layer] : []),
      scatterLayer,
    ];

    deck.setProps({
      viewState,
      layers: layerStack,
    });

    model.set('displayed_cells', selectedCells.map((c) => c.id));
    model.save_changes();
  };

  const updateYearbook = async () => {
    if (!state.mounted) return;
    await Promise.all([loadCellPositions(), loadMetaCell()]);
    await renderCells();
  };

  await makeDeck();
  await setupImagery();
  const meta = await loadMetaCell();
  buildControls(meta.attr || []);
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
  addListener('change:selection_mode', updateYearbook);
  addListener('change:selection_attribute', updateYearbook);
  addListener('change:cell_size_um', updateYearbook);

  return () => {
    state.mounted = false;
    listeners.forEach(([name, fn]) => model.off(name, fn));
    state.deck?.finalize();
  };
};
