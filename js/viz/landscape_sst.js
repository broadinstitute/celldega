import * as d3 from 'd3'
import { get_arrow_table } from "../read_parquet/get_arrow_table.js"
import { get_scatter_data } from "../read_parquet/get_scatter_data.js"
import { options, set_options } from '../global_variables/fetch_options.js'
import { ini_deck_sst } from '../deck-gl/deck_sst.js'
import { ini_square_scatter_layer, set_tile_layer_onclick } from "../deck-gl/square_scatter_layer.js"
import { set_tile_scatter_data } from "../global_variables/tile_scatter_data.js"
import { set_tile_names_array, set_tile_name_to_index_map } from "../global_variables/tile_names_array.js"
import { set_tile_color_dict } from "../global_variables/tile_color_dict.js"
import { set_meta_gene } from "../global_variables/meta_gene.js"
import { set_dimensions } from '../global_variables/image_dimensions.js'
import { set_landscape_parameters } from "../global_variables/landscape_parameters.js"
import { make_simple_image_layer } from "../deck-gl/simple_image_layer.js"
import { set_global_base_url } from "../global_variables/global_base_url.js"
import { update_tile_landscape_from_cgm } from "../widget_interactions/update_tile_landscape_from_cgm.js"
import { make_sst_ui_container } from '../ui/ui_containers.js'
import { set_views } from '../deck-gl/views.js'
import { make_tile_tooltip } from '../deck-gl/make_tile_tooltip.js';

export const landscape_sst = async (
    ini_model,
    el,
    base_url,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    // dataset_name=''
) => {

    // Create and append the visualization container
    let root = document.createElement("div")
    root.style.height = "   800px"

    let viz_state = {}
    set_options(token)
    set_global_base_url(viz_state, base_url)

    viz_state.model = ini_model

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
    viz_state.cats.cat = 'cluster'
    viz_state.cats.reset_cat = false
    viz_state.cats.selected_cats = []
    viz_state.cats.cell_cats = []
    viz_state.cats.dict_cell_cats = {}
    viz_state.cats.color_dict_cluster = {}
    viz_state.cats.cluster_counts = []
    viz_state.cats.polygon_cell_names = []
    viz_state.cats.svg_bar_cluster = d3.create("svg")

    await set_meta_gene(viz_state.genes, base_url)

    // move this to landscape_parameters
    // const imgage_name_for_dim = 'dapi'
    const info = {
        name: 'cells',
        color: [0, 0, 255]
    }

    const tile_url = base_url + '/tile_geometries.parquet'

    var tile_arrow_table = await get_arrow_table(tile_url, options.fetch)

    viz_state.cats.tile_cats_array = tile_arrow_table.getChild("cluster").toArray()
    viz_state.cats.tile_exp_array = []
    viz_state.cats.tile_names_array = []
    viz_state.cats.tile_scatter_data = []

    set_tile_scatter_data(viz_state.cats, get_scatter_data(tile_arrow_table))

    set_tile_names_array(viz_state.cats, tile_arrow_table.getChild("name").toArray())
    set_tile_name_to_index_map(viz_state.cats)

    viz_state.cats.tile_color_dict = await set_tile_color_dict(base_url)

    let simple_image_layer = await make_simple_image_layer(viz_state, info)
    let square_scatter_layer = ini_square_scatter_layer(viz_state.cats)

    let layers_sst = {
        'simple_image_layer': simple_image_layer,
        'square_scatter_layer': square_scatter_layer
    }

    viz_state.views = set_views()

    let deck_sst = ini_deck_sst(root)

    const initial_view_state = {
        target: [ini_x, ini_y, ini_z],
        zoom: ini_zoom
    }

    deck_sst.setProps({
        views: viz_state.views,
        layers: [ layers_sst.simple_image_layer, layers_sst.square_scatter_layer],
        getTooltip: (info) => make_tile_tooltip(info, viz_state.cats),
        initialViewState: initial_view_state,
    })

    // disable for now
    // model.on('change:update_trigger', update_tile_landscape_from_cgm)

    if (Object.keys(viz_state.model).length > 0) {

        // ist version
        // viz_state.model.on('change:update_trigger', () => update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state))

        viz_state.model.on('change:update_trigger', () => update_tile_landscape_from_cgm(deck_sst, layers_sst, viz_state))
    }

    set_tile_layer_onclick(deck_sst, layers_sst, viz_state)
    console.log(layers_sst)
    console.log(layers_sst.square_scatter_layer.onClick)

    const ui_container = make_sst_ui_container(deck_sst, layers_sst, viz_state)

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root)

    return () => deck_sst.finalize()

}