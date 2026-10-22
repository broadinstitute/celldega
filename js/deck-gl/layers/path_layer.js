import { PathLayer } from 'deck.gl';

import { update_selected_cats, update_cat } from '../../global_variables/cat';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { getModelMatrixProps } from '../../utils/rotation';
import { grab_cell_tiles_in_view } from '../../vector_tile/polygons/grab_cell_tiles_in_view';

import { is_cluster_color_mode } from './cell_color';
import { create_segmentation_error_handler } from './segmentation_recovery';

const pathDataRequests = new WeakMap();

export const get_path_color = (cats, i, d) => {
  const inst_cell_id = cats.polygon_cell_names[d.index];
  if (
    cats.meta_cell_id_set &&
    !cats.meta_cell_id_set.has(String(inst_cell_id))
  ) {
    return [0, 0, 0, 0];
  }
  const inst_cat = cats.dict_cell_cats[inst_cell_id];

  let inst_color;

  // Convert to string for consistent color lookup
  // (meta_cell values may be numbers, color_dict keys are always strings)
  const inst_cat_str = String(inst_cat);

  const color_dict_cluster = cats.color_dict_cluster || {};

  // check if inst_cat is not in cats.color_dict_cluster
  if (inst_cat_str in color_dict_cluster) {
    inst_color = color_dict_cluster[inst_cat_str];
  } else {
    // default segmentation color
    inst_color = [0, 0, 255];
  }

  const selected_cats = Array.isArray(cats.selected_cats)
    ? cats.selected_cats.map((cat) => String(cat))
    : [];

  // selected_cats doubles as the polygon cluster filter, but when a gene is
  // selected it holds the gene name (see gene search / yearbook query handling).
  // A gene name never matches a cluster category, so filtering polygons by it
  // would drive every polygon's alpha to 0 and hide all cell boundaries. In gene
  // mode, only keep selected_cats entries that are real cluster categories -- a
  // pure gene selection then leaves every polygon visible (matching how the cell
  // centroid layer stays visible in gene mode).
  const cluster_filter = is_cluster_color_mode(cats)
    ? selected_cats
    : selected_cats.filter((cat) => cat in color_dict_cluster);

  const alpha =
    cluster_filter.length === 0 || cluster_filter.includes(inst_cat_str)
      ? 255
      : 0;

  return [...inst_color, alpha];
};

export const ini_path_layer = (viz_state) => {
  const path_layer = new PathLayer({
    id: 'path-layer',
    data: [],
    pickable: true,
    widthScale: 3,
    widthMinPixels: 1,
    getPath: (d) => d,
    getColor: (i, d) => get_path_color(viz_state.cats, i, d),
    onError: create_segmentation_error_handler(viz_state),
    widthUnits: 'pixels',
    ...getModelMatrixProps(viz_state.rotation),
  });

  return path_layer;
};

const path_layer_onclick = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_cell_id = viz_state.cats.polygon_cell_names[info.index];
  const inst_cat = viz_state.cats.dict_cell_cats[inst_cell_id];

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });

  update_cat(viz_state.cats, 'cluster');
  update_selected_cats(viz_state.cats, [inst_cat], viz_state.obs_store);
  update_selected_genes(viz_state.genes, [], viz_state.obs_store);
};

export const update_path_layer_data = async (
  base_url,
  tiles_in_view,
  layers_obj,
  viz_state
) => {
  if (
    viz_state.disposed ||
    (viz_state.global_base_url !== undefined &&
      base_url !== viz_state.global_base_url)
  ) {
    return false;
  }

  const request = {};
  pathDataRequests.set(viz_state, request);
  const datasetUrl = viz_state.global_base_url;
  const segmentationVersion = viz_state.seg?.version;
  const viewportRequestId = viz_state.viewport_request_id;
  const { cats } = viz_state;
  const cellReader = viz_state.row_group_readers?.cell;
  // Tile requests can finish out of order after a pan, zoom, or dataset change.
  // Discard the complete result before touching either geometry or cell IDs.
  const isCurrentRequest = () =>
    pathDataRequests.get(viz_state) === request &&
    !viz_state.disposed &&
    !cellReader?.disposed &&
    datasetUrl === viz_state.global_base_url &&
    segmentationVersion === viz_state.seg?.version &&
    viewportRequestId === viz_state.viewport_request_id &&
    cats === viz_state.cats &&
    cellReader === viz_state.row_group_readers?.cell;

  let result;
  let succeeded = true;
  try {
    result = await grab_cell_tiles_in_view(base_url, tiles_in_view, viz_state);
    if (
      !Array.isArray(result.paths) ||
      !Array.isArray(result.cellNames) ||
      result.paths.length !== result.cellNames.length
    ) {
      throw new Error(
        'Segmentation paths and cell names must have equal lengths'
      );
    }
  } catch (error) {
    if (!isCurrentRequest()) return false;

    // Fetch caches hold decoded Arrow tables before geometry validation. Evict
    // a bad result so the next viewport can fetch/decode fresh data to recover.
    viz_state.cache?.cell?.clear?.();
    cellReader?.requestCache?.clear?.();

    // Never leave a previously rendered set of boundaries paired with failed
    // or partially decoded data. A future viewport update can retry the tiles.
    result = { paths: [], cellNames: [] };
    succeeded = false;
    // eslint-disable-next-line no-console -- Surface invalid tile data for diagnosis.
    console.error('[segmentation] Failed to load cell boundaries:', error);
  }

  if (!isCurrentRequest()) {
    return false;
  }

  // PathLayer packs positions and boundary masks into separate GPU buffers.
  // Recreate both together when tiles change, rather than carrying partial
  // renderer state from an earlier geometry update into the new outlines.
  viz_state.path_data_revision = (viz_state.path_data_revision || 0) + 1;
  const pathLayer = layers_obj.path_layer.clone({
    id: `path-layer-data-${viz_state.path_data_revision}`,
    data: result.paths,
    onError: create_segmentation_error_handler(viz_state),
  });
  cats.polygon_cell_names = result.cellNames;
  layers_obj.path_layer = pathLayer;

  // ensure state updated prior to deck_ready notification
  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    path_data: true,
  });

  return succeeded;
};

export const set_path_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.path_layer = layers_obj.path_layer.clone({
    onClick: (info, d) =>
      path_layer_onclick(info, d, deck_ist, layers_obj, viz_state),
  });
};

export const toggle_path_layer_visibility = (layers_obj, visible) => {
  layers_obj.path_layer = layers_obj.path_layer.clone({
    visible,
  });
};

export const update_path_pickable_state = (layers_obj, pickable) => {
  layers_obj.path_layer = layers_obj.path_layer.clone({
    pickable,
  });
};
