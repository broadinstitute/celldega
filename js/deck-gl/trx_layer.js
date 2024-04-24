import { ScatterplotLayer } from 'deck.gl';
import { trx_data, set_trx_data } from '../vector_tile/transcripts/trx_data';
import { color_dict } from '../global_variables/color_dict';
import { trx_names_array } from '../global_variables/trx_names_array';

export let trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: trx_data,
    getRadius: 0.5,
    pickable: true,
    getColor: (i, d) => {
        var inst_gene = trx_names_array[d.index]
        var inst_color = color_dict[inst_gene]
        return [inst_color[0], inst_color[1], inst_color[2], 255]
    },
});       

export const update_trx_layer = async ( base_url, tiles_in_view, ) => {

    await set_trx_data(base_url, tiles_in_view)

    trx_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...trx_layer.props,
        data: trx_data,
    });
        
}