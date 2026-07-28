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

export const ini_composition_layer = (viz_state) => {
  const transitions = {
    getPosition: { duration: viz_state.animate.duration, easing: d3.easeCubic },
    getSize: { duration: viz_state.animate.duration, easing: d3.easeCubic },
    getFillColor: {
      duration: viz_state.animate.duration,
      easing: d3.easeCubic,
    },
  };

  const trig = [
    viz_state.order.current.row,
    viz_state.order.current.col,
    viz_state.mat.viz_mode,
    viz_state.mat.composition_normalized,
    viz_state.mat.composition_encoding,
  ];

  return new CompositionLayer({
    id: 'mat-layer',
    data: viz_state.mat.mat_data,
    getPosition: (d) => comp_geom_for(viz_state, d).position,
    getSize: (d) => comp_geom_for(viz_state, d).half,
    getFillColor: (d) => {
      const base = viz_state.mat.comp_colors[d.row] || [128, 128, 128, 255];
      if (viz_state.mat.composition_encoding !== 'opacity') return base;
      const { alpha } = comp_geom_for(viz_state, d);
      return [base[0], base[1], base[2], Math.round(255 * (alpha ?? 1))];
    },
    pickable: true,
    antialiasing: false,
    updateTriggers: {
      getPosition: trig,
      getSize: trig,
      getFillColor: [
        viz_state.mat.viz_mode,
        viz_state.mat.composition_encoding,
      ],
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
 * Toggle segment encoding between "height" (share of column -> segment
 * height, full opacity) and "opacity" (equal-height slots, share -> fill
 * alpha). Shared by the control-panel HEIGHT|OPACITY button and the Python
 * `composition_encoding` trait listener.
 *
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @param {string} value - New `composition_encoding` value ("height" | "opacity").
 */
export const set_composition_encoding = (
  deck_mat,
  layers_mat,
  viz_state,
  value
) => {
  viz_state.mat.composition_encoding = value;
  viz_state.mat._comp_cache = null;

  if (viz_state.model?.set) {
    viz_state.model.set('composition_encoding', value);
    viz_state.model.save_changes();
  }

  if (viz_state.mat.viz_mode !== 'composition') return;

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: mat_reorder_triggers(viz_state),
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};
