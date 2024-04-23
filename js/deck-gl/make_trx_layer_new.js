import { ScatterplotLayer } from 'deck.gl';
import { grab_trx_tiles_in_view } from '../vector_tile/transcripts/grab_trx_tiles_in_view';

export const make_trx_layer_new = async (
    base_url,
    tiles_in_view, 
    trx_layer
) => {

    let trx_scatter_data = grab_trx_tiles_in_view(
        base_url,
        tiles_in_view, 
    )

    const trx_layer_new = new ScatterplotLayer({
        // Re-use existing layer props
        ...trx_layer.props,
        data: trx_scatter_data,
    });

    return trx_layer_new
        
}