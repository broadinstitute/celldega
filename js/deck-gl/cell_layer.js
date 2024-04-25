import { ScatterplotLayer } from 'deck.gl';

export let cell_layer = new ScatterplotLayer({
    id: 'cell-layer',
    // data: cell_scatter_data,
    getRadius: 5.0,
    pickable: true,
    getColor: [0, 0, 255, 240],
})


export const update_cell_layer = (cell_scatter_data, cell_names_array) => {
    cell_layer = new ScatterplotLayer({
        // Re-use existing layer props
        ...cell_layer.props,
        data: cell_scatter_data,
        onClick: info => {
            console.log('click!!')
            console.log(info.index)
            console.log(cell_names_array[info.index])
        },        
    });
}