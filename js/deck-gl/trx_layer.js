import { ScatterplotLayer } from 'deck.gl'
import { trx_data, set_trx_data } from '../vector_tile/transcripts/trx_data'
import { color_dict } from '../global_variables/color_dict'
import { trx_names_array } from '../global_variables/trx_names_array'
import { selected_cats, update_selected_cats } from '../global_variables/selected_cats'
import { deck_ist } from './deck_ist'
import { layers } from './layers'

export let trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: trx_data,
    pickable: true,
    getColor: (i, d) => {
        var inst_gene = trx_names_array[d.index]
        var inst_color = color_dict[inst_gene]

        var inst_opacity

        if (selected_cats.length === 0){
            inst_opacity = 255
        } else {
            inst_opacity = 25
        }
        
        return [inst_color[0], inst_color[1], inst_color[2], inst_opacity]
    },
    onClick: info => {
        console.log('trx click')

        let inst_gene = trx_names_array[info.index]
        update_selected_cats([inst_gene])

        update_trx_layer_filter()

        deck_ist.setProps({layers: [trx_layer]})
        
    }
});       

export const update_trx_layer = async ( base_url, tiles_in_view, ) => {

    await set_trx_data(base_url, tiles_in_view)

    trx_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...trx_layer.props,
        data: trx_data,
    });
        
}

export const toggle_trx_layer_visibility = (visible) => {
    trx_layer = trx_layer.clone({
        visible: visible,
    });
}

export const update_trx_layer_radius = (radius) => {
    trx_layer = trx_layer.clone({
        getRadius: radius,
    });
}

export const update_trx_layer_filter = () => {
    trx_layer = trx_layer.clone({
        id: 'something',
    });    
}