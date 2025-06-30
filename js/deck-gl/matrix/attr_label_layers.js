import * as d3 from 'd3';
import { TextLayer } from 'deck.gl';

export const ini_row_attr_label_layer = (viz_state) => {
  const transitions = {
    getPosition: { duration: viz_state.animate.duration, easing: d3.easeCubic },
  };

  const layer = new TextLayer({
    id: 'row-attr-label-layer',
    data: viz_state.cats.row_attr_label_data,
    getPosition: (d) => [
      viz_state.viz.row_cat_offset * (d.index + 0.5) +
        20 +
        viz_state.viz.cat_shift_row,
      10,
    ],
    getText: (d) => d.name,
    getSize: 12,
    getColor: [0, 0, 0],
    getTextAnchor: 'start',
    getAlignmentBaseline: 'bottom',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 1,
    pickable: false,
    transitions,
  });

  return layer;
};

export const ini_col_attr_label_layer = (viz_state) => {
  const transitions = {
    getPosition: { duration: viz_state.animate.duration, easing: d3.easeCubic },
  };

  const layer = new TextLayer({
    id: 'col-attr-label-layer',
    data: viz_state.cats.col_attr_label_data,
    getPosition: (d) => [
      10,
      viz_state.viz.col_cat_offset * (d.index + 0.5) +
        viz_state.viz.cat_shift_col,
    ],
    getText: (d) => d.name,
    getSize: 12,
    getColor: [0, 0, 0],
    getTextAnchor: 'start',
    getAlignmentBaseline: 'middle',
    fontFamily: 'Arial',
    sizeUnits: 'pixels',
    sizeScale: 1,
    pickable: false,
    transitions,
  });

  return layer;
};
