import * as d3 from 'd3'
import { cluster_counts, cluster_color_dict } from '../global_variables/meta_cluster'
import { update_cat, selected_cats, update_selected_cats } from '../global_variables/cat'
import { update_selected_genes } from '../global_variables/selected_genes'
import { toggle_image_layers_and_ctrls } from './ui_containers'
import { update_cell_layer_id } from '../deck-gl/cell_layer'
import { update_path_layer_id } from '../deck-gl/path_layer'
import { update_trx_layer_filter } from '../deck-gl/trx_layer'
import { layers_ist, update_layers_ist } from '../deck-gl/layers_ist'
import { deck_ist } from '../deck-gl/deck_ist'

export let bar_clusters_container


export const make_bar_clusters = () => {

    bar_clusters_container = document.createElement("div")
    bar_clusters_container.className = "bar_clusters_container"
    bar_clusters_container.style.width = "107px" // Set a fixed width for the container
    bar_clusters_container.style.height = "55px" // Set a fixed height for the container
    bar_clusters_container.style.marginLeft = '5px'
    bar_clusters_container.style.overflowY = "auto" // Enable vertical scrolling
    bar_clusters_container.style.border = "1px solid #d3d3d3" // Optional: Add a border for better visualization

    // Prevent page scrolling when reaching the top/bottom of the scrollable container
    bar_clusters_container.addEventListener('wheel', (event) => {
        const { scrollTop, scrollHeight, clientHeight } = bar_clusters_container

        const atTop = scrollTop === 0
        const atBottom = scrollTop + clientHeight === scrollHeight

        if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
            event.preventDefault()
        }
    })

    // Calculate the total height needed for the SVG based on data length
    const bar_height = 15
    const svg_height = bar_height * (cluster_counts.length + 1)

    const svg = d3.create("svg")
        .attr("width", 100) // Slightly larger width to accommodate text
        .attr("height", svg_height)
        .attr("font-family", "sans-serif")
        .attr("font-size", "13")
        .attr("text-anchor", "end")
        .style("user-select", "none")

    bar_clusters_container.appendChild(svg.node())

    let max_bar_width = 90

    let cluster_counts_values = cluster_counts.map(x => x.value)

    let y_new = d3.scaleBand()
        .domain(d3.range(cluster_counts_values.length))
        .range([0, (bar_height + 1) * cluster_counts_values.length])

    let x_new = d3.scaleLinear()
        .domain([0, d3.max(cluster_counts_values)])
        .range([0, max_bar_width])

    const bar_click_callback = (event, d) => {
        const currentTarget = d3.select(event.currentTarget)
        const isBold = currentTarget.attr('font-weight') === 'bold'

        svg.selectAll("g").attr('font-weight', 'normal')

        if (!isBold) {
            currentTarget.attr('font-weight', 'bold')
        } else {
            currentTarget.attr('font-weight', 'normal')
        }

        update_cat('cluster')
        update_selected_cats([d.name])
        update_selected_genes([])

        toggle_image_layers_and_ctrls(!selected_cats.length > 0)

        const inst_cat_name = selected_cats.join('-')

        update_cell_layer_id(inst_cat_name)
        update_path_layer_id(inst_cat_name)
        update_trx_layer_filter()

        update_layers_ist()

        deck_ist.setProps({layers: layers_ist})
    }

    const bar = svg.selectAll("g")
        .data(cluster_counts)
        .join("g")
        .attr("transform", (d, i) => `translate(2,${y_new(i) + 2})`)
        .on('click', bar_click_callback)

    bar.append("rect")
        .attr("fill", (d) => {
            const inst_rgb = cluster_color_dict[d.name]

            const inst_color = `rgb(${inst_rgb[0]}, ${inst_rgb[1]}, ${inst_rgb[2]})`

            return inst_color
        })
        .attr("width", d => x_new(d.value))
        .attr("height", y_new.bandwidth() - 1)

    bar.append("text")
        .attr("fill", 'black')
        .attr("x", '5px')
        .attr("y", y_new.bandwidth() / 2 - 1) // Adjust this value to push the text up
        .attr("dy", "0.35em")
        .attr('text-anchor', 'start')
        .text(d => d.name)

    // Ensure the container is appended to the DOM
    document.body.appendChild(bar_clusters_container) // Or append it to your desired parent container
}
