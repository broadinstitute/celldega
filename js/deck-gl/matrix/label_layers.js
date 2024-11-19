import { TextLayer } from "deck.gl"
import * as d3 from 'd3'
import { get_mat_layers_list } from "./matrix_layers"
import { toggle_dendro_layer_visibility } from "./dendro_layers"

const row_label_get_position = (d, index, viz_state) => {

    const inst_index = index.index
    const inst_order = viz_state.order.current.row
    const row_offset = 50 // 25

    let inst_row_index = viz_state.mat.num_rows - viz_state.mat.orders.row[inst_order][inst_index]


    let pos_x = row_offset
    let pos_y = viz_state.viz.row_offset * (inst_row_index + 1.5)

    const position = [pos_x, pos_y]

    return position

}

const col_label_get_position = (d, index, viz_state) => {

    const inst_index = index.index
    const inst_order = viz_state.order.current.col
    const col_offset = 50


    let inst_col_index = viz_state.mat.num_cols - viz_state.mat.orders.col[inst_order][inst_index]

    let pos_x = viz_state.viz.col_offset * (inst_col_index + 0.5)
    let pos_y = col_offset // * zoom_factor

    const position = [pos_x, pos_y]

    return position

}

export const ini_row_label_layer = (viz_state) => {

    const transitions = {
        getPosition: {
            duration: viz_state.animate.duration,
            easing: d3.easeCubic
        }
    }

    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: viz_state.labels.row_label_data,
        getPosition: (d, index) => row_label_get_position(d, index, viz_state),
        getText: d => d.name,
        getSize: viz_state.viz.font_size.rows,
        getColor: [0, 0, 0],
        getAngle: 0,
        getTextAnchor: 'end',
        getAlignmentBaseline: 'center',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        sizeScale: 2,
        // updateTriggers: {
        //   getSize: viz_state.viz.ini_font_size,
        // },
        pickable: true,
        transitions: transitions,
    })

    return row_label_layer
}

export const ini_col_label_layer = (viz_state) => {

    // Define zoom-dependent offset
    function getPixelOffset(zoom_x, num_cols) {

        const zoom_factor = Math.pow(2, zoom_x)
        const offset_y = 75 / num_cols
        const scaled_offset_y = offset_y * zoom_factor

        return [0, scaled_offset_y];
    }

    const transitions = {
        getPosition: {
            duration: viz_state.animate.duration,
            easing: d3.easeCubic
        }
    }

    const col_label_layer  = new TextLayer({
        id: 'col-label-layer',
        data: viz_state.labels.col_label_data,
        getPosition: (d, index) => col_label_get_position(d, index, viz_state),
        getText: d => d.name,
        getSize: viz_state.viz.font_size.cols,
        getColor: [0, 0, 0],
        getAngle: 45, // Optional: Text angle in degrees
        getTextAnchor: 'start', // middle
        getAlignmentBaseline: 'bottom',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        sizeScale: 2,
        // updateTriggers: {
        // //   getSize: viz_state.viz.ini_font_size,
        //   getPosition: viz_state.viz.font_size,
        //   getPixelOffset: viz_state.zoom.zoom_data.matrix.zoom_x,
        // },
        pickable: true,
        transitions: transitions,
        getPixelOffset: () => getPixelOffset(viz_state.zoom.zoom_data.matrix.zoom_x, viz_state.mat.num_cols),
    })

    return col_label_layer

}


const DOUBLE_CLICK_DELAY = 250;

const custom_label_reorder = (deck_mat, layers_mat, viz_state, axis, name, index) => {

    let tmp_arr = []
    const other_axis = axis === 'col' ? 'row' : 'col'

    // deactivate reordering buttons when setting a custom order
    d3.select(viz_state.el)
      .selectAll('.button-' + other_axis)
      .classed('active', false)
      .style('border-color', viz_state.buttons.gray)

    if (axis === 'col') {
        tmp_arr = viz_state.mat.net_mat.map(inst_row => inst_row[index])
    } else {
        tmp_arr = viz_state.mat.net_mat[index]
    }

    // tmp_sort is an array of the indexes of the other axis that are ranked by the values of the selected index
    const tmp_sort = Array.from(tmp_arr.keys()).sort((a, b) => tmp_arr[b] - tmp_arr[a])

    const length_other_axis = tmp_sort.length
    const ranked_sort = Array(length_other_axis);


    // convert tmp_sort into an array of the ranks of each index
    // Fill the ranks array with the rank of each index
    tmp_sort.forEach((columnIndex, rank) => {
        ranked_sort[columnIndex] = length_other_axis - rank ; // Add 1 to make it 1-indexed
    });

    viz_state.mat.orders[other_axis].custom = ranked_sort

    viz_state.order.current[other_axis] = 'custom'

    layers_mat.mat_layer = layers_mat.mat_layer.clone({
        updateTriggers: {
            getPosition: [viz_state.order.current.row, viz_state.order.current.col, name]
        }
    })

    if (other_axis === 'col') {
        layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
            updateTriggers: {
                getPosition: [viz_state.order.current.col, name]
            }
        })
        toggle_dendro_layer_visibility(layers_mat, viz_state, 'col')
    } else if (other_axis === 'row') {
        layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
            updateTriggers: {
                getPosition: [viz_state.order.current.row, name]
            }
        })
        toggle_dendro_layer_visibility(layers_mat, viz_state, 'row')
    }

    deck_mat.setProps({
        layers: get_mat_layers_list(layers_mat),
    })

}

const row_label_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {

    viz_state.labels.clicks.row += 1

    if (viz_state.labels.clicks.row === 1) {

        viz_state.click.type = 'row_label'
        viz_state.click.value = {
            'name': event.object.name
        }


        setTimeout(() => {
            viz_state.labels.clicks.row = 0
        }, DOUBLE_CLICK_DELAY)


    } else if (viz_state.labels.clicks.row === 2) {
        viz_state.labels.clicks.row = 0

        custom_label_reorder(deck_mat, layers_mat, viz_state, 'row', event.object.name, event.object.index)
    }

    // deck_mat.setProps({layers: get_mat_layers_list(layers_mat)})
    console.log(viz_state.click)

    if (Object.keys(viz_state.model).length > 0) {
        viz_state.model.set('click_info', null);
        viz_state.model.set('click_info', viz_state.click)
        viz_state.model.save_changes()
    }

}

const col_label_layer_onclick = (event, deck_mat, layers_mat, viz_state) => {

    viz_state.labels.clicks.col += 1

    if (viz_state.labels.clicks.col === 1) {

        viz_state.click.type = 'col_label'
        viz_state.click.value = {
            'name': event.object.name
        }

        setTimeout(() => {
            viz_state.labels.clicks.col = 0
        }, DOUBLE_CLICK_DELAY)

    } else if (viz_state.labels.clicks.col === 2) {
        viz_state.labels.clicks.col = 0

        custom_label_reorder(deck_mat, layers_mat, viz_state, 'col', event.object.name, event.object.index)

    }

    // deck_mat.setProps({layers: get_mat_layers_list(layers_mat)})
    console.log(viz_state.click)

    if (Object.keys(viz_state.model).length > 0) {
        viz_state.model.set('click_info', null);
        viz_state.model.set('click_info', viz_state.click)
        viz_state.model.save_changes()
    }

}

export const set_row_label_layer_onclick = (deck_mat, layers_mat, viz_state) => {

    layers_mat.row_label_layer = layers_mat.row_label_layer.clone({
        onClick: (event) => row_label_layer_onclick(event, deck_mat, layers_mat, viz_state)
    })

}

export const set_col_label_layer_onclick = (deck_mat, layers_mat, viz_state) => {

    layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
        onClick: (event) => col_label_layer_onclick(event, deck_mat, layers_mat, viz_state)
    })

}