import { GeoJsonLayer } from "deck.gl"
import { hexToRgb } from '../utils/hexToRgb.js'
import { update_selected_cats, update_cat } from '../global_variables/cat'
import { update_selected_genes } from "../global_variables/selected_genes.js"
import { toggle_image_layers_and_ctrls } from "../ui/ui_containers.js"
import { update_gene_text_box } from "../ui/gene_search.js"
import { update_cell_layer_id } from "./cell_layer.js"
import { update_path_layer_id } from "./path_layer.js"
import { update_trx_layer_id } from "./trx_layer.js"
import { get_layers_list } from "./layers_ist.js"
import * as d3 from 'd3'

export const ini_nbhd_layer = (viz_state) => {

    const nbhd_layer = new GeoJsonLayer({
        id: 'nbhd-layer',
        data: viz_state.nbhd.feature_collection,
        pickable: true,
        stroked: false,
        filled: true,
        // extruded: false,
        // getPolygon: d => d.geometry.coordinates,
        // getFillColor: [255, 0, 0, 100],
        getLineWidth: 1,
        // getLineColor: [0, 0, 0, 255],
        getFillColor: (d) => hexToRgb(d.properties.color),
        opacity: 0.5,
        // getElevation: 0,
        // updateTriggers: {
        //     getFillColor: viz_state.nbhd.update_trigger,
        // },

    })

    return nbhd_layer

}

const nbhd_layer_onclick = async (info, event, deck_ist, layers_obj, viz_state) => {
    console.log('clicked on nbhd set after all layers')
    console.log(info.object.properties)

    let inst_cat = info.object.properties.cat

    update_cat(viz_state.cats, 'cluster')
    update_selected_cats(viz_state.cats, [inst_cat])
    update_selected_genes(viz_state.genes, [])

    toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

    const inst_cat_name = viz_state.cats.selected_cats.join('-')

    // reset gene
    viz_state.genes.svg_bar_gene
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 1.0)

    viz_state.cats.svg_bar_cluster.selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', viz_state.cats.reset_cat ? 1.0 : 0.25)

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
    } else {
        viz_state.containers.bar_cluster.scrollTo({
            top: 0,
            behavior: 'smooth'
        })
    }

    update_cell_layer_id(layers_obj, inst_cat_name)
    update_path_layer_id(layers_obj, inst_cat_name)
    update_trx_layer_id(viz_state.genes, layers_obj)

    // update data for nbhd layer

    filter_cat_nbhd_feature_collection(viz_state, inst_cat)
    update_nbhd_layer_data(viz_state, layers_obj)


    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    viz_state.genes.gene_search_input.value = ''
    update_gene_text_box(viz_state.genes, '')


}

export const set_nbhd_layer_onclick = (deck_ist, layers_obj, viz_state) => {
    layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        onClick: (info, event) => nbhd_layer_onclick(info, event, deck_ist, layers_obj, viz_state)
    })
}

export const filter_cat_nbhd_feature_collection = (viz_state, cat) => {

    console.log('selected_cats', viz_state.cats.selected_cats)
    let filt_features

    if (viz_state.cats.selected_cats.length === 0) {
        filt_features = viz_state.nbhd.ini_feature_collection.features
                            // .filter(d => d.properties.cat === cat)
                            .filter(d => d.properties.inv_alpha === viz_state.nbhd.inst_alpha)
    } else {
        filt_features = viz_state.nbhd.ini_feature_collection.features
                            .filter(d => viz_state.cats.selected_cats.includes(d.properties.cat))
                            .filter(d => d.properties.inv_alpha === viz_state.nbhd.inst_alpha)
    }
    viz_state.nbhd.feature_collection = {
        "type": "FeatureCollection",
        "features": filt_features
    }

}

export const update_nbhd_layer_data = (viz_state, layers_obj) => {

    console.log('update_nbhd_layer_data!!')
    layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        data: viz_state.nbhd.feature_collection
    })
}