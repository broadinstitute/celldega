import * as d3 from 'd3';

import { get_point_cloud_source_index } from './point_cloud_indices';

/**
 * Creates tooltips for tile layers showing category information
 * @param {Object} info - Layer interaction info with index and layer data
 * @param {Object} viz_state - Application visualization state
 * @returns {Object|null} Tooltip configuration object or null if invalid
 */
export const make_tile_tooltip = (info, viz_state) => {
  if (info.index === -1 || !info.layer) return null;

  const inst_cat = viz_state.cats.tile_cats_array[info.index];

  viz_state.tooltip_cat_cell = inst_cat;

  d3.selectAll('.deck-tooltip').style('margin-top', '75px');
  return {
    html: `<div>${inst_cat}</div>`,
  };
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

  // Handle cell and path layer tooltips
  if (
    info.layer.id.startsWith('cell-layer') ||
    info.layer.id.startsWith('path-layer')
  ) {
    if (info.layer.id.startsWith('cell-layer')) {
      const sourceIndex = get_point_cloud_source_index(viz_state, info.index);
      if (sourceIndex < 0) {
        return null;
      }
      inst_name = viz_state.cats.cell_names_array[sourceIndex];
      inst_cat =
        viz_state.cats.cell_cats?.[sourceIndex] ??
        viz_state.cats.dict_cell_cats?.[inst_name];
    } else {
      inst_name = viz_state.cats.polygon_cell_names[info.index];
      inst_cat = viz_state.cats.dict_cell_cats?.[inst_name];
    }
    inst_html = `<div>cell: ${inst_name}</div><div>cluster: ${inst_cat}</div>`;

    viz_state.tooltip_cat_cell = inst_cat;
  }
  // Handle transcript layer tooltips
  else if (info.layer.id.startsWith('trx-layer')) {
    const geneId = viz_state.genes.trx_gene_ids?.[info.index];
    inst_name =
      geneId === undefined || geneId < 0
        ? ''
        : viz_state.genes.g_nameMapping_inv?.[geneId] || '';
    inst_html = `<div>transcript: ${inst_name}</div>`;
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

  // Configure tooltip positioning and styling
  const tooltipContainer = viz_state.root.querySelector('.deck-tooltip');
  if (tooltipContainer) {
    tooltipContainer.style.marginTop = '50px';
    const tooltipParent = tooltipContainer.parentElement?.parentElement;
    if (tooltipParent) {
      tooltipParent.style.position = 'unset';
    }
  }

  return {
    html: inst_html,
  };
};
