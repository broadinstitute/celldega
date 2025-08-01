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
} from '../deck-gl/layers/cell_layer';
// import {
//   ini_edit_layer,
//   set_edit_layer_on_click,
//   set_edit_layer_on_edit,
// } from '../deck-gl/layers/edit_layer';
import { make_image_layers } from '../deck-gl/layers/image_layers';
import {
  ini_nbhd_layer,
  set_nbhd_layer_onclick,
} from '../deck-gl/layers/nbhd_layer';
import {
  ini_path_layer,
  set_path_layer_onclick,
  toggle_path_layer_visibility,
} from '../deck-gl/layers/path_layer';
import {
  ini_trx_layer,
  set_trx_layer_onclick,
  update_trx_layer_radius,
  toggle_trx_layer_visibility,
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
import { update_cell_clusters } from '../widget_interactions/update_cell_clusters';
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm';

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
  landscape_state = 'spatial',
  segmentation = 'default',
  creds = {},
  max_tiles_to_view = 50,
  view_change_custom_callback = null
) => {
  if (width === 0) {
    width = '100%';
  }

  const viz_state = {};

  viz_state.obs_store = create_obs_store();

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
      viz_state.obs_store.viz_image_layers.set(true);
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
      viz_state.nbhd.is_nbhd = false;

      viz_state.nbhd.ini_feature_collection = {
        type: 'FeatureCollection',
        features: [],
        inst_alpha: null,
      };

      viz_state.nbhd.feature_collection = viz_state.nbhd.ini_feature_collection;
    } else {
      viz_state.nbhd.is_nbhd = true;

      viz_state.nbhd.ini_feature_collection = nbhd; // viz_state.model.get('nbhd');

      viz_state.nbhd.bar_data = nbhd.features
        .map((feature) => {
          return {
            name: feature.properties.cat, // "1_50" → "1"
            value: feature.properties.area, // use area as the value
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

  if (Object.keys(meta_cell).length === 0) {
    viz_state.cats.has_meta_cell = false;
  } else {
    viz_state.cats.has_meta_cell = true;
  }
  viz_state.cats.meta_cell = meta_cell;
  viz_state.cats.meta_cell_attr = meta_cell_attr;
  viz_state.cats.inst_cell_attr = meta_cell_attr[0] || 'N.A.';

  if (Object.keys(meta_cluster).length === 0) {
    viz_state.cats.has_meta_cluster = false;
  } else {
    viz_state.cats.has_meta_cluster = true;
  }
  viz_state.cats.meta_cluster = meta_cluster;
  viz_state.cats.meta_cluster_attr = meta_cluster_attr;
  viz_state.cats.inst_cluster_attr = meta_cluster_attr[0] || 'N.A.';

  viz_state.umap = {};
  if (Object.keys(umap).length === 0) {
    viz_state.umap.has_umap = false;
  } else {
    viz_state.umap.has_umap = true;
  }
  viz_state.umap.umap = umap;

  if (landscape_state === 'spatial') {
    viz_state.umap.state = false;
  } else if (landscape_state === 'umap') {
    viz_state.umap.state = true;
  }

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

  viz_state.cats.cell_exp_array = [];
  viz_state.cats.cell_names_array = [];
  viz_state.cats.cell_name_to_index_map = new Map();

  viz_state.img = {};
  viz_state.img.image_layer_colors = {};
  viz_state.img.image_layer_sliders = {};

  set_options(token);

  await set_landscape_parameters(viz_state.img, base_url, viz_state.aws);

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

  // Create and append the visualization.
  const root = document.createElement('div');
  root.style.height = `${height}px`;
  root.style.border = '1px solid #d3d3d3';

  await set_dimensions(viz_state, base_url, image_name_for_dim);

  await set_meta_gene(
    viz_state.genes,
    base_url,
    viz_state.seg.version,
    viz_state.aws
  );

  await set_cluster_metadata(viz_state);

  viz_state.views = set_views();

  const deck_ist = await ini_deck(root, width, height);
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
  viz_state.edit.rgn_opacity = 0.75;
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
  const trx_layer = ini_trx_layer(viz_state.genes);
  // const edit_layer = ini_edit_layer(viz_state);
  const nbhd_layer = ini_nbhd_layer(viz_state, true);

  // make layers object
  const layers_obj = {
    background_layer,
    image_layers,
    cell_layer,
    path_layer,
    trx_layer,
    // edit_layer,
    nbhd_layer,
  };

  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    nbhd_layer: true,
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
    },
    { immediate: false }
  );

  // set onclicks after all layers are made
  set_cell_layer_onclick(deck_ist, layers_obj, viz_state);
  set_path_layer_onclick(deck_ist, layers_obj, viz_state);
  set_trx_layer_onclick(deck_ist, layers_obj, viz_state);
  // set_edit_layer_on_edit(deck_ist, layers_obj, viz_state);
  // set_edit_layer_on_click(deck_ist, layers_obj, viz_state);
  set_nbhd_layer_onclick(deck_ist, layers_obj, viz_state);

  viz_state.obs_store.deck_ready.subscribe((ready) => {
    if (ready) {
      const list = get_layers_list(viz_state.layers_obj, viz_state.close_up);
      deck_ist.setProps({ layers: list });
    }
  });

  viz_state.obs_store.selected_cats.subscribe((selected_cats) => {
    const selected_cats_name = selected_cats.join('-');

    layers_obj.cell_layer = layers_obj.cell_layer.clone({
      id: `cell-layer-${selected_cats_name}`,
    });

    layers_obj.path_layer = layers_obj.path_layer.clone({
      id: `path-layer-${selected_cats_name}`,
    });

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      path_layer: true,
      cell_layer: true,
    });
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

  if (viz_state.umap.state === true) {
    viz_state.obs_store.viz_background_layer.set(false);
    viz_state.obs_store.viz_image_layers.set(false);
    toggle_trx_layer_visibility(layers_obj, false);
    toggle_path_layer_visibility(layers_obj, false);
  }

  set_initial_view_state(deck_ist, ini_x, ini_y, ini_z, ini_zoom, viz_state);

  set_deck_on_view_state_change(deck_ist, layers_obj, viz_state);

  if (Object.keys(viz_state.model).length > 0) {
    viz_state.model.on('change:update_trigger', () =>
      update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state)
    );
    viz_state.model.on('change:cell_clusters', () =>
      update_cell_clusters(deck_ist, layers_obj, viz_state)
    );
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

  const landscape = {
    update_matrix_gene: async (inst_gene) => {
      const reset_gene = inst_gene === viz_state.cats.cat;
      const new_cat = reset_gene ? 'cluster' : inst_gene;

      update_cat(viz_state.cats, new_cat);
      update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
      // update_selected_cats(viz_state.cats, [], viz_state.obs_store);
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
    finalize: () => {
      deck_ist.finalize();
    },
  };

  return landscape;
};
