import * as d3 from 'd3';
import { ScatterplotLayer } from 'deck.gl';

import { comp_geom_for } from '../../matrix/composition_data';

import { comp_vs, comp_fs } from './composition_shaders';
import { get_mat_layers_list, mat_reorder_triggers } from './matrix_layers';

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
const FILL_COLOR_TRANSITION_MS = 200;

// Hover must dwell this long before the cross-bar highlight kicks in, so a
// quick mouse pass-over doesn't flash; leaving a segment clears instantly.
const HOVER_HIGHLIGHT_DELAY_MS = 250;

export const ini_composition_layer = (viz_state) => {
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
  ];

  return new CompositionLayer({
    id: 'mat-layer',
    data: viz_state.mat.mat_data,
    getPosition: (d) => comp_geom_for(viz_state, d).position,
    getSize: (d) => comp_geom_for(viz_state, d).half,
    getFillColor: (d) => {
      const base = viz_state.mat.comp_colors[d.row] || [128, 128, 128, 255];
      const hover_row = viz_state.mat.comp_hover_row;
      if (hover_row == null || hover_row === d.row) return base;
      return [
        base[0],
        base[1],
        base[2],
        Math.round((base[3] ?? 255) * HOVER_DIM_ALPHA),
      ];
    },
    pickable: true,
    antialiasing: false,
    updateTriggers: {
      getPosition: trig,
      getSize: trig,
      getFillColor: [viz_state.mat.viz_mode, viz_state.mat.comp_hover_row],
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
    updateTriggers: mat_reorder_triggers(viz_state),
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
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
export const set_composition_layer_onhover = (deck_mat, layers_mat, viz_state) => {
  const apply_hover_row = (row) => {
    if (viz_state.mat.comp_hover_row === row) return;
    viz_state.mat.comp_hover_row = row;
    layers_mat.mat_layer = layers_mat.mat_layer.clone({
      updateTriggers: {
        getFillColor: [viz_state.mat.viz_mode, viz_state.mat.comp_hover_row],
      },
    });
    deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
  };

  const on_hover = (info) => {
    clearTimeout(viz_state.mat._comp_hover_timer);

    const row = info?.object ? info.object.row : null;

    if (row === null || row === viz_state.mat.comp_hover_row) {
      if (row === null) apply_hover_row(null);
      return;
    }

    viz_state.mat._comp_hover_timer = setTimeout(
      () => apply_hover_row(row),
      HOVER_HIGHLIGHT_DELAY_MS
    );
  };

  layers_mat.mat_layer = layers_mat.mat_layer.clone({ onHover: on_hover });
};
