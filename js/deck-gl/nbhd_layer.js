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

// export function get_nbhd_color(viz_state, featureName, attributeKey) {
//     if (
//         viz_state.meta_nbhd.name.hasOwnProperty(featureName) &&
//         viz_state.meta_nbhd.color.hasOwnProperty(featureName)
//     ) {
//         return viz_state.meta_nbhd.color[featureName];
//     }

//     console.warn(`Feature "${featureName}" missing or missing color.`);
//     return [0, 0, 0, 0]; // transparent fallback
// }

// export function get_nbhd_color(viz_state, featureName) {
//     if (
//         viz_state.meta_nbhd.name.hasOwnProperty(featureName) &&
//         viz_state.meta_nbhd.color.hasOwnProperty(featureName)
//     ) {
//         const hex = viz_state.meta_nbhd.color[featureName];
//         const [r, g, b] = hexToRgb(hex);
//         return [r, g, b, 128]; // semi-transparent
//     }

//     console.warn(`Feature "${featureName}" missing or missing color.`);
//     return [0, 0, 0, 0]; // fully transparent fallback
// }

export function get_nbhd_color(viz_state, featureName, attributeKey) {
  // Get the value for the feature and attribute key
  const val = viz_state.meta_nbhd[attributeKey]?.[featureName];

  if (val === undefined) {
    console.warn(`Value missing for feature "${featureName}" and attribute "${attributeKey}"`);
    return [0, 0, 0, 0]; // transparent fallback
  }

  // Map val (0 to 1) to shade of red (adjust as needed)
  const red = 255;
  const green = Math.floor(230 * (1 - val));
  const blue = Math.floor(230 * (1 - val));
  const alpha = 200;

  return [red, green, blue, alpha];
}

export const get_color_dict_by_color_value = (viz_state) => {
  const colorDict = {};

  viz_state.nbhd.feature_collection.features.forEach((feature) => {
    const featureName = feature.properties.name;

    const colorValue = viz_state.meta_nbhd.color[featureName];

    if (colorValue) {
      colorDict[featureName] = colorValue;
    } else {
      console.warn(`Color missing for feature "${featureName}"`);
      colorDict[featureName] = [0, 0, 0, 0]; // fallback
    }
  });

  return colorDict;
};

export const ini_nbhd_layer = (viz_state, visible) => {

    // console.log(viz_state.nbhd.feature_collection)

    // console.log(viz_state.cat_meta.feature_collection)

    // console.log("/////")

    // const metaFeatures = viz_state.meta_nbhd.feature_collection.features;

    // const metaMap = new Map(
    // metaFeatures.map(f => [f.properties.id, f.properties])
    // );

    // viz_state.nbhd.feature_collection.features.forEach(f => {
    // const id = f.properties.id;
    // const metaProps = metaMap.get(id) ?? {};
    // Object.assign(f.properties, metaProps);
    // });

    // console.log(viz_state.nbhd.feature_collection)

    const layer_attr = viz_state.nbhd_attr // string
    console.log(layer_attr)

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
        getFillColor: (d) => get_nbhd_color(viz_state, d.properties.name, layer_attr),
        opacity: 0.5,
        // getElevation: 0,
        // updateTriggers: {
        //     getFillColor: viz_state.nbhd.update_trigger,
        // },
        visible: visible

    })

    return nbhd_layer

}

const nbhd_layer_onclick = async (info, event, deck_ist, layers_obj, viz_state) => {

    let inst_cat = info.object.properties.cat

    update_cat(viz_state.cats, 'cluster')
    update_selected_cats(viz_state.cats, [inst_cat])
    update_selected_genes(viz_state.genes, [])

    // toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

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
    // update_trx_layer_id(viz_state.genes, layers_obj)

    // update data for nbhd layer

    filter_cat_nbhd_feature_collection(viz_state)
    update_nbhd_layer_data(viz_state, layers_obj)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    // viz_state.genes.gene_search_input.value = ''
    // update_gene_text_box(viz_state.genes, '')

}

export const set_nbhd_layer_onclick = (deck_ist, layers_obj, viz_state) => {
    layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        onClick: (info, event) => nbhd_layer_onclick(info, event, deck_ist, layers_obj, viz_state)
    })
}

export const filter_cat_nbhd_feature_collection = (viz_state) => {

    let filt_features

    if (viz_state.cats.selected_cats.length === 0) {
        filt_features = viz_state.nbhd.ini_feature_collection.features
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

export const toggle_nbhd_layer_visibility = (layers_obj, visible) => {
    layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        visible: visible
    })
}
