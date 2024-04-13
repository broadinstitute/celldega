import { ScatterplotLayer } from 'deck.gl';
export const make_cell_layer = (cell_scatter_data, cell_names_array) => {
    const cell_layer = new ScatterplotLayer({
        id: 'cell-layer',
        data: cell_scatter_data,
        getRadius: 5.0,
        pickable: true,
        getColor: [0, 0, 255, 240],
        onClick: info => {
            console.log('click!!')
            console.log(info.index)
            console.log(cell_names_array[info.index])
        },
    });

    return cell_layer
}