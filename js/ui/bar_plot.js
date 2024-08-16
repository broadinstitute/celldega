import * as d3 from 'd3'
import { cat, update_cat_new, update_selected_cats } from '../global_variables/cat'
import { update_selected_genes } from '../global_variables/selected_genes'
import { toggle_image_layers_and_ctrls } from './ui_containers'
import { update_cell_layer_id } from '../deck-gl/cell_layer'
import { update_path_layer_id } from '../deck-gl/path_layer'
import { update_trx_layer_id } from '../deck-gl/trx_layer'
import { get_layers_list } from '../deck-gl/layers_ist'
import { update_cell_exp_array } from '../global_variables/cell_exp_array'
import { global_base_url } from '../global_variables/global_base_url'
import { gene_search_input } from './gene_search_input'
import { update_gene_text_box } from './gene_search'

export let svg_bar_cluster = d3.create("svg")
export let svg_bar_gene = d3.create("svg")

export const make_bar_container = () => {
    return document.createElement("div")
}

export const bar_callback_cluster = (event, d, deck_ist, layers_obj, viz_state) => {

    // reset gene
    svg_bar_gene
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 1.0)

    const currentTarget = d3.select(event.currentTarget)
    const isBold = currentTarget.attr('font-weight') === 'bold'

    svg_bar_cluster
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 0.25)

    if (!isBold) {
        currentTarget.attr('font-weight', 'bold')
        currentTarget.attr('opacity', 1.0)
    } else {
        currentTarget.attr('font-weight', 'normal')

        svg_bar_cluster
            .selectAll("g")
            .attr('opacity', 1.0)
    }

    update_cat_new(viz_state.cats, 'cluster')
    update_selected_cats(viz_state.cats, [d.name])
    update_selected_genes([])
    toggle_image_layers_and_ctrls(layers_obj, viz_state, !viz_state.cats.selected_cats.length > 0)

    const inst_cat_name = viz_state.cats.selected_cats.join('-')
    update_cell_layer_id(layers_obj, inst_cat_name)
    update_path_layer_id(layers_obj, inst_cat_name)
    update_trx_layer_id(layers_obj)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    gene_search_input.value = ''
    update_gene_text_box('')
}

export const bar_callback_gene = async (event, d, deck_ist, layers_obj, viz_state) => {

    // reset cluster bar plot
    svg_bar_cluster
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 1.0)

    const currentTarget = d3.select(event.currentTarget)
    const isBold = currentTarget.attr('font-weight') === 'bold'

    svg_bar_gene
        .selectAll("g")
        .attr('font-weight', 'normal')
        .attr('opacity', 0.25)

    if (!isBold) {
        currentTarget.attr('font-weight', 'bold')
        currentTarget.attr('opacity', 1.0)
    } else {
        currentTarget.attr('font-weight', 'normal')

        svg_bar_gene
            .selectAll("g")
            .attr('opacity', 1.0)
    }

    const inst_gene = d.name
    const reset_gene = inst_gene === cat;
    const new_cat = reset_gene ? 'cluster' : inst_gene

    toggle_image_layers_and_ctrls(layers_obj, viz_state, cat === inst_gene)

    update_cat_new(viz_state.cats, new_cat)
    update_selected_genes([inst_gene])
    update_selected_cats(viz_state.cats, [])
    await update_cell_exp_array(global_base_url, inst_gene)

    update_cell_layer_id(layers_obj, new_cat)
    update_path_layer_id(layers_obj, new_cat)
    update_trx_layer_id(layers_obj)

    const layers_list = get_layers_list(layers_obj, viz_state.close_up)
    deck_ist.setProps({layers: layers_list})

    gene_search_input.value = gene_search_input.value !== inst_gene ? inst_gene : ''
    update_gene_text_box(reset_gene ? '' : inst_gene)
}

export const make_bar_graph = (bar_container, click_callback, svg_bar, bar_data, color_dict, deck_ist, layers_obj, viz_state) => {

    bar_container.className = "bar_container"
    bar_container.style.width = "107px"
    bar_container.style.height = "72px"
    bar_container.style.marginLeft = '5px'
    bar_container.style.overflowY = "auto"
    bar_container.style.border = "1px solid #d3d3d3"

    bar_container.addEventListener('wheel', (event) => {
        const { scrollTop, scrollHeight, clientHeight } = bar_container
        const atTop = scrollTop === 0
        const atBottom = scrollTop + clientHeight === scrollHeight

        if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
            event.preventDefault()
        }
    })

    const bar_height = 15
    const svg_height = bar_height * (bar_data.length + 1)

    svg_bar
        .attr("width", 100)
        .attr("height", svg_height)
        .attr("font-family", "sans-serif")
        .attr("font-size", "13")
        .attr("text-anchor", "end")
        .style("user-select", "none")

    bar_container.appendChild(svg_bar.node())

    let max_bar_width = 90
    let bar_data_values = bar_data.map(x => x.value)

    let y_new = d3.scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, (bar_height + 1) * bar_data_values.length])

    let x_new = d3.scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, max_bar_width])

    const bar = svg_bar.selectAll("g")
        .data(bar_data)
        .join("g")
        .attr("transform", (d, i) => `translate(2,${y_new(i) + 2})`)
        .on('click', (event, d) => click_callback(event, d, deck_ist, layers_obj, viz_state))

    bar.append("rect")
        .attr("fill", (d) => {
            const inst_rgb = color_dict[d.name]
            const inst_color = `rgb(${inst_rgb[0]}, ${inst_rgb[1]}, ${inst_rgb[2]})`
            return inst_color
        })
        .attr("width", d => x_new(d.value))
        .attr("height", y_new.bandwidth() - 1)

    bar.append("text")
        .attr("fill", 'black')
        .attr("x", '5px')
        .attr("y", y_new.bandwidth() / 2 - 1)
        .attr("dy", "0.35em")
        .attr('text-anchor', 'start')
        .text(d => d.name)
}

export const update_bar_graph = (svg_bar, bar_data, color_dict, click_callback, selected_array, deck_ist, layers_obj, viz_state) => {

    const bar_height = 15;
    const svg_height = bar_height * (bar_data.length + 1);

    svg_bar.attr("height", svg_height);

    const max_bar_width = 90;
    const bar_data_values = bar_data.map(x => x.value);

    const y_new = d3.scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, (bar_height + 1) * bar_data_values.length]);

    const x_new = d3.scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, max_bar_width]);

    const bars = svg_bar.selectAll("g")
        .data(bar_data, d => d.name);

    // Enter new bars
    const bars_enter = bars.enter().append("g")
        .attr("transform", (d, i) => `translate(2,${y_new(i) + 2})`)
        .on('click', (event, d) => click_callback(event, d, deck_ist, layers_obj, viz_state))

    bars_enter.append("rect")
        .attr("width", 0) // Initial width set to 0 for transition effect
        .attr("height", y_new.bandwidth() - 1)
        .transition() // Transition for entering elements
        .duration(750)
        .attr("width", d => x_new(d.value));

    bars_enter.append("text")
        .attr("fill", 'black')
        .attr("x", '5px')
        .attr("y", y_new.bandwidth() / 2 - 1) // Adjust this value to push the text up
        .attr("dy", "0.35em")
        .attr('text-anchor', 'start')
        .text(d => d.name)
        .attr("opacity", 0) // Initial opacity set to 0 for transition effect
        .transition() // Transition for entering elements
        .duration(750)
        .attr("opacity", 1);

    // Merge the enter and update selections
    const bars_merged = bars.merge(bars_enter);

    // Update existing bars
    bars_merged.transition() // Transition for updating elements
        .duration(750)
        .attr("transform", (d, i) => `translate(2,${y_new(i) + 2})`);

    bars_merged.select("rect")
        .attr("width", d => x_new(d.value))
        .attr("fill", d => {
            const inst_rgb = color_dict[d.name] || [0, 0, 0]; // Default to black if not in color_dict
            const inst_opacity = selected_array.length === 0 || selected_array.includes(d.name) ? 1 : 0.1;
            return `rgba(${inst_rgb[0]}, ${inst_rgb[1]}, ${inst_rgb[2]}, ${inst_opacity})`;
        });

    bars_merged.select("text")
        .text(d => d.name);

    // Remove old bars
    bars.exit().transition() // Transition for exiting elements
        .duration(750)
        .attr("opacity", 0)
        .remove();
}
