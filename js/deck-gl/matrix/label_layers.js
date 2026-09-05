import * as d3 from 'd3';
import { TextLayer } from 'deck.gl';

import {
  sync_selected_genes,
  sync_selected_rows,
  sync_selected_cols,
} from '../../global_variables/selected_genes';
import {
  composition_row_label_position,
  refresh_row_label_visibility,
} from '../../matrix/composition_data';
import {
  crop_fade_axis_alpha_factor,
  crop_filter_signature,
  filter_label_data,
  get_axis_center_position,
  get_axis_display_count,
  get_axis_label_font_size,
  get_zoomed_axis_label_font_size,
  is_axis_index_visible,
} from '../../matrix/crop_filter';
import {
  buildColAxisSlice,
  emitMatrixSliceRequest,
} from '../../matrix/matrix_axis_slice';
import { deselect_reorder_buttons } from '../../ui/text_buttons';

import {
  apply_composition_hover_col,
  apply_composition_hover_row,
  clear_composition_hover,
  HOVER_HIGHLIGHT_DELAY_MS,
} from './composition_layer';
import {
  clear_dendro_hover,
  refresh_composition_dendro,
  toggle_dendro_layer_visibility,
} from './dendro_layers';
import {
  col_label_color_triggers,
  get_layer_update_triggers,
  get_mat_layers_list,
  mat_reorder_triggers,
  row_label_color_triggers,
} from './matrix_layers';

const MAX_COL_LABEL_PIXEL_OFFSET = 18;

const row_label_get_position = (d, index, viz_state) => {
  const inst_index = d.index ?? index.index;

  // Composition mode: position at the row's actual stacked-bar segment
  // (next to the leftmost bar) so labels track reordering/normalization
  // exactly, rather than a uniform heatmap-style slot.
  if (viz_state.mat.viz_mode === 'composition') {
    return composition_row_label_position(viz_state, inst_index);
  }

  const row_offset = 50; // 25

  const pos_x = row_offset;
  const pos_y = get_axis_center_position(viz_state, 'row', inst_index) ?? 0;

  const position = [pos_x, pos_y];

  return position;
};

const col_label_get_position = (d, index, viz_state) => {
  const inst_index = d.index ?? index.index;
  const col_offset = 50;

  const pos_x = get_axis_center_position(viz_state, 'col', inst_index) ?? 0;
  const pos_y = col_offset; // * zoom_factor

  const position = [pos_x, pos_y];

  return position;
};

// Enrich's "In term" blue (#2f74ff) — row labels for genes in the currently
// selected enriched term are drawn in this color, mirroring the Enrich
// paragraph view.
const HIGHLIGHT_LABEL_COLOR = [47, 116, 255];

// Enrich lowercases term genes before syncing, so membership is matched
// case-insensitively against the row name.
const is_row_label_highlighted = (viz_state, d) =>
  Boolean(
    viz_state.labels.highlighted_genes?.has(String(d.name || '').toLowerCase())
  );

// The reorder driver is the double-clicked label the matrix is custom-sorted
// by; it stays blue only while the *other* axis's order is still 'custom'
// (a reorder button on that axis replaces the custom order and un-blues it).
const is_reorder_driver_label = (viz_state, axis, d) => {
  const driver = viz_state.labels.reorder_driver;
  if (!driver || driver.axis !== axis || driver.index !== d.index) {
    return false;
  }
  const sorted_axis = axis === 'col' ? 'row' : 'col';
  return viz_state.order?.current?.[sorted_axis] === 'custom';
};

const set_reorder_driver = (viz_state, axis, name, index) => {
  viz_state.labels.reorder_driver = { axis, name, index };
  viz_state.labels._row_style_rev = (viz_state.labels._row_style_rev || 0) + 1;
  viz_state.labels._col_style_rev = (viz_state.labels._col_style_rev || 0) + 1;
};

// Per-instance so composition mode can hide labels that don't fit their
// segment (fully transparent, rather than removed from `data`, so
// reorder/index-keyed picking stays stable). Shared by the base row-label
// layer and the bold focus overlay so both respect crop fade, composition
// visibility, and term-gene highlighting.
const row_label_text_color = (viz_state, d) => {
  const crop_alpha = Math.round(
    255 * crop_fade_axis_alpha_factor(viz_state, 'row', d.index)
  );
  if (crop_alpha === 0) return [0, 0, 0, 0];
  if (viz_state.mat.viz_mode === 'composition') {
    const visible = viz_state.labels.row_visibility;
    if (visible && visible[d.index] === false) return [0, 0, 0, 0];
  }
  return is_row_label_highlighted(viz_state, d) ||
    is_reorder_driver_label(viz_state, 'row', d)
    ? [...HIGHLIGHT_LABEL_COLOR, crop_alpha]
    : [0, 0, 0, crop_alpha];
};

// Column labels: crop fade plus the reorder-driver blue (no term-gene
// highlighting — columns aren't genes).
const col_label_text_color = (viz_state, d) => {
  const crop_alpha = Math.round(
    255 * crop_fade_axis_alpha_factor(viz_state, 'col', d.index)
  );
  if (crop_alpha === 0) return [0, 0, 0, 0];
  return is_reorder_driver_label(viz_state, 'col', d)
    ? [...HIGHLIGHT_LABEL_COLOR, crop_alpha]
    : [0, 0, 0, crop_alpha];
};

export const ini_row_label_layer = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const row_label_layer = new TextLayer({
    id: 'row-label-layer',
    data: filter_label_data(viz_state, 'row'),
    getPosition: (d, index) => row_label_get_position(d, index, viz_state),
    getText: (d) => d.display_name || d.name,
    getSize: get_axis_label_font_size(viz_state, 'row'),
    // The focused row's base label is drawn fully transparent: the bold
    // overlay replaces it (bold glyph widths differ, so drawing both would
    // ghost). The datum stays in `data` so sibling labels keep their indices
    // (removing it would index-shift-animate the whole column).
    getColor: (d) =>
      d.index === viz_state.labels.focused_row_index
        ? [0, 0, 0, 0]
        : row_label_text_color(viz_state, d),
    getAngle: 0,
    getTextAnchor: 'end',
    getAlignmentBaseline: 'center',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 2,
    updateTriggers: {
      getPosition: crop_sig,
      getColor: row_label_color_triggers(viz_state),
      getSize: crop_sig,
    },
    pickable: true,
    transitions,
  });

  return row_label_layer;
};

/**
 * Bold overlay for the focused row's label (Enrich gene click or row search).
 * deck.gl TextLayer font weight is layer-level, not per-datum, so the focused
 * label is drawn as its own one-datum bold layer on top of the base label
 * (same color/position/size — bold glyphs fully cover the regular ones). The
 * base datum stays in place and pickable; the overlay is not pickable.
 *
 * Rebuilt (fresh one-element `data` array) wherever the base layer's
 * geometry-affecting props change, so accessors re-evaluate without
 * trigger bookkeeping.
 */
export const ini_row_label_focus_layer = (viz_state) => {
  const focused_index = viz_state.labels.focused_row_index;
  const data =
    focused_index == null
      ? []
      : filter_label_data(viz_state, 'row').filter(
          (d) => d.index === focused_index
        );

  return new TextLayer({
    // Contains 'row-label-layer' so layer_filter routes it to the rows
    // viewport, and listed in SNAP_ANNOTATION_LAYER_IDS for crop snaps.
    id: 'row-label-layer-focus',
    data,
    getPosition: (d, index) => row_label_get_position(d, index, viz_state),
    getText: (d) => d.display_name || d.name,
    getSize: get_zoomed_axis_label_font_size(
      viz_state,
      'row',
      viz_state.zoom?.zoom_data?.matrix?.zoom_y ?? 0
    ),
    getColor: (d) => row_label_text_color(viz_state, d),
    getAngle: 0,
    getTextAnchor: 'end',
    getAlignmentBaseline: 'center',
    fontFamily: 'Arial',
    fontWeight: 'bold',
    sizeUnits: 'pixels',
    sizeScale: 2,
    // The overlay REPLACES the (transparent) base label, so it takes over its
    // click/hover behavior via the handlers stashed by the set_* wiring.
    pickable: true,
    onClick: (event) => viz_state.labels._row_label_click_handler?.(event),
    onHover: (info) => viz_state.labels._row_label_hover_handler?.(info),
    // Deliberately no transitions: TextLayer expands strings into
    // per-character instances, so transitioning this one-datum layer between
    // differently-named genes both "flies" the bold label from the previous
    // focus position and truncates it to the overlapping character count
    // mid-flight. Snapping keeps the overlay exactly in the base label's slot.
  });
};

export const refresh_row_label_focus_layer = (layers_mat, viz_state) => {
  layers_mat.row_label_focus_layer = ini_row_label_focus_layer(viz_state);
};

/**
 * Re-trigger row-label colors (term-gene highlight, reorder driver, and the
 * hide-under-bold rule) and rebuild the bold focus overlay. Call after
 * changing highlighted_genes, the focused row, or the reorder driver; the
 * caller issues the setProps.
 */
export const refresh_row_label_styles = (layers_mat, viz_state) => {
  viz_state.labels._row_style_rev = (viz_state.labels._row_style_rev || 0) + 1;
  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.row_label_layer),
      getColor: row_label_color_triggers(viz_state),
    },
  });
  refresh_row_label_focus_layer(layers_mat, viz_state);
};

/**
 * Re-trigger row-label colors after the highlighted (term) gene set changes,
 * and rebuild the bold focus overlay so it picks up the new palette too.
 */
export const refresh_row_label_highlight = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  refresh_row_label_styles(layers_mat, viz_state);
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

export const ini_col_label_layer = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  function get_pixel_offset(num_cols) {
    const offset_y = 75 / Math.max(num_cols, 1);
    return [0, Math.min(MAX_COL_LABEL_PIXEL_OFFSET, offset_y)];
  }

  const transitions = {
    getPosition: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const col_label_layer = new TextLayer({
    id: 'col-label-layer',
    data: filter_label_data(viz_state, 'col'),
    getPosition: (d, index) => col_label_get_position(d, index, viz_state),
    getText: (d) => d.display_name || d.name,
    getSize: get_axis_label_font_size(viz_state, 'col'),
    getColor: (d) => col_label_text_color(viz_state, d),
    getAngle: 45, // Optional: Text angle in degrees
    getTextAnchor: 'start', // middle
    getAlignmentBaseline: 'bottom',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 2,
    // updateTriggers: {
    // //   getSize: viz_state.viz.ini_font_size,
    //   getPosition: viz_state.viz.font_size,
    //   getPixelOffset: viz_state.zoom.zoom_data.matrix.zoom_x,
    // },
    pickable: true,
    transitions,
    getPixelOffset: () =>
      get_pixel_offset(get_axis_display_count(viz_state, 'col')),
    updateTriggers: {
      getPosition: crop_sig,
      getPixelOffset: crop_sig,
      getColor: col_label_color_triggers(viz_state),
      getSize: crop_sig,
    },
  });

  return col_label_layer;
};

const DOUBLE_CLICK_DELAY = 250;

const ensure_label_click_tracking = (viz_state) => {
  viz_state.labels.click_timeouts ||= { row: null, col: null };
  viz_state.labels.pending_click ||= { row: null, col: null };
};

const clear_pending_label_click = (viz_state, axis) => {
  ensure_label_click_tracking(viz_state);
  clearTimeout(viz_state.labels.click_timeouts[axis]);
  viz_state.labels.click_timeouts[axis] = null;
  viz_state.labels.pending_click[axis] = null;
};

// Enrichment needs at least a handful of genes to say anything, so very narrow
// views fall back to this rather than to a percentage of almost nothing.
const MIN_TOP_GENES = 5;
const DEFAULT_TOP_GENE_PERCENT = 10;
const DEFAULT_TOP_GENE_CAP = 50;

/**
 * How many of a column's top genes to send to enrichment.
 *
 * Scaled to the *visible* row count rather than fixed: under a rank view a flat
 * "top 50" can be the entire view (50 of 45 rows), which enriches a gene set
 * against itself and says nothing. `top_n_genes` stays the upper bound, so a
 * full matrix still behaves exactly as before.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {number} Gene count, clamped to the visible rows.
 */
const resolve_top_gene_count = (viz_state) => {
  const visible = get_axis_display_count(viz_state, 'row');

  const cap = Number(viz_state.top_n_genes);
  const max_genes =
    Number.isFinite(cap) && cap > 0 ? Math.floor(cap) : DEFAULT_TOP_GENE_CAP;

  const percent = Number(viz_state.top_gene_percent);
  const share =
    Number.isFinite(percent) && percent > 0
      ? percent
      : DEFAULT_TOP_GENE_PERCENT;

  const scaled = Math.round((visible * share) / 100);
  return Math.min(
    visible,
    Math.max(MIN_TOP_GENES, Math.min(max_genes, scaled))
  );
};

// Top genes for a clicked column, ranked over the *visible* (crop-filtered)
// rows only, so a row crop never leaks hidden genes into linked widgets.
const top_gene_names_for_column = (viz_state, col_index) => {
  const slice = buildColAxisSlice(
    viz_state,
    col_index,
    resolve_top_gene_count(viz_state),
    (row_index) => is_axis_index_visible(viz_state, 'row', row_index)
  );
  return slice ? slice.entries.map((entry) => entry.counterpart_name) : [];
};

const custom_label_reorder = (
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  name,
  index
) => {
  let tmp_arr = [];
  const other_axis = axis === 'col' ? 'row' : 'col';

  // deactivate reordering buttons when setting a custom order
  deselect_reorder_buttons(viz_state, other_axis);

  // Track the double-clicked label driving this custom order: it renders in
  // the linkage blue until the sorted axis's order changes again.
  set_reorder_driver(viz_state, axis, name, index);

  if (axis === 'col') {
    tmp_arr = viz_state.mat.net_mat.map((inst_row) => inst_row[index]);
  } else {
    tmp_arr = viz_state.mat.net_mat[index];
  }

  // tmp_sort is an array of the indexes of the other axis that are ranked by the values of the selected index
  const tmp_sort = Array.from(tmp_arr.keys()).sort(
    (a, b) => tmp_arr[b] - tmp_arr[a]
  );

  const length_other_axis = tmp_sort.length;
  const ranked_sort = Array(length_other_axis);

  // convert tmp_sort into an array of the ranks of each index
  // Fill the ranks array with the rank of each index
  tmp_sort.forEach((columnIndex, rank) => {
    ranked_sort[columnIndex] = length_other_axis - rank; // Add 1 to make it 1-indexed
  });

  viz_state.mat.orders[other_axis].custom = ranked_sort;

  viz_state.order.current[other_axis] = 'custom';

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: mat_reorder_triggers(viz_state, [name]),
  });

  if (other_axis === 'col') {
    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.col_label_layer),
        getPosition: [
          viz_state.order.current.col,
          name,
          crop_filter_signature(viz_state),
        ],
      },
    });

    // reorder cat_layer
    layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.col_cat_layer),
        getPosition: [
          viz_state.order.current.col,
          crop_filter_signature(viz_state),
        ],
      },
    });

    toggle_dendro_layer_visibility(layers_mat, viz_state, 'col');
  } else if (other_axis === 'row') {
    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.row_label_layer),
        getPosition: [
          viz_state.order.current.row,
          name,
          crop_filter_signature(viz_state),
        ],
      },
    });

    // reorder cat_layer
    layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.row_cat_layer),
        getPosition: [
          viz_state.order.current.row,
          crop_filter_signature(viz_state),
        ],
      },
    });

    toggle_dendro_layer_visibility(layers_mat, viz_state, 'row');
  }

  // Re-trigger both axes' label colors: the new driver label turns blue and
  // any previous driver reverts (the style revisions were bumped above).
  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.row_label_layer),
      getColor: row_label_color_triggers(viz_state),
    },
  });
  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.col_label_layer),
      getColor: col_label_color_triggers(viz_state),
    },
  });

  // Reordering (in particular a column reorder, which can change which
  // column is leftmost/rightmost) can change which row labels fit their
  // segment, and where the row dendrogram's leaves sit.
  refresh_row_label_visibility(layers_mat, viz_state);
  refresh_composition_dendro(layers_mat, viz_state);
  // Rebuild the bold focus overlay so it lands at the reordered position
  // (it snaps there while the base label animates in underneath).
  refresh_row_label_focus_layer(layers_mat, viz_state);

  deck_mat.setProps({
    layers: get_mat_layers_list(layers_mat),
  });
};

const apply_row_label_single_click = (label, viz_state) => {
  viz_state.click.type = 'row_label';
  const { name, index: rowMatrixIndex } = label;
  // Include full entity info (entity type + attribute)
  viz_state.click.value = {
    name,
    index: rowMatrixIndex,
    entity: viz_state.row_entity.entity,
    attr: viz_state.row_entity.attr,
    row_entity: viz_state.row_entity.entity,
  };

  if (viz_state.model?.set) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
    emitMatrixSliceRequest(viz_state.model, 'row', {
      index: rowMatrixIndex,
    });
  }

  // Sync selected row to Python model
  sync_selected_rows(viz_state, [name]);
  // Also sync to selected_genes for backwards compatibility
  sync_selected_genes(viz_state, [name]);

  if (typeof viz_state.custom_callbacks.row === 'function') {
    viz_state.custom_callbacks.row(name);
  }
};

const apply_col_label_single_click = (label, viz_state) => {
  viz_state.click.type = 'col_label';
  const { name, index: colMatrixIndex } = label;
  viz_state.click.value = {
    name,
    index: colMatrixIndex,
    entity: viz_state.col_entity.entity,
    attr: viz_state.col_entity.attr,
    col_entity: viz_state.col_entity.entity,
  };

  if (viz_state.model?.set) {
    viz_state.model.set('click_info', null);
    viz_state.model.set('click_info', viz_state.click);
    viz_state.model.save_changes();
    emitMatrixSliceRequest(viz_state.model, 'col', {
      index: colMatrixIndex,
    });
  }

  // Sync selected column to Python model
  sync_selected_cols(viz_state, [name]);

  sync_selected_genes(
    viz_state,
    top_gene_names_for_column(viz_state, colMatrixIndex)
  );

  if (typeof viz_state.custom_callbacks.col === 'function') {
    viz_state.custom_callbacks.col(name);
  }
};

const queue_label_single_click = (viz_state, axis, label, callback) => {
  ensure_label_click_tracking(viz_state);
  viz_state.labels.pending_click[axis] = label;
  viz_state.labels.click_timeouts[axis] = setTimeout(() => {
    const pending = viz_state.labels.pending_click[axis];
    clear_pending_label_click(viz_state, axis);

    if (pending) {
      callback(pending);
    }
  }, DOUBLE_CLICK_DELAY);
};

const handle_label_click = (
  event,
  deck_mat,
  layers_mat,
  viz_state,
  axis,
  single_click_callback
) => {
  if (!event?.object) return;

  const label = {
    name: event.object.name,
    index: event.object.index,
  };

  ensure_label_click_tracking(viz_state);
  const pending = viz_state.labels.pending_click[axis];

  if (!viz_state.labels.click_timeouts[axis]) {
    queue_label_single_click(viz_state, axis, label, single_click_callback);
    return;
  }

  clear_pending_label_click(viz_state, axis);

  if (pending?.index === label.index) {
    // A column double-click is a "focus on this column" gesture: alongside
    // reordering the rows by it, run the single-click sync so its top genes
    // reach a linked Enrich widget (with the column named as the source).
    // Row double-clicks skip this — the row_label click would recenter
    // linked spatial views, which is unwanted for a pure reorder.
    if (axis === 'col') {
      single_click_callback(label);
    }
    custom_label_reorder(
      deck_mat,
      layers_mat,
      viz_state,
      axis,
      label.name,
      label.index
    );
    return;
  }

  if (pending) {
    single_click_callback(pending);
  }
  queue_label_single_click(viz_state, axis, label, single_click_callback);
};

const row_label_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {
  if (!event?.object) return;

  const visibility = viz_state.labels.row_visibility;
  if (visibility && visibility[event.object.index] === false) return;

  handle_label_click(event, deck_mat, layers_mat, viz_state, 'row', (label) =>
    apply_row_label_single_click(label, viz_state)
  );
};

const col_label_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {
  handle_label_click(event, deck_mat, layers_mat, viz_state, 'col', (label) =>
    apply_col_label_single_click(label, viz_state)
  );
};

export const set_row_label_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  // Stashed so the bold focus overlay (rebuilt at many sites without access
  // to deck_mat/layers_mat) can forward its clicks to the same handler — the
  // base label underneath it is drawn transparent and therefore unpickable.
  viz_state.labels._row_label_click_handler = (event) =>
    row_label_layer_onclick(event, deck_mat, layers_mat, viz_state);
  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    onClick: viz_state.labels._row_label_click_handler,
  });
};

export const set_col_label_layer_onclick = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    onClick: (event) =>
      col_label_layer_onclick(event, deck_mat, layers_mat, viz_state),
  });
};

/**
 * Composition-only: hovering a row label highlights that population across
 * every bar, after the same short dwell delay as hovering a bar segment
 * directly (`set_composition_layer_onhover`) — the two are equivalent ways
 * to reach the same cross-bar highlight, so they share its delay/apply/clear
 * functions for a consistent feel. No-op outside composition mode (plain
 * Clustergram row labels aren't part of this interaction).
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const set_row_label_layer_onhover = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  const on_hover = (info) => {
    // A label is now actively hovered, so the dendrogram can't be — clear its
    // highlight proactively (in any viz_mode) rather than relying solely on
    // the dendro layer's own onHover(null) to fire for this transition.
    if (info?.object) clear_dendro_hover(deck_mat, layers_mat, viz_state);

    // Note: hovering deliberately does NOT touch the gene info panel — the
    // tooltip carries transient info, the panel only reflects the current
    // selection (see make_gene_info_box).

    if (viz_state.mat.viz_mode !== 'composition') return;

    const row = info?.object ? info.object.index : null;

    if (row === null || row === viz_state.mat.comp_hover_row) {
      if (row === null)
        clear_composition_hover(deck_mat, layers_mat, viz_state);
      return;
    }

    clearTimeout(viz_state.mat._comp_hover_timer);
    viz_state.mat._comp_hover_timer = setTimeout(
      () => apply_composition_hover_row(deck_mat, layers_mat, viz_state, row),
      HOVER_HIGHLIGHT_DELAY_MS
    );
  };

  viz_state.labels._row_label_hover_handler = on_hover;
  layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
    onHover: on_hover,
  });
};

/**
 * Composition-only: hovering a column (dataset) label highlights that bar
 * (dims every other bar) after the same short dwell delay used everywhere
 * else in composition's hover-highlight family. No-op outside composition
 * mode.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const set_col_label_layer_onhover = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  const on_hover = (info) => {
    // A label is now actively hovered, so the dendrogram can't be — clear its
    // highlight proactively (in any viz_mode) rather than relying solely on
    // the dendro layer's own onHover(null) to fire for this transition.
    if (info?.object) clear_dendro_hover(deck_mat, layers_mat, viz_state);

    if (viz_state.mat.viz_mode !== 'composition') return;

    const col = info?.object ? info.object.index : null;

    if (col === null || col === viz_state.mat.comp_hover_col) {
      if (col === null)
        clear_composition_hover(deck_mat, layers_mat, viz_state);
      return;
    }

    clearTimeout(viz_state.mat._comp_hover_col_timer);
    viz_state.mat._comp_hover_col_timer = setTimeout(
      () => apply_composition_hover_col(deck_mat, layers_mat, viz_state, col),
      HOVER_HIGHLIGHT_DELAY_MS
    );
  };

  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    onHover: on_hover,
  });
};
