import * as d3 from 'd3';

import { get_total_pages } from '../deck-gl/core/yearbook_viewports';
import { toggle_background_layer_visibility } from '../deck-gl/layers/background_layer';
import { toggle_visibility_image_layers } from '../deck-gl/layers/image_layers';
import {
  uniprot_data,
  uniprot_get_request,
} from '../external_apis/uniprot_api';
import { debounce } from '../utils/debounce';
import { refresh_layer } from '../utils/refresh_layer';

import {
  make_bar_graph,
  bar_callback_cat,
  make_bar_container,
  bar_callback_gene,
} from './bar_plot';
import { set_gene_search } from './gene_search';
import { logo } from './logo';
import {
  make_img_layer_slider_callback,
  toggle_slider,
  ini_slider,
  ini_slider_params,
} from './sliders';
import { make_button } from './text_buttons';

// Counter for unique datalist IDs to prevent contamination between instances
let yearbook_datalist_counter = 0;

/**
 * Create the query UI box for searching cells by cluster and/or gene
 * @param {object} viz_state - Visualization state
 * @param {function} on_query_change - Callback when query changes
 * @returns {HTMLElement} Query container element
 */
const make_query_container = (viz_state, on_query_change) => {
  const container = document.createElement('div');
  container.className = 'query_container';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.marginLeft = '5px';
  container.style.marginTop = '3px';
  container.style.minWidth = '130px';
  container.style.maxWidth = '150px';

  // Title
  const title = document.createElement('div');
  title.textContent = 'Query Cells';
  title.style.fontSize = '11px';
  title.style.fontWeight = 'bold';
  title.style.color = '#47515b';
  title.style.marginBottom = '3px';
  title.style.fontFamily =
    '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';
  container.appendChild(title);

  // Cluster input row
  const cluster_row = document.createElement('div');
  cluster_row.style.display = 'flex';
  cluster_row.style.flexDirection = 'row';
  cluster_row.style.alignItems = 'center';
  cluster_row.style.marginBottom = '2px';

  const cluster_label = document.createElement('span');
  cluster_label.textContent = 'Cluster:';
  cluster_label.style.fontSize = '10px';
  cluster_label.style.width = '42px';
  cluster_label.style.color = '#555';
  cluster_row.appendChild(cluster_label);

  const cluster_input = document.createElement('input');
  cluster_input.type = 'text';
  cluster_input.placeholder = 'e.g. 5';
  cluster_input.style.width = '70px';
  cluster_input.style.height = '16px';
  cluster_input.style.fontSize = '11px';
  cluster_input.style.border = '1px solid #d3d3d3';
  cluster_input.style.borderRadius = '2px';
  cluster_input.style.padding = '1px 3px';

  // Create cluster datalist for autocomplete with unique ID
  yearbook_datalist_counter += 1;
  const instance_id = `${yearbook_datalist_counter}_${Date.now()}`;
  const cluster_datalist = document.createElement('datalist');
  cluster_datalist.id = `yearbook_cluster_datalist_${instance_id}`;
  cluster_input.setAttribute('list', cluster_datalist.id);

  // Populate with cluster names from cluster_counts
  if (viz_state.cats.cluster_counts) {
    viz_state.cats.cluster_counts.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.name;
      cluster_datalist.appendChild(option);
    });
  }

  cluster_row.appendChild(cluster_input);
  cluster_row.appendChild(cluster_datalist);
  container.appendChild(cluster_row);

  // Gene input row
  const gene_row = document.createElement('div');
  gene_row.style.display = 'flex';
  gene_row.style.flexDirection = 'row';
  gene_row.style.alignItems = 'center';
  gene_row.style.marginBottom = '3px';

  const gene_label = document.createElement('span');
  gene_label.textContent = 'Gene:';
  gene_label.style.fontSize = '10px';
  gene_label.style.width = '42px';
  gene_label.style.color = '#555';
  gene_row.appendChild(gene_label);

  const gene_input = document.createElement('input');
  gene_input.type = 'text';
  gene_input.placeholder = 'e.g. BRCA1';
  gene_input.style.width = '70px';
  gene_input.style.height = '16px';
  gene_input.style.fontSize = '11px';
  gene_input.style.border = '1px solid #d3d3d3';
  gene_input.style.borderRadius = '2px';
  gene_input.style.padding = '1px 3px';

  // Create gene datalist for autocomplete with unique ID
  const gene_datalist = document.createElement('datalist');
  gene_datalist.id = `yearbook_gene_datalist_${instance_id}`;
  gene_input.setAttribute('list', gene_datalist.id);

  // Populate with gene names
  if (viz_state.genes.gene_names) {
    viz_state.genes.gene_names.forEach((gene) => {
      const option = document.createElement('option');
      option.value = gene;
      gene_datalist.appendChild(option);
    });
  }

  gene_row.appendChild(gene_input);
  gene_row.appendChild(gene_datalist);
  container.appendChild(gene_row);

  // Query button
  const button_row = document.createElement('div');
  button_row.style.display = 'flex';
  button_row.style.flexDirection = 'row';
  button_row.style.gap = '5px';

  const query_button = document.createElement('button');
  query_button.textContent = 'Query';
  query_button.style.padding = '3px 10px';
  query_button.style.fontSize = '11px';
  query_button.style.cursor = 'pointer';
  query_button.style.border = '1px solid #8797ff';
  query_button.style.borderRadius = '3px';
  query_button.style.backgroundColor = '#8797ff';
  query_button.style.color = 'white';
  query_button.style.fontWeight = 'bold';

  query_button.onmouseenter = () => {
    query_button.style.backgroundColor = '#6677ee';
  };
  query_button.onmouseleave = () => {
    query_button.style.backgroundColor = '#8797ff';
  };

  const clear_button = document.createElement('button');
  clear_button.textContent = 'Clear';
  clear_button.style.padding = '3px 8px';
  clear_button.style.fontSize = '11px';
  clear_button.style.cursor = 'pointer';
  clear_button.style.border = '1px solid #d3d3d3';
  clear_button.style.borderRadius = '3px';
  clear_button.style.backgroundColor = '#f0f0f0';
  clear_button.style.color = '#555';

  // Build query object and trigger callback
  const execute_query = () => {
    const cluster_value = cluster_input.value.trim();
    const gene_value = gene_input.value.trim();

    // Validate inputs
    const valid_cluster =
      !cluster_value ||
      viz_state.cats.cluster_counts?.some((c) => c.name === cluster_value);
    const valid_gene =
      !gene_value || viz_state.genes.gene_names?.includes(gene_value);

    if (!valid_cluster) {
      cluster_input.style.borderColor = '#ff6666';
      return;
    } else {
      cluster_input.style.borderColor = '#d3d3d3';
    }

    if (!valid_gene) {
      gene_input.style.borderColor = '#ff6666';
      return;
    } else {
      gene_input.style.borderColor = '#d3d3d3';
    }

    // Build query object
    const query = {};

    if (cluster_value) {
      // Use the current cluster attribute (default to 'leiden')
      const cluster_attr = viz_state.cats.inst_cluster_attr || 'leiden';
      query.cluster = { attr: cluster_attr, value: cluster_value };
    }

    if (gene_value) {
      query.gene = gene_value;
    }

    // Only execute if at least one field is filled
    if (Object.keys(query).length > 0) {
      on_query_change(query);
    }
  };

  query_button.onclick = execute_query;

  // Allow Enter key to trigger query
  const on_enter = (event) => {
    if (event.key === 'Enter') {
      execute_query();
    }
  };
  cluster_input.addEventListener('keydown', on_enter);
  gene_input.addEventListener('keydown', on_enter);

  clear_button.onclick = () => {
    cluster_input.value = '';
    gene_input.value = '';
    cluster_input.style.borderColor = '#d3d3d3';
    gene_input.style.borderColor = '#d3d3d3';
  };

  button_row.appendChild(query_button);
  button_row.appendChild(clear_button);
  container.appendChild(button_row);

  // Status text (shows current query info)
  const status_text = document.createElement('div');
  status_text.className = 'query_status';
  status_text.style.fontSize = '10px';
  status_text.style.color = '#888';
  status_text.style.marginTop = '3px';
  status_text.style.maxHeight = '30px';
  status_text.style.overflow = 'hidden';
  status_text.style.textOverflow = 'ellipsis';
  container.appendChild(status_text);

  // Store references for external updates
  viz_state.yearbook.query_ui = {
    cluster_input,
    gene_input,
    status_text,
    update_status: (message) => {
      status_text.textContent = message;
    },
  };

  return container;
};

export const make_ui_container = () => {
  const ui_container = document.createElement('div');
  ui_container.style.display = 'flex';
  ui_container.style.flexDirection = 'row';
  ui_container.style.border = '1px solid #d3d3d3';
  ui_container.className = 'ui_container';
  ui_container.style.height = '100px';
  ui_container.style.boxSizing = 'border-box';
  ui_container.style.width = '100%';
  ui_container.style.maxWidth = '100%';
  ui_container.style.margin = '0 auto';

  return ui_container;
};

export const make_ctrl_container = () => {
  const ctrl_container = document.createElement('div');
  ctrl_container.style.display = 'flex';
  ctrl_container.style.flexDirection = 'row';
  ctrl_container.className = 'ctrl_container';
  ctrl_container.style.width = '100%';
  return ctrl_container;
};

export const flex_container = (class_name, flex_direction, height = null) => {
  const container = document.createElement('div');
  container.className = class_name;

  container.style.display = 'flex';
  container.style.flexDirection = flex_direction;

  if (height !== null) {
    container.style.height = `${height}px`;
    container.style.overflow = 'scroll';
  }

  return container;
};

export const make_slider_container = (class_name) => {
  const slider_container = document.createElement('div');
  slider_container.className = class_name;
  slider_container.style.width = '100%';
  slider_container.style.marginLeft = '2px';
  slider_container.style.marginTop = '2px';
  return slider_container;
};

/**
 * Create pagination controls for the yearbook
 */
const make_pagination_container = (viz_state, handle_page_change) => {
  const container = document.createElement('div');
  container.className = 'pagination_container';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'center';
  container.style.justifyContent = 'center';
  container.style.marginLeft = '10px';
  container.style.marginRight = '10px';
  container.style.minWidth = '100px';

  const { cells, num_rows, num_cols, current_page } = viz_state.yearbook;
  const total_pages = get_total_pages(cells.length, num_rows, num_cols);

  // Colors for quick nav buttons
  const active_color = '#8797ff'; // Blue when at position
  const inactive_color = 'gray'; // Gray when not at position

  // Page indicator
  const page_text = document.createElement('div');
  page_text.className = 'page_text';
  page_text.style.fontSize = '12px';
  page_text.style.fontWeight = 'bold';
  page_text.style.color = '#47515b';
  page_text.style.marginBottom = '5px';
  page_text.style.fontFamily =
    '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';
  page_text.textContent = `${current_page + 1} / ${total_pages}`;

  // Arrow button container
  const button_container = document.createElement('div');
  button_container.style.display = 'flex';
  button_container.style.flexDirection = 'row';
  button_container.style.gap = '5px';

  // Previous button
  const prev_button = document.createElement('button');
  prev_button.textContent = '◀';
  prev_button.style.padding = '4px 8px';
  prev_button.style.cursor = 'pointer';
  prev_button.style.border = '1px solid #d3d3d3';
  prev_button.style.borderRadius = '4px';
  prev_button.style.backgroundColor = current_page > 0 ? '#f0f0f0' : '#e0e0e0';
  prev_button.style.color = current_page > 0 ? '#333' : '#999';
  prev_button.disabled = current_page === 0;

  prev_button.onclick = () => {
    if (viz_state.yearbook.current_page > 0) {
      const new_page = viz_state.yearbook.current_page - 1;
      handle_page_change(new_page);
    }
  };

  // Next button
  const next_button = document.createElement('button');
  next_button.textContent = '▶';
  next_button.style.padding = '4px 8px';
  next_button.style.cursor = 'pointer';
  next_button.style.border = '1px solid #d3d3d3';
  next_button.style.borderRadius = '4px';
  next_button.style.backgroundColor =
    current_page < total_pages - 1 ? '#f0f0f0' : '#e0e0e0';
  next_button.style.color = current_page < total_pages - 1 ? '#333' : '#999';
  next_button.disabled = current_page >= total_pages - 1;

  next_button.onclick = () => {
    const _total_pages = get_total_pages(
      viz_state.yearbook.cells.length,
      viz_state.yearbook.num_rows,
      viz_state.yearbook.num_cols
    );
    if (viz_state.yearbook.current_page < _total_pages - 1) {
      const new_page = viz_state.yearbook.current_page + 1;
      handle_page_change(new_page);
    }
  };

  // Quick navigation button container (Start, Mid, End)
  const quick_nav_container = document.createElement('div');
  quick_nav_container.style.display = 'flex';
  quick_nav_container.style.flexDirection = 'row';
  quick_nav_container.style.gap = '8px';
  quick_nav_container.style.marginTop = '5px';

  // Helper to create quick nav text buttons
  const create_quick_nav_button = (label) => {
    const btn = document.createElement('span');
    btn.textContent = label;
    btn.style.fontSize = '11px';
    btn.style.fontWeight = 'bold';
    btn.style.cursor = 'pointer';
    btn.style.fontFamily =
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';
    btn.style.userSelect = 'none';
    return btn;
  };

  // Start button
  const start_button = create_quick_nav_button('START');
  start_button.style.color = current_page === 0 ? active_color : inactive_color;
  start_button.onclick = () => {
    if (viz_state.yearbook.current_page !== 0) {
      handle_page_change(0);
    }
  };

  // Mid button
  const mid_page = Math.floor((total_pages - 1) / 2);
  const mid_button = create_quick_nav_button('MID');
  mid_button.style.color =
    current_page === mid_page ? active_color : inactive_color;
  mid_button.onclick = () => {
    const _total_pages = get_total_pages(
      viz_state.yearbook.cells.length,
      viz_state.yearbook.num_rows,
      viz_state.yearbook.num_cols
    );
    const _mid_page = Math.floor((_total_pages - 1) / 2);
    if (viz_state.yearbook.current_page !== _mid_page) {
      handle_page_change(_mid_page);
    }
  };

  // End button
  const end_page = total_pages - 1;
  const end_button = create_quick_nav_button('END');
  end_button.style.color =
    current_page === end_page ? active_color : inactive_color;
  end_button.onclick = () => {
    const _total_pages = get_total_pages(
      viz_state.yearbook.cells.length,
      viz_state.yearbook.num_rows,
      viz_state.yearbook.num_cols
    );
    const _end_page = _total_pages - 1;
    if (viz_state.yearbook.current_page !== _end_page) {
      handle_page_change(_end_page);
    }
  };

  const update_pagination_ui = () => {
    const _total_pages = get_total_pages(
      viz_state.yearbook.cells.length,
      viz_state.yearbook.num_rows,
      viz_state.yearbook.num_cols
    );
    const _current_page = viz_state.yearbook.current_page;
    const _mid_page = Math.floor((_total_pages - 1) / 2);
    const _end_page = _total_pages - 1;

    page_text.textContent = `${_current_page + 1} / ${_total_pages}`;

    // Update arrow buttons
    prev_button.disabled = _current_page === 0;
    prev_button.style.backgroundColor =
      _current_page > 0 ? '#f0f0f0' : '#e0e0e0';
    prev_button.style.color = _current_page > 0 ? '#333' : '#999';

    next_button.disabled = _current_page >= _total_pages - 1;
    next_button.style.backgroundColor =
      _current_page < _total_pages - 1 ? '#f0f0f0' : '#e0e0e0';
    next_button.style.color =
      _current_page < _total_pages - 1 ? '#333' : '#999';

    // Update quick nav button colors
    start_button.style.color =
      _current_page === 0 ? active_color : inactive_color;
    mid_button.style.color =
      _current_page === _mid_page ? active_color : inactive_color;
    end_button.style.color =
      _current_page === _end_page ? active_color : inactive_color;
  };

  // Store update function in viz_state for external updates
  viz_state.yearbook.update_pagination_ui = update_pagination_ui;

  button_container.appendChild(prev_button);
  button_container.appendChild(next_button);

  quick_nav_container.appendChild(start_button);
  quick_nav_container.appendChild(mid_button);
  quick_nav_container.appendChild(end_button);

  container.appendChild(page_text);
  container.appendChild(button_container);
  container.appendChild(quick_nav_container);

  return container;
};

/**
 * Create the main UI container for the Yearbook widget
 * Similar to make_ist_ui_container but with pagination and query box
 */
export const make_yearbook_ui_container = (
  dataset_name,
  deck_yearbook,
  layers_obj,
  viz_state,
  handle_page_change,
  handle_query_change
) => {
  const ui_container = make_ui_container();
  const ctrl_container = make_ctrl_container();

  viz_state.containers.image = flex_container('image_container', 'column');

  const img_layers_container = flex_container(
    'img_layers_container',
    'column',
    72
  );
  img_layers_container.style.width = '135px';
  img_layers_container.style.border = '1px solid #d3d3d3';
  img_layers_container.style.marginTop = '3px';
  img_layers_container.style.marginLeft = '2px';

  img_layers_container.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } = img_layers_container;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  const bar_container_width = '115px';

  // Cell container
  const cell_container = flex_container('cell_container', 'column');
  cell_container.style.width = bar_container_width;
  const cell_ctrl_container = flex_container('cell_ctrl_container', 'row');
  cell_ctrl_container.style.marginLeft = '0px';

  // Gene container
  const gene_container = flex_container('gene_container', 'column');
  gene_container.style.marginTop = '0px';
  gene_container.style.width = bar_container_width;
  const trx_container = flex_container('trx_container', 'row');

  const cell_slider_container = make_slider_container('cell_slider_container');
  const trx_slider_container = make_slider_container('trx_slider_container');

  // Image layer toggle
  const spatial_toggle_container = flex_container(
    'image_layer_container',
    'row'
  );

  make_button(
    spatial_toggle_container,
    'ist',
    'IMG',
    'blue',
    30,
    'button',
    deck_yearbook,
    layers_obj,
    viz_state
  );

  viz_state.containers.image.appendChild(spatial_toggle_container);

  // Image layer sliders
  const get_slider_by_name = (img, name) => {
    return img.image_layer_sliders.filter((slider) => slider.name === name);
  };

  const make_img_layer_ctrl = (img, inst_image) => {
    const inst_name = inst_image.button_name;

    const inst_container = flex_container('image_layer_container', 'row');
    inst_container.style.height = '21px';

    make_button(
      inst_container,
      'ist',
      inst_name,
      'blue',
      75,
      'img_layer_button',
      deck_yearbook,
      layers_obj,
      viz_state
    );

    const inst_slider_container = make_slider_container(inst_name);
    const slider = get_slider_by_name(img, inst_name)[0];

    const img_layer_slider_callback = make_img_layer_slider_callback(
      inst_name,
      deck_yearbook,
      layers_obj,
      viz_state
    );

    const debounce_time = 100;
    const img_layer_slider_callback_debounced = debounce(
      img_layer_slider_callback,
      debounce_time
    );
    const ini_img_slider_value = 50;
    ini_slider_params(
      slider,
      ini_img_slider_value,
      img_layer_slider_callback_debounced
    );

    inst_slider_container.appendChild(slider);
    inst_container.appendChild(inst_slider_container);
    img_layers_container.appendChild(inst_container);
  };

  viz_state.img.image_info.map((inst_image) =>
    make_img_layer_ctrl(viz_state.img, inst_image)
  );

  // Subscribe to image layer visibility
  viz_state.obs_store.viz_image_layers.subscribe((viz_image_layers) => {
    d3.select(viz_state.containers.image)
      .selectAll('.img_layer_button')
      .style('color', viz_image_layers ? 'blue' : 'gray');

    viz_state.img.image_layer_sliders.map((slider) =>
      toggle_slider(slider, viz_image_layers)
    );

    toggle_visibility_image_layers(layers_obj, viz_image_layers);
    refresh_layer(viz_state, layers_obj, 'image_layers');
  });

  viz_state.obs_store.viz_background_layer.subscribe((visible) => {
    toggle_background_layer_visibility(layers_obj, visible);
    refresh_layer(viz_state, layers_obj, 'background_layer');
  });

  viz_state.containers.image.appendChild(img_layers_container);

  // Cell button
  make_button(
    cell_ctrl_container,
    'ist',
    'CELL',
    'blue',
    40,
    'button',
    deck_yearbook,
    layers_obj,
    viz_state
  );

  // TRX button
  make_button(
    trx_container,
    'ist',
    'TRX',
    'blue',
    40,
    'button',
    deck_yearbook,
    layers_obj,
    viz_state
  );

  viz_state.sliders = {};

  ini_slider('cell', deck_yearbook, layers_obj, viz_state);
  cell_slider_container.appendChild(viz_state.sliders.cell);
  cell_ctrl_container.appendChild(cell_slider_container);

  // Bar graphs
  viz_state.containers.bar_cluster = make_bar_container();
  viz_state.cats.svg_bar_cluster = d3.create('svg');
  viz_state.genes.svg_bar_gene = d3.create('svg');

  make_bar_graph(
    viz_state.containers.bar_cluster,
    bar_callback_cat,
    viz_state.cats.svg_bar_cluster,
    viz_state.cats.cluster_counts,
    viz_state.cats.color_dict_cluster,
    deck_yearbook,
    layers_obj,
    viz_state
  );

  viz_state.containers.bar_gene = make_bar_container();

  const max_num_gene_bars = 1000;
  viz_state.genes.gene_counts = viz_state.genes.gene_counts
    .sort((a, b) => b.value - a.value)
    .slice(0, max_num_gene_bars);

  make_bar_graph(
    viz_state.containers.bar_gene,
    bar_callback_gene,
    viz_state.genes.svg_bar_gene,
    viz_state.genes.top_gene_counts,
    viz_state.genes.color_dict_gene,
    deck_yearbook,
    layers_obj,
    viz_state
  );

  // Bar graph subscribers
  const make_bar_cat_subscriber = (svg, container) => {
    return (selected_cats) => {
      if (!Array.isArray(selected_cats) || selected_cats.length === 0) {
        svg.selectAll('g').attr('font-weight', 'normal').attr('opacity', 1.0);
        container.scrollTo({ top: 0, behavior: 'smooth' });
      } else {
        svg
          .selectAll('g')
          .attr('font-weight', (d) =>
            selected_cats.includes(d.name) ? 'bold' : 'normal'
          )
          .attr('opacity', (d) => (selected_cats.includes(d.name) ? 1.0 : 0.2));

        if (selected_cats.length === 1) {
          const inst_cat = selected_cats[0];
          const selectedBar = svg.selectAll('g').filter(function () {
            return d3.select(this).select('text').text() === inst_cat;
          });

          if (!selectedBar.empty()) {
            const barElement = selectedBar.node();
            const containerRect = container.getBoundingClientRect();
            const barRect = barElement.getBoundingClientRect();

            const barTop = barRect.top;
            const barBottom = barRect.bottom;
            const containerTop = containerRect.top;
            const containerBottom = containerRect.bottom;

            const barFullyVisible =
              barTop >= containerTop && barBottom <= containerBottom;

            if (!barFullyVisible) {
              const offsetTop = barTop - containerTop;
              const scrollTop = container.scrollTop + offsetTop;
              container.scrollTo({ top: scrollTop, behavior: 'smooth' });
            }
          }
        }
      }
    };
  };

  viz_state.obs_store.selected_cats.subscribe(
    make_bar_cat_subscriber(
      viz_state.cats.svg_bar_cluster,
      viz_state.containers.bar_cluster
    ),
    { immediate: false }
  );

  viz_state.obs_store.selected_genes.subscribe(
    make_bar_cat_subscriber(
      viz_state.genes.svg_bar_gene,
      viz_state.containers.bar_gene
    ),
    { immediate: false }
  );

  // New bar data subscriber (updates bars based on viewport)
  const subscriber_new_bar_data =
    ({ svg, color_dict, selected_array, bar_callback, container }) =>
    (bar_data) => {
      const bar_height = 15;
      const svg_height = bar_height * (bar_data.length + 1);
      svg.attr('height', svg_height);

      const max_bar_width = 90;
      const bar_data_values = bar_data.map((d) => d.value);

      const y_scale = d3
        .scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, (bar_height + 1) * bar_data_values.length]);

      const x_scale = d3
        .scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, max_bar_width]);

      const bars = svg.selectAll('g').data(bar_data, (d) => d.name);

      const bars_enter = bars
        .enter()
        .append('g')
        .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`)
        .on('click', (event, d) =>
          bar_callback(event, d, deck_yearbook, layers_obj, viz_state)
        );

      bars_enter
        .append('rect')
        .attr('width', 0)
        .attr('height', y_scale.bandwidth() - 1)
        .transition()
        .duration(750)
        .attr('width', (d) => x_scale(d.value));

      bars_enter
        .append('text')
        .attr('fill', 'black')
        .attr('x', '5px')
        .attr('y', y_scale.bandwidth() / 2 - 1)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'start')
        .attr('opacity', 0)
        .text((d) => d.name)
        .transition()
        .duration(750)
        .attr('opacity', 1);

      const bars_merged = bars.merge(bars_enter);

      bars_merged
        .transition()
        .duration(750)
        .attr('transform', (d, i) => `translate(2,${y_scale(i) + 2})`);

      bars_merged
        .select('rect')
        .attr('width', (d) => x_scale(d.value))
        .attr('fill', (d) => {
          const rgb = color_dict[d.name] || [0, 0, 0];
          const opacity =
            selected_array.length === 0 || selected_array.includes(d.name)
              ? 1
              : 0.1;
          return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${opacity})`;
        });

      bars_merged.select('text').text((d) => d.name);

      bars.exit().transition().duration(750).attr('opacity', 0).remove();

      if (container) {
        container.scrollTo({ top: 0, behavior: 'smooth' });
      }
    };

  viz_state.obs_store.new_cell_bar_data.subscribe(
    subscriber_new_bar_data({
      svg: viz_state.cats.svg_bar_cluster,
      color_dict: viz_state.cats.color_dict_cluster,
      selected_array: viz_state.cats.selected_cats,
      bar_callback: bar_callback_cat,
      container: viz_state.containers.bar_cluster,
    }),
    { immediate: false }
  );

  viz_state.obs_store.new_gene_bar_data.subscribe(
    subscriber_new_bar_data({
      svg: viz_state.genes.svg_bar_gene,
      color_dict: viz_state.genes.color_dict_gene,
      selected_array: viz_state.genes.selected_genes,
      bar_callback: bar_callback_gene,
      container: viz_state.containers.bar_gene,
    }),
    { immediate: false }
  );

  cell_container.appendChild(cell_ctrl_container);
  cell_container.appendChild(viz_state.containers.bar_cluster);

  ini_slider('trx', deck_yearbook, layers_obj, viz_state);
  trx_container.appendChild(trx_slider_container);
  trx_slider_container.appendChild(viz_state.sliders.trx);

  gene_container.appendChild(trx_container);
  gene_container.appendChild(viz_state.containers.bar_gene);

  // Gene search
  set_gene_search('ist', deck_yearbook, layers_obj, viz_state);
  viz_state.genes.gene_search.style.marginLeft = '0px';

  viz_state.obs_store.selected_genes.subscribe(async (selected_genes) => {
    if (selected_genes.length === 1) {
      const inst_gene = selected_genes[0];
      viz_state.genes.gene_search_input.value = inst_gene;

      if (inst_gene !== '') {
        if (viz_state.genes.gene_names.includes(inst_gene)) {
          viz_state.genes.gene_text_box.textContent = 'loading';
          await uniprot_get_request(inst_gene);
          const gene_data = uniprot_data[inst_gene];

          if (gene_data && gene_data.name && gene_data.description) {
            viz_state.genes.gene_text_box.innerHTML = `<span style="color: blue;">${gene_data.name}</span><br>${gene_data.description}`;
          } else {
            viz_state.genes.gene_text_box.textContent = '';
          }
        }
      } else {
        viz_state.genes.gene_text_box.textContent = '';
      }

      viz_state.genes.gene_text_box.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (selected_genes.length === 0) {
      viz_state.genes.gene_search_input.value = '';
      viz_state.genes.gene_text_box.textContent = '';
    }
  });

  ui_container.appendChild(ctrl_container);

  ctrl_container.appendChild(viz_state.containers.image);
  ctrl_container.appendChild(cell_container);
  ctrl_container.appendChild(gene_container);

  viz_state.genes.gene_search.style.width = '160px';
  viz_state.genes.gene_search.style.marginLeft = '5px';

  ctrl_container.appendChild(viz_state.genes.gene_search);

  // Add query box for searching cells by cluster/gene
  const query_container = make_query_container(viz_state, handle_query_change);
  ctrl_container.appendChild(query_container);

  // Add pagination controls
  const pagination_container = make_pagination_container(
    viz_state,
    handle_page_change
  );
  ctrl_container.appendChild(pagination_container);

  // Logo
  const logo_button = document.createElement('div');
  logo_button.className = 'logo_button';
  logo_button.style.marginTop = '5px';
  logo_button.style.marginRight = '5px';
  logo_button.style.cursor = 'pointer';

  const logo_img = document.createElement('img');
  logo_img.src = `data:image/png;base64,${logo}`;
  logo_img.alt = 'Celldega logo';
  logo_img.style.height = '17px';
  logo_img.style.transition = 'transform 0.2s ease, filter 0.2s ease';

  logo_button.onclick = () => {
    window.open('https://broadinstitute.github.io/celldega/', '_blank');
  };

  logo_button.appendChild(logo_img);
  ui_container.appendChild(logo_button);

  return ui_container;
};
