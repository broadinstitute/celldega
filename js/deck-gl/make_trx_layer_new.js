import { ScatterplotLayer } from 'deck.gl';
import { trx_data, set_trx_data } from '../vector_tile/transcripts/trx_data';

export const make_trx_layer_new = async (
    base_url,
    tiles_in_view, 
    trx_layer
) => {

    set_trx_data(base_url, tiles_in_view)

    const trx_layer_new = new ScatterplotLayer({
        // Re-use existing layer props
        ...trx_layer.props,
        data: trx_data,
    });

    return trx_layer_new
        
}