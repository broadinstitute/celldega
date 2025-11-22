import { DrawPolygonMode, EditableGeoJsonLayer, ViewMode } from '@deck.gl-community/editable-layers';
import * as d3 from 'd3';
import { ScatterplotLayer } from 'deck.gl';

import { ini_deck, set_views_prop } from '../deck-gl/core/deck_ist';
import { set_views } from '../deck-gl/core/views';
import { set_cell_cats, set_dict_cell_cats } from '../global_variables/cat';
import {
  set_cell_name_to_index_map,
  set_cell_names_array,
} from '../global_variables/cell_names_array';
import { fetch_gene_expression_values } from '../global_variables/cell_exp_array';
import { set_options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_meta_gene } from '../global_variables/meta_gene';
import { set_cluster_metadata } from '../global_variables/meta_cluster';
import { create_obs_store } from '../obs_store/obs_store';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { update_selected_genes } from '../global_variables/selected_genes';
import { options } from '../global_variables/fetch_options';

const SCALE_MODES = {
  log1p: 'log1p',
  raw: 'raw',
};

const buildScatterPoints = (xVals, yVals, cats, scaleMode) => {
  const xData = scaleMode === SCALE_MODES.raw ? xVals.raw : xVals.log1p;
  const yData = scaleMode === SCALE_MODES.raw ? yVals.raw : yVals.log1p;

  const points = xData.map((x, idx) => ({
    position: [x, yData[idx]],
    cat: cats.cell_cats[idx],
  }));

  return {
    points,
    bounds: {
      xMin: d3.min(xData),
      xMax: d3.max(xData),
      yMin: d3.min(yData),
      yMax: d3.max(yData),
    },
  };
};

const defaultViewStateForBounds = (bounds, width, height) => {
  const dataWidth = Math.max(bounds.xMax - bounds.xMin, 1e-3);
  const dataHeight = Math.max(bounds.yMax - bounds.yMin, 1e-3);

  const scaleX = width / dataWidth;
  const scaleY = height / dataHeight;
  const scale = Math.min(scaleX, scaleY) * 0.9;

  const centerX = (bounds.xMax + bounds.xMin) / 2;
  const centerY = (bounds.yMax + bounds.yMin) / 2;

  return {
    target: [centerX, centerY, 0],
    zoom: Math.log2(scale),
    minZoom: -20,
    maxZoom: 20,
  };
};

const makeAxisScales = (deckInstance, bounds) => {
  const viewport = deckInstance.getViewports()[0];
  if (!viewport) {
    return null;
  }

  const xRange = [
    viewport.project([bounds.xMin, bounds.yMin, 0])[0],
    viewport.project([bounds.xMax, bounds.yMin, 0])[0],
  ];

  const yRange = [
    viewport.project([bounds.xMin, bounds.yMax, 0])[1],
    viewport.project([bounds.xMin, bounds.yMin, 0])[1],
  ];

  return {
    xScale: d3.scaleLinear().domain([bounds.xMin, bounds.xMax]).range(xRange),
    yScale: d3.scaleLinear().domain([bounds.yMax, bounds.yMin]).range(yRange),
    xAxisY: viewport.project([bounds.xMin, bounds.yMin, 0])[1],
    yAxisX: viewport.project([bounds.xMin, bounds.yMin, 0])[0],
  };
};

const renderAxes = (axisContainer, deckInstance, bounds) => {
  const scales = makeAxisScales(deckInstance, bounds);
  if (!scales) {
    return null;
  }

  const { xScale, yScale, xAxisY, yAxisX } = scales;

  axisContainer
    .select('.x-axis')
    .attr('transform', `translate(0, ${xAxisY})`)
    .call(d3.axisBottom(xScale).ticks(5));

  axisContainer
    .select('.y-axis')
    .attr('transform', `translate(${yAxisX}, 0)`)
    .call(d3.axisLeft(yScale).ticks(5));

  return scales;
};

const getColorForCat = (cat, colorDict) => {
  const color = colorDict[cat];
  if (Array.isArray(color)) {
    return [...color, 180];
  }
  return [100, 100, 100, 150];
};

const polygonKey = (xGene, yGene, scaleMode) => `${xGene}|${yGene}|${scaleMode}`;

const enrichFeatureProperties = (features, xGene, yGene, scaleMode) =>
  features.map((feature, idx) => ({
    ...feature,
    properties: {
      name: feature.properties?.name ?? `poly-${idx + 1}`,
      color:
        feature.properties?.color ?? [
          Math.random() * 255,
          Math.random() * 255,
          Math.random() * 255,
        ],
      xGene,
      yGene,
      scaleMode,
      ...feature.properties,
    },
  }));

const buildEditLayer = (features, viz_state, onEdit) =>
  new EditableGeoJsonLayer({
    id: 'gene-edit-layer',
    data: { type: 'FeatureCollection', features },
    selectedFeatureIndexes: [],
    mode: ViewMode,
    filled: true,
    getFillColor: (d) => d.properties?.color ?? [120, 120, 120, 160],
    getLineColor: [50, 50, 50, 200],
    pickable: true,
    autoHighlight: true,
    modeConfig: { preventOverlappingLines: true },
    visible: true,
    opacity: viz_state.edit?.rgn_opacity ?? 0.25,
    onEdit,
  });

export const render_gene_scatter = async ({ model, el }) => {
  const token = model.get('token');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const width = model.get('width') || el.clientWidth || 900;
  const height = model.get('height') || 700;
  const segmentation = model.get('segmentation') ?? 'default';
  const creds = model.get('creds');
  const initialXGene = model.get('x_gene');
  const initialYGene = model.get('y_gene');
  const initialScaleMode = model.get('scale_mode') ?? SCALE_MODES.log1p;

  const viz_state = {
    obs_store: create_obs_store(),
    cats: {
      color_dict_cluster: {},
      cluster_counts: [],
      cell_cats: [],
      selected_cats: [],
      cat: 'cluster',
      cell_name_to_index_map: new Map(),
      meta_cell_id_set: null,
      meta_cluster_attr: [],
      meta_cluster: {},
      has_meta_cluster: false,
    },
    genes: {
      meta_gene: {},
      gene_names: [],
      selected_genes: [],
      gene_counts: [],
    },
    seg: { version: segmentation },
    polygonStore: new Map(),
    scaleMode: initialScaleMode,
    edit: { rgn_opacity: 0.25 },
    vector_name_integer: false,
    aws: null,
  };

  if (creds && 'accessKeyId' in creds) {
    viz_state.aws = creds;
  }

  set_global_base_url(viz_state, base_url);
  set_options(token);

  const scatterRoot = document.createElement('div');
  scatterRoot.style.display = 'flex';
  scatterRoot.style.gap = '8px';
  scatterRoot.style.alignItems = 'flex-start';

  const controlPanel = document.createElement('div');
  controlPanel.style.display = 'flex';
  controlPanel.style.flexDirection = 'column';
  controlPanel.style.gap = '8px';
  controlPanel.style.minWidth = '200px';

  const header = document.createElement('div');
  header.textContent = dataset_name || 'Gene scatter';
  header.style.fontWeight = 'bold';
  controlPanel.appendChild(header);

  const makeGeneSelector = (labelText) => {
    const wrapper = document.createElement('label');
    wrapper.style.display = 'flex';
    wrapper.style.flexDirection = 'column';
    wrapper.style.fontSize = '12px';

    const label = document.createElement('span');
    label.textContent = labelText;
    wrapper.appendChild(label);

    const input = document.createElement('input');
    input.type = 'text';
    input.style.border = '1px solid #d3d3d3';
    input.style.padding = '4px';
    input.style.fontSize = '12px';
    wrapper.appendChild(input);

    return { wrapper, input };
  };

  const xGeneSelector = makeGeneSelector('X gene');
  const yGeneSelector = makeGeneSelector('Y gene');
  controlPanel.appendChild(xGeneSelector.wrapper);
  controlPanel.appendChild(yGeneSelector.wrapper);

  const scaleWrapper = document.createElement('div');
  scaleWrapper.style.display = 'flex';
  scaleWrapper.style.flexDirection = 'column';
  scaleWrapper.style.gap = '4px';
  const scaleLabel = document.createElement('span');
  scaleLabel.textContent = 'Scale';
  scaleWrapper.appendChild(scaleLabel);

  const makeScaleOption = (value, text) => {
    const optionWrapper = document.createElement('label');
    optionWrapper.style.fontSize = '12px';
    optionWrapper.style.display = 'flex';
    optionWrapper.style.gap = '4px';

    const radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'scale-mode';
    radio.value = value;
    radio.checked = viz_state.scaleMode === value;

    const optionText = document.createElement('span');
    optionText.textContent = text;

    optionWrapper.appendChild(radio);
    optionWrapper.appendChild(optionText);

    return { optionWrapper, radio };
  };

  const logOption = makeScaleOption(SCALE_MODES.log1p, 'log1p');
  const rawOption = makeScaleOption(SCALE_MODES.raw, 'raw');
  scaleWrapper.appendChild(logOption.optionWrapper);
  scaleWrapper.appendChild(rawOption.optionWrapper);
  controlPanel.appendChild(scaleWrapper);

  const polygonControls = document.createElement('div');
  polygonControls.style.display = 'flex';
  polygonControls.style.flexDirection = 'column';
  polygonControls.style.gap = '4px';

  const polygonHeader = document.createElement('span');
  polygonHeader.textContent = 'Manual neighborhoods';
  polygonHeader.style.fontSize = '12px';
  polygonControls.appendChild(polygonHeader);

  const toggleDrawButton = document.createElement('button');
  toggleDrawButton.textContent = 'Draw polygon';
  toggleDrawButton.style.fontSize = '12px';
  toggleDrawButton.style.padding = '6px';

  const clearPolygonsButton = document.createElement('button');
  clearPolygonsButton.textContent = 'Clear current';
  clearPolygonsButton.style.fontSize = '12px';
  clearPolygonsButton.style.padding = '6px';

  polygonControls.appendChild(toggleDrawButton);
  polygonControls.appendChild(clearPolygonsButton);
  controlPanel.appendChild(polygonControls);

  const vizContainer = document.createElement('div');
  vizContainer.style.position = 'relative';
  vizContainer.style.width = `${width}px`;
  vizContainer.style.height = `${height}px`;
  vizContainer.style.border = '1px solid #d3d3d3';

  scatterRoot.appendChild(controlPanel);
  scatterRoot.appendChild(vizContainer);
  el.appendChild(scatterRoot);

  const axisSvg = d3
    .create('svg')
    .attr('width', width)
    .attr('height', height)
    .style('position', 'absolute')
    .style('left', '0px')
    .style('top', '0px')
    .style('pointer-events', 'none');

  axisSvg.append('g').attr('class', 'x-axis');
  axisSvg.append('g').attr('class', 'y-axis');
  vizContainer.appendChild(axisSvg.node());

  const deckRoot = document.createElement('div');
  deckRoot.style.width = `${width}px`;
  deckRoot.style.height = `${height}px`;
  vizContainer.appendChild(deckRoot);

  const views = set_views();
  const deck_ist = await ini_deck(deckRoot, width, height, '');
  set_views_prop(deck_ist, views);

  viz_state.deck = deck_ist;
  viz_state.layers = {};

  const cellMetadataUrl =
    segmentation === 'default'
      ? `${base_url}/cell_metadata.parquet`
      : `${base_url}/cell_metadata_${segmentation}.parquet`;

  const clusterUrl =
    segmentation === 'default'
      ? `${base_url}/cell_clusters/cluster.parquet`
      : `${base_url}/cell_clusters_${segmentation}/cluster.parquet`;

  const cell_arrow_table = await get_arrow_table(
    cellMetadataUrl,
    options.fetch,
    viz_state.aws
  );

  set_cell_names_array(viz_state.cats, cell_arrow_table);
  set_cell_name_to_index_map(viz_state.cats);
  set_cell_cats(viz_state.cats, cell_arrow_table, 'cluster');

  const cluster_arrow_table = await get_arrow_table(
    clusterUrl,
    options.fetch,
    viz_state.aws
  );

  viz_state.cats.has_meta_cluster = false;
  set_dict_cell_cats(viz_state.cats);

  const clusterNames = cluster_arrow_table.getChild('__index_level_0__').toArray();
  const clusterColors = cluster_arrow_table.getChild('color').toArray();
  const clusterCounts = cluster_arrow_table.getChild('count').toArray();
  clusterNames.forEach((name, idx) => {
    viz_state.cats.color_dict_cluster[name] = [
      parseInt(clusterColors[idx].slice(1, 3), 16),
      parseInt(clusterColors[idx].slice(3, 5), 16),
      parseInt(clusterColors[idx].slice(5, 7), 16),
    ];
    viz_state.cats.cluster_counts.push({ name, value: Number(clusterCounts[idx]) });
  });

  await set_meta_gene(viz_state.genes, base_url, segmentation, viz_state.aws);
  await set_cluster_metadata(viz_state);

  const geneOptions = viz_state.genes.gene_names;
  xGeneSelector.input.setAttribute('list', 'gene-scatter-x');
  yGeneSelector.input.setAttribute('list', 'gene-scatter-y');
  const xDatalist = document.createElement('datalist');
  const yDatalist = document.createElement('datalist');
  xDatalist.id = 'gene-scatter-x';
  yDatalist.id = 'gene-scatter-y';
  geneOptions.forEach((geneName) => {
    const optX = document.createElement('option');
    optX.value = geneName;
    xDatalist.appendChild(optX);

    const optY = document.createElement('option');
    optY.value = geneName;
    yDatalist.appendChild(optY);
  });
  el.appendChild(xDatalist);
  el.appendChild(yDatalist);

  xGeneSelector.input.value = initialXGene || geneOptions[0] || '';
  yGeneSelector.input.value = initialYGene || geneOptions[1] || '';

  const loadGeneValues = async (geneName) => {
    if (!viz_state.geneValues) {
      viz_state.geneValues = new Map();
    }

    if (viz_state.geneValues.has(geneName)) {
      return viz_state.geneValues.get(geneName);
    }

    const values = await fetch_gene_expression_values(
      viz_state.cats,
      base_url,
      geneName,
      segmentation,
      viz_state.vector_name_integer,
      viz_state.aws
    );

    viz_state.geneValues.set(geneName, values);
    return values;
  };

  const syncEditLayer = (features) => {
    viz_state.layers.edit_layer = viz_state.layers.edit_layer
      ? viz_state.layers.edit_layer.clone({
          data: { type: 'FeatureCollection', features },
        })
      : buildEditLayer(features, viz_state, ({ updatedData }) => {
          const storedFeatures = enrichFeatureProperties(
            updatedData.features,
            viz_state.currentGenes.x,
            viz_state.currentGenes.y,
            viz_state.scaleMode
          );

          viz_state.polygonStore.set(
            polygonKey(
              viz_state.currentGenes.x,
              viz_state.currentGenes.y,
              viz_state.scaleMode
            ),
            { type: 'FeatureCollection', features: storedFeatures }
          );

          syncEditLayer(storedFeatures);
          viz_state.deck.setProps({
            layers: [viz_state.layers.scatter, viz_state.layers.edit_layer],
          });
        });
  };

  const setEditMode = (mode) => {
    viz_state.layers.edit_layer = viz_state.layers.edit_layer.clone({ mode });
    viz_state.deck.setProps({
      layers: [viz_state.layers.scatter, viz_state.layers.edit_layer],
    });
  };

  const applySelectedGenes = async () => {
    const xGene = xGeneSelector.input.value;
    const yGene = yGeneSelector.input.value;

    if (!viz_state.genes.gene_names.includes(xGene)) {
      return;
    }
    if (!viz_state.genes.gene_names.includes(yGene)) {
      return;
    }

    const [xVals, yVals] = await Promise.all([
      loadGeneValues(xGene),
      loadGeneValues(yGene),
    ]);

    const scatter = buildScatterPoints(
      xVals,
      yVals,
      viz_state.cats,
      viz_state.scaleMode
    );

    viz_state.scatter = scatter;
    viz_state.currentGenes = { x: xGene, y: yGene };
    viz_state.viewState = defaultViewStateForBounds(
      scatter.bounds,
      width,
      height
    );

    viz_state.layers.scatter = new ScatterplotLayer({
      id: 'gene-scatter-layer',
      data: scatter.points,
      pickable: true,
      getPosition: (d) => d.position,
      getFillColor: (d) =>
        getColorForCat(d.cat, viz_state.cats.color_dict_cluster),
      radiusMinPixels: 2,
      getRadius: 4,
    });

    const currentKey = polygonKey(
      viz_state.currentGenes.x,
      viz_state.currentGenes.y,
      viz_state.scaleMode
    );
    const featureCollection =
      viz_state.polygonStore.get(currentKey) || viz_state.nbhd?.ini_feature_collection || {
        type: 'FeatureCollection',
        features: [],
      };

    const enrichedFeatures = enrichFeatureProperties(
      featureCollection.features,
      viz_state.currentGenes.x,
      viz_state.currentGenes.y,
      viz_state.scaleMode
    );

    syncEditLayer(enrichedFeatures);

    viz_state.deck.setProps({
      viewState: viz_state.viewState,
      initialViewState: viz_state.viewState,
      layers: [viz_state.layers.scatter, viz_state.layers.edit_layer],
      controller: true,
    });

    renderAxes(axisSvg, viz_state.deck, scatter.bounds);

    update_selected_genes(viz_state.genes, [xGene, yGene], viz_state.obs_store);
  };

  const updateScaleMode = (mode) => {
    viz_state.scaleMode = mode;
    applySelectedGenes();
  };

  logOption.radio.addEventListener('change', () => {
    if (logOption.radio.checked) {
      updateScaleMode(SCALE_MODES.log1p);
    }
  });

  rawOption.radio.addEventListener('change', () => {
    if (rawOption.radio.checked) {
      updateScaleMode(SCALE_MODES.raw);
    }
  });

  xGeneSelector.input.addEventListener('change', applySelectedGenes);
  yGeneSelector.input.addEventListener('change', applySelectedGenes);

  toggleDrawButton.addEventListener('click', () => {
    const isDrawing = viz_state.layers.edit_layer.props?.mode === DrawPolygonMode;
    if (isDrawing) {
      toggleDrawButton.textContent = 'Draw polygon';
      setEditMode(ViewMode);
    } else {
      toggleDrawButton.textContent = 'Finish drawing';
      setEditMode(DrawPolygonMode);
    }
  });

  clearPolygonsButton.addEventListener('click', () => {
    if (!viz_state.currentGenes) {
      return;
    }

    const key = polygonKey(
      viz_state.currentGenes.x,
      viz_state.currentGenes.y,
      viz_state.scaleMode
    );
    viz_state.polygonStore.set(key, { type: 'FeatureCollection', features: [] });
    syncEditLayer([]);
    viz_state.deck.setProps({
      layers: [viz_state.layers.scatter, viz_state.layers.edit_layer],
    });
  });

  await applySelectedGenes();

  viz_state.deck.setProps({
    onViewStateChange: ({ viewState }) => {
      viz_state.viewState = viewState;
      renderAxes(axisSvg, viz_state.deck, viz_state.scatter.bounds);
      return viewState;
    },
  });

  return () => {
    if (viz_state.deck) {
      viz_state.deck.finalize();
    }
  };
};
