import * as d3 from 'd3'

export const scale_umap_data = (viz_state, cell_scatter_data_objects) => {

    // scale umap values to be centered around the middle of the image x and y positions (max - min / 2)
    // use d3 to find the min and max of the flatCoordinateArray
    const x_min = viz_state.spatial.x_min
    const x_max = viz_state.spatial.x_max
    const y_min = viz_state.spatial.y_min
    const y_max = viz_state.spatial.y_max

    console.log('spatial')
    console.log(x_min, x_max)
    console.log(y_min, y_max)


    // take the smaller of the two ranges for x and y
    const x_range = x_max - x_min
    const y_range = y_max - y_min

    const range_min = Math.min(x_range, y_range)

    const x_mid = (x_max - x_min) / 2;
    const y_mid = (y_max - y_min) / 2;

    // make sure that the min x and y umap values are positive
    let umap_x_min = d3.min(cell_scatter_data_objects.map(d => d.umap[0]))
    let umap_y_min = d3.min(cell_scatter_data_objects.map(d => d.umap[1]))

    if (umap_x_min < 0) {
        console.log('shifting umap because of negative x')
        cell_scatter_data_objects.forEach(d => {
            d.umap[0] = d.umap[0] - umap_x_min
        })

        umap_x_min = 0
    }

    if (umap_y_min < 0) {
        console.log('shifting umap because of negative y')
        cell_scatter_data_objects.forEach(d => {
            d.umap[1] = d.umap[1] - umap_y_min
        })
        umap_y_min = 0
    }

    let umap_x_max = d3.max(cell_scatter_data_objects.map(d => d.umap[0]))
    let umap_y_max = d3.max(cell_scatter_data_objects.map(d => d.umap[1]))

    console.log('umap range')
    console.log(umap_x_min, umap_x_max)
    console.log(umap_y_min, umap_y_max)

    const umap_x_range = umap_x_max - umap_x_min
    const umap_y_range = umap_y_max - umap_y_min

    // scale the umap values to be within range_min and c   entered about x_mid and y_mid
    cell_scatter_data_objects.forEach(d => {
        d.umap[0] = (d.umap[0] - umap_x_min) / (umap_x_range) * range_min
        d.umap[1] = (d.umap[1] - umap_y_min) / (umap_y_range) * range_min
    })

    umap_x_min = d3.min(cell_scatter_data_objects.map(d => d.umap[0]))
    umap_x_max = d3.max(cell_scatter_data_objects.map(d => d.umap[0]))
    umap_y_min = d3.min(cell_scatter_data_objects.map(d => d.umap[1]))
    umap_y_max = d3.max(cell_scatter_data_objects.map(d => d.umap[1]))

    const umap_x_mid = (umap_x_max - umap_x_min) / 2;
    const umap_y_mid = (umap_y_max - umap_y_min) / 2;

    const x_diff = x_mid - umap_x_mid;
    const y_diff = y_mid - umap_y_mid;

    cell_scatter_data_objects.forEach((d) => {
        d.umap[0] = d.umap[0] + x_diff;
        d.umap[1] = d.umap[1] + y_diff;
    })

    return cell_scatter_data_objects

}