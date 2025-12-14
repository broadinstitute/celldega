import * as d3 from 'd3';

/**
 * Create a container for matrix category bar graphs.
 * Shows breakdown of categorical attributes for clustergram rows/cols.
 */
export const make_matrix_cat_bar_container = () => {
  const container = document.createElement('div');
  container.className = 'matrix-cat-bar-container';
  container.style.display = 'flex';
  container.style.flexDirection = 'row';
  container.style.gap = '10px';
  container.style.marginTop = '5px';
  container.style.maxHeight = '100px';
  container.style.overflow = 'hidden';
  return container;
};

/**
 * Create a single category bar graph for an attribute.
 */
const make_single_cat_bar = (
  attr_name,
  breakdown_data,
  color_dict,
  on_click
) => {
  const wrapper = document.createElement('div');
  wrapper.className = 'cat-bar-wrapper';
  wrapper.style.display = 'flex';
  wrapper.style.flexDirection = 'column';
  wrapper.style.width = '100px';

  // Title
  const title = document.createElement('div');
  title.textContent = attr_name;
  title.style.fontSize = '10px';
  title.style.fontWeight = 'bold';
  title.style.marginBottom = '2px';
  title.style.whiteSpace = 'nowrap';
  title.style.overflow = 'hidden';
  title.style.textOverflow = 'ellipsis';
  wrapper.appendChild(title);

  // Bar container
  const bar_container = document.createElement('div');
  bar_container.className = 'cat-bar-graph';
  bar_container.style.width = '100px';
  bar_container.style.height = '72px';
  bar_container.style.overflowY = 'auto';
  bar_container.style.border = '1px solid #d3d3d3';
  wrapper.appendChild(bar_container);

  // Prevent scroll propagation
  bar_container.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } = bar_container;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  const svg = d3
    .create('svg')
    .attr('width', 95)
    .attr('font-family', 'sans-serif')
    .attr('font-size', '11')
    .attr('text-anchor', 'end')
    .style('user-select', 'none');

  bar_container.appendChild(svg.node());

  update_cat_bar_graph(svg, breakdown_data, color_dict, on_click);

  return { wrapper, svg };
};

/**
 * Update a category bar graph with new data.
 */
const update_cat_bar_graph = (svg, breakdown_data, color_dict, on_click) => {
  const bar_height = 14;
  const max_bar_width = 85;
  const svg_height = bar_height * (breakdown_data.length + 1);

  svg.attr('height', svg_height);

  const values = breakdown_data.map((d) => d.value);

  const y_scale = d3
    .scaleBand()
    .domain(d3.range(values.length))
    .range([0, (bar_height + 1) * values.length]);

  const x_scale = d3
    .scaleLinear()
    .domain([0, d3.max(values) || 1])
    .range([0, max_bar_width]);

  const bars = svg.selectAll('g').data(breakdown_data, (d) => d.name);

  // Enter
  const bars_enter = bars
    .enter()
    .append('g')
    .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`)
    .style('cursor', on_click ? 'pointer' : 'default')
    .on('click', (event, d) => {
      if (on_click) {
        on_click(d);
      }
    });

  bars_enter
    .append('rect')
    .attr('fill', (d) => {
      const rgb = color_dict?.[d.name] || [100, 100, 100];
      if (Array.isArray(rgb)) {
        return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
      }
      return rgb;
    })
    .attr('width', 0)
    .attr('height', y_scale.bandwidth() - 1)
    .transition()
    .duration(300)
    .attr('width', (d) => x_scale(d.value));

  bars_enter
    .append('text')
    .attr('fill', 'black')
    .attr('x', '3px')
    .attr('y', y_scale.bandwidth() / 2 - 1)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'start')
    .text((d) => `${d.name} (${d.value})`);

  // Update
  const bars_merged = bars.merge(bars_enter);

  bars_merged
    .transition()
    .duration(300)
    .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`);

  bars_merged
    .select('rect')
    .transition()
    .duration(300)
    .attr('width', (d) => x_scale(d.value))
    .attr('fill', (d) => {
      const rgb = color_dict?.[d.name] || [100, 100, 100];
      if (Array.isArray(rgb)) {
        return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
      }
      return rgb;
    });

  bars_merged.select('text').text((d) => `${d.name} (${d.value})`);

  // Exit
  bars.exit().transition().duration(300).attr('opacity', 0).remove();
};

/**
 * Initialize the matrix category bar UI.
 * Creates containers for row and column category breakdowns.
 */
export const init_matrix_cat_bars = (viz_state, ui_container) => {
  // Create main container
  const cat_bars_container = make_matrix_cat_bar_container();

  // Create row section
  const row_section = document.createElement('div');
  row_section.className = 'cat-bars-row-section';
  row_section.style.display = 'none'; // Hidden until dendro click

  const row_title = document.createElement('div');
  row_title.textContent = 'Row Categories';
  row_title.style.fontSize = '11px';
  row_title.style.fontWeight = 'bold';
  row_title.style.marginBottom = '3px';
  row_section.appendChild(row_title);

  const row_bars_container = document.createElement('div');
  row_bars_container.className = 'row-bars-container';
  row_bars_container.style.display = 'flex';
  row_bars_container.style.flexDirection = 'row';
  row_bars_container.style.gap = '5px';
  row_section.appendChild(row_bars_container);

  // Create col section
  const col_section = document.createElement('div');
  col_section.className = 'cat-bars-col-section';
  col_section.style.display = 'none'; // Hidden until dendro click

  const col_title = document.createElement('div');
  col_title.textContent = 'Col Categories';
  col_title.style.fontSize = '11px';
  col_title.style.fontWeight = 'bold';
  col_title.style.marginBottom = '3px';
  col_section.appendChild(col_title);

  const col_bars_container = document.createElement('div');
  col_bars_container.className = 'col-bars-container';
  col_bars_container.style.display = 'flex';
  col_bars_container.style.flexDirection = 'row';
  col_bars_container.style.gap = '5px';
  col_section.appendChild(col_bars_container);

  cat_bars_container.appendChild(row_section);
  cat_bars_container.appendChild(col_section);

  // Store references
  viz_state.cat_bars = {
    container: cat_bars_container,
    row_section,
    row_bars_container,
    col_section,
    col_bars_container,
    bar_svgs: { row: {}, col: {} },
  };

  // Subscribe to category breakdown changes
  if (viz_state.obs_store?.category_breakdown) {
    viz_state.obs_store.category_breakdown.subscribe(
      (breakdown) => {
        update_matrix_cat_bars(viz_state, breakdown);
      },
      { immediate: false }
    );
  }

  // Append to UI container
  ui_container.appendChild(cat_bars_container);

  return cat_bars_container;
};

/**
 * Update the matrix category bar graphs with new breakdown data.
 */
const update_matrix_cat_bars = (viz_state, breakdown) => {
  const { row_section, row_bars_container, col_section, col_bars_container } =
    viz_state.cat_bars;

  // Get color dictionaries from viz_state
  const get_color_dict = (axis) => {
    const colors = viz_state.attr?.category_colors || {};
    // Convert hex colors to RGB arrays if needed
    const rgb_colors = {};
    Object.entries(colors).forEach(([key, value]) => {
      if (typeof value === 'string' && value.startsWith('#')) {
        // Convert hex to RGB
        const hex = value.replace('#', '');
        rgb_colors[key] = [
          parseInt(hex.substring(0, 2), 16),
          parseInt(hex.substring(1, 2) + hex.substring(2, 4), 16),
          parseInt(hex.substring(4, 6), 16),
        ];
      } else if (Array.isArray(value)) {
        rgb_colors[key] = value;
      } else {
        rgb_colors[key] = [100, 100, 100];
      }
    });
    return rgb_colors;
  };

  // Update row bars
  const row_breakdown = breakdown?.row || {};
  const row_attrs = Object.keys(row_breakdown);

  if (row_attrs.length > 0) {
    row_section.style.display = 'block';
    row_bars_container.innerHTML = '';

    const color_dict = get_color_dict('row');

    row_attrs.forEach((attr_name) => {
      const { wrapper, svg } = make_single_cat_bar(
        attr_name,
        row_breakdown[attr_name],
        color_dict,
        (d) => {
          // Click callback - could filter or highlight
          if (viz_state.obs_store?.selected_category) {
            viz_state.obs_store.selected_category.set({
              axis: 'row',
              attr_name,
              value: d.name,
            });
          }
        }
      );
      row_bars_container.appendChild(wrapper);
      viz_state.cat_bars.bar_svgs.row[attr_name] = svg;
    });
  } else {
    row_section.style.display = 'none';
  }

  // Update col bars
  const col_breakdown = breakdown?.col || {};
  const col_attrs = Object.keys(col_breakdown);

  if (col_attrs.length > 0) {
    col_section.style.display = 'block';
    col_bars_container.innerHTML = '';

    const color_dict = get_color_dict('col');

    col_attrs.forEach((attr_name) => {
      const { wrapper, svg } = make_single_cat_bar(
        attr_name,
        col_breakdown[attr_name],
        color_dict,
        (d) => {
          // Click callback
          if (viz_state.obs_store?.selected_category) {
            viz_state.obs_store.selected_category.set({
              axis: 'col',
              attr_name,
              value: d.name,
            });
          }
        }
      );
      col_bars_container.appendChild(wrapper);
      viz_state.cat_bars.bar_svgs.col[attr_name] = svg;
    });
  } else {
    col_section.style.display = 'none';
  }
};
