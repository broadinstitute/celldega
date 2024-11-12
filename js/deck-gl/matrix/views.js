import { OrthographicView } from 'deck.gl'
import { update_zoom_data } from './zoom.js'
import { get_layers_list } from './matrix_layers.js'

export const ini_views = (viz_state) => {

    const views_list = [

        new OrthographicView({
          id: 'matrix',
          x: ( viz_state.viz.row_region_width + viz_state.viz.label_buffer) + 'px',
          y: ( viz_state.viz.col_region_height + viz_state.viz.label_buffer) + 'px',
          width: viz_state.viz.mat_width + 'px',
          height: viz_state.viz.mat_height + 'px',
        //   controller: {scrollZoom: true, inertia: false, zoomAxis: 'all'},
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'Y'},
        }),

        new OrthographicView({
          id: 'rows',
          x: '0px',
          y: (viz_state.viz.col_region_height + viz_state.viz.label_buffer) + 'px',
          width: viz_state.viz.row_region_width + 'px',
          height: viz_state.viz.mat_height + 'px',
        //   controller: {scrollZoom: true, inertia: false, zoomAxis: 'Y'},
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'all'},
        }),

        new OrthographicView({
          id: 'cols',
          x: (viz_state.viz.row_region_width + viz_state.viz.label_buffer) + 'px',
          y: '0px',
          width: viz_state.viz.mat_width + 'px',
          height: viz_state.viz.col_region_height + 'px',
        //   controller: {scrollZoom: true, inertia: false, zoomAxis: 'X'},
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'all'},
        }),

    ]

    viz_state.views = {}

    viz_state.views.views_list = views_list

}


export const ini_view_state = (viz_state) => {

    let globalViewState = {
      matrix: {
        target: [viz_state.zoom.ini_pan_x, viz_state.zoom.ini_pan_y],
        zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
      },
      rows: {
        target: [viz_state.viz.label_row_x, viz_state.zoom.ini_pan_y],
        zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
        // zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
      },
      cols: {
        target: [viz_state.zoom.ini_pan_x, viz_state.viz.label_col_y],
        zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
        // zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
      },
    }

    return globalViewState

  }


  const curate_pan_y = (target_y, zoom_curated_y, viz_state) => {

    const ini_pan_y = viz_state.zoom.ini_pan_y

    var pan_curated_y

    var zoom_factor_y = Math.pow(2, zoom_curated_y)

    var min_pan_y = (ini_pan_y - viz_state.viz.row_offset)/zoom_factor_y + viz_state.viz.row_offset

    // calculating the shift to the min, to re-use for the max
    var min_diff = ini_pan_y - min_pan_y

    var max_pan_y = ini_pan_y + min_diff

    if (target_y <= min_pan_y){
      // console.log('below min')
      pan_curated_y = min_pan_y
    } else if (target_y > max_pan_y) {
      pan_curated_y = max_pan_y
      // console.log('above min')
    } else {
      pan_curated_y = target_y
      // console.log('within bounds')
    }

    return pan_curated_y
  }

const curate_pan_x = (target_x, zoom_curated_x, viz_state) => {

    const ini_pan_x = viz_state.zoom.ini_pan_x

    var pan_curated_x

    var zoom_factor_x = Math.pow(2, zoom_curated_x)

    var min_pan_x = ini_pan_x/zoom_factor_x

    // calculating the shift to the min, to re-use for the max
    var min_diff = ini_pan_x - min_pan_x

    var max_pan_x = ini_pan_x + min_diff

    if (target_x <= min_pan_x){
        // console.log('below min')
        pan_curated_x = min_pan_x
    } else if (target_x > max_pan_x) {
        pan_curated_x = max_pan_x
        // console.log('above min')
    } else {
        pan_curated_x = target_x
        // console.log('within bounds')
    }

    return pan_curated_x

}

const redefine_global_view_state = (viz_state, viewId, zoom, target) => {

    const zoom_data = viz_state.zoom.zoom_data

    var globalViewState

    var min_zoom_x = 0
    var min_zoom_y = 0

    var zoom_curated_x = Math.max(min_zoom_x, zoom[0])
    var zoom_curated_y = Math.max(min_zoom_y, zoom[1])

    var pan_curated_x = curate_pan_x(target[0], zoom_curated_x, viz_state)
    var pan_curated_y = curate_pan_y(target[1], zoom_curated_y, viz_state)

    if (viewId === 'matrix') {

        globalViewState = {
            matrix: {
                zoom: [zoom_curated_x, zoom_curated_y],
                target: [pan_curated_x, pan_curated_y]
            },
            rows:   {
                zoom: [viz_state.zoom.ini_zoom_x, zoom_curated_y],
                target: [viz_state.viz.label_row_x, pan_curated_y]
            },
            cols:   {
                zoom: [zoom_curated_x, viz_state.zoom.ini_zoom_y],
                target: [pan_curated_x, viz_state.viz.label_col_y]
            },
        }

    } else if (viewId === 'cols'){

        globalViewState = {
            matrix: {
                zoom: [zoom_curated_x, zoom_data.zoom_y],
                target: [pan_curated_x, zoom_data.pan_y]

                // zoom: [zoom_curated_x, zoom_curated_y],
                // target: [pan_curated_x, pan_curated_y]

            },
            rows:   {
                zoom: [viz_state.zoom.ini_zoom_x, zoom_data.zoom_y],
                target: [viz_state.viz.label_row_x, zoom_data.pan_y]
            },
            cols:   {
                zoom: [zoom_curated_x, viz_state.zoom.ini_zoom_y],
                target: [pan_curated_x, viz_state.viz.label_col_y]
            },
        }

    } else if (viewId === 'rows'){

        globalViewState = {
            matrix: {
                zoom: [zoom_data.zoom_x, zoom_curated_y],
                target: [zoom_data.pan_x, pan_curated_y]

                // zoom: [zoom_curated_x, zoom_curated_y],
                // target: [pan_curated_x, pan_curated_y]
            },
            rows:   {
                zoom: [viz_state.zoom.ini_zoom_x, zoom_curated_y],
                target: [viz_state.viz.label_row_x, pan_curated_y]
            },
            cols:   {
                zoom: [zoom_data.zoom_x, viz_state.zoom.ini_zoom_y],
                target: [zoom_data.pan_x, viz_state.viz.label_col_y]
            },
        }

    }

    return globalViewState
}

export const on_view_state_change = (params, deck_mat, layers_mat, viz_state) => {

    const viewState = params.viewState
    const viewId = params.viewId

    const {zoom, target} = viewState;

    var global_view_state = redefine_global_view_state(viz_state, viewId, zoom, target)

    var zoom_factor_x = Math.pow(2, viz_state.zoom.zoom_data.zoom_x)

    var zoom_factor_y = Math.pow(2, viz_state.zoom.zoom_data.zoom_y)

    console.log(zoom_factor_y)

    let row_to_col = viz_state.mat.num_rows/viz_state.mat.num_cols

    viz_state.viz.inst_font_size = viz_state.viz.ini_font_size * zoom_factor_x

    update_zoom_data(viz_state.zoom.zoom_data, viewId, zoom, target)

    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        getSize: viz_state.viz.inst_font_size,
    })

    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        getSize: viz_state.viz.inst_font_size,
    })

    let zoom_mode = zoom_factor_y < row_to_col ? 'Y' : 'all'


    // Recreate each view with updated zoomAxis in controller
    viz_state.views.views_list = viz_state.views.views_list.map(view => {
        return new OrthographicView({
            ...view.props,
            controller: {
                ...view.props.controller,
                doubleClickZoom: false,
                scrollZoom: true,
                inertia: true,
                zoomAxis: zoom_mode,
            },
        });
    });

    deck_mat.setProps({
        viewState: global_view_state,
        layers: get_layers_list(layers_mat),
        views: viz_state.views.views_list,
    })

}