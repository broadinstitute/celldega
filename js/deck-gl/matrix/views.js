import { OrthographicView } from 'deck.gl'

export const ini_views = (viz_state) => {
    const views = [

        new OrthographicView({
          id: 'matrix',
          x: ( viz_state.viz.row_region_width + viz_state.viz.label_buffer) + 'px',
          y: ( viz_state.viz.col_region_height + viz_state.viz.label_buffer) + 'px',
          width: viz_state.viz.mat_width + 'px',
          height: viz_state.viz.mat_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'all'},
        }),

        new OrthographicView({
          id: 'rows',
          x: '0px',
          y: (viz_state.viz.col_region_height + viz_state.viz.label_buffer) + 'px',
          width: viz_state.viz.row_region_width + 'px',
          height: viz_state.viz.mat_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'Y'},
        }),

        new OrthographicView({
          id: 'cols',
          x: (viz_state.viz.row_region_width + viz_state.viz.label_buffer) + 'px',
          y: '0px',
          width: viz_state.viz.mat_width + 'px',
          height: viz_state.viz.col_region_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'X'},
        }),

  ]
  return views
}