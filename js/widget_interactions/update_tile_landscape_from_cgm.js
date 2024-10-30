// import { model } from '../global_variables/model.js'
import { update_cat, update_selected_cats } from "../global_variables/cat.js"
import { update_tile_exp_array } from "../global_variables/tile_exp_array.js";
// import { global_base_url } from '../global_variables/global_base_url.js';
// import { set_gene_search_input } from "../ui/gene_search_input.js";
import { update_square_scatter_layer } from "../deck-gl/square_scatter_layer.js";
// import { deck_sst } from "../deck-gl/deck_sst.js";
// import { simple_image_layer } from "../deck-gl/simple_image_layer.js";
import { update_gene_text_box } from "../ui/gene_search.js";

export const update_tile_landscape_from_cgm = async (deck_sst, layers_sst, viz_state) => {

    const click_info = viz_state.model.get('update_trigger')

    let inst_gene

    if (click_info.click_type === 'row-label') {

        inst_gene = click_info.click_value
        update_cat(viz_state.cats, inst_gene)
        await update_tile_exp_array(viz_state, inst_gene)

    } else if (click_info.click_type === 'col-label') {

        update_cat(viz_state.cats, 'cluster')
        update_selected_cats(viz_state.cats, [click_info.click_value])

    } else if (click_info.click_type === 'col-dendro') {

        update_cat(viz_state.cats, 'cluster')
        update_selected_cats(viz_state.cats, click_info.click_value)

    } else {

        update_cat('cluster')

    }

    update_square_scatter_layer(viz_state, layers_sst)
    deck_sst.setProps({layers: [layers_sst.simple_image_layer, layers_sst.square_scatter_layer]})

    // only run if inst_gene is defined and not 'cluster'
    if (inst_gene && inst_gene !== 'cluster'){
        viz_state.genes.gene_search_input.value = (viz_state.genes.gene_search_input.value !== inst_gene) ? inst_gene : ''
        await update_gene_text_box(viz_state.genes, inst_gene)
    }


}