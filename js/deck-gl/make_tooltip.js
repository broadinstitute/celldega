import * as d3 from 'd3'

export const make_tooltip = (viz_state, info) => {

    if (info.index === -1 || !info.layer) return null;

    let inst_html = ''
    let inst_name = ''
    let inst_cat = ''

    if (info.layer.id.startsWith('cell-layer') || info.layer.id.startsWith('path-layer')) {
        inst_name = info.layer.id.startsWith('cell-layer') ? viz_state.cats.cell_names_array[info.index] : viz_state.cats.polygon_cell_names[info.index]
        inst_cat = viz_state.cats.dict_cell_cats[inst_name]
        inst_html = `<div>cell: ${inst_name}</div><div>cluster: ${inst_cat}</div>`

        viz_state.tooltip_cat_cell = inst_cat

    } else if (info.layer.id.startsWith('trx-layer')) {
        inst_name = viz_state.genes.trx_names_array[info.index]
        inst_html = `<div>transcript: ${inst_name}</div>`
    } else if (info.layer.id.startsWith('nbhd-layer')) {
        inst_name = viz_state.nbhd.feature_collection.features[info.index].properties.name
        inst_cat = viz_state.nbhd.feature_collection.features[info.index].properties.cat
        inst_html = `<div>neighborhood: ${inst_name}</div><div>cluster: ${inst_cat}</div>`
    }

    // d3.selectAll('.deck-tooltip')
    //   .style('margin-top', '75px')

    // console.log(viz_state.root)

    // select the parent element of .deck-tooltip within viz_state.root
    const tooltipContainer = viz_state.root.querySelector('.deck-tooltip');
    tooltipContainer.style.marginTop = '50px'
    const tooltipParent = tooltipContainer.parentElement.parentElement;
    tooltipParent.style.position = 'unset'

    return {
        html: inst_html,
    }

}