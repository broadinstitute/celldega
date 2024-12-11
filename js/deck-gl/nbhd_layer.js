import { GeoJsonLayer } from "deck.gl"
import { hexToRgb } from '../utils/hexToRgb.js'

export const ini_nbhd_layer = (viz_state) => {

    console.log('ini nbhd layer')
    console.log(viz_state.nbhd.feature_collection)

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
    // console.log(event)
}

export const set_nbhd_layer_onclick = (deck_ist, layers_obj, viz_state) => {
    layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
        onClick: (info, event) => nbhd_layer_onclick(info, event, deck_ist, layers_obj, viz_state)
    })
}