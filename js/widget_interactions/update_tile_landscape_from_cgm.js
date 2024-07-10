import { model } from '../global_variables/model.js'
import { update_tile_cat } from "../global_variables/tile_cat.js"
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js"; 
import { global_base_url } from '../global_variables/global_base_url.js';
import { update_selected_cats } from "../global_variables/selected_cats.js";
import { gene_search_input } from "../ui/gene_search_input.js";
import { square_scatter_layer, update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";  
import { deck_sst } from "../deck-gl/deck_sst.js";
import { simple_image_layer } from "../deck-gl/simple_image_layer.js";

export const update_tile_landscape_from_cgm = async () => {

    const click_info = model.get('update_trigger');

    let selected_gene
    if (click_info.click_type === 'row-label') {

        selected_gene = click_info.click_value 
        update_tile_cat(selected_gene)
        await update_tile_exp_array(global_base_url, selected_gene)

    } else if (click_info.click_type === 'col-label') {

        selected_gene = 'cluster'
        update_tile_cat(selected_gene)
        update_selected_cats([click_info.click_value])
    
    } else if (click_info.click_type === 'col-dendro') {
        
        selected_gene = 'cluster'
        update_tile_cat(selected_gene)
        update_selected_cats(click_info.click_value)        
    
    } else {
        selected_gene = 'cluster'
        update_tile_cat(selected_gene)
    }

    gene_search_input.value = selected_gene
    
    update_square_scatter_layer()
    deck_sst.setProps({layers: [simple_image_layer, square_scatter_layer]})

}    