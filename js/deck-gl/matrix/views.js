import { OrthographicView } from 'deck.gl'

export const ini_views = (viz_state) => {


    let switch_ratio

    if (viz_state.mat.num_rows > viz_state.mat.num_cols){
        viz_state.zoom.major_zoom_axis = 'Y'
        viz_state.zoom.minor_zoom_axis = 'X'
        switch_ratio = viz_state.mat.num_rows/viz_state.mat.num_cols

    } else if (viz_state.mat.num_rows < viz_state.mat.num_cols){
        viz_state.zoom.major_zoom_axis = 'X'
        viz_state.zoom.minor_zoom_axis = 'Y'
        switch_ratio = viz_state.mat.num_cols/viz_state.mat.num_rows
    } else if (viz_state.mat.num_rows === viz_state.mat.num_cols){
        viz_state.zoom.major_zoom_axis = 'all'
        viz_state.zoom.minor_zoom_axis = 'none'
        switch_ratio = 1
    }

    viz_state.zoom.switch_ratio = switch_ratio
    viz_state.zoom.zoom_delay = Math.log2(switch_ratio)

    const views_list = [

        new OrthographicView({
            id: 'matrix',
            x: ( viz_state.viz.row_region + viz_state.viz.label_buffer) + 'px',
            y: ( viz_state.viz.col_region + viz_state.viz.label_buffer) + 'px',
            width: viz_state.viz.mat_width + 'px',
            height: viz_state.viz.mat_height + 'px',
            controller: {
                scrollZoom: true,
                inertia: true,
                zoomAxis: viz_state.zoom.major_zoom_axis,
                doubleClickZoom: false
            },
        }),

        new OrthographicView({
            id: 'rows',
            x: '0px',
            y: (viz_state.viz.col_region + viz_state.viz.label_buffer) + 'px',
            width: viz_state.viz.row_region + 'px',
            height: viz_state.viz.mat_height + 'px',
            controller: {
                scrollZoom: true,
                inertia: false,
                zoomAxis: viz_state.zoom.major_zoom_axis,
                doubleClickZoom: false
            },
        }),

        new OrthographicView({
            id: 'cols',
            x: (viz_state.viz.row_region + viz_state.viz.label_buffer) + 'px',
            y: '0px',
            width: viz_state.viz.mat_width + 'px',
            height: viz_state.viz.col_region + 'px',
            controller: {
                scrollZoom: true,
                inertia: false,
                zoomAxis: viz_state.zoom.major_zoom_axis,
                doubleClickZoom: false
            },
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
      },
      cols: {
        target: [viz_state.zoom.ini_pan_x, viz_state.viz.label_col_y],
        zoom: [viz_state.zoom.ini_zoom_x, viz_state.zoom.ini_zoom_y],
      },
    }

    return globalViewState

  }
