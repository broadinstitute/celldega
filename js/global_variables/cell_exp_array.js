import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';

function processExpression(exp_value, max_exp) {
  const log_exp_value = Math.log1p(exp_value);
  const log_max_exp = Math.log1p(max_exp);
  return (log_exp_value / log_max_exp) * 255;
}

// Threshold for frontend multi-gene loading (above this, use Python backend)
const MULTI_GENE_THRESHOLD = 10;

export const update_cell_exp_array = async (
  cats,
  genes,
  base_url,
  inst_gene,
  version,
  vector_name_integer,
  aws
) => {
  let file_path;
  if (version === 'default') {
    file_path = `${base_url}/cbg/${inst_gene}.parquet`;
  } else {
    file_path = `${base_url}/cbg_${version}/${inst_gene}.parquet`;
  }

  const exp_table = await get_arrow_table(file_path, options.fetch, aws);
  const cell_names = exp_table.getChild('__index_level_0__').toArray();
  const cell_exp = exp_table.getChild(inst_gene).toArray();

  const new_exp_array = new Array(cats.cell_names_array.length).fill(0);

  const allowedCellIds =
    cats.meta_cell_id_set && cats.meta_cell_id_set.size > 0
      ? cats.meta_cell_id_set
      : null;

  // Use Sets to track missing names (automatically keeps them unique)
  const missingCellNames1 = new Set(); // For cell_name_to_index_map
  const missingCellNames2 = new Set(); // For nameMapping_inv

  cell_names.forEach((name, i) => {
    name = String(name);
    const exp_value = Number(cell_exp[i]);
    const max_exp = Number(genes.meta_gene[inst_gene].max);

    if (!vector_name_integer) {
      if (cats.cell_name_to_index_map.has(name)) {
        const index = cats.cell_name_to_index_map.get(name);
        const shouldInclude = !allowedCellIds || allowedCellIds.has(name);

        if (shouldInclude) {
          new_exp_array[index] = processExpression(exp_value, max_exp);
        }
      } else {
        missingCellNames1.add(name);
      }
    } else {
      if (name in cats.nameMapping_inv) {
        const cellName = String(cats.nameMapping_inv[name]);
        const shouldInclude = !allowedCellIds || allowedCellIds.has(cellName);

        if (shouldInclude) {
          new_exp_array[name] = processExpression(exp_value, max_exp);
        }
      } else {
        missingCellNames2.add(name);
      }
    }
  });

  // Log missing names (if any) after processing all cells
  if (missingCellNames1.size > 0) {
    // console.log(`Cell names not found in cell_name_to_index_map (${missingCellNames1.size} unique names):`,
    //             Array.from(missingCellNames1).slice(0, 5),
    //             missingCellNames1.size > 5 ? '...' : '');
  }
  if (missingCellNames2.size > 0) {
    // console.log(`Cell names not found in cats.nameMapping_inv (${missingCellNames2.size} unique names):`,
    //             Array.from(missingCellNames2).slice(0, 5),
    //             missingCellNames2.size > 5 ? '...' : '');
  }

  cats.cell_exp_array = new_exp_array;
};

/**
 * Load and combine expression data for multiple genes.
 * Each gene is normalized to [0, 1] (by dividing by its max expression),
 * then averaged across all genes, and scaled to [0, 255] for display.
 *
 * @param {Object} cats - Cell categories object
 * @param {Object} genes - Genes metadata object
 * @param {string} base_url - Base URL for data files
 * @param {string[]} gene_list - List of gene names to load
 * @param {string} version - Segmentation version
 * @param {boolean} vector_name_integer - Whether cell names are integers
 * @param {Object} aws - AWS configuration
 * @returns {Promise<boolean>} True if successful, false if too many genes
 */
export const update_multi_gene_exp_array = async (
  cats,
  genes,
  base_url,
  gene_list,
  version,
  vector_name_integer,
  aws
) => {
  // Check threshold
  if (gene_list.length > MULTI_GENE_THRESHOLD) {
    console.warn(
      `Too many genes (${gene_list.length}) for frontend multi-gene loading. ` +
        `Max is ${MULTI_GENE_THRESHOLD}.`
    );
    return false;
  }

  if (gene_list.length === 0) {
    cats.cell_exp_array = new Array(cats.cell_names_array.length).fill(0);
    return true;
  }

  // Load all gene parquet files in parallel
  const gene_promises = gene_list.map(async (gene_name) => {
    let file_path;
    if (version === 'default') {
      file_path = `${base_url}/cbg/${gene_name}.parquet`;
    } else {
      file_path = `${base_url}/cbg_${version}/${gene_name}.parquet`;
    }

    try {
      const exp_table = await get_arrow_table(file_path, options.fetch, aws);
      const cell_names = exp_table.getChild('__index_level_0__').toArray();
      const cell_exp = exp_table.getChild(gene_name).toArray();

      // Get max expression for this gene (for normalization)
      const max_exp = genes.meta_gene?.[gene_name]?.max || 1;

      return { gene_name, cell_names, cell_exp, max_exp };
    } catch (error) {
      console.warn(`Failed to load gene ${gene_name}:`, error);
      return null;
    }
  });

  const gene_results = await Promise.all(gene_promises);
  const valid_results = gene_results.filter((r) => r !== null);

  if (valid_results.length === 0) {
    cats.cell_exp_array = new Array(cats.cell_names_array.length).fill(0);
    return true;
  }

  // Initialize accumulator array (stores sum of normalized values)
  const num_cells = cats.cell_names_array.length;
  const sum_array = new Float32Array(num_cells);
  const count_array = new Uint8Array(num_cells); // Track how many genes contributed

  const allowedCellIds =
    cats.meta_cell_id_set && cats.meta_cell_id_set.size > 0
      ? cats.meta_cell_id_set
      : null;

  // Process each gene's expression data
  for (const result of valid_results) {
    const { cell_names, cell_exp, max_exp } = result;
    const log_max_exp = Math.log1p(max_exp);

    cell_names.forEach((name, i) => {
      name = String(name);
      const exp_value = Number(cell_exp[i]);

      // Normalize to [0, 1] using log scale (same as single gene)
      const log_exp = Math.log1p(exp_value);
      const normalized = log_max_exp > 0 ? log_exp / log_max_exp : 0;

      let index = -1;
      if (!vector_name_integer) {
        if (cats.cell_name_to_index_map.has(name)) {
          index = cats.cell_name_to_index_map.get(name);
        }
      } else {
        if (name in cats.nameMapping_inv) {
          index = Number(name);
        }
      }

      if (index >= 0 && index < num_cells) {
        const shouldInclude =
          !allowedCellIds ||
          allowedCellIds.has(
            vector_name_integer ? String(cats.nameMapping_inv[name]) : name
          );

        if (shouldInclude) {
          sum_array[index] += normalized;
          count_array[index] += 1;
        }
      }
    });
  }

  // Compute average and scale to [0, 255]
  const new_exp_array = new Array(num_cells);
  for (let i = 0; i < num_cells; i++) {
    if (count_array[i] > 0) {
      // Average normalized expression, then scale to 255
      const avg = sum_array[i] / count_array[i];
      new_exp_array[i] = Math.round(avg * 255);
    } else {
      new_exp_array[i] = 0;
    }
  }

  cats.cell_exp_array = new_exp_array;
  return true;
};

/**
 * Check if multi-gene loading should be done on the frontend.
 */
export const canLoadMultiGeneOnFrontend = (gene_count) => {
  return gene_count <= MULTI_GENE_THRESHOLD;
};
