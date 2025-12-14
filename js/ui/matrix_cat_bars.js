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
  container.style.gap = '8px';
  container.style.marginTop = '5px';
  container.style.marginLeft = '10px';
  container.style.maxHeight = '100px';
  container.style.overflow = 'hidden';
  return container;
};

/**
 * Create a single category bar graph for an axis.
 */
const make_axis_cat_bar = (axis, entity_name, on_click) => {
  const wrapper = document.createElement('div');
  wrapper.className = `cat-bar-wrapper-${axis}`;
  wrapper.style.display = 'flex';
  wrapper.style.flexDirection = 'column';
  wrapper.style.width = '95px';

  // Title - use entity name if available
  const title = document.createElement('div');
  title.className = `cat-bar-title-${axis}`;
  title.textContent = entity_name || axis.toUpperCase();
  title.style.fontSize = '10px';
  title.style.fontWeight = 'bold';
  title.style.marginBottom = '2px';
  title.style.whiteSpace = 'nowrap';
  title.style.overflow = 'hidden';
  title.style.textOverflow = 'ellipsis';
  title.style.textTransform = 'capitalize';
  wrapper.appendChild(title);

  // Bar container
  const bar_container = document.createElement('div');
  bar_container.className = `cat-bar-graph-${axis}`;
  bar_container.style.width = '95px';
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
    .attr('width', 90)
    .attr('font-family', 'sans-serif')
    .attr('font-size', '11')
    .attr('text-anchor', 'end')
    .style('user-select', 'none');

  bar_container.appendChild(svg.node());

  return { wrapper, bar_container, svg, title };
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
 * Compute initial category breakdown for all nodes (no filter).
 * Uses the first categorical attribute for each axis.
 */
const compute_initial_breakdown = (viz_state, axis) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const cats = viz_state.attr?.cats?.[axis] || [];

  // Use first categorical attribute if available
  if (cats.length === 0 || !nodes || nodes.length === 0) {
    return null;
  }

  const first_cat = cats[0];
  const attr_names = viz_state.attr?.names?.[axis] || [];
  const attr_index = attr_names.indexOf(first_cat);

  if (attr_index < 0) return null;

  const cat_key = `cat-${attr_index}`;
  const counts = {};

  nodes.forEach((node) => {
    const value = node[cat_key];
    if (value !== undefined && value !== null) {
      counts[value] = (counts[value] || 0) + 1;
    }
  });

  // Convert to sorted array
  const breakdown_array = Object.entries(counts)
    .map(([name, count]) => ({ name, value: count }))
    .sort((a, b) => b.value - a.value);

  return {
    attr_name: first_cat,
    attr_index,
    data: breakdown_array,
  };
};

/**
 * Compute filtered category breakdown for selected nodes.
 */
const compute_filtered_breakdown = (viz_state, axis, selected_names) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  const cats = viz_state.attr?.cats?.[axis] || [];

  if (cats.length === 0 || !nodes || nodes.length === 0) {
    return null;
  }

  const first_cat = cats[0];
  const attr_names = viz_state.attr?.names?.[axis] || [];
  const attr_index = attr_names.indexOf(first_cat);

  if (attr_index < 0) return null;

  const selected_set = new Set(selected_names);
  const selected_nodes = nodes.filter((node) => selected_set.has(node.name));

  const cat_key = `cat-${attr_index}`;
  const counts = {};

  selected_nodes.forEach((node) => {
    const value = node[cat_key];
    if (value !== undefined && value !== null) {
      counts[value] = (counts[value] || 0) + 1;
    }
  });

  const breakdown_array = Object.entries(counts)
    .map(([name, count]) => ({ name, value: count }))
    .sort((a, b) => b.value - a.value);

  return {
    attr_name: first_cat,
    attr_index,
    data: breakdown_array,
  };
};

/**
 * Get entity display name for an axis.
 */
const get_entity_display_name = (viz_state, axis) => {
  const entity_info =
    axis === 'row' ? viz_state.row_entity : viz_state.col_entity;

  if (entity_info && entity_info.entity) {
    // Capitalize and format nicely
    const entity = entity_info.entity;
    const attr = entity_info.attr;

    if (attr && attr !== 'name') {
      return `${entity} (${attr})`;
    }
    return entity;
  }

  return axis.toUpperCase();
};

/**
 * Initialize the matrix category bar UI.
 * Creates containers for row and column category breakdowns.
 * Bar graphs are always shown when categories are available.
 */
export const init_matrix_cat_bars = (viz_state, ui_container) => {
  // Check if there are categorical attributes
  const row_cats = viz_state.attr?.cats?.row || [];
  const col_cats = viz_state.attr?.cats?.col || [];

  if (row_cats.length === 0 && col_cats.length === 0) {
    // No categories to show
    return null;
  }

  // Create main container
  const cat_bars_container = make_matrix_cat_bar_container();

  // Store references
  viz_state.cat_bars = {
    container: cat_bars_container,
    row: null,
    col: null,
  };

  // Create row bar if categories exist
  if (row_cats.length > 0) {
    const entity_name = get_entity_display_name(viz_state, 'row');
    const { wrapper, svg, title } = make_axis_cat_bar('row', entity_name);
    cat_bars_container.appendChild(wrapper);

    viz_state.cat_bars.row = { wrapper, svg, title };

    // Compute and display initial breakdown
    const initial = compute_initial_breakdown(viz_state, 'row');
    if (initial && initial.data.length > 0) {
      const color_dict = get_color_dict(viz_state);
      update_cat_bar_graph(svg, initial.data, color_dict, (d) => {
        if (viz_state.obs_store?.selected_category) {
          viz_state.obs_store.selected_category.set({
            axis: 'row',
            attr_name: initial.attr_name,
            attr_index: initial.attr_index,
            value: d.name,
          });
        }
      });
    }
  }

  // Create col bar if categories exist
  if (col_cats.length > 0) {
    const entity_name = get_entity_display_name(viz_state, 'col');
    const { wrapper, svg, title } = make_axis_cat_bar('col', entity_name);
    cat_bars_container.appendChild(wrapper);

    viz_state.cat_bars.col = { wrapper, svg, title };

    // Compute and display initial breakdown
    const initial = compute_initial_breakdown(viz_state, 'col');
    if (initial && initial.data.length > 0) {
      const color_dict = get_color_dict(viz_state);
      update_cat_bar_graph(svg, initial.data, color_dict, (d) => {
        if (viz_state.obs_store?.selected_category) {
          viz_state.obs_store.selected_category.set({
            axis: 'col',
            attr_name: initial.attr_name,
            attr_index: initial.attr_index,
            value: d.name,
          });
        }
      });
    }
  }

  // Subscribe to dendro selection changes
  if (viz_state.obs_store?.dendro_selection) {
    viz_state.obs_store.dendro_selection.subscribe(
      (selection) => {
        update_cat_bars_on_selection(viz_state, selection);
      },
      { immediate: false }
    );
  }

  // Append to UI container
  ui_container.appendChild(cat_bars_container);

  return cat_bars_container;
};

/**
 * Get color dictionary from viz_state.
 */
const get_color_dict = (viz_state) => {
  const colors = viz_state.attr?.category_colors || {};
  const rgb_colors = {};

  Object.entries(colors).forEach(([key, value]) => {
    if (typeof value === 'string' && value.startsWith('#')) {
      const hex = value.replace('#', '');
      rgb_colors[key] = [
        parseInt(hex.substring(0, 2), 16),
        parseInt(hex.substring(2, 4), 16),
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

/**
 * Update category bar graphs when dendro selection changes.
 */
const update_cat_bars_on_selection = (viz_state, selection) => {
  const color_dict = get_color_dict(viz_state);

  if (!selection) {
    // Reset to full breakdown
    ['row', 'col'].forEach((axis) => {
      if (viz_state.cat_bars?.[axis]) {
        const initial = compute_initial_breakdown(viz_state, axis);
        if (initial && initial.data.length > 0) {
          update_cat_bar_graph(
            viz_state.cat_bars[axis].svg,
            initial.data,
            color_dict,
            (d) => {
              if (viz_state.obs_store?.selected_category) {
                viz_state.obs_store.selected_category.set({
                  axis,
                  attr_name: initial.attr_name,
                  attr_index: initial.attr_index,
                  value: d.name,
                });
              }
            }
          );

          // Update title to show full count
          const entity_name = get_entity_display_name(viz_state, axis);
          viz_state.cat_bars[axis].title.textContent = entity_name;
        }
      }
    });
    return;
  }

  // Update the bar for the selected axis
  const { axis, selected_names } = selection;

  if (viz_state.cat_bars?.[axis]) {
    const filtered = compute_filtered_breakdown(viz_state, axis, selected_names);
    if (filtered && filtered.data.length > 0) {
      update_cat_bar_graph(
        viz_state.cat_bars[axis].svg,
        filtered.data,
        color_dict,
        (d) => {
          if (viz_state.obs_store?.selected_category) {
            viz_state.obs_store.selected_category.set({
              axis,
              attr_name: filtered.attr_name,
              attr_index: filtered.attr_index,
              value: d.name,
            });
          }
        }
      );

      // Update title to show filtered count
      const entity_name = get_entity_display_name(viz_state, axis);
      const total = filtered.data.reduce((sum, d) => sum + d.value, 0);
      viz_state.cat_bars[axis].title.textContent = `${entity_name} (${total})`;
    }
  }
};

