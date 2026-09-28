import * as d3 from 'd3';
import { ScatterplotLayer } from 'deck.gl';

import { comp_geom_for } from '../../matrix/composition_data';
import {
  crop_fade_alpha_factor,
  crop_fade_signature,
  crop_filter_signature,
  filter_matrix_data,
} from '../../matrix/crop_filter';

import { comp_vs, comp_fs } from './composition_shaders';
import {
  clear_dendro_hover,
  dendro_highlight_alpha_factor,
} from './dendro_layers';
import {
  get_layer_update_triggers,
  get_mat_layers_list,
  get_matrix_body_layer_id,
  mat_reorder_triggers,
} from './matrix_layers';

/**
 * A ScatterplotLayer variant that renders the Clustergram body as column-wise
 * stacked bars. It adds a per-instance `instanceSize` attribute (world-space
 * [halfWidth, halfHeight]) so each segment can have an independent height.
 */
export class CompositionLayer extends ScatterplotLayer {
  getShaders() {
    const shaders = super.getShaders();
    shaders.vs = comp_vs;
    shaders.fs = comp_fs;
    return shaders;
  }

  initializeState(params) {
    super.initializeState(params);
    this.getAttributeManager().addInstanced({
      instanceSize: {
        size: 2,
        accessor: 'getSize',
        defaultValue: [0, 0],
        // Without this, deck.gl's AttributeTransitionManager skips this
        // attribute entirely (Attribute.supportsTransition() gates on it),
        // so the `getSize` entry in `transitions` below is silently a
        // no-op and segment height snaps to its final value instantly.
        transition: true,
      },
    });
  }
}

CompositionLayer.layerName = 'CompositionLayer';
CompositionLayer.defaultProps = {
  ...ScatterplotLayer.defaultProps,
  getSize: { type: 'accessor', value: [0, 0] },
};

// Non-matching segments are dimmed to this fraction of their normal alpha
// while another row is hover-highlighted.
const HOVER_DIM_ALPHA = 0.25;

// Fill color has no reason to animate slowly here: population colors are
// static for the life of the widget, so the only thing that ever changes
// `getFillColor` is the hover highlight below, which should feel immediate.
const FILL_COLOR_TRANSITION_MS = 120;

// Hover must dwell this long before the cross-bar highlight kicks in, so a
// quick mouse pass-over doesn't flash; leaving a segment clears instantly.
// Exported so row/col label hover (`label_layers.js`) uses the identical
// delay for a consistent feel across every hover-highlight in composition mode.
export const HOVER_HIGHLIGHT_DELAY_MS = 250;

const hover_trigger_key = (viz_state) => [
  viz_state.mat.viz_mode,
  viz_state.mat.comp_hover_row,
  viz_state.mat.comp_hover_col,
  crop_filter_signature(viz_state),
  crop_fade_signature(viz_state),
  viz_state.dendro?._highlight_rev || 0,
];

export const ini_composition_layer = (viz_state) => {
  const crop_sig = crop_filter_signature(viz_state);
  const transitions = {
    getPosition: { duration: viz_state.animate.duration, easing: d3.easeCubic },
    getSize: { duration: viz_state.animate.duration, easing: d3.easeCubic },
    getFillColor: {
      duration: FILL_COLOR_TRANSITION_MS,
      easing: d3.easeCubic,
    },
  };

  const trig = [
    viz_state.order.current.row,
    viz_state.order.current.col,
    viz_state.mat.viz_mode,
    viz_state.mat.composition_normalized,
    crop_sig,
  ];

  return new CompositionLayer({
    id: get_matrix_body_layer_id(viz_state),
    data: filter_matrix_data(viz_state),
    getPosition: (d) => comp_geom_for(viz_state, d).position,
    getSize: (d) => comp_geom_for(viz_state, d).half,
    getFillColor: (d) => {
      const base = viz_state.mat.comp_colors[d.row] || [128, 128, 128, 255];
      const hover_row = viz_state.mat.comp_hover_row;
      const hover_col = viz_state.mat.comp_hover_col;
      const row_factor =
        hover_row == null || hover_row === d.row ? 1 : HOVER_DIM_ALPHA;
      const col_factor =
        hover_col == null || hover_col === d.col ? 1 : HOVER_DIM_ALPHA;
      const dendro_factor = dendro_highlight_alpha_factor(
        viz_state,
        d.row,
        d.col
      );
      const crop_factor = crop_fade_alpha_factor(viz_state, d.row, d.col);
      const alpha_factor =
        row_factor * col_factor * dendro_factor * crop_factor;
      if (alpha_factor === 1) return base;
      return [
        base[0],
        base[1],
        base[2],
        Math.round((base[3] ?? 255) * alpha_factor),
      ];
    },
    pickable: true,
    antialiasing: false,
    updateTriggers: {
      getPosition: trig,
      getSize: trig,
      getFillColor: hover_trigger_key(viz_state),
    },
    transitions,
  });
};

/**
 * Toggle proportion (column-normalized to 100%) vs. raw-count segment
 * heights. Shared by the control-panel PROPORTION|COUNTS button and the
 * Python `composition_normalized` trait listener.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {boolean} value - New `composition_normalized` value.
 */
export const set_composition_normalized = (
  deck_mat,
  layers_mat,
  viz_state,
  value
) => {
  viz_state.mat.composition_normalized = value;
  viz_state.mat._comp_cache = null;

  if (viz_state.model?.set) {
    viz_state.model.set('composition_normalized', value);
    viz_state.model.save_changes();
  }

  if (viz_state.mat.viz_mode !== 'composition') return;

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    data: filter_matrix_data(viz_state),
    updateTriggers: mat_reorder_triggers(viz_state),
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

/**
 * Set (or clear, with `row = null`) composition's cross-bar hover-highlighted
 * population, re-rendering the body layer so `getFillColor` picks it up.
 * Exported (rather than a private closure) so a failsafe "pointer left the
 * whole widget" handler can force-clear it directly — see
 * `clear_composition_hover`.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {number|null} row - Raw row index to highlight, or null to clear.
 */
export const apply_composition_hover_row = (
  deck_mat,
  layers_mat,
  viz_state,
  row
) => {
  if (viz_state.mat.comp_hover_row === row) return;
  viz_state.mat.comp_hover_row = row;
  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.mat_layer),
      getFillColor: hover_trigger_key(viz_state),
    },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

/**
 * Set (or clear, with `col = null`) composition's hover-highlighted group
 * (dataset) — dims every other bar's segments, the column analogue of
 * `apply_composition_hover_row`. Driven by hovering a column label (see
 * `label_layers.js`); there's no bar-segment equivalent since a segment
 * hover already identifies a row, and column identity is visually obvious
 * from which bar it's in.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {number|null} col - Raw column index to highlight, or null to clear.
 */
export const apply_composition_hover_col = (
  deck_mat,
  layers_mat,
  viz_state,
  col
) => {
  if (viz_state.mat.comp_hover_col === col) return;
  viz_state.mat.comp_hover_col = col;
  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: {
      ...get_layer_update_triggers(layers_mat.mat_layer),
      getFillColor: hover_trigger_key(viz_state),
    },
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

/**
 * Force-clear composition's cross-bar hover highlight (both row and column),
 * cancelling any pending delayed-highlight timers first. Without cancelling
 * the timers, a hover-highlight already armed (but not yet applied) when the
 * pointer leaves would otherwise still fire a few hundred ms later —
 * applying a highlight for a segment/label the pointer isn't over anymore —
 * which is exactly the "leaves the highlight in a previous state" symptom
 * this guards against. Safe to call unconditionally (e.g. from a
 * whole-widget pointer-leave failsafe) even when nothing is highlighted.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const clear_composition_hover = (deck_mat, layers_mat, viz_state) => {
  clearTimeout(viz_state.mat._comp_hover_timer);
  clearTimeout(viz_state.mat._comp_hover_col_timer);
  apply_composition_hover_row(deck_mat, layers_mat, viz_state, null);
  apply_composition_hover_col(deck_mat, layers_mat, viz_state, null);
};

/**
 * Wire up composition's cross-bar hover highlight: hovering a segment
 * dims every other population's segments (across all bars) after a short
 * dwell delay, so the hovered population's share is easy to compare bar to
 * bar; moving off a segment clears the highlight immediately.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 */
export const set_composition_layer_onhover = (
  deck_mat,
  layers_mat,
  viz_state
) => {
  const on_hover = (info) => {
    const row = info?.object ? info.object.row : null;

    if (row === null || row === viz_state.mat.comp_hover_row) {
      if (row === null)
        clear_composition_hover(deck_mat, layers_mat, viz_state);
      return;
    }

    // A bar segment is now actively hovered, so the dendrogram (to the
    // right) can't be — clear its highlight proactively rather than relying
    // solely on the dendro layer's own onHover(null) to fire for this
    // transition.
    clear_dendro_hover(deck_mat, layers_mat, viz_state);

    clearTimeout(viz_state.mat._comp_hover_timer);
    viz_state.mat._comp_hover_timer = setTimeout(
      () => apply_composition_hover_row(deck_mat, layers_mat, viz_state, row),
      HOVER_HIGHLIGHT_DELAY_MS
    );
  };

  layers_mat.mat_layer = layers_mat.mat_layer.clone({ onHover: on_hover });
};
