import * as d3 from 'd3';
import { ScatterplotLayer } from 'deck.gl';

import { comp_geom_for } from '../../matrix/composition_data';

import { comp_vs, comp_fs } from './composition_shaders';

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
  ];

  return new CompositionLayer({
    id: 'mat-layer',
    data: viz_state.mat.mat_data,
    getPosition: (d) => comp_geom_for(viz_state, d).position,
    getSize: (d) => comp_geom_for(viz_state, d).half,
    getFillColor: (d) =>
      viz_state.mat.comp_colors[d.row] || [128, 128, 128, 255],
    pickable: true,
    antialiasing: false,
    updateTriggers: {
      getPosition: trig,
      getSize: trig,
      getFillColor: [viz_state.mat.viz_mode],
    },
    transitions,
  });
};
