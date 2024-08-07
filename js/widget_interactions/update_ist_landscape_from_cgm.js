import * as d3 from 'd3'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { cat, update_cat, update_selected_cats, selected_cats, reset_cat } from '../global_variables/cat'
import { update_selected_genes } from '../global_variables/selected_genes'
import { update_cell_exp_array } from '../global_variables/cell_exp_array'
import { update_cell_layer_id } from '../deck-gl/cell_layer'
import { update_path_layer_id } from '../deck-gl/path_layer'
import { update_trx_layer_filter } from '../deck-gl/trx_layer'
import { gene_search_input } from '../ui/gene_search_input'
import { global_base_url } from '../global_variables/global_base_url'
import { svg_bar_gene, svg_bar_cluster } from '../ui/bar_plot'
import { bar_container_gene, bar_container_cluster } from '../ui/bar_plot'
import { layers_ist, update_layers_ist } from '../deck-gl/layers_ist'
import { model } from '../global_variables/model.js'
import { update_gene_text_box } from '../ui/gene_search.js'

export const update_ist_landscape_from_cgm = async (deck_ist) => {

    const click_info = model.get('update_trigger')

    let inst_gene
    let new_cat

    if (click_info.click_type === 'row-label') {

        inst_gene = click_info.click_value

        const new_cat = inst_gene === cat ? 'cluster' : inst_gene

        toggle_image_layers_and_ctrls(cat === inst_gene)

        update_cat(new_cat)
        update_selected_genes([inst_gene])
        update_selected_cats([])
        await update_cell_exp_array(global_base_url, inst_gene)
        update_cell_layer_id(new_cat)
        update_path_layer_id(new_cat)
        update_trx_layer_filter()
        update_layers_ist()

        // turning off update for now
        // deck_ist.setProps({layers: layers_ist})

        const reset_gene = false

        svg_bar_gene.selectAll("g")
            .attr('font-weight', 'normal')
            .attr('opacity', reset_gene ? 1.0 : 0.25)

        if (!reset_gene) {
            const selectedBar = svg_bar_gene.selectAll("g")
                .filter(function() {
                    return d3.select(this).select("text").text() === inst_gene
                })
                .attr('opacity', 1.0)

            if (!selectedBar.empty()) {
                const barPosition = selectedBar.node().getBoundingClientRect().top
                const containerPosition = bar_container_gene.getBoundingClientRect().top
                const scrollPosition = barPosition - containerPosition + bar_container_gene.scrollTop

                bar_container_gene.scrollTo({
                    top: scrollPosition,
                    behavior: 'smooth'
                })
            }
        }

        gene_search_input.value = (gene_search_input.value !== inst_gene) ? inst_gene : ''
        update_gene_text_box(inst_gene)

    } else if (click_info.click_type === 'col-label') {

        inst_gene = 'cluster'
        new_cat = click_info.click_value

        update_cat('cluster')
        update_selected_cats([new_cat])
        update_selected_genes([])
        toggle_image_layers_and_ctrls(!selected_cats.length > 0)

        const inst_cat_name = selected_cats.join('-')
        update_cell_layer_id(inst_cat_name)
        update_path_layer_id(inst_cat_name)
        update_trx_layer_filter()
        update_layers_ist()

        svg_bar_cluster.selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', reset_cat ? 1.0 : 0.25)

        const inst_cat = new_cat

        if (!reset_cat) {
            const selectedBar = svg_bar_cluster.selectAll("g")
                .filter(function() {
                    return d3.select(this).select("text").text() === inst_cat
                })
                .attr('opacity', 1.0)

            if (!selectedBar.empty()) {
                const barPosition = selectedBar.node().getBoundingClientRect().top
                const containerPosition = bar_container_cluster.getBoundingClientRect().top
                const scrollPosition = barPosition - containerPosition + bar_container_cluster.scrollTop

                bar_container_cluster.scrollTo({
                    top: scrollPosition,
                    behavior: 'smooth'
                })
            }
        }

        // turning off update for now
        // deck_ist.setProps({layers: layers_ist})

    } else if (click_info.click_type === 'col-dendro') {

        inst_gene = 'cluster'

        inst_gene = 'cluster'
        const new_cats = click_info.click_value

        update_cat('cluster')
        update_selected_cats(new_cats)
        update_selected_genes([])
        toggle_image_layers_and_ctrls(!selected_cats.length > 0)

        const inst_cat_name = selected_cats.join('-')
        update_cell_layer_id(inst_cat_name)
        update_path_layer_id(inst_cat_name)
        update_trx_layer_filter()
        update_layers_ist()

        svg_bar_cluster.selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', reset_cat ? 1.0 : 0.25)

        // const inst_cat = new_cats

        // if (!reset_cat) {
        //     const selectedBar = svg_bar_cluster.selectAll("g")
        //         .filter(function() {
        //             return d3.select(this).select("text").text() === inst_cat
        //         })
        //         .attr('opacity', 1.0)

        //     if (!selectedBar.empty()) {
        //         const barPosition = selectedBar.node().getBoundingClientRect().top
        //         const containerPosition = bar_container_cluster.getBoundingClientRect().top
        //         const scrollPosition = barPosition - containerPosition + bar_container_cluster.scrollTop

        //         bar_container_cluster.scrollTo({
        //             top: scrollPosition,
        //             behavior: 'smooth'
        //         })
        //     }
        // }

        // turning off update for now
        // deck_ist.setProps({layers: layers_ist})

        // update_cat(selected_gene)
        // update_selected_cats(click_info.click_value)

    } else {
        inst_gene = 'cluster'
        // update_cat(selected_gene)
    }

}