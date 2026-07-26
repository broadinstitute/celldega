import * as d3 from 'd3';

import {
  get_mat_layers_list,
  mat_reorder_triggers,
} from '../deck-gl/matrix/matrix_layers';

const rgba_css = (rgba) =>
  Array.isArray(rgba)
    ? `rgba(${rgba[0]}, ${rgba[1]}, ${rgba[2]}, ${(rgba[3] ?? 255) / 255})`
    : '#808080';

/**
 * Sort the columns (datasets) by a single population row's values, mirroring the
 * double-click "reorder other axis" behavior so a legend click focuses a bar's
 * ordering on one population.
 */
const sort_cols_by_row = (deck_mat, layers_mat, viz_state, row_index) => {
  const vals = viz_state.mat.net_mat[row_index] || [];
  const sorted = Array.from(vals.keys()).sort((a, b) => vals[b] - vals[a]);
  const ranked = new Array(vals.length);
  sorted.forEach((col_index, rank) => {
    ranked[col_index] = vals.length - rank;
  });

  viz_state.mat.orders.col.custom = ranked;
  viz_state.order.current.col = 'custom';

  d3.select(viz_state.el)
    .selectAll('.button-col')
    .classed('active', false)
    .style('border-color', viz_state.buttons.gray);

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: mat_reorder_triggers(viz_state, [row_index]),
  });
  layers_mat.col_label_layer = layers_mat.col_label_layer.clone({
    updateTriggers: { getPosition: [viz_state.order.current.col, row_index] },
  });
  layers_mat.col_cat_layer = layers_mat.col_cat_layer.clone({
    updateTriggers: { getPosition: viz_state.order.current.col },
  });

  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

/**
 * Toggle between proportion (column-normalized to 100%) and raw-count heights.
 */
const set_normalized = (deck_mat, layers_mat, viz_state, normalized) => {
  viz_state.mat.composition_normalized = normalized;
  viz_state.mat._comp_cache = null;

  if (viz_state.model?.set) {
    viz_state.model.set('composition_normalized', normalized);
    viz_state.model.save_changes();
  }

  layers_mat.mat_layer = layers_mat.mat_layer.clone({
    updateTriggers: mat_reorder_triggers(viz_state),
  });
  deck_mat.setProps({ layers: get_mat_layers_list(layers_mat) });
};

/**
 * Build the composition legend: a proportion/count toggle plus a clickable list
 * of populations (color swatch + name). Clicking a population sorts the datasets
 * by that population's share.
 *
 * @param {HTMLElement} el - Container the widget is mounted in.
 * @param {object} deck_mat - deck.gl instance.
 * @param {object} layers_mat - Layer registry.
 * @param {object} viz_state - Visualization state.
 * @returns {HTMLElement} The legend element.
 */
export const render_composition_legend = (
  el,
  deck_mat,
  layers_mat,
  viz_state
) => {
  const container = document.createElement('div');
  container.className = 'composition-legend';
  container.style.cssText =
    'display:flex;flex-direction:column;gap:4px;padding:6px 8px;font-size:11px;' +
    'font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif;';

  const sel = d3.select(container);

  // Proportion / count toggle
  const toggle_row = sel
    .append('div')
    .style('display', 'flex')
    .style('gap', '6px')
    .style('align-items', 'center')
    .style('margin-bottom', '2px');

  const make_toggle = (label, normalized) => {
    toggle_row
      .append('div')
      .text(label)
      .style('cursor', 'pointer')
      .style('padding', '2px 8px')
      .style('border', '1px solid #d3d3d3')
      .style('border-radius', '8px')
      .style('user-select', 'none')
      .style('font-weight', 'bold')
      .style('color', '#47515b')
      .classed('active', viz_state.mat.composition_normalized === normalized)
      .style(
        'background',
        viz_state.mat.composition_normalized === normalized
          ? '#eef0ff'
          : 'transparent'
      )
      .on('click', function handle() {
        set_normalized(deck_mat, layers_mat, viz_state, normalized);
        toggle_row
          .selectAll('div')
          .style('background', 'transparent')
          .classed('active', false);
        d3.select(this).style('background', '#eef0ff').classed('active', true);
      });
  };

  make_toggle('Proportion', true);
  make_toggle('Count', false);

  // Population swatches (click -> sort datasets by that population)
  const nodes = viz_state.row_nodes || [];
  const colors = viz_state.mat.comp_colors || [];

  const list = sel
    .append('div')
    .style('display', 'flex')
    .style('flex-wrap', 'wrap')
    .style('gap', '2px 12px')
    .style('max-height', '120px')
    .style('overflow-y', 'auto');

  nodes.forEach((node, i) => {
    const item = list
      .append('div')
      .style('display', 'flex')
      .style('align-items', 'center')
      .style('gap', '5px')
      .style('cursor', 'pointer')
      .style('user-select', 'none')
      .attr('title', `Sort datasets by ${node.name}`)
      .on('click', () => sort_cols_by_row(deck_mat, layers_mat, viz_state, i));

    item
      .append('span')
      .style('width', '11px')
      .style('height', '11px')
      .style('border-radius', '2px')
      .style('flex', '0 0 auto')
      .style('background', rgba_css(colors[i]));

    item.append('span').text(String(node.name)).style('color', '#47515b');
  });

  el.appendChild(container);
  return container;
};
