import * as d3 from 'd3'

export let bar_plot_container

export const make_bar_plot = () => {

    console.log('here!!!')

    bar_plot_container = document.createElement("div")
    bar_plot_container.className = "bar_plot_container"

    const svg = d3.create("svg")
        .attr("width", 100)
        .attr("height", 100)
        .attr("font-family", "sans-serif")
        .attr("font-size", "16")
        .attr("text-anchor", "end");

    bar_plot_container.appendChild(svg.node())

    // // initialized
    // svg.property('value', {
    // 'term_name': 'Select Term',
    // 'term_genes': []
    // })

    const bar_data = [
        {name: 'one', value: 10},
        {name: 'two', value: 20},
        {name: 'three', value: 30},
    ]

    let max_bar_width = 100

    let bar_data_values = bar_data.map(x => x.value)

    let y_new = d3.scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, 22 * bar_data_values.length])

    let x_new = d3.scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, max_bar_width])

    const bar = svg.selectAll("g")
    .data(bar_data)
    .join("g")
        .attr("transform", (d, i) => `translate(0,${y_new(i)})`)
        .on('click', (event, d) => {

            console.log(d)

            svg.selectAll("g")
                .attr('font-weight', 'normal')

            // d3.select(this)
            d3.select(event.currentTarget)
                .attr('font-weight', 'bold')
        })

    bar.append("rect")
        .attr("fill", "steelblue")
        .attr('opacity', 0.25)
        .attr("width", function(d){return x_new(d.value)})
        .attr("height", y_new.bandwidth() - 1);

    bar.append("text")
        .attr("fill", 'black')
        //.attr("x", d => x_new(d.value) - 3)
        .attr("x", '5px')
        .attr("y", y_new.bandwidth() / 2)
        .attr("dy", "0.35em")
        .attr('text-anchor', 'start')
        .text(d => d.name);

}