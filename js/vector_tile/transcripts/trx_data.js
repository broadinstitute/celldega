import { grab_trx_tiles_in_view } from './grab_trx_tiles_in_view'

export let trx_data = []

export const set_trx_data = (base_url, tiles_in_view) => {

    trx_data = grab_trx_tiles_in_view(
        base_url,
        tiles_in_view, 
    )    

} 