import { ScatterplotLayer } from 'deck.gl'
import { trx_data, set_trx_data } from '../vector_tile/transcripts/trx_data'
import { color_dict } from '../global_variables/color_dict'
import { trx_names_array } from '../global_variables/trx_names_array'
import { selected_cats, update_selected_cats } from '../global_variables/selected_cats'
import { deck_ist } from './deck_ist'
import { background_layer } from './background_layer'
import { image_layers } from './image_layers'
import { path_layer } from './path_layer'
import { cell_layer } from './cell_layer'
import { gene_search } from '../ui/gene_search'
import { gene_search_input } from '../ui/gene_search_input'


export let trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: trx_data,
    pickable: true,
    getColor: (i, d) => {
        const inst_gene = trx_names_array[d.index];
        const inst_color = color_dict[inst_gene];
        const inst_opacity = selected_cats.length === 0 || selected_cats.includes(inst_gene) ? 255 : 5;
        
        return [...inst_color, inst_opacity];
    },
    onClick: info => {

        const inst_gene = trx_names_array[info.index]
        update_selected_cats([inst_gene])

        update_trx_layer_filter()

        let new_layers = [
            background_layer,
            ...image_layers, 
            path_layer, 
            cell_layer,             
            trx_layer
        ]

        deck_ist.setProps({layers: new_layers})

        gene_search_input.value = (gene_search_input.value !== inst_gene) ? inst_gene : '';
        
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
        id: 'trx-layer-' + selected_cats.join('-'),
    });    
}