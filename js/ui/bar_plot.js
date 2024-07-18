import * as d3 from 'd3'

export let bar_plot_container

const bar_data = [
    {name: 'one', value: 10},
    {name: 'two', value: 20},
    {name: 'three', value: 30},
    {name: 'four', value: 40},
    {name: 'five', value: 50},
    {name: 'six', value: 60},
    {name: 'seven', value: 70},
    {name: 'eight', value: 80},
    {name: 'nine', value: 90},
    {name: 'ten', value: 100}
]

bar_data.sort((a, b) => b.value - a.value)

export const make_bar_plot = () => {
    console.log('here!!!')

    bar_plot_container = document.createElement("div")
    bar_plot_container.className = "bar_plot_container"
    bar_plot_container.style.width = "107px" // Set a fixed width for the container
    bar_plot_container.style.height = "50px" // Set a fixed height for the container
    bar_plot_container.style.marginLeft = '5px'
    bar_plot_container.style.overflowY = "auto" // Enable vertical scrolling
    bar_plot_container.style.border = "1px solid #d3d3d3" // Optional: Add a border for better visualization

    // Calculate the total height needed for the SVG based on data length
    const bar_height = 14
    const svg_height = bar_height * ( bar_data.length + 1)

    const svg = d3.create("svg")
        .attr("width", 120) // Slightly larger width to accommodate text
        .attr("height", svg_height)
        .attr("font-family", "sans-serif")
        .attr("font-size", "12")
        .attr("text-anchor", "end")
        .style("user-select", "none")

    bar_plot_container.appendChild(svg.node())

    let max_bar_width = 100

    let bar_data_values = bar_data.map(x => x.value)

    let y_new = d3.scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, (bar_height + 1) * bar_data_values.length])

    let x_new = d3.scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, max_bar_width])

    const bar = svg.selectAll("g")
        .data(bar_data)
        .join("g")
        .attr("transform", (d, i) => `translate(0,${y_new(i)})`)
        .on('click', (event, d) => {
            const currentTarget = d3.select(event.currentTarget)
            const isBold = currentTarget.attr('font-weight') === 'bold'

            // Reset all bars to normal weight
            svg.selectAll("g").attr('font-weight', 'normal')

            // Toggle the clicked bar
            if (!isBold) {
                currentTarget.attr('font-weight', 'bold')
            } else {
                currentTarget.attr('font-weight', 'normal')
            }
        })

    bar.append("rect")
        .attr("fill", "steelblue")
        .attr('opacity', 0.25)
        .attr("width", d => x_new(d.value))
        .attr("height", y_new.bandwidth() - 1)

    bar.append("text")
        .attr("fill", 'black')
        .attr("x", '5px')
        .attr("y", y_new.bandwidth() / 2)
        .attr("dy", "0.35em")
        .attr('text-anchor', 'start')
        .text(d => d.name)

    // Ensure the container is appended to the DOM
    document.body.appendChild(bar_plot_container) // Or append it to your desired parent container
}
