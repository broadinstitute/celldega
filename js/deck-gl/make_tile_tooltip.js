import * as d3 from 'd3'

export const make_tile_tooltip = (info, cats) => {

    let inst_name

    if (info.index === -1 || !info.layer) return null;

    inst_name = cats.tile_cats_array[info.index]

    d3.selectAll('.deck-tooltip')
      .style('margin-top', '75px')
    return {
        html: `<div>${inst_name}</div?`,
    };

}