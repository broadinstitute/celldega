import { has_uniprot_info } from '../../external_apis/uniprot_api';
import {
  escape_html,
  gene_info_tooltip_html,
  refresh_gene_tooltip_async,
} from '../../ui/gene_info';
import { is_cluster_color_mode } from '../layers/cell_color';

import { get_point_cloud_source_index } from './point_cloud_indices';

/**
 * Expression of the selected gene (summed over several selected genes) in one
 * cell, from the raw values kept for coloring; empty when cells are colored
 * by cluster.
 *
 * @param {Object} cats - viz_state.cats
 * @param {number} cellIndex - Index into cats.cell_names_array
 * @returns {string} Tooltip HTML line, or ''
 */
export const cell_expression_html = (cats, cellIndex) => {
  const value = cats.cell_exp_raw?.[cellIndex];
  if (
    is_cluster_color_mode(cats) ||
    !cats.cell_exp_genes?.length ||
    !Number.isFinite(value)
  ) {
    return '';
  }

  const label = escape_html(cats.cell_exp_genes.join(' + '));
  const formatted = Number.isInteger(value) ? value : value.toFixed(2);
  return `<div>${label}: ${formatted}</div>`;
};

/** Same cap as the Enrich/bar-plot gene tooltips, so descriptions wrap. */
const TOOLTIP_MAX_WIDTH = '260px';
const TOOLTIP_EDGE_PAD_PX = 4;
const TOOLTIP_CURSOR_GAP_PX = 12;

/**
 * Keep a deck.gl tooltip inside `bounds`: flip it left of the cursor when it
 * would run off the right edge, above the cursor when it would run off the
 * bottom, then clamp. deck.gl positions the tooltip with
 * `translate(x, y)` (plus the downward `margin-top` set below), so this
 * rewrites that transform.
 *
 * @param {HTMLElement} tooltip - The `.deck-tooltip` element.
 * @param {number} x - Pointer x passed to deck's setTooltip.
 * @param {number} y - Pointer y passed to deck's setTooltip.
 * @param {HTMLElement} bounds - Element the tooltip must stay inside.
 */
export const fit_tooltip_in_bounds = (tooltip, x, y, bounds) => {
  if (!tooltip || !bounds || tooltip.style.display === 'none') return;

  tooltip.style.transform = `translate(${x}px, ${y}px)`;
  const rect = tooltip.getBoundingClientRect();
  const box = bounds.getBoundingClientRect();
  if (!rect.width || !box.width) return;

  const margin_top = parseFloat(tooltip.style.marginTop) || 0;
  const cursor_left = rect.left;
  const cursor_top = rect.top - margin_top;
  let { left, top } = rect;

  if (rect.right > box.right - TOOLTIP_EDGE_PAD_PX) {
    left = cursor_left - rect.width - TOOLTIP_CURSOR_GAP_PX;
  }
  if (rect.bottom > box.bottom - TOOLTIP_EDGE_PAD_PX) {
    top = cursor_top - rect.height - TOOLTIP_CURSOR_GAP_PX;
  }
  left = Math.max(
    box.left + TOOLTIP_EDGE_PAD_PX,
    Math.min(left, box.right - TOOLTIP_EDGE_PAD_PX - rect.width)
  );
  top = Math.max(
    box.top + TOOLTIP_EDGE_PAD_PX,
    Math.min(top, box.bottom - TOOLTIP_EDGE_PAD_PX - rect.height)
  );

  tooltip.style.transform = `translate(${x + left - rect.left}px, ${
    y + top - rect.top
  }px)`;
};

const fit_and_reveal = (viz_state, x, y, reveal) => {
  const tooltip = viz_state.root?.querySelector('.deck-tooltip');
  fit_tooltip_in_bounds(tooltip, x, y, viz_state.root);
  if (reveal && tooltip) tooltip.style.visibility = 'visible';
};

/**
 * Fit the tooltip right after deck.gl renders it. deck applies the returned
 * html/style synchronously after getTooltip returns, from inside its own
 * animation frame, so a microtask runs after that and before the browser
 * paints: the tooltip's first painted position is already the fitted one. (A
 * requestAnimationFrame here would paint one frame at deck's default position,
 * then jump.)
 */
const schedule_tooltip_fit = (viz_state, x, y) => {
  queueMicrotask(() => fit_and_reveal(viz_state, x, y, false));
};

/**
 * Creates tooltips for various layer types with detailed information
 * @param {Object} viz_state - Application visualization state
 * @param {Object} info - Layer interaction info with index and layer data
 * @returns {Object|null} Tooltip configuration object or null if invalid
 */
export const make_tooltip = (viz_state, info) => {
  if (info.index === -1 || !info.layer) return null;

  // Disable tooltips when in sketch mode to avoid interference while drawing
  if (viz_state.edit?.mode === 'sktch') return null;

  let inst_html = '';
  let inst_name = '';
  let inst_cat = '';
  let tooltip_visibility = 'visible';

  // Handle cell and path layer tooltips
  if (
    info.layer.id.startsWith('cell-layer') ||
    info.layer.id.startsWith('path-layer')
  ) {
    let cellIndex;
    if (info.layer.id.startsWith('cell-layer')) {
      cellIndex = get_point_cloud_source_index(viz_state, info.index);
      if (cellIndex < 0) {
        return null;
      }
      inst_name = viz_state.cats.cell_names_array[cellIndex];
      inst_cat =
        viz_state.cats.cell_cats?.[cellIndex] ??
        viz_state.cats.dict_cell_cats?.[inst_name];
    } else {
      inst_name = viz_state.cats.polygon_cell_names[info.index];
      inst_cat = viz_state.cats.dict_cell_cats?.[inst_name];
      cellIndex = viz_state.cats.cell_name_to_index_map?.get(String(inst_name));
    }
    inst_html = `<div>cell: ${inst_name}</div><div>cluster: ${inst_cat}</div>${cell_expression_html(
      viz_state.cats,
      cellIndex
    )}`;

    viz_state.tooltip_cat_cell = inst_cat;
  }
  // Handle transcript layer tooltips
  else if (info.layer.id.startsWith('trx-layer')) {
    const geneId = viz_state.genes.trx_gene_ids?.[info.index];
    inst_name =
      geneId === undefined || geneId < 0
        ? ''
        : viz_state.genes.g_nameMapping_inv?.[geneId] || '';

    // Same UniProt name/description the Clustergram shows on a gene row.
    // Until the lookup lands the tooltip stays hidden, so it first appears at
    // its final size and position instead of growing (and flipping) in place.
    const build_trx_html = () =>
      `<div>transcript: ${escape_html(
        inst_name
      )}</div>${gene_info_tooltip_html(inst_name)}`;
    refresh_gene_tooltip_async(viz_state.root, inst_name, build_trx_html, () =>
      fit_and_reveal(viz_state, info.x, info.y, true)
    );
    inst_html = build_trx_html();
    tooltip_visibility =
      !inst_name || has_uniprot_info(inst_name) ? 'visible' : 'hidden';
  }
  // Handle neighborhood layer tooltips
  else if (info.layer.id.startsWith('nbhd-layer')) {
    inst_name =
      viz_state.nbhd.feature_collection.features[info.index].properties.name;
    inst_cat =
      viz_state.nbhd.feature_collection.features[info.index].properties.cat;
    inst_html = `<div>neighborhood: ${inst_name}</div><div>category: ${inst_cat}</div>`;
  }
  // Handle edit layer tooltips (for editable neighborhoods)
  else if (info.layer.id.startsWith('edit-layer')) {
    const feature = viz_state.edit?.feature_collection?.features?.[info.index];
    if (feature) {
      inst_name = feature.properties.name || `nbhd_${info.index + 1}`;
      inst_cat = feature.properties.cat || inst_name;
      inst_html = `<div>neighborhood: ${inst_name}</div>`;
    }
  }
  // Handle neighborhood-cloud shape tooltips -- GeoJsonLayer hands back the
  // picked feature directly as info.object (not indexed into a separate
  // array like the layers above), and properties differ by mode: gene-shapes
  // features carry gene/mean_expression, cluster shapes carry cluster_id.
  else if (info.layer.id.startsWith('nbhd-cloud-shapes-layer')) {
    const properties = info.object?.properties;
    if (properties) {
      inst_html =
        properties.gene !== undefined
          ? `<div>gene: ${properties.gene}</div><div>slice: ${properties.slice_id}</div><div>mean expression: ${Number(properties.mean_expression).toFixed(2)}</div>`
          : `<div>cluster: ${properties.cluster_id}</div><div>slice: ${properties.slice_id}</div>`;
    }
  }

  // No branch above produced content for this layer (e.g. an unhandled or
  // future layer type) -- return null rather than an empty-but-present
  // tooltip box, which otherwise renders as a small blank/black square.
  if (!inst_html) return null;

  // Configure tooltip positioning and styling
  const tooltipContainer = viz_state.root.querySelector('.deck-tooltip');
  if (tooltipContainer) {
    tooltipContainer.style.marginTop = '50px';
    const tooltipParent = tooltipContainer.parentElement?.parentElement;
    if (tooltipParent) {
      tooltipParent.style.position = 'unset';
    }
  }

  schedule_tooltip_fit(viz_state, info.x, info.y);

  return {
    html: inst_html,
    style: {
      maxWidth: TOOLTIP_MAX_WIDTH,
      overflowWrap: 'break-word',
      visibility: tooltip_visibility,
    },
  };
};
