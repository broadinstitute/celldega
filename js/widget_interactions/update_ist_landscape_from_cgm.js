import * as d3 from 'd3'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { update_cat, update_selected_cats } from '../global_variables/cat'
import { update_selected_genes } from '../global_variables/selected_genes'
import { update_cell_exp_array } from '../global_variables/cell_exp_array'
import { update_cell_layer_id } from '../deck-gl/cell_layer'
import { update_path_layer_id } from '../deck-gl/path_layer'
import { update_trx_layer_id } from '../deck-gl/trx_layer'
import { get_layers_list } from '../deck-gl/layers_ist'
import { update_gene_text_box } from '../ui/gene_search.js'

export const update_ist_landscape_from_cgm = async (deck_ist, layers_obj, viz_state) => {

    const click_info = viz_state.model.get('update_trigger')

    let inst_gene
    let new_cat

    // // check if click_info has both keys: type and value
    // if (!('click_type' in click_info) || !('click_value' in click_info)) {
    //     console.log('new mat!')

    // console.log('click_info', click_info)

    // add try catch block
    try {

        if (click_info.type === 'row_label') {

            inst_gene = click_info.value.name

            const new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene

            if (viz_state.umap.state === false) {
                toggle_image_layers_and_ctrls(layers_obj, viz_state, viz_state.cats.cat === inst_gene)
            }

            update_cat(viz_state.cats, new_cat)
            update_selected_genes(viz_state.genes, [inst_gene])
            update_selected_cats(viz_state.cats, [])
            await update_cell_exp_array(viz_state.cats, viz_state.genes, viz_state.global_base_url, inst_gene)

            update_cell_layer_id(layers_obj, new_cat)
            update_path_layer_id(layers_obj, new_cat)
            update_trx_layer_id(viz_state.genes, layers_obj)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

            const reset_gene = false

            viz_state.genes.svg_bar_gene.selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', reset_gene ? 1.0 : 0.25)

            if (!reset_gene) {
                const selectedBar = viz_state.genes.svg_bar_gene.selectAll("g")
                    .filter(function() {
                        return d3.select(this).select("text").text() === inst_gene
                    })
                    .attr('opacity', 1.0)

                if (!selectedBar.empty()) {
                    const barPosition = selectedBar.node().getBoundingClientRect().top
                    const containerPosition = viz_state.containers.bar_gene.getBoundingClientRect().top
                    const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_gene.scrollTop

                    viz_state.containers.bar_gene.scrollTo({
                        top: scrollPosition,
                        behavior: 'smooth'
                    })
                }
            }

            viz_state.genes.gene_search_input.value = (viz_state.genes.gene_search_input.value !== inst_gene) ? inst_gene : ''

            update_gene_text_box(viz_state.genes, inst_gene)

        }
        else if (click_info.type === 'col_label') {

            inst_gene = 'cluster'
            new_cat = click_info.value.name

            // console.log('new_cat', new_cat)

            update_cat(viz_state.cats, 'cluster')
            update_selected_cats(viz_state.cats, [new_cat])
            update_selected_genes(viz_state.genes, [])

            if (viz_state.umap.state === false) {
                toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)
            }

            const inst_cat_name = viz_state.cats.selected_cats.join('-')

            update_cell_layer_id(layers_obj, inst_cat_name)
            update_path_layer_id(layers_obj, inst_cat_name)
            update_trx_layer_id(viz_state.genes, layers_obj)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

            viz_state.cats.svg_bar_cluster.selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', viz_state.cats.reset_cat ? 1.0 : 0.25)

            const inst_cat = new_cat

            if (!viz_state.cats.reset_cat) {
                const selectedBar = viz_state.cats.svg_bar_cluster.selectAll("g")
                    .filter(function() {
                        return d3.select(this).select("text").text() === inst_cat
                    })
                    .attr('opacity', 1.0)

                if (!selectedBar.empty()) {
                    const barPosition = selectedBar.node().getBoundingClientRect().top
                    const containerPosition = viz_state.containers.bar_cluster.getBoundingClientRect().top
                    const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_cluster.scrollTop

                    viz_state.containers.bar_cluster.scrollTo({
                        top: scrollPosition,
                        behavior: 'smooth'
                    })
                }
            }

        }

        else if (click_info.type === 'col_dendro') {

            inst_gene = 'cluster'

            inst_gene = 'cluster'
            const new_cats = click_info.value.selected_names

            update_cat(viz_state.cats, 'cluster')
            update_selected_cats(viz_state.cats, new_cats)
            update_selected_genes(viz_state.genes, [])

            if (viz_state.umap.state === false) {
                toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)
            }

            const inst_cat_name = viz_state.cats.selected_cats.join('-')

            update_cell_layer_id(layers_obj, inst_cat_name)
            update_path_layer_id(layers_obj, inst_cat_name)
            update_trx_layer_id(viz_state.genes, layers_obj)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

            viz_state.cats.svg_bar_cluster.selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', viz_state.cats.reset_cat ? 1.0 : 0.25)

            const inst_cat = new_cats

            if (!viz_state.cats.reset_cat) {
                const selectedBar = viz_state.cats.svg_bar_cluster.selectAll("g")
                    .filter(function() {
                        return d3.select(this).select("text").text() === inst_cat
                    })
                    .attr('opacity', 1.0)

                if (!selectedBar.empty()) {
                    const barPosition = selectedBar.node().getBoundingClientRect().top
                    const containerPosition = viz_state.containers.bar_cluster.getBoundingClientRect().top
                    const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_cluster.scrollTop

                    viz_state.containers.bar_cluster.scrollTo({
                        top: scrollPosition,
                        behavior: 'smooth'
                    })
                }
            }

            update_cat(viz_state.cats, inst_gene)
            update_selected_cats(viz_state.cats, click_info.click_value)

        }
    } catch (error) {
        console.error(error)
    }


}