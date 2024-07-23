import * as d3 from 'd3'
import { set_trx_ini_raidus } from '../global_variables/trx_ini_raidus'
import { set_options } from '../global_variables/fetch_options'
import { set_global_base_url } from '../global_variables/global_base_url'
import { set_landscape_parameters } from '../global_variables/landscape_parameters'
import { set_dimensions } from '../global_variables/image_dimensions'
import { set_initial_view_state } from '../deck-gl/initial_view_state'
import { set_cell_layer } from "../deck-gl/cell_layer"
import { layers_ist, update_layers_ist } from '../deck-gl/layers_ist'
import { make_image_layers } from '../deck-gl/image_layers'
import { update_views } from '../deck-gl/views'
import { deck_ist, set_deck } from '../deck-gl/deck_ist'
import { set_background_layer } from '../deck-gl/background_layer'
import { make_ist_ui_container } from '../ui/ui_containers'
import { model, set_model } from '../global_variables/model'
import { update_trx_layer_radius } from '../deck-gl/trx_layer'
import { image_info, set_image_info, set_image_layer_colors } from '../global_variables/image_info'
import { set_image_layer_sliders } from "../ui/sliders"
import { set_meta_gene } from '../global_variables/meta_gene'
import { set_cluster_metadata } from '../global_variables/meta_cluster'
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



export const landscape_ist = async (
    el,
    ini_model,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    base_url,
    dataset_name='',
    trx_radius=0.25,
) => {

    // move this to landscape_parameters
    const imgage_name_for_dim = 'dapi'
    const tmp_image_info = [
        {
            name: 'dapi',
            button_name: 'DAPI',
            color: [0, 0, 255]
        },
        {
            name: 'cellbound',
            button_name: 'BOUND',
            color: [255, 0, 0]
        }
    ]

    set_image_info(tmp_image_info)
    set_image_layer_sliders(image_info)
    set_image_layer_colors(image_info)


    // Create and append the visualization.
    set_trx_ini_raidus(trx_radius)
    let root = document.createElement("div");
    root.style.height = "800px";

    set_model(ini_model)

    set_global_base_url(base_url)

    set_options(token)
    set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)
    await set_dimensions(base_url, imgage_name_for_dim )
    await set_landscape_parameters(base_url)
    await set_meta_gene(base_url)

    await set_cluster_metadata()

    // update layers
    await make_image_layers(base_url)
    await set_cell_layer(base_url)

    set_background_layer()

    update_trx_layer_radius(trx_radius)

    // update_layers_ist([background_layer, ...image_layers, cell_layer])
    update_layers_ist()

    update_views()

    set_deck(root)

    const update_ist_landscape_from_cgm = async () => {
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

            deck_ist.setProps({layers: layers_ist})


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

            deck_ist.setProps({layers: layers_ist})

        } else if (click_info.click_type === 'col-dendro') {

            inst_gene = 'cluster'

            console.log(click_info.click_value)

            // update_cat(selected_gene)
            // update_selected_cats(click_info.click_value)

        } else {
            inst_gene = 'cluster'
            // update_cat(selected_gene)
        }

    }

    model.on('change:update_trigger', update_ist_landscape_from_cgm)

    const ui_container = make_ist_ui_container(dataset_name)

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root);

    return () => deck_ist.finalize();

}