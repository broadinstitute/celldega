import * as d3 from 'd3'

export const make_tile_tooltip = (info, viz_state) => {

    if (info.index === -1 || !info.layer) return null;

    let inst_cat = viz_state.cats.tile_cats_array[info.index]

    viz_state.tooltip_cat_cell = inst_cat

    d3.selectAll('.deck-tooltip')
      .style('margin-top', '75px')
    return {
        html: `<div>${inst_cat}</div?`,
    };

}