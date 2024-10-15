import * as d3 from 'd3'
import { get_arrow_table } from "../read_parquet/get_arrow_table.js"
import { get_scatter_data } from "../read_parquet/get_scatter_data.js"
import { options, set_options } from '../global_variables/fetch_options.js'
// import { update_views } from '../deck-gl/views.js'
// import { set_initial_view_state } from "../deck-gl/initial_view_state.js"
import { deck_sst, set_deck } from '../deck-gl/deck_sst.js'
import { update_layers_sst } from "../deck-gl/layers_sst.js"
import { square_scatter_layer, ini_square_scatter_layer } from "../deck-gl/square_scatter_layer.js"
import { set_tile_scatter_data } from "../global_variables/tile_scatter_data.js"
import { update_tile_cats_array } from "../global_variables/tile_cats_array.js"
import { set_tile_names_array, set_tile_name_to_index_map } from "../global_variables/tile_names_array.js"
import { set_tile_color_dict } from "../global_variables/tile_color_dict.js"
import { set_meta_gene } from "../global_variables/meta_gene.js"
import { set_dimensions } from '../global_variables/image_dimensions.js'
import { set_landscape_parameters } from "../global_variables/landscape_parameters.js"
import { simple_image_layer, make_simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { set_global_base_url } from "../global_variables/global_base_url.js"
// import { model, set_model} from "../global_variables/model.js"
import { update_tile_landscape_from_cgm } from "../widget_interactions/update_tile_landscape_from_cgm.js"
import { set_gene_search } from '../ui/gene_search.js'
import { make_sst_ui_container } from '../ui/ui_containers.js'


export const landscape_sst = async (
    ini_model,
    el,
    base_url,
    token,
    // ini_x,
    // ini_y,
    // ini_z,
    // ini_zoom,
    // dataset_name=''
) => {

    // Create and append the visualization container
    let root = document.createElement("div")
    root.style.height = "800px"

    let model = ''

    let viz_state = {}
    set_options(token)
    set_global_base_url(viz_state, base_url)
    console.log('after set_global_base_url')

    viz_state.img = {}
    viz_state.img.image_layer_colors = {}
    viz_state.img.image_layer_sliders = {}

    await set_landscape_parameters(viz_state.img, base_url)

    await set_dimensions(viz_state, base_url, 'cells')

    viz_state.genes = {}
    viz_state.genes.color_dict_gene = {}
    viz_state.genes.gene_names = []
    viz_state.genes.meta_gene = {}
    viz_state.genes.gene_counts = []
    viz_state.genes.selected_genes = []
    viz_state.genes.trx_ini_radius = 1
    viz_state.genes.trx_names_array = []
    viz_state.genes.trx_data = []
    viz_state.genes.gene_text_box = ''
    viz_state.genes.trx_slider = document.createElement("input")
    viz_state.genes.gene_search = document.createElement("div")
    viz_state.genes.svg_bar_gene = d3.create("svg")

    viz_state.cats = {}
    viz_state.cats.cat
    viz_state.cats.reset_cat = false
    viz_state.cats.selected_cats = []
    viz_state.cats.cell_cats = []
    viz_state.cats.dict_cell_cats = {}
    viz_state.cats.color_dict_cluster = {}
    viz_state.cats.cluster_counts = []
    viz_state.cats.polygon_cell_names = []
    viz_state.cats.svg_bar_cluster = d3.create("svg")


    await set_meta_gene(viz_state.genes, base_url)

    await set_gene_search('sst', deck_sst, {}, viz_state)

    console.log('after set_gene_search')

    // move this to landscape_parameters
    // const imgage_name_for_dim = 'dapi'
    const info = {
        name: 'cells',
        color: [0, 0, 255]
    }

    await make_simple_image_layer(info)

    const tile_url = base_url + '/tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)

    set_tile_scatter_data(get_scatter_data(tile_arrow_table))
    update_tile_cats_array(tile_arrow_table.getChild("cluster").toArray())
    set_tile_names_array(tile_arrow_table.getChild("name").toArray())
    set_tile_name_to_index_map()

    await set_tile_color_dict(base_url)
    ini_square_scatter_layer()
    const new_layers = [simple_image_layer, square_scatter_layer]
    await update_layers_sst(new_layers)

    // commenting out for now
    // set_initial_view_state(ini_x, ini_y, ini_z, ini_zoom)
    // update_views()

    set_deck(root)

    model.on('change:update_trigger', update_tile_landscape_from_cgm)

    const ui_container = make_sst_ui_container()

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root)

    return () => deck_sst.finalize()

}