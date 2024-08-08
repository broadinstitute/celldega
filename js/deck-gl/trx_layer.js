import * as d3 from 'd3'
import { ScatterplotLayer } from 'deck.gl'
import { trx_data, set_trx_data } from '../vector_tile/transcripts/trx_data'
import { color_dict_gene } from '../global_variables/color_dict_gene'
import { trx_names_array } from '../global_variables/trx_names_array'
import { selected_genes, update_selected_genes } from '../global_variables/selected_genes'
import { new_update_cell_layer_id } from './cell_layer'
import { gene_search_input } from '../ui/gene_search_input'
import { cat, update_cat, update_selected_cats } from '../global_variables/cat'
import { update_cell_exp_array } from '../global_variables/cell_exp_array'
import { global_base_url } from '../global_variables/global_base_url'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { get_layers_list } from './layers_ist'
import { new_update_path_layer_id } from './path_layer'
import { svg_bar_gene, svg_bar_cluster } from '../ui/bar_plot'
import { bar_container_gene } from '../ui/bar_plot'
import { update_gene_text_box } from '../ui/gene_search'
import { close_up } from '../global_variables/close_up'

const trx_layer_callback = async (info, d, deck_ist, layers_obj) => {

    const inst_gene = trx_names_array[info.index]

    if (!inst_gene) {
        console.error("Invalid gene name at index:", info.index)
        return
    }

    const reset_gene = inst_gene === cat

    const new_cat = reset_gene ? 'cluster' : inst_gene

    toggle_image_layers_and_ctrls(cat === inst_gene)

    update_cat(new_cat)
    update_selected_genes([inst_gene])
    update_selected_cats([])

    await update_cell_exp_array(global_base_url, inst_gene)

    new_update_cell_layer_id(layers_obj, new_cat)

    new_update_path_layer_id(layers_obj, new_cat)

    new_update_trx_layer_id(layers_obj)

    const layers_list = get_layers_list(layers_obj, close_up)
    deck_ist.setProps({layers: layers_list})

    svg_bar_gene.selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', reset_gene ? 1.0 : 0.25)

    if (!reset_gene) {
        const selectedBar = svg_bar_gene.selectAll("g")
            .filter(function() {
                const textElement = d3.select(this).select("text").node()
                return textElement && textElement.textContent === inst_gene
            })
            .attr('opacity', 1.0)

        if (!selectedBar.empty()) {
            const barPosition = selectedBar.node().getBoundingClientRect().top
            const containerPosition = bar_container_gene.getBoundingClientRect().top
            const scrollPosition = barPosition - containerPosition + bar_container_gene.scrollTop

            svg_bar_gene
                .attr('opacity', 1.0)

            bar_container_gene.scrollTo({
                top: scrollPosition,
                behavior: 'smooth'
            })
        }
    } else {
        bar_container_gene.scrollTo({
            top: 0,
            behavior: 'smooth'
        })
    }

    // reset cluster bar plot
    svg_bar_cluster
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 1.0)


    gene_search_input.value = (gene_search_input.value !== inst_gene) ? inst_gene : ''

    // update_gene_text_box(inst_gene)
    update_gene_text_box(reset_gene ? '' : inst_gene)

}

export let trx_layer

export const ini_trx_layer = () => {
    trx_layer = new ScatterplotLayer({
        id: 'trx-layer',
        data: trx_data,
        pickable: true,
        getColor: (i, d) => {
            const inst_gene = trx_names_array[d.index]
            const inst_color = color_dict_gene[inst_gene]
            const inst_opacity = selected_genes.length === 0 || selected_genes.includes(inst_gene) ? 255 : 5

            return [...inst_color, inst_opacity]
        },
    })

    return trx_layer
}

export const set_trx_layer_onclick = (deck_ist, layers_obj) => {
    layers_obj.trx_layer = layers_obj.trx_layer.clone({
        onClick: (event, d) => trx_layer_callback(event, d, deck_ist, layers_obj)
    })
}

export const update_trx_layer = async ( base_url, tiles_in_view ) => {

    await set_trx_data(base_url, tiles_in_view)

    trx_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...trx_layer.props,
        data: trx_data,
    })

}

export const update_trx_layer_data = async (base_url, tiles_in_view, layers_obj) => {
    await set_trx_data(base_url, tiles_in_view)

    console.log(layers_obj)

    layers_obj.trx_layer = layers_obj.trx_layer.clone({
        data: trx_data,
    })
}

export const toggle_trx_layer_visibility = (visible) => {
    trx_layer = trx_layer.clone({
        visible: visible,
    })
}

export const update_trx_layer_radius = (radius) => {
    trx_layer = trx_layer.clone({
        getRadius: radius,
    })
}

export const new_update_trx_layer_id = (layers_obj) => {
    layers_obj.trx_layer = layers_obj.trx_layer.clone({
        id: 'trx-layer-' + selected_genes.join('-'),
    })
}