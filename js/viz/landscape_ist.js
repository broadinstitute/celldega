import { ViewMode } from '@deck.gl-community/editable-layers';
import { AwsClient } from 'aws4fetch';
import * as d3 from 'd3';

import { calc_viewport } from '../deck-gl/core/calc_viewport';
import {
  ini_deck,
  set_deck_on_view_state_change,
  set_initial_view_state,
  set_get_tooltip,
  set_views_prop,
} from '../deck-gl/core/deck_ist';
import { set_views } from '../deck-gl/core/views';
import { ini_background_layer } from '../deck-gl/layers/background_layer';
import {
  ini_cell_layer,
  new_toggle_cell_layer_visibility,
  set_cell_layer_onclick,
  toggle_spatial_umap,
  update_cell_pickable_state,
} from '../deck-gl/layers/cell_layer';
import {
  ini_edit_layer,
  set_edit_layer_on_click,
  set_edit_layer_on_edit,
  update_edit_visitility,
  update_edit_layer_mode,
} from '../deck-gl/layers/edit_layer';
import {
  make_image_layers,
  toggle_visibility_single_image_layer,
} from '../deck-gl/layers/image_layers';
import {
  ini_nbhd_layer,
  set_nbhd_layer_onclick,
  toggle_nbhd_layer_visibility,
} from '../deck-gl/layers/nbhd_layer';
import {
  ini_path_layer,
  set_path_layer_onclick,
  toggle_path_layer_visibility,
  update_path_pickable_state,
} from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  set_trx_layer_onclick,
  update_trx_layer_radius,
  toggle_trx_layer_visibility,
  update_trx_pickable_state,
} from '../deck-gl/layers/trx_layer';
import { get_layers_list } from '../deck-gl/utils/layers_ist';
import { ini_cache } from '../global_variables/cache';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { set_options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_dimensions } from '../global_variables/image_dimensions';
import {
  set_image_info,
  set_image_layer_colors,
  set_image_format,
} from '../global_variables/image_info';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_cluster_metadata } from '../global_variables/meta_cluster';
import { set_meta_gene } from '../global_variables/meta_gene';
import { update_selected_genes } from '../global_variables/selected_genes';
import { colorToRgba } from '../matrix/cat_data';
import { create_obs_store } from '../obs_store/obs_store';
import { toggle_slider, set_image_layer_sliders } from '../ui/sliders';
import { get_img_layer_visible } from '../ui/text_buttons';
import { make_ist_ui_container } from '../ui/ui_containers';
import { refresh_layer } from '../utils/refresh_layer';
import { build_rotation_state } from '../utils/rotation';
import { update_cell_clusters } from '../widget_interactions/update_cell_clusters';
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm';

const PIXEL_SIZE_MICRONS = {
  Xenium: 0.2125,
  MERSCOPE: 0.108,
};

const create_scale_bar = (microns_per_pixel, tech) => {
  const tech_key = tech || '';
  const black_label_techs = ['Visium-HD'];
  const white_label_techs = ['Xenium', 'MERSCOPE'];

  const label_color = black_label_techs.includes(tech_key)
    ? 'black'
    : white_label_techs.includes(tech_key)
      ? 'white'
      : 'white';

  const reverse_label_color = label_color === 'white' ? 'black' : 'white';

  const container = document.createElement('div');
  container.style.position = 'absolute';
  container.style.bottom = '10px';
  container.style.left = '10px';
  container.style.backgroundColor = 'transparent';
  container.style.color = label_color;
  container.style.padding = '6px 8px';
  container.style.fontSize = '12px';
  container.style.lineHeight = '1.2';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'flex-start';
  container.style.pointerEvents = 'none';
  container.style.zIndex = '10';
  container.style.opacity = '0.5';

  const label = document.createElement('div');
  label.textContent = '1 µm';

  const bar = document.createElement('div');
  bar.style.height = '2px';
  bar.style.backgroundColor = label_color;
  bar.style.outline = `1px solid ${reverse_label_color}`;
  bar.style.marginTop = '4px';
  bar.style.width = '80px';

  if (label_color === 'white') {
    container.style.textShadow = '0 0 3px black';
  }

  container.appendChild(label);
  container.appendChild(bar);

  const format_label = (microns) => {
    if (microns >= 1000) {
      const millimeters = microns / 1000;
      if (millimeters >= 10) {
        return `${Math.round(millimeters)} mm`;
      }
      if (millimeters >= 1) {
        return `${Number(millimeters.toFixed(1))} mm`;
      }
    }

    if (microns >= 100) {
      return `${Math.round(microns)} µm`;
    }
    if (microns >= 10) {
      return `${Number(microns.toFixed(1))} µm`;
    }
    return `${Number(microns.toPrecision(2))} µm`;
  };

  const set_visible = (visible) => {
    container.style.display = visible ? 'flex' : 'none';
  };

  const update = ({ zoom }) => {
    const zoom_factor = Math.pow(2, zoom || 0);
    const microns_per_screen_pixel = microns_per_pixel / zoom_factor;
    const target_pixel_width = 100;
    const raw_microns = microns_per_screen_pixel * target_pixel_width;
    const capped_microns = Math.min(raw_microns, 1000);

    const magnitude = Math.pow(10, Math.floor(Math.log10(capped_microns)));
    const normalized = capped_microns / magnitude;

    let normalized_target = 1;
    if (normalized > 5) {
      normalized_target = 10;
    } else if (normalized > 2) {
      normalized_target = 5;
    } else if (normalized > 1) {
      normalized_target = 2;
    }

    const bar_microns = normalized_target * magnitude;
    const bar_pixel_width = bar_microns / microns_per_screen_pixel;

    label.textContent = format_label(bar_microns);
    bar.style.width = `${bar_pixel_width}px`;
  };

  return { container, update, set_visible };
};

export const landscape_ist = async (
  el,
  ini_model,
  token,
  ini_x,
  ini_y,
  ini_z,
  ini_zoom,
  base_url,
  dataset_name = '',
  trx_radius = 0.25,
  width = 0,
  height = 800,
  meta_cell = {},
  meta_cell_attr = [],
  meta_cluster = {},
  meta_cluster_attr = [],
  umap = {},
  nbhd = {},
  nbhd_edit = false,
  landscape_state = 'spatial',
  segmentation = 'default',
  creds = {},
  view_change_custom_callback = null,
  rotation_orbit = 0,
  rotation_x = 0,
  rotate = 0,
  max_tiles_to_view = 50,
  scale_bar_microns_per_pixel = null
) => {
  if (width === 0) {
    width = '100%';
  }

  const viz_state = {};

  viz_state.obs_store = create_obs_store();

  viz_state.highlighted_cells = new Set();
  viz_state.selection_token = 0;

  const initial_selected_cells =
    typeof ini_model?.get === 'function'
      ? ini_model.get('selected_cells') || []
      : [];

  if (Array.isArray(initial_selected_cells)) {
    viz_state.highlighted_cells = new Set(initial_selected_cells);
    viz_state.obs_store.selected_cells.set(initial_selected_cells);
  }

  viz_state.max_tiles_to_view = max_tiles_to_view;
  const update_viz_image_layers = () => {
    if (!get_img_layer_visible()) {
      return;
    }

    const hasCats = viz_state.obs_store.selected_cats.get().length > 0;
    const hasGenes = viz_state.obs_store.selected_genes.get().length > 0;

    if (hasCats || hasGenes) {
      viz_state.obs_store.viz_image_layers.set(false);
    } else {
      // only do this if not in umap view
      if (viz_state.obs_store.umap_state.get() === false) {
        viz_state.obs_store.viz_image_layers.set(true);
      }
    }
  };

  // Subscribe both, but they call the same function
  viz_state.obs_store.selected_cats.subscribe(update_viz_image_layers);
  viz_state.obs_store.selected_genes.subscribe(update_viz_image_layers);

  viz_state.seg = {};
  viz_state.seg.version = segmentation;

  viz_state.root = el;
  viz_state.buttons = {};
  viz_state.buttons.blue = '#8797ff';
  viz_state.buttons.gray = 'gray';
  viz_state.buttons.light_gray = '#EEEEEE';
  viz_state.buttons.buttons = {};

  set_global_base_url(viz_state, base_url);

  viz_state.close_up = false;
  viz_state.model = ini_model;

  viz_state.nbhd = {};
  viz_state.nbhd.visible = false;
  viz_state.nbhd.edit = nbhd_edit;
  viz_state.dataset_options = ini_model?.get('base_url_options') || [];

  const datasetLabel = dataset_name ? String(dataset_name) : '';
  const datasetPrefixSeparator = '_';
  const prefixAttr = ini_model?.get('cell_name_prefix_col');
  const baseIdAttr = '__cell_base_id__';
  const autoStripPrefix = prefixAttr === true;
  const hasPrefixColumn = typeof prefixAttr === 'string' && prefixAttr.length > 0;

  const filteredMeta = (() => {
    if (!Array.isArray(meta_cell_attr)) {
      return {
        metaCell: meta_cell,
        metaAttr: meta_cell_attr,
        idMap: [],
      };
    }

    if (autoStripPrefix) {
      const metaCell = {};
      const idMap = [];

      Object.entries(meta_cell || {}).forEach(([key, values]) => {
        const sepIdx = String(key).indexOf(datasetPrefixSeparator);
        if (sepIdx <= 0) {
          metaCell[key] = values;
          return;
        }

        const baseId = String(key).slice(sepIdx + 1);
        metaCell[baseId] = values;
        idMap.push({ sourceId: key, baseId });
      });

      return { metaCell, metaAttr: meta_cell_attr, idMap };
    }

    if (!hasPrefixColumn && datasetLabel) {
      const metaCell = {};
      const idMap = [];

      Object.entries(meta_cell || {}).forEach(([key, values]) => {
        const keyStr = String(key);
        const sepIdx = keyStr.indexOf(datasetPrefixSeparator);

        if (sepIdx <= 0) return;

        const datasetValue = keyStr.slice(0, sepIdx);
        if (datasetValue !== datasetLabel) return;

        const baseId = keyStr.slice(sepIdx + 1);
        metaCell[baseId] = values;
        idMap.push({ sourceId: key, baseId });
      });

      if (idMap.length) {
        return { metaCell, metaAttr: meta_cell_attr, idMap };
      }
    }

    if (!hasPrefixColumn) {
      return {
        metaCell: meta_cell,
        metaAttr: meta_cell_attr,
        idMap: [],
      };
    }

    const prefixIdx = meta_cell_attr.indexOf(prefixAttr);
    if (prefixIdx === -1) {
      return {
        metaCell: meta_cell,
        metaAttr: meta_cell_attr,
        idMap: [],
      };
    }

    const baseIdx = meta_cell_attr.indexOf(baseIdAttr);
    const metaAttr = meta_cell_attr.filter((attr) => attr !== baseIdAttr);
    const metaCell = {};
    const idMap = [];

    Object.entries(meta_cell || {}).forEach(([key, values]) => {
      const datasetValue = values?.[prefixIdx];
      if (datasetLabel && String(datasetValue) !== datasetLabel) {
        return;
      }

      const baseId = baseIdx >= 0 ? String(values[baseIdx]) : key;
      const cleanedValues =
        baseIdx >= 0
          ? values.filter((_, idx) => idx !== baseIdx)
          : values.slice();

      metaCell[baseId] = cleanedValues;
      idMap.push({ sourceId: key, baseId });
    });

    return { metaCell, metaAttr, idMap };
  })();

  const filteredUmap = (() => {
    if (!filteredMeta.idMap.length) {
      return prefixAttr ? {} : umap;
    }

    const mapped = {};
    filteredMeta.idMap.forEach(({ sourceId, baseId }) => {
      if (umap?.[sourceId]) {
        mapped[baseId] = umap[sourceId];
      } else if (umap?.[baseId]) {
        mapped[baseId] = umap[baseId];
      }
    });

    return mapped;
  })();

  viz_state.spatial = {};

  // later we will parse the region from the s3 url

  if ('accessKeyId' in creds) {
    viz_state.aws = new AwsClient({
      accessKeyId: creds.accessKeyId,
      secretAccessKey: creds.secretAccessKey,
      sessionToken: creds.sessionToken,
      region: 'us-east-1',
      service: 's3',
    });

    // fetch after initialization of aws client is apparently required?
    const response = await viz_state.aws.fetch(
      `${base_url}/landscape_parameters.json`
    );

    if (!response.ok) {
      throw new Error(`Fetch failed: ${response.statusText}`);
    }

    // const json = await response.json();
    // el.textContent = "Fetch succeeded! Here's the object: " + JSON.stringify(json, null, 2).slice(0,50);
  } else {
    viz_state.aws = null;
  }

  if (Object.keys(viz_state.model).length !== 0) {
    if (Object.keys(nbhd).length === 0) {
      viz_state.nbhd.is_nbhd = nbhd_edit;

      viz_state.nbhd.ini_feature_collection = {
        type: 'FeatureCollection',
        features: [],
        inst_alpha: null,
      };

      viz_state.nbhd.feature_collection = viz_state.nbhd.ini_feature_collection;
    } else {
      viz_state.nbhd.is_nbhd = true;

      viz_state.nbhd.ini_feature_collection = nbhd; // viz_state.model.get('nbhd');

      // viz_state.nbhd.bar_data = nbhd.features
      //   .map((feature) => {
      //     return {
      //       name: feature.properties.cat, // "1_50" → "1"
      //       value: feature.properties.area, // use area as the value
      //     };
      //   })
      //   .sort((a, b) => b.value - a.value);

      // find all unique categories in the nbhd features
      const unique_cats = new Set(
        nbhd.features.map((feature) => feature.properties.cat)
      );

      // calculate the area of all unique categories
      viz_state.nbhd.bar_data = Array.from(unique_cats)
        .map((cat) => {
          const features = nbhd.features.filter(
            (feature) => feature.properties.cat === cat
          );
          const area = features.reduce(
            (acc, feature) => acc + feature.properties.area,
            0
          );

          return {
            name: cat,
            value: area,
          };
        })
        .sort((a, b) => b.value - a.value);

      // parse colors from features and make a dictionary with cat name and
      // color as rgb array that is converted from hex
      viz_state.nbhd.color_dict = {};
      nbhd.features.forEach((feature) => {
        const color = colorToRgba(feature.properties.color);
        viz_state.nbhd.color_dict[feature.properties.cat] = color;
      });

      viz_state.nbhd.feature_collection = {
        type: 'FeatureCollection',
        features: nbhd.features,
      };
    }
  }

  viz_state.containers = {};
  viz_state.containers.root_dim = {};
  viz_state.containers.root_dim.width = width;
  viz_state.containers.root_dim.height = height;

  viz_state.custom_callbacks = {};
  viz_state.custom_callbacks.view_change = view_change_custom_callback;

  viz_state.cats = {};
  viz_state.cats.cat = null;
  viz_state.cats.reset_cat = false;
  viz_state.cats.selected_cats = [];
  viz_state.cats.cell_cats = [];
  viz_state.cats.dict_cell_cats = {};
  viz_state.cats.color_dict_cluster = {};
  viz_state.cats.cluster_counts = [];
  viz_state.cats.polygon_cell_names = [];

  if (Object.keys(filteredMeta.metaCell).length === 0) {
    viz_state.cats.has_meta_cell = false;
  } else {
    viz_state.cats.has_meta_cell = true;
  }
  viz_state.cats.meta_cell = filteredMeta.metaCell;
  viz_state.cats.meta_cell_attr = filteredMeta.metaAttr;
  viz_state.cats.meta_cell_id_set = new Set(
    Object.keys(filteredMeta.metaCell || {}).map((cell_id) => String(cell_id))
  );
  viz_state.cats.inst_cell_attr = filteredMeta.metaAttr?.[0] || 'N.A.';

  if (viz_state.cats.selected_cats.length > 0) {
    viz_state.obs_store.selected_cats.set(viz_state.cats.selected_cats);
  }

  if (Object.keys(meta_cluster).length === 0) {
    viz_state.cats.has_meta_cluster = false;
  } else {
    viz_state.cats.has_meta_cluster = true;
  }
  viz_state.cats.meta_cluster = meta_cluster;
  viz_state.cats.meta_cluster_attr = meta_cluster_attr;
  viz_state.cats.inst_cluster_attr = meta_cluster_attr[0] || 'N.A.';

  viz_state.umap = {};
  if (Object.keys(filteredUmap).length === 0) {
    viz_state.umap.has_umap = false;
  } else {
    viz_state.umap.has_umap = true;
  }
  viz_state.umap.umap = filteredUmap;

  const isUmapInit = landscape_state === 'umap';
  viz_state.obs_store.umap_state.set(isUmapInit);
  viz_state.obs_store.landscape_view.set(landscape_state);

  viz_state.genes = {};
  viz_state.genes.color_dict_gene = {};
  viz_state.genes.gene_names = [];
  viz_state.genes.meta_gene = {};
  viz_state.genes.gene_counts = [];
  viz_state.genes.selected_genes = [];
  viz_state.genes.trx_ini_radius = trx_radius;
  viz_state.genes.trx_names_array = [];
  viz_state.genes.trx_data = [];
  viz_state.genes.gene_text_box = '';
  viz_state.genes.trx_slider = document.createElement('input');
  viz_state.genes.gene_search = document.createElement('div');

  if (viz_state.genes.selected_genes.length > 0) {
    viz_state.obs_store.selected_genes.set(viz_state.genes.selected_genes);
  }

  viz_state.cats.cell_exp_array = [];
  viz_state.cats.cell_names_array = [];
  viz_state.cats.cell_name_to_index_map = new Map();

  viz_state.img = {};
  viz_state.img.image_layer_colors = {};
  viz_state.img.image_layer_sliders = {};

  set_options(token);

  await set_landscape_parameters(viz_state.img, base_url, viz_state.aws);
  const tech = viz_state.img.landscape_parameters.technology;
  if (tech === 'Chromium' || tech === 'point-cloud') {
    viz_state.obs_store.viz_image_layers.set(false);
    viz_state.obs_store.viz_background_layer.set(false);
  }

  const tmp_image_info = viz_state.img.landscape_parameters.image_info;

  // set image_name_for_dim using the first image info name
  const image_name_for_dim = tmp_image_info[0].name;

  viz_state.vector_name_integer =
    viz_state.img.landscape_parameters.use_int_index;

  set_image_format(
    viz_state.img,
    viz_state.img.landscape_parameters.image_format
  );
  set_image_info(viz_state.img, tmp_image_info);
  set_image_layer_sliders(viz_state.img);
  set_image_layer_colors(
    viz_state.img.image_layer_colors,
    viz_state.img.image_info
  );

  const all_image_layer_names = viz_state.img.image_info.map(
    (info) => info.button_name
  );

  viz_state.img.visible_layers = new Set(all_image_layer_names);

  // Create and append the visualization.
  const root = document.createElement('div');
  root.style.position = 'relative';
  root.style.height = `${height}px`;
  root.style.border = '1px solid #d3d3d3';

  const user_microns_per_pixel =
    typeof scale_bar_microns_per_pixel === 'number' &&
    !Number.isNaN(scale_bar_microns_per_pixel) &&
    scale_bar_microns_per_pixel > 0
      ? scale_bar_microns_per_pixel
      : null;

  const default_microns_per_pixel = PIXEL_SIZE_MICRONS[tech];
  const microns_per_pixel = default_microns_per_pixel ?? user_microns_per_pixel;

  if (microns_per_pixel) {
    viz_state.scale_bar = create_scale_bar(microns_per_pixel, tech);
    root.appendChild(viz_state.scale_bar.container);
  }

  if (viz_state.scale_bar) {
    viz_state.obs_store.scale_bar_view_state.subscribe(
      (viewState) => {
        if (viewState && viz_state.scale_bar?.update) {
          viz_state.scale_bar.update(viewState);
        }
      },
      { immediate: false }
    );
  }

  if (tech === 'Chromium' || tech === 'point-cloud') {
    viz_state.dimensions = { width: 1, height: 1, tileSize: 1 };
  } else {
    await set_dimensions(viz_state, base_url, image_name_for_dim);
  }

  const center_x = viz_state.dimensions?.width
    ? viz_state.dimensions.width / 2
    : 0;
  const center_y = viz_state.dimensions?.height
    ? viz_state.dimensions.height / 2
    : 0;
  viz_state.rotation = build_rotation_state(rotate, [center_x, center_y]);

  await set_meta_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  await set_cluster_metadata(viz_state);

  viz_state.views = set_views(tech);

  const deck_ist = await ini_deck(root, width, height, tech);
  // set_initial_view_state(deck_ist, ini_x, ini_y, ini_z, ini_zoom)
  set_views_prop(deck_ist, viz_state.views);

  // initialize cell and trx caches
  viz_state.cache = {};
  viz_state.cache.cell = await ini_cache();
  // we will try to reuse cell functions to make trx cache
  viz_state.cache.trx = await ini_cache();

  viz_state.combo_data = {};

  viz_state.tooltip_cat_cell = '';

  set_get_tooltip(deck_ist, viz_state);

  viz_state.edit = {};
  viz_state.edit.svg_bar_rgn = d3.create('svg');
  viz_state.edit.rgn_areas = [];
  viz_state.edit.color_dict_rgn = {};
  // default opacity for editable neighborhoods
  viz_state.edit.rgn_opacity = 0.3;
  viz_state.edit.visible = false;
  viz_state.edit.modify_index = null;

  if (Object.keys(viz_state.model).length !== 0) {
    if (Object.keys(viz_state.model.get('region')).length === 0) {
      viz_state.edit.feature_collection = {
        type: 'FeatureCollection',
        features: [],
      };
    } else {
      viz_state.edit.feature_collection = viz_state.model.get('region');
    }
  } else {
    viz_state.edit.feature_collection = {
      type: 'FeatureCollection',
      features: [],
    };
  }

  const background_layer = ini_background_layer(viz_state);
  const image_layers = await make_image_layers(viz_state);
  const cell_layer = await ini_cell_layer(base_url, viz_state);
  const path_layer = await ini_path_layer(viz_state);
  const trx_layer = ini_trx_layer(viz_state);
  const edit_layer = ini_edit_layer(viz_state);
  const nbhd_layer = ini_nbhd_layer(viz_state, true);

  // make layers object
  const layers_obj = {
    background_layer,
    image_layers,
    cell_layer,
    path_layer,
    trx_layer,
    nbhd_layer,
    edit_layer,
  };

  const enforce_image_layer_visibility = () => {
    viz_state.img.image_info.forEach(({ button_name }) => {
      const should_show = viz_state.img.visible_layers.has(button_name);
      toggle_visibility_single_image_layer(layers_obj, button_name, should_show);

      const slider = viz_state.img.image_layer_sliders.find(
        (instSlider) => instSlider.name === button_name
      );

      toggle_slider(
        slider,
        should_show && viz_state.obs_store.viz_image_layers.get()
      );
    });
  };

  viz_state.img.enforce_visibility = enforce_image_layer_visibility;

  enforce_image_layer_visibility();

  const refresh_cell_layer = () => {
    const selected_cats_name = viz_state.cats.selected_cats.join('-');

    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-${selected_cats_name}-sel-${viz_state.selection_token}`,
      updateTriggers: {
        ...layers_obj.cell_layer.props.updateTriggers,
        getPosition: [viz_state.obs_store.umap_state.get()],
        getFillColor: [viz_state.selection_token],
      },
    });

    // Toggle cell layer readiness so deck.gl re-renders when selections arrive
    // from the Python backend.
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: false,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: true,
    });
  };

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    nbhd_layer: true,
    edit_layer: true,
  });

  viz_state.obs_store.selected_nbhds.subscribe(
    (selected_nbhds) => {
      const selected_nbhds_name = selected_nbhds.join('-');

      layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        id: `nbhd-layer-${selected_nbhds_name}`,
      });
    },
    { immediate: false }
  );

  viz_state.obs_store.viz_nbhd_layer.subscribe(
    (visible) => {
      if (visible) {
        // set cell layer to not visible
        new_toggle_cell_layer_visibility(viz_state.layers_obj, false);

        // set gene/cat bars to disabled color
        viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 0.2);
        viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 0.2);
        viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);

        viz_state.buttons.buttons.cell.style('color', 'gray');
        viz_state.buttons.buttons.trx.style('color', 'gray');

        toggle_slider(viz_state.sliders.cell, false);
        toggle_slider(viz_state.sliders.trx, false);
      } else {
        new_toggle_cell_layer_visibility(viz_state.layers_obj, true);

        viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);
        viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 1.0);
        viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 0.2);

        viz_state.buttons.buttons.cell.style('color', 'blue');
        viz_state.buttons.buttons.trx.style('color', 'blue');

        toggle_slider(viz_state.sliders.cell, true);
        toggle_slider(viz_state.sliders.trx, true);
      }
      if (visible) {
        viz_state.obs_store.viz_edit_layer.set(false);
      }
    },
    { immediate: false }
  );

  // set onclicks after all layers are made
  set_cell_layer_onclick(deck_ist, layers_obj, viz_state);
  set_path_layer_onclick(deck_ist, layers_obj, viz_state);
  set_trx_layer_onclick(deck_ist, layers_obj, viz_state);
  set_edit_layer_on_edit(deck_ist, layers_obj, viz_state);
  set_edit_layer_on_click(deck_ist, layers_obj, viz_state);
  set_nbhd_layer_onclick(deck_ist, layers_obj, viz_state);

  viz_state.obs_store.deck_ready.subscribe((ready) => {
    if (ready) {
      const list = get_layers_list(viz_state.layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: list });
    }
  });

  viz_state.obs_store.viz_edit_layer.subscribe(
    (visible) => {
      update_edit_visitility(layers_obj, visible);
      if (visible) {
        viz_state.obs_store.viz_nbhd_layer.set(false);
        toggle_nbhd_layer_visibility(layers_obj, false);
        toggle_trx_layer_visibility(layers_obj, false);
        viz_state.buttons.buttons.trx.style('color', 'gray');
        d3.select(viz_state.edit.buttons.nbhd).style('color', 'blue');
        d3.select(viz_state.edit.buttons.sktch)
          .style('display', 'inline-flex')
          .style('color', 'gray')
          .classed('active', false);
        if (viz_state.nbhd.edit && viz_state.containers.nbhd_opacity_slider) {
          d3.select(viz_state.containers.nbhd_opacity_slider).style(
            'display',
            'inline-flex'
          );
          toggle_slider(viz_state.sliders.nbhd_opacity, true);
        }
      } else {
        toggle_trx_layer_visibility(layers_obj, true);
        viz_state.buttons.buttons.trx.style('color', 'blue');
        d3.select(viz_state.edit.buttons.nbhd)
          .style('color', 'gray')
          .classed('active', false);
        d3.select(viz_state.edit.buttons.sktch)
          .style('display', 'none')
          .style('color', 'gray')
          .classed('active', false);
        update_edit_layer_mode(layers_obj, ViewMode);
        update_cell_pickable_state(layers_obj, true);
        update_path_pickable_state(layers_obj, true);
        update_trx_pickable_state(layers_obj, true);
        if (viz_state.nbhd.edit && viz_state.containers.nbhd_opacity_slider) {
          d3.select(viz_state.containers.nbhd_opacity_slider).style(
            'display',
            'none'
          );
          toggle_slider(viz_state.sliders.nbhd_opacity, false);
        }
      }
      refresh_layer(viz_state, layers_obj, 'edit_layer');
    },
    { immediate: false }
  );

  viz_state.obs_store.selected_cats.subscribe((selected_cats) => {
    const selected_cats_name = selected_cats.join('-');

    refresh_cell_layer();

    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-${selected_cats_name}`,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      path_layer: true,
    });
  });

  viz_state.obs_store.selected_cells.subscribe((selected_cells) => {
    viz_state.highlighted_cells = new Set(selected_cells ?? []);
    viz_state.selection_token += 1;
    refresh_cell_layer();
  });

  viz_state.obs_store.selected_genes.subscribe((selected_genes) => {
    const selected_genes_name = selected_genes.join('-');
    layers_obj.trx_layer = layers_obj.trx_layer.clone({
      id: `trx-layer-${selected_genes_name}`,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      trx_layer: true,
    });
  });

  update_trx_layer_radius(layers_obj, trx_radius);

  if (viz_state.obs_store.umap_state.get() === true) {
    viz_state.obs_store.viz_background_layer.set(false);
    viz_state.obs_store.viz_image_layers.set(false);

    toggle_trx_layer_visibility(layers_obj, false);
    toggle_path_layer_visibility(layers_obj, false);
  }

  set_initial_view_state(
    deck_ist,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    viz_state,
    rotation_orbit,
    rotation_x
  );

  set_deck_on_view_state_change(deck_ist, layers_obj, viz_state);

  const updateTriggerHandler = () =>
    update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state);

  const cellClusterHandler = () =>
    update_cell_clusters(deck_ist, layers_obj, viz_state);

  const selectedCellsHandler = () => {
    const cells = viz_state.model.get('selected_cells') || [];
    viz_state.obs_store.selected_cells.set(cells);
  };

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.on('change:update_trigger', updateTriggerHandler);
    viz_state.model.on('change:cell_clusters', cellClusterHandler);
    viz_state.model.on('change:selected_cells', selectedCellsHandler);
  }

  const ui_container = make_ist_ui_container(
    dataset_name,
    deck_ist,
    layers_obj,
    viz_state
  );

  // UI and Viz Container
  el.appendChild(ui_container);
  el.appendChild(root);

  const is_chromium = ['Chromium', 'point-cloud'].includes(
    viz_state.img.landscape_parameters.technology
  );
  viz_state.obs_store.landscape_view.subscribe(
    (view) => {
      const is_umap = view === 'umap';
      viz_state.obs_store.umap_state.set(is_umap);

      if (viz_state.scale_bar) {
        viz_state.scale_bar.set_visible(!is_umap);
      }

      toggle_spatial_umap(deck_ist, layers_obj, viz_state);

      if (is_umap) {
        viz_state.buttons.buttons.umap.style('color', 'blue');
        if (!is_chromium) {
          viz_state.buttons.buttons.spatial.style('color', 'gray');
          viz_state.buttons.buttons.img.style('color', 'gray');
        }

        viz_state.obs_store.viz_background_layer.set(false);
        viz_state.obs_store.viz_image_layers.set(false);

        toggle_trx_layer_visibility(layers_obj, false);
        toggle_path_layer_visibility(layers_obj, false);

        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: false,
          path_layer: false,
          trx_layer: false,
        });

        viz_state.layers_obj = layers_obj;

        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: true,
          path_layer: true,
          trx_layer: true,
        });
      } else {
        if (!isChromium) {
          viz_state.buttons.buttons.umap.style('color', 'gray');
          viz_state.buttons.buttons.spatial.style('color', 'blue');
          viz_state.buttons.buttons.img.style('color', 'blue');
        }

        toggle_trx_layer_visibility(layers_obj, true);
        toggle_path_layer_visibility(layers_obj, true);

        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: false,
          path_layer: false,
          trx_layer: false,
        });
        viz_state.layers_obj = layers_obj;
        viz_state.obs_store.deck_check.set({
          ...viz_state.obs_store.deck_check.get(),
          cell_layer: true,
          path_layer: true,
          trx_layer: true,
        });

        setTimeout(() => {
          viz_state.obs_store.viz_background_layer.set(true);
          viz_state.obs_store.viz_image_layers.set(true);
        }, 3000);
      }
    },
    { immediate: false }
  );

  const get_state_snapshot = () => {
    return {
      selected_cats: [...(viz_state.obs_store.selected_cats.get() || [])],
      selected_genes: [...(viz_state.obs_store.selected_genes.get() || [])],
      landscape_view: viz_state.obs_store.landscape_view.get(),
      viz_image_layers: viz_state.obs_store.viz_image_layers.get(),
      visible_images: viz_state.img?.visible_layers
        ? Array.from(viz_state.img.visible_layers)
        : [],
    };
  };

  const landscape = {
    update_matrix_gene: async (inst_gene) => {
      const reset_gene = inst_gene === viz_state.cats.cat;
      const new_cat = reset_gene ? 'cluster' : inst_gene;

      update_cat(viz_state.cats, new_cat);
      update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
      update_selected_cats(
        viz_state.cats,
        new_cat === 'cluster' ? [] : [inst_gene],
        viz_state.obs_store
      );
      await update_cell_exp_array(
        viz_state.cats,
        viz_state.genes,
        viz_state.global_base_url,
        inst_gene,
        viz_state.seg.version,
        viz_state.vector_name_integer,
        viz_state.aws
      );

      viz_state.layers_obj = layers_obj;

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: true,
      });
    },
    update_matrix_col: async (inst_col) => {
      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, [inst_col], viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: false,
        path_layer: false,
        trx_layer: false,
      });
      viz_state.layers_obj = layers_obj;
    },
    update_matrix_dendro_col: async (selected_cols) => {
      // const inst_gene = 'cluster'
      const new_cats = selected_cols; // click_info.value.selected_names

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);

      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: false,
        path_layer: false,
        trx_layer: false,
      });
      viz_state.layers_obj = layers_obj;
    },
    update_view_state: async (new_view_state, close_up, _trx_layer) => {
      viz_state.close_up = close_up;

      calc_viewport(
        new_view_state,
        deck_ist,
        layers_obj,
        viz_state,
        viz_state.obs_store
      );
      viz_state.obs_store.deck_check.set({
        ...viz_state.obs_store.deck_check.get(),
        cell_layer: false,
        path_layer: false,
        trx_layer: false,
      });

      deck_ist.setProps({
        controller: { doubleClickZoom: false },
        initialViewState: new_view_state,
        views: viz_state.views,
      });

      viz_state.layers_obj = layers_obj;
    },
    update_layers: () => {},
    get_state: get_state_snapshot,
    finalize: () => {
      if (updateTriggerHandler) {
        viz_state.model.off('change:update_trigger', updateTriggerHandler);
      }

      if (cellClusterHandler) {
        viz_state.model.off('change:cell_clusters', cellClusterHandler);
      }

      if (selectedCellsHandler) {
        viz_state.model.off('change:selected_cells', selectedCellsHandler);
      }

      const gl = deck_ist?.animationLoop?.gl;
      const loseCtxExtension = gl?.getExtension('WEBGL_lose_context');
      if (loseCtxExtension) {
        loseCtxExtension.loseContext();
      }

      deck_ist.finalize();
    },
  };

  return landscape;
};
