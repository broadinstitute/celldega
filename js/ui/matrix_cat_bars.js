import * as d3 from 'd3';

import {
  get_layer_update_triggers,
  get_mat_layers_list,
} from '../deck-gl/matrix/matrix_layers';
import {
  crop_fade_signature,
  crop_filter_signature,
  has_crop_filter,
  is_axis_index_visible,
} from '../matrix/crop_filter';

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
const make_axis_cat_bar = (axis, entity_name, _on_click) => {
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
const update_cat_bar_graph = (
  svg,
  breakdown_data,
  color_dict,
  on_click,
  on_hover,
  on_hover_out
) => {
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
    .attr('class', 'cat-bar-item')
    .attr('data-name', (d) => d.name)
    .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`)
    .style('cursor', on_click ? 'pointer' : 'default')
    .on('click', (event, d) => {
      if (on_click) {
        on_click(d);
      }
    })
    .on('mouseenter', (event, d) => {
      if (on_hover) {
        on_hover(d);
      }
    })
    .on('mouseleave', (event, d) => {
      if (on_hover_out) {
        on_hover_out(d);
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

  // Add hover handlers to existing bars
  bars_merged
    .on('mouseenter', (event, d) => {
      if (on_hover) {
        on_hover(d);
      }
    })
    .on('mouseleave', (event, d) => {
      if (on_hover_out) {
        on_hover_out(d);
      }
    });

  // Exit
  bars.exit().transition().duration(300).attr('opacity', 0).remove();
};

/**
 * Update bar opacity based on hovered category.
 * If a category is hovered, matching bars stay at full opacity,
 * all other bars become very transparent.
 */
const update_bar_hover_state = (viz_state, hovered_name) => {
  ['row', 'col'].forEach((axis) => {
    const svg = viz_state.cat_bars?.[axis]?.svg;
    if (!svg) return;

    svg.selectAll('.cat-bar-item').each(function (d) {
      const group = d3.select(this);
      const rect = group.select('rect');
      const text = group.select('text');

      // Convert both to strings for comparison to handle type mismatches
      const bar_name = String(d.name);
      const hover_name = hovered_name != null ? String(hovered_name) : null;

      if (!hover_name) {
        // No hover - restore full opacity by removing inline styles
        group.style('opacity', null);
        rect.style('opacity', null);
        text.style('opacity', null);
      } else if (bar_name === hover_name) {
        // Matching category - full opacity (explicitly set to override any transitions)
        group.style('opacity', '1');
        rect.style('opacity', '1');
        text.style('opacity', '1');
      } else {
        // Non-matching - very transparent
        group.style('opacity', '0.15');
        rect.style('opacity', '0.15');
        text.style('opacity', '0.15');
      }
    });
  });
};

/**
 * Trigger re-render of category tile layers to reflect hover state.
 */
const update_cat_tile_layers = (viz_state) => {
  const { deck_mat } = viz_state;
  const { layers_mat } = viz_state;

  if (!deck_mat || !layers_mat) return;

  // Clone layers with updated triggers to force re-render
  if (layers_mat.row_cat_layer) {
    layers_mat.row_cat_layer = layers_mat.row_cat_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.row_cat_layer),
        getFillColor: [
          crop_filter_signature(viz_state),
          crop_fade_signature(viz_state),
          viz_state.hovered_cat,
        ],
      },
    });
  }
  if (layers_mat.col_cat_layer) {
    layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
      updateTriggers: {
        ...get_layer_update_triggers(layers_mat.col_cat_layer),
        getFillColor: [
          crop_filter_signature(viz_state),
          crop_fade_signature(viz_state),
          viz_state.hovered_cat,
        ],
      },
    });
  }

  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

/**
 * Create hover handlers for bar graphs that sync with viz_state.hovered_cat.
 */
const create_bar_hover_handlers = (viz_state, axis, attr_index) => {
  const on_hover = (d) => {
    // Set hovered_cat on viz_state (for category tile highlighting)
    viz_state.hovered_cat = {
      axis,
      name: d.name,
      level: attr_index,
    };

    // Update bar graph opacities
    update_bar_hover_state(viz_state, d.name);

    // Update category tile layers in the Clustergram visualization
    update_cat_tile_layers(viz_state);

    // Update obs_store for any other listeners
    if (viz_state.obs_store?.hovered_category) {
      const attr_name = viz_state.attr.names[axis]?.[attr_index];
      viz_state.obs_store.hovered_category.set({
        axis,
        attr_name,
        attr_index,
        value: d.name,
      });
    }
  };

  const on_hover_out = () => {
    viz_state.hovered_cat = null;
    update_bar_hover_state(viz_state, null);

    // Update category tile layers
    update_cat_tile_layers(viz_state);

    if (viz_state.obs_store?.hovered_category) {
      viz_state.obs_store.hovered_category.set(null);
    }
  };

  return { on_hover, on_hover_out };
};

/**
 * Compute category breakdown from manual categories.
 */
export const compute_manual_category_breakdown = (viz_state, axis) => {
  const manual_store = viz_state.obs_store?.manual_cat?.[axis];
  if (!manual_store) return null;

  // ManualCategoryStore exposes `attribute` and `getValueFor(name)`.
  const attr_name =
    manual_store.attribute ||
    viz_state.manual_cat?.config?.[axis]?.attribute ||
    'Manual';

  // Count occurrences of each category value
  const counts = {};
  const nodes =
    (axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes) || [];
  nodes.forEach((node, index) => {
    if (!is_axis_index_visible(viz_state, axis, index)) return;

    const value = manual_store.getValueFor(node.name);
    if (value != null && value !== '') {
      const key = String(value);
      counts[key] = (counts[key] || 0) + 1;
    }
  });

  // Convert to array format
  const data = Object.entries(counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  return {
    attr_name,
    attr_index: 0,
    data,
  };
};

const MANUAL_SOURCE = '__manual__';

const BAR_FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

/**
 * Categorical sources a bar can show for an axis: each static categorical
 * attribute, plus the manual category once it exists.
 * @returns {Array<{value: string, label: string}>}
 */
const get_bar_sources = (viz_state, axis) => {
  const sources = (viz_state.attr?.cats?.[axis] || []).map((name) => ({
    value: name,
    label: name,
  }));
  const manual_store = viz_state.obs_store?.manual_cat?.[axis];
  const manual_name =
    manual_store?.attribute || viz_state.manual_cat?.config?.[axis]?.attribute;
  if (manual_store && (viz_state.manual_cat?.flags?.[axis] || manual_name)) {
    sources.push({ value: MANUAL_SOURCE, label: manual_name || 'manual' });
  }
  return sources;
};

/**
 * Count category values on an axis for one source, over visible nodes
 * (optionally only `selected_names`).
 */
const compute_breakdown = (viz_state, axis, source, selected_names = null) => {
  const nodes = axis === 'row' ? viz_state.row_nodes : viz_state.col_nodes;
  if (!source || !nodes || nodes.length === 0) return null;

  let attr_name;
  let attr_index;
  let value_of;
  if (source === MANUAL_SOURCE) {
    const breakdown = compute_manual_category_breakdown(viz_state, axis);
    if (!breakdown) return null;
    const manual_store = viz_state.obs_store.manual_cat[axis];
    ({ attr_name } = breakdown);
    attr_index = 0; // manual categories use index 0
    value_of = (node) => manual_store.getValueFor(node.name);
  } else {
    attr_index = (viz_state.attr?.names?.[axis] || []).indexOf(source);
    if (attr_index < 0) return null;
    attr_name = source;
    const cat_key = `cat-${attr_index}`;
    value_of = (node) => node[cat_key];
  }

  const selected_set = selected_names ? new Set(selected_names) : null;
  const counts = {};
  nodes.forEach((node, index) => {
    if (!is_axis_index_visible(viz_state, axis, index)) return;
    if (selected_set && !selected_set.has(node.name)) return;
    const value = value_of(node);
    if (value !== undefined && value !== null && value !== '') {
      counts[value] = (counts[value] || 0) + 1;
    }
  });

  const data = Object.entries(counts)
    .map(([name, count]) => ({ name, value: count }))
    .sort((x, y) => y.value - x.value);

  return { attr_name, attr_index, data };
};

/**
 * Redraw one axis's bar for its current source, honoring an active dendrogram
 * selection on that axis and showing a count while cropped or selected.
 */
const render_axis_cat_bar = (viz_state, axis) => {
  const bar = viz_state.cat_bars?.[axis];
  if (!bar?.svg) return;

  const selection = viz_state.obs_store?.dendro_selection?.get?.() || null;
  const selected_names =
    selection && selection.axis === axis ? selection.selected_names : null;
  const breakdown = compute_breakdown(
    viz_state,
    axis,
    bar.source,
    selected_names
  );
  if (!breakdown) return;

  const { on_hover, on_hover_out } = create_bar_hover_handlers(
    viz_state,
    axis,
    breakdown.attr_index
  );
  update_cat_bar_graph(
    bar.svg,
    breakdown.data,
    get_color_dict(viz_state),
    (d) => {
      viz_state.obs_store?.selected_category?.set({
        axis,
        attr_name: breakdown.attr_name,
        attr_index: breakdown.attr_index,
        value: d.name,
      });
    },
    on_hover,
    on_hover_out
  );

  const show_total = selected_names || has_crop_filter(viz_state);
  const total = breakdown.data.reduce((sum, d) => sum + d.value, 0);
  bar.count.textContent = show_total ? ` (${total})` : '';
};

/**
 * Replace a bar's static title with "ROW:" / "COL:" plus a dropdown of the
 * axis's categorical sources, styled like the order dropdown (bold, no arrow).
 */
const build_bar_title = (viz_state, axis) => {
  const bar = viz_state.cat_bars[axis];
  const { title } = bar;
  title.textContent = '';
  title.style.textTransform = 'none';
  title.style.display = 'flex';
  title.style.alignItems = 'baseline';
  title.style.fontFamily = BAR_FONT_FAMILY;

  const label = document.createElement('span');
  label.textContent = axis === 'row' ? 'ROW:' : 'COL:';
  label.style.marginRight = '3px';
  label.style.flexShrink = '0';

  const select = document.createElement('select');
  select.className = `cat-bar-source-${axis}`;
  select.title = 'Category';
  Object.assign(select.style, {
    appearance: 'none',
    webkitAppearance: 'none',
    MozAppearance: 'none',
    border: 'none',
    background: 'transparent',
    padding: '0',
    margin: '0',
    minWidth: '0',
    flex: '0 1 auto',
    textOverflow: 'ellipsis',
    fontFamily: BAR_FONT_FAMILY,
    fontSize: '10px',
    fontWeight: 'bold',
    color: viz_state.buttons?.text_active || '#2f74ff',
    cursor: 'pointer',
    outline: 'none',
  });
  select.addEventListener('change', () => {
    bar.source = select.value;
    render_axis_cat_bar(viz_state, axis);
  });

  const count = document.createElement('span');
  count.style.flexShrink = '0';

  title.appendChild(label);
  title.appendChild(select);
  title.appendChild(count);
  bar.select = select;
  bar.count = count;
};

/** Sync a bar's dropdown options (and selected value) with its sources. */
const sync_bar_sources = (viz_state, axis) => {
  const bar = viz_state.cat_bars?.[axis];
  if (!bar?.select) return;
  const sources = get_bar_sources(viz_state, axis);
  if (!sources.some((src) => src.value === bar.source)) {
    bar.source = sources[0]?.value ?? null;
  }
  bar.select.textContent = '';
  sources.forEach(({ value, label }) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    bar.select.appendChild(option);
  });
  bar.select.value = bar.source ?? '';
  // Blue marks a clickable picker; a single source is plain black text.
  const pickable = sources.length > 1;
  bar.select.style.pointerEvents = pickable ? 'auto' : 'none';
  bar.select.style.color = pickable
    ? viz_state.buttons?.text_active || '#2f74ff'
    : 'black';
};

/**
 * Initialize the matrix category bar UI.
 * Creates containers for row and column category breakdowns.
 * Bar graphs are always shown when categories are available or when manual categories are enabled.
 */
export const init_matrix_cat_bars = (viz_state, ui_container) => {
  // Check if there are categorical attributes
  const row_cats = viz_state.attr?.cats?.row || [];
  const col_cats = viz_state.attr?.cats?.col || [];

  // Check if manual categories are enabled
  const has_manual_row = viz_state.manual_cat?.flags?.row;
  const has_manual_col = viz_state.manual_cat?.flags?.col;

  // If no static categories and no manual categories, don't show anything
  if (
    row_cats.length === 0 &&
    col_cats.length === 0 &&
    !has_manual_row &&
    !has_manual_col
  ) {
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

  ['row', 'col'].forEach((axis) => {
    const has_static = (axis === 'row' ? row_cats : col_cats).length > 0;
    const has_manual = axis === 'row' ? has_manual_row : has_manual_col;
    if (!has_static && !has_manual) return;

    const { wrapper, svg, title, bar_container } = make_axis_cat_bar(
      axis,
      axis.toUpperCase()
    );
    cat_bars_container.appendChild(wrapper);
    viz_state.cat_bars[axis] = { wrapper, svg, title, bar_container };

    build_bar_title(viz_state, axis);
    sync_bar_sources(viz_state, axis);
    render_axis_cat_bar(viz_state, axis);
  });

  // Subscribe to dendro selection changes
  if (viz_state.obs_store?.dendro_selection) {
    viz_state.obs_store.dendro_selection.subscribe(
      (selection) => {
        update_cat_bars_on_selection(viz_state, selection);
      },
      { immediate: false }
    );
  }

  // Subscribe to hovered_category changes (from category tile hover)
  if (viz_state.obs_store?.hovered_category) {
    viz_state.obs_store.hovered_category.subscribe(
      (hovered) => {
        if (hovered) {
          update_bar_hover_state(viz_state, hovered.value);
        } else {
          update_bar_hover_state(viz_state, null);
        }
      },
      { immediate: false }
    );
  }

  // Manual edits switch that axis's bar to the manual category (so the user
  // sees their annotation take shape); the dropdown can switch back.
  if (viz_state.obs_store?.manual_cat) {
    ['row', 'col'].forEach((axis) => {
      const manual_store = viz_state.obs_store.manual_cat[axis];
      if (!manual_store) return;

      manual_store.subscribe(
        () => {
          const bar = viz_state.cat_bars?.[axis];
          if (!bar?.svg) return;
          const breakdown = compute_manual_category_breakdown(viz_state, axis);
          if (breakdown && breakdown.data.length > 0) {
            bar.source = MANUAL_SOURCE;
          }
          sync_bar_sources(viz_state, axis);
          render_axis_cat_bar(viz_state, axis);
        },
        { immediate: false }
      );
    });
  }

  // Append to UI container
  ui_container.appendChild(cat_bars_container);

  return cat_bars_container;
};

/**
 * Get color dictionary from viz_state.
 * Looks in multiple places for category colors:
 * 1. Attribute definitions (where colors are stored during static def building)
 * 2. Global category colors from network
 * 3. Fallback category colors
 */
function get_color_dict(viz_state) {
  const rgb_colors = {};

  // Helper to convert hex to RGB array
  const hexToRgb = (hex) => {
    if (!hex || typeof hex !== 'string') return null;
    const cleanHex = hex.replace('#', '');
    if (cleanHex.length !== 6) return null;
    return [
      parseInt(cleanHex.substring(0, 2), 16),
      parseInt(cleanHex.substring(2, 4), 16),
      parseInt(cleanHex.substring(4, 6), 16),
    ];
  };

  // Extract colors from attribute definitions (primary source)
  ['row', 'col'].forEach((axis) => {
    const all_defs = viz_state.attr?.all_defs?.[axis] || [];
    all_defs.forEach((def) => {
      if (def.type === 'categorical' && def.color_map) {
        Object.entries(def.color_map).forEach(([key, value]) => {
          if (rgb_colors[key]) return; // Don't override

          if (typeof value === 'string') {
            const rgb = hexToRgb(value);
            if (rgb) {
              rgb_colors[key] = rgb;
            }
          } else if (Array.isArray(value)) {
            rgb_colors[key] = value.slice(0, 3);
          }
        });
      }
    });
  });

  // Also check global_cat_colors from network (secondary source)
  const global_colors =
    viz_state.network?.global_cat_colors || viz_state.global_cat_colors || {};

  Object.entries(global_colors).forEach(([key, value]) => {
    if (rgb_colors[key]) return; // Don't override

    if (typeof value === 'string') {
      const rgb = hexToRgb(value);
      if (rgb) {
        rgb_colors[key] = rgb;
      }
    } else if (Array.isArray(value)) {
      rgb_colors[key] = value.slice(0, 3);
    }
  });

  return rgb_colors;
}

/**
 * Update category bar graphs when dendro selection changes.
 */
function update_cat_bars_on_selection(viz_state, _selection) {
  // render_axis_cat_bar reads the current dendro selection itself.
  ['row', 'col'].forEach((axis) => render_axis_cat_bar(viz_state, axis));
}

export const refresh_matrix_cat_bars = (viz_state) => {
  update_cat_bars_on_selection(
    viz_state,
    viz_state.obs_store?.dendro_selection?.get?.() || null
  );
};
