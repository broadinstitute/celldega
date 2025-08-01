import { AwsClient } from 'aws4fetch';
import * as d3 from 'd3';

import { ini_deck_sst } from '../deck-gl/core/deck_sst';
import { set_views } from '../deck-gl/core/views';
import { make_simple_image_layer } from '../deck-gl/layers/simple_image_layer';
import {
  ini_square_scatter_layer,
  set_tile_layer_onclick,
} from '../deck-gl/layers/square_scatter_layer';
import { make_tile_tooltip } from '../deck-gl/utils/tooltips';
import { options, set_options } from '../global_variables/fetch_options';
import { set_global_base_url } from '../global_variables/global_base_url';
import { set_dimensions } from '../global_variables/image_dimensions';
import { set_landscape_parameters } from '../global_variables/landscape_parameters';
import { set_meta_gene } from '../global_variables/meta_gene';
import { set_tile_color_dict } from '../global_variables/tile_color_dict';
import {
  set_tile_names_array,
  set_tile_name_to_index_map,
} from '../global_variables/tile_names_array';
import { set_tile_scatter_data } from '../global_variables/tile_scatter_data';
import { create_obs_store } from '../obs_store/obs_store';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { get_scatter_data } from '../read_parquet/get_scatter_data';
import { make_sst_ui_container } from '../ui/ui_containers';
import { update_tile_landscape_from_cgm } from '../widget_interactions/update_tile_landscape_from_cgm';

export const landscape_sst = async (
  ini_model,
  el,
  base_url,
  token,
  ini_x,
  ini_y,
  ini_z,
  ini_zoom,
  square_tile_size = 1.4,
  _dataset_name = '',
  width = 0,
  height = 800,
  creds = {}
) => {
  if (width === 0) {
    width = '100%';
  }


  // Create and append the visualization container
  const root = document.createElement('div');
  // root.style.height = '800px';
  root.style.height = `${height}px`;
  root.style.width = typeof width === 'number' ? `${width}px` : width;

  const viz_state = {};

  viz_state.obs_store = create_obs_store();

  set_options(token);
  set_global_base_url(viz_state, base_url);

  viz_state.model = ini_model;

  viz_state.img = {};
  viz_state.img.image_layer_colors = {};
  viz_state.img.image_layer_sliders = {};

  await set_landscape_parameters(viz_state.img, base_url);




  // AWS credentials setup

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

  await set_dimensions(viz_state, base_url, 'cells');

 const parseDim = (val, ref) => {
    if (typeof val === 'string' && val.includes('%')) {
      const ratio = parseFloat(val) / 100;
      return ref * ratio;
    }
    return parseFloat(val) || ref;
  };

  const imgWidth = viz_state.dimensions.width;
  const imgHeight = viz_state.dimensions.height;
  const containerWidth = parseDim(width, el.clientWidth || imgWidth);
  const containerHeight = parseDim(height, el.clientHeight || imgHeight);
  const scale = Math.min(
    containerWidth / imgWidth,
    containerHeight / imgHeight
  );
  const autoZoom = Math.log2(scale);

  if (ini_x === 0 && ini_y === 0 && ini_zoom === 0) {
    ini_x = imgWidth / 2;
    ini_y = imgHeight / 2;
    ini_zoom = autoZoom;
  }

  viz_state.buttons = {};
  viz_state.buttons.blue = '#8797ff';
  viz_state.buttons.gray = 'gray';
  viz_state.buttons.light_gray = '#EEEEEE';
  viz_state.buttons.buttons = {};

  viz_state.genes = {};
  viz_state.genes.color_dict_gene = {};
  viz_state.genes.gene_names = [];
  viz_state.genes.meta_gene = {};
  viz_state.genes.gene_counts = [];
  viz_state.genes.selected_genes = [];
  viz_state.genes.trx_ini_radius = 1;
  viz_state.genes.trx_names_array = [];
  viz_state.genes.trx_data = [];
  viz_state.genes.gene_text_box = '';
  viz_state.genes.trx_slider = document.createElement('input');
  viz_state.genes.gene_search = document.createElement('div');
  viz_state.genes.svg_bar_gene = d3.create('svg');

  viz_state.cats = {};
  viz_state.cats.cat = 'cluster';
  viz_state.cats.reset_cat = false;
  viz_state.cats.selected_cats = [];
  viz_state.cats.cell_cats = [];
  viz_state.cats.dict_cell_cats = {};
  viz_state.cats.color_dict_cluster = {};
  viz_state.cats.cluster_counts = [];
  viz_state.cats.polygon_cell_names = [];
  viz_state.cats.svg_bar_cluster = d3.create('svg');

  viz_state.tooltip_cat_tile = '';

  viz_state.cats.square_tile_size = square_tile_size;

  await set_meta_gene(
    viz_state.genes,
    base_url,
    'default',
    viz_state.aws
  );


  // move this to landscape_parameters
  const _info = {
    name: 'cells',
    color: [0, 0, 255],
  };

  const tile_url = `${base_url}/tile_geometries.parquet`;

  const tile_arrow_table = await get_arrow_table(
    tile_url,
    options.fetch,
    viz_state.aws
  );

  viz_state.cats.tile_cats_array = tile_arrow_table
    .getChild('cluster')
    .toArray();
  viz_state.cats.tile_exp_array = [];
  viz_state.cats.tile_names_array = [];
  viz_state.cats.tile_scatter_data = [];

  set_tile_scatter_data(viz_state.cats, get_scatter_data(tile_arrow_table));

  set_tile_names_array(
    viz_state.cats,
    tile_arrow_table.getChild('name').toArray()
  );
  set_tile_name_to_index_map(viz_state.cats);

  viz_state.cats.tile_color_dict = await set_tile_color_dict(viz_state, base_url);

  const simple_image_layer = await make_simple_image_layer(viz_state, _info);
  const square_scatter_layer = ini_square_scatter_layer(viz_state.cats);

  const layers_sst = {
    simple_image_layer,
    square_scatter_layer,
  };

  viz_state.views = set_views();

  const deck_sst = ini_deck_sst(root, width, height);

  const initial_view_state = {
    target: [ini_x, ini_y, ini_z],
    zoom: ini_zoom,
  };

  deck_sst.setProps({
    views: viz_state.views,
    layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer],
    getTooltip: (info) => make_tile_tooltip(info, viz_state),
    initialViewState: initial_view_state,
  });

  if (Object.keys(viz_state.model).length > 0) {
    // ist version
    viz_state.model.on('change:update_trigger', () =>
      update_tile_landscape_from_cgm(deck_sst, layers_sst, viz_state)
    );
  }

  set_tile_layer_onclick(deck_sst, layers_sst, viz_state);

  const ui_container = make_sst_ui_container(deck_sst, layers_sst, viz_state);

  // UI and Viz Container
  el.appendChild(ui_container);
  el.appendChild(root);

  return () => deck_sst.finalize();
};
