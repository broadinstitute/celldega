import { options } from '../../global_variables/fetch_options';
import { fetch_all_tables_new } from '../../read_parquet/fetch_all_tables';
import { parse_cells_tables } from '../../read_parquet/nbhd_cloud_tables';
import {
  refresh_nbhd_cloud_cell_layer_data,
  update_nbhd_cloud_cell_layer_opacity,
} from '../layers/nbhd_cloud_cell_layer';
import { update_nbhd_cloud_shapes_fill_opacity } from '../layers/nbhd_cloud_shapes_layer';

import {
  compute_nbhd_cloud_lod,
  compute_nearest_slices,
  makeSliceSetKey,
} from './nbhd_cloud_lod';

// The `neighborhood-cloud` counterpart to `calc_viewport`'s 2D tile-based LOD
// — driven by the same 200ms-debounced view-state change
// (on_view_state_change.js), but keyed on nearest-slice distance instead of
// tile count, and a continuous opacity crossfade instead of a discrete
// close_up toggle.
export const calc_nbhd_cloud_viewport = async (
  { zoom, target },
  _deck_ist,
  layers_obj,
  viz_state
) => {
  const { nbhd_cloud } = viz_state;
  if (!nbhd_cloud || !Array.isArray(nbhd_cloud.meta_slice)) {
    return;
  }

  const nearestN = nbhd_cloud.nearest_n_slices?.cells ?? 3;
  if (nbhd_cloud.meta_slice.length > 0) {
    const nearestSliceIds = compute_nearest_slices(
      target,
      nbhd_cloud.meta_slice,
      nearestN
    );
    const sliceSetKey = makeSliceSetKey(nearestSliceIds);

    if (sliceSetKey !== nbhd_cloud.loaded_slice_set_key) {
      nbhd_cloud.cache_cells ??= new Map();
      const urls = nearestSliceIds.map(
        (sliceId) =>
          `${viz_state.global_base_url}/nbhd_cloud/cells/by_slice/slice_${sliceId}.parquet`
      );
      const tables = await fetch_all_tables_new(
        nbhd_cloud.cache_cells,
        urls,
        options,
        viz_state.aws ?? null
      );
      const merged = parse_cells_tables(tables.filter(Boolean));
      refresh_nbhd_cloud_cell_layer_data(viz_state, layers_obj, merged);

      nbhd_cloud.loaded_slice_set_key = sliceSetKey;
      nbhd_cloud.loaded_slice_ids = new Set(nearestSliceIds);
    }
  }

  const { fillOpacity, cellOpacity } = compute_nbhd_cloud_lod(
    zoom,
    nbhd_cloud.lod_state,
    nbhd_cloud.zoom_thresholds
  );
  // Remembered so a mid-crossfade gene selection (bar_plot.js) can redraw the
  // fill accessor at the current fade level without re-deriving it from zoom.
  nbhd_cloud.last_fill_opacity = fillOpacity;
  update_nbhd_cloud_shapes_fill_opacity(layers_obj, viz_state, fillOpacity);
  update_nbhd_cloud_cell_layer_opacity(layers_obj, cellOpacity);

  viz_state.layers_obj = layers_obj;
};
