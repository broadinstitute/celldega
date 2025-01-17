import * as d3 from 'd3'
import { set_options } from '../global_variables/fetch_options'
import { set_global_base_url } from '../global_variables/global_base_url'
import { set_landscape_parameters } from '../global_variables/landscape_parameters'
import { set_dimensions } from '../global_variables/image_dimensions'
import { ini_cell_layer, set_cell_layer_onclick, update_cell_layer_id } from "../deck-gl/cell_layer"
import { get_layers_list } from '../deck-gl/layers_ist'
import { make_image_layers } from '../deck-gl/image_layers'
import { set_views } from '../deck-gl/views'
import { ini_deck, set_deck_on_view_state_change, set_initial_view_state, set_get_tooltip, set_views_prop } from '../deck-gl/deck_ist'
import { ini_background_layer } from '../deck-gl/background_layer'
import { ini_path_layer, set_path_layer_onclick, update_path_layer_id } from '../deck-gl/path_layer'
import { make_ist_ui_container } from '../ui/ui_containers'
import { ini_trx_layer, set_trx_layer_onclick, update_trx_layer_radius, update_trx_layer_id } from '../deck-gl/trx_layer'
import { set_image_info, set_image_layer_colors, set_image_format } from '../global_variables/image_info'
import { set_image_layer_sliders } from "../ui/sliders"
import { set_meta_gene } from '../global_variables/meta_gene'
import { set_cluster_metadata } from '../global_variables/meta_cluster'
import { update_ist_landscape_from_cgm } from '../widget_interactions/update_ist_landscape_from_cgm'
import { update_cell_clusters } from '../widget_interactions/update_cell_clusters'
import { ini_cache } from '../global_variables/cache'
import { toggle_image_layers_and_ctrls } from '../ui/ui_containers'
import { update_cat, update_selected_cats } from '../global_variables/cat'
import { update_selected_genes } from '../global_variables/selected_genes'
import { update_cell_exp_array } from '../global_variables/cell_exp_array'
import { update_gene_text_box } from '../ui/gene_search'
import { calc_viewport } from '../deck-gl/calc_viewport'
import { ini_edit_layer, set_edit_layer_on_click, set_edit_layer_on_edit } from '../deck-gl/edit_layer'
import { ini_nbhd_layer, set_nbhd_layer_onclick } from '../deck-gl/nbhd_layer'
import { toggle_visibility_image_layers } from '../deck-gl/image_layers'
import { toggle_trx_layer_visibility } from '../deck-gl/trx_layer'
import { toggle_path_layer_visibility } from '../deck-gl/path_layer'
import { toggle_background_layer_visibility } from '../deck-gl/background_layer'

export const landscape_ist = async (
    el,
    ini_model,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    base_url,
    dataset_name='',
    trx_radius=0.25,
    width = 0,
    height = 800,
    meta_cell={},
    meta_cluster={},
    umap={},
    landscape_state='spatial',
    view_change_custom_callback=null
) => {

    if (width === 0){
        width = '100%'
    }

    let viz_state = {}

    viz_state.root = el

    viz_state.buttons = {}
    viz_state.buttons.blue = '#8797ff'
    viz_state.buttons.gray = 'gray'
    viz_state.buttons.light_gray = '#EEEEEE'
    viz_state.buttons.buttons = {}

    set_global_base_url(viz_state, base_url)

    viz_state.close_up = false
    viz_state.model = ini_model

    viz_state.nbhd = {}
    viz_state.nbhd.visible = false

    viz_state.spatial = {}

    if (Object.keys(viz_state.model).length !== 0){
        if (Object.keys(viz_state.model.get('nbhd')).length === 0) {

            viz_state.nbhd.alpha_nbhd = false

            viz_state.nbhd.ini_feature_collection =  {
                "type": "FeatureCollection",
                "features": [],
                "inst_alpha": null
            }
            viz_state.nbhd.feature_collection = viz_state.nbhd.ini_feature_collection

        } else {
            viz_state.nbhd.alpha_nbhd = true

            viz_state.nbhd.ini_feature_collection = viz_state.model.get('nbhd')

            viz_state.nbhd.inst_alpha = viz_state.nbhd.ini_feature_collection['inst_alpha']

            const filt_features = viz_state.nbhd.ini_feature_collection.features.filter(d => d.properties.inv_alpha === viz_state.nbhd.inst_alpha)

            // filter for alpha shapes that have a inv_alpha value of 200
            viz_state.nbhd.feature_collection = {
                "type": "FeatureCollection",
                "features": filt_features
            }

        }
    } else {
        viz_state.nbhd.alpha_nbhd = false

        viz_state.nbhd.ini_feature_collection =  {
            "type": "FeatureCollection",
            "features": [],
            "inst_alpha": null
        }
        viz_state.nbhd.feature_collection = viz_state.nbhd.ini_feature_collection
    }

    viz_state.containers = {}
    viz_state.containers.root_dim = {}
    viz_state.containers.root_dim.width = width
    viz_state.containers.root_dim.height = height

    viz_state.custom_callbacks = {}
    viz_state.custom_callbacks.view_change = view_change_custom_callback

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

    // check if meta_cell is an empty object
    if (Object.keys(meta_cell).length === 0) {
        viz_state.cats.has_meta_cell = false
    } else {
        viz_state.cats.has_meta_cell = true
    }
    viz_state.cats.meta_cell = meta_cell


    if (Object.keys(meta_cluster).length === 0) {
        viz_state.cats.has_meta_cluster = false
    } else {
        viz_state.cats.has_meta_cluster = true
    }
    viz_state.cats.meta_cluster = meta_cluster

    viz_state.umap = {}
    if (Object.keys(umap).length === 0) {
        viz_state.umap.has_umap = false
    } else {
        viz_state.umap.has_umap = true
    }
    viz_state.umap.umap = umap

    if (landscape_state === 'spatial') {
        viz_state.umap.state = false
    } else if (landscape_state === 'umap') {
        viz_state.umap.state = true
    }

    console.log(landscape_state)
    console.log('viz_state.umap.state', viz_state.umap.state)

    viz_state.genes = {}
    viz_state.genes.color_dict_gene = {}
    viz_state.genes.gene_names = []
    viz_state.genes.meta_gene = {}
    viz_state.genes.gene_counts = []
    viz_state.genes.selected_genes = []
    viz_state.genes.trx_ini_radius = trx_radius
    viz_state.genes.trx_names_array = []
    viz_state.genes.trx_data = []
    viz_state.genes.gene_text_box = ''
    viz_state.genes.trx_slider = document.createElement("input")
    viz_state.genes.gene_search = document.createElement("div")
    viz_state.genes.svg_bar_gene = d3.create("svg")

    viz_state.cats.cell_exp_array = []
    viz_state.cats.cell_names_array = []
    viz_state.cats.cell_name_to_index_map = new Map()

    viz_state.img = {}
    viz_state.img.image_layer_colors = {}
    viz_state.img.image_layer_sliders = {}

    set_options(token)

    // move this to landscape_parameters
    const imgage_name_for_dim = 'dapi'

    await set_landscape_parameters(viz_state.img, base_url)

    const tmp_image_info = viz_state.img.landscape_parameters.image_info

    set_image_format(viz_state.img, viz_state.img.landscape_parameters.image_format)
    set_image_info(viz_state.img, tmp_image_info)
    set_image_layer_sliders(viz_state.img)
    set_image_layer_colors(viz_state.img.image_layer_colors, viz_state.img.image_info)

    // Create and append the visualization.
    let root = document.createElement("div")
    root.style.height = height + "px"
    root.style.border = "1px solid #d3d3d3"

    await set_dimensions(viz_state, base_url, imgage_name_for_dim)

    await set_meta_gene(viz_state.genes, base_url)

    await set_cluster_metadata(viz_state)

    viz_state.views = set_views()

    let deck_ist = await ini_deck(root, width, height)
    // set_initial_view_state(deck_ist, ini_x, ini_y, ini_z, ini_zoom)
    set_views_prop(deck_ist, viz_state.views)

    // initialize cell and trx caches
    viz_state.cache = {}
    viz_state.cache.cell = await ini_cache()
    // we will try to reuse cell functions to make trx cache
    viz_state.cache.trx  = await ini_cache()

    viz_state.combo_data = {}

    viz_state.tooltip_cat_cell = ''

    set_get_tooltip(deck_ist, viz_state)

    viz_state.edit = {}
    viz_state.edit.svg_bar_rgn = d3.create("svg")
    viz_state.edit.rgn_areas = []
    viz_state.edit.color_dict_rgn = {}
    viz_state.edit.rgn_opacity = 0.75
    viz_state.edit.visible = false
    viz_state.edit.modify_index = null

    if (Object.keys(viz_state.model).length !== 0){

        if (Object.keys(viz_state.model.get('region')).length === 0) {

            viz_state.edit.feature_collection =  {
                "type": "FeatureCollection",
                "features": []
            }

        } else {
            viz_state.edit.feature_collection = viz_state.model.get('region')
        }

    } else {

        viz_state.edit.feature_collection =  {
            "type": "FeatureCollection",
            "features": []
        }
    }

    let background_layer = ini_background_layer(viz_state)
    let image_layers = await make_image_layers(viz_state)
    let cell_layer = await ini_cell_layer(base_url, viz_state)
    let path_layer = await ini_path_layer(viz_state)
    let trx_layer = ini_trx_layer(viz_state.genes)
    let edit_layer = ini_edit_layer(viz_state)
    let nbhd_layer = ini_nbhd_layer(viz_state, false)

    // make layers object
    let layers_obj = {
        'background_layer': background_layer,
        'image_layers': image_layers,
        'cell_layer': cell_layer,
        'path_layer': path_layer,
        'trx_layer': trx_layer,
        'edit_layer': edit_layer,
        'nbhd_layer': nbhd_layer
    }

    // set onclicks after all layers are made
    set_cell_layer_onclick(deck_ist, layers_obj, viz_state)
    set_path_layer_onclick(deck_ist, layers_obj, viz_state)
    set_trx_layer_onclick(deck_ist, layers_obj, viz_state)
    set_edit_layer_on_edit(deck_ist, layers_obj, viz_state)
    set_edit_layer_on_click(deck_ist, layers_obj, viz_state)
    set_nbhd_layer_onclick(deck_ist, layers_obj, viz_state)

    update_trx_layer_radius(layers_obj, trx_radius)

    if (viz_state.umap.state === true) {
        toggle_background_layer_visibility(layers_obj, false)
        toggle_visibility_image_layers(layers_obj, false)
        toggle_trx_layer_visibility(layers_obj, false)
        toggle_path_layer_visibility(layers_obj, false)
    }

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)

    set_initial_view_state(deck_ist, ini_x, ini_y, ini_z, ini_zoom, viz_state)



    deck_ist.setProps({layers: layers_list})

    set_deck_on_view_state_change(deck_ist, layers_obj, viz_state)

    if (Object.keys(viz_state.model).length > 0) {
        viz_state.model.on('change:update_trigger', () => update_ist_landscape_from_cgm(deck_ist, layers_obj, viz_state))
        viz_state.model.on('change:cell_clusters', () => update_cell_clusters(deck_ist, layers_obj, viz_state))
    }

    const ui_container = make_ist_ui_container(dataset_name, deck_ist, layers_obj, viz_state)

    // UI and Viz Container
    el.appendChild(ui_container)
    el.appendChild(root)

    const landscape = {
        update_matrix_gene: async (inst_gene) => {

            const reset_gene = inst_gene === viz_state.cats.cat;
            const new_cat = reset_gene ? 'cluster' : inst_gene

            if (!reset_gene) {
                const selectedBar = viz_state.genes.svg_bar_gene.selectAll("g")
                    .filter(function() {
                        const textElement = d3.select(this).select("text").node()
                        return textElement && textElement.textContent === inst_gene
                    })
                    .attr('opacity', 1.0)

                if (!selectedBar.empty()) {

                    const barPosition = selectedBar.node().getBoundingClientRect().top

                    const containerPosition = viz_state.containers.bar_gene.getBoundingClientRect().top
                    const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_gene.scrollTop

                    viz_state.genes.svg_bar_gene
                        .attr('opacity', 1.0)

                        viz_state.containers.bar_gene.scrollTo({
                        top: scrollPosition,
                        behavior: 'smooth'
                    })
                }
            } else {
                viz_state.containers.bar_gene.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                })
            }

            // reset cluster bar plot
            viz_state.cats.svg_bar_cluster
                .selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', 1.0)

            toggle_image_layers_and_ctrls(layers_obj, viz_state, viz_state.cats.cat === inst_gene)

            update_cat(viz_state.cats, new_cat)
            update_selected_genes(viz_state.genes, [inst_gene])
            update_selected_cats(viz_state.cats, [])
            await update_cell_exp_array(viz_state.cats, viz_state.genes, viz_state.global_base_url, inst_gene)

            update_cell_layer_id(layers_obj, new_cat)
            update_path_layer_id(layers_obj, new_cat)
            update_trx_layer_id(viz_state.genes, layers_obj)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

            viz_state.genes.gene_search_input.value = viz_state.genes.gene_search_input.value !== inst_gene ? inst_gene : ''
            update_gene_text_box(viz_state.genes, reset_gene ? '' : inst_gene)
        },
        update_matrix_col: async (inst_col) => {

            // reset bar graphs (will remove duplicate code later)
            //////////////////////////////////////////
            viz_state.genes.svg_bar_gene
                .selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', 1.0)

            viz_state.cats.svg_bar_cluster.selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', viz_state.cats.reset_cat ? 1.0 : 0.25)

            if (!viz_state.cats.reset_cat) {
                const selectedBar = viz_state.cats.svg_bar_cluster.selectAll("g")
                    .filter(function() {
                        return d3.select(this).select("text").text() === inst_col
                    })
                    .attr('opacity', 1.0)

                if (!selectedBar.empty()) {
                    const barPosition = selectedBar.node().getBoundingClientRect().top
                    const containerPosition = viz_state.containers.bar_cluster.getBoundingClientRect().top
                    const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_cluster.scrollTop

                    viz_state.containers.bar_cluster.scrollTo({
                        top: scrollPosition,
                        behavior: 'smooth'
                    })
                }
            } else {
                viz_state.containers.bar_cluster.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                })
            }

            update_cat(viz_state.cats, 'cluster')
            update_selected_cats(viz_state.cats, [inst_col])
            update_selected_genes(viz_state.genes, [])
            toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

            const inst_cat_name = viz_state.cats.selected_cats.join('-')
            update_cell_layer_id(layers_obj, inst_cat_name)
            update_path_layer_id(layers_obj, inst_cat_name)
            update_trx_layer_id(viz_state.genes, layers_obj)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

            viz_state.genes.gene_search_input.value = ''
            update_gene_text_box(viz_state.genes, '')

        },
        update_matrix_dendro_col: async (selected_cols) => {

            // const inst_gene = 'cluster'
            const new_cats = selected_cols // click_info.value.selected_names

            update_cat(viz_state.cats, 'cluster')
            update_selected_cats(viz_state.cats, new_cats)

            update_selected_genes(viz_state.genes, [])
            toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

            const inst_cat_name = viz_state.cats.selected_cats.join('-')

            update_cell_layer_id(layers_obj, inst_cat_name)
            update_path_layer_id(layers_obj, inst_cat_name)
            update_trx_layer_id(viz_state.genes, layers_obj)

            const layers_list = get_layers_list(layers_obj, viz_state.close_up)
            deck_ist.setProps({layers: layers_list})

            viz_state.cats.svg_bar_cluster.selectAll("g")
                .attr('font-weight', 'normal')
                .attr('opacity', viz_state.cats.reset_cat ? 1.0 : 0.25)

            const inst_cat = new_cats

            if (!viz_state.cats.reset_cat) {
                const selectedBar = viz_state.cats.svg_bar_cluster.selectAll("g")
                    .filter(function() {
                        return d3.select(this).select("text").text() === inst_cat
                    })
                    .attr('opacity', 1.0)

                if (!selectedBar.empty()) {
                    const barPosition = selectedBar.node().getBoundingClientRect().top
                    const containerPosition = viz_state.containers.bar_cluster.getBoundingClientRect().top
                    const scrollPosition = barPosition - containerPosition + viz_state.containers.bar_cluster.scrollTop

                    viz_state.containers.bar_cluster.scrollTo({
                        top: scrollPosition,
                        behavior: 'smooth'
                    })
                }
            }

        },
        update_view_state: async (new_view_state, close_up, trx_layer) => {

            viz_state.close_up = close_up

            calc_viewport(new_view_state, deck_ist, layers_obj, viz_state)
            const layers_list = get_layers_list(layers_obj, viz_state.close_up)

            deck_ist.setProps({
                controller: {doubleClickZoom: false},
                initialViewState: new_view_state,
                views: viz_state.views,
                layers: layers_list
            })
        },
        update_layers: () => {
            console.log('update_layers')
        },
        finalize: () => {
            deck_ist.finalize();
        }
    };

    return landscape;

}

