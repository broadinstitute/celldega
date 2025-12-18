/**
 * Cell query utilities for finding cells based on cluster and gene criteria.
 * Used by Yearbook to find cells from LandscapeFiles based on a query object.
 */

import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';

/**
 * Load cluster assignments from LandscapeFiles.
 * Returns a Map of cell_name -> cluster_value.
 *
 * @param {string} base_url - Base URL for LandscapeFiles
 * @param {string} version - Segmentation version (e.g., 'default')
 * @param {object} aws - AWS client for authenticated requests
 * @param {string} attr - Cluster attribute name (e.g., 'leiden', 'cluster')
 * @returns {Promise<Map<string, string>>} Map of cell_name -> cluster_value
 */
export const load_cluster_data = async (base_url, version, aws, attr = 'cluster') => {
  const version_suffix = version && version !== 'default' ? `_${version}` : '';
  const cluster_url = `${base_url}/cell_clusters${version_suffix}/cluster.parquet`;

  const cluster_table = await get_arrow_table(cluster_url, options.fetch, aws);

  const cell_names = cluster_table.getChild('__index_level_0__')?.toArray() || [];
  const cluster_values = cluster_table.getChild(attr)?.toArray() ||
                         cluster_table.getChild('cluster')?.toArray() || [];

  const cluster_map = new Map();
  cell_names.forEach((name, i) => {
    cluster_map.set(String(name), String(cluster_values[i]));
  });

  return cluster_map;
};

/**
 * Load gene expression data from cbg parquet files.
 * Returns a Map of cell_name -> expression_value.
 *
 * @param {string} base_url - Base URL for LandscapeFiles
 * @param {string} version - Segmentation version
 * @param {object} aws - AWS client for authenticated requests
 * @param {string} gene_name - Gene name to load expression for
 * @returns {Promise<Map<string, number>>} Map of cell_name -> expression_value
 */
export const load_gene_expression = async (base_url, version, aws, gene_name) => {
  const version_suffix = version && version !== 'default' ? `_${version}` : '';
  const gene_url = `${base_url}/cbg${version_suffix}/${gene_name}.parquet`;

  const exp_table = await get_arrow_table(gene_url, options.fetch, aws);

  const cell_names = exp_table.getChild('__index_level_0__')?.toArray() || [];
  const exp_values = exp_table.getChild(gene_name)?.toArray() || [];

  const exp_map = new Map();
  cell_names.forEach((name, i) => {
    exp_map.set(String(name), Number(exp_values[i]));
  });

  return exp_map;
};

/**
 * Execute a cell query to find cells matching the criteria.
 *
 * Query formats:
 * - {"cluster": {"attr": "leiden", "value": "8"}} - random cells from cluster
 * - {"gene": "BRCA1"} - cells ranked by gene expression (highest first)
 * - {"cluster": {...}, "gene": "BRCA1"} - cluster cells ranked by gene
 * - {"max_cells": 100} - limit number of cells (default based on grid size)
 *
 * @param {object} query - Query object
 * @param {object} viz_state - Visualization state with cell data
 * @param {number} default_max_cells - Default max cells if not specified in query
 * @returns {Promise<string[]>} Array of cell names matching the query
 */
export const execute_cell_query = async (query, viz_state, default_max_cells = 60) => {
  if (!query || Object.keys(query).length === 0) {
    return [];
  }

  const max_cells = query.max_cells || default_max_cells;
  const cluster_query = query.cluster;
  const gene_name = query.gene;

  // Get all available cell names from viz_state
  const all_cell_names = viz_state.cats.cell_names_array || [];
  if (all_cell_names.length === 0) {
    console.warn('No cell names available for query');
    return [];
  }

  let candidate_cells = [...all_cell_names];

  // Filter by cluster if specified
  if (cluster_query) {
    const cluster_attr = cluster_query.attr || 'leiden';
    const cluster_value = String(cluster_query.value);

    // Check if we have meta_cell data (from adata) or need to load from files
    if (viz_state.cats.has_meta_cell && viz_state.cats.meta_cell) {
      // Use meta_cell from adata
      const attr_index = viz_state.cats.meta_cell_attr.indexOf(cluster_attr);
      if (attr_index >= 0) {
        candidate_cells = candidate_cells.filter((cell_name) => {
          const attrs = viz_state.cats.meta_cell[cell_name];
          if (!attrs) return false;
          return String(attrs[attr_index]) === cluster_value;
        });
      } else {
        console.warn(`Cluster attribute '${cluster_attr}' not found in meta_cell_attr`);
      }
    } else if (viz_state.cats.dict_cell_cats && Object.keys(viz_state.cats.dict_cell_cats).length > 0) {
      // Use dict_cell_cats if available (loaded from LandscapeFiles)
      candidate_cells = candidate_cells.filter((cell_name) => {
        return String(viz_state.cats.dict_cell_cats[cell_name]) === cluster_value;
      });
    } else {
      // Load cluster data from LandscapeFiles
      try {
        const cluster_map = await load_cluster_data(
          viz_state.global_base_url,
          viz_state.seg.version,
          viz_state.aws,
          cluster_attr
        );
        candidate_cells = candidate_cells.filter((cell_name) => {
          return cluster_map.get(cell_name) === cluster_value;
        });
      } catch (error) {
        console.error('Failed to load cluster data:', error);
        return [];
      }
    }
  }

  // If no cells match the cluster filter, return empty
  if (candidate_cells.length === 0) {
    return [];
  }

  // Rank/filter by gene expression if specified
  if (gene_name) {
    try {
      const exp_map = await load_gene_expression(
        viz_state.global_base_url,
        viz_state.seg.version,
        viz_state.aws,
        gene_name
      );

      // Filter to cells with non-zero expression and sort by expression (descending)
      const cells_with_exp = candidate_cells
        .map((cell_name) => ({
          name: cell_name,
          exp: exp_map.get(cell_name) || 0,
        }))
        .filter((c) => c.exp > 0)
        .sort((a, b) => b.exp - a.exp);

      candidate_cells = cells_with_exp.map((c) => c.name);
    } catch (error) {
      console.error(`Failed to load gene expression for ${gene_name}:`, error);
      // Fall back to unranked cells if gene data fails
    }
  } else if (!gene_name && cluster_query) {
    // Cluster only - shuffle for random selection
    candidate_cells = shuffle_array(candidate_cells);
  }

  // Limit to max_cells
  return candidate_cells.slice(0, max_cells);
};

/**
 * Fisher-Yates shuffle for random cell selection.
 */
const shuffle_array = (array) => {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
};
