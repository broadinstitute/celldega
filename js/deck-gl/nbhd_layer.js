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
        opacity: 0.1
        // getElevation: 0,
        // updateTriggers: {
        //     getFillColor: viz_state.nbhd.update_trigger,
        // },
    })

    return nbhd_layer

}