import { options } from '../global_variables/fetch_options';
import { getGeneExpressionColumns } from '../read_parquet/gene_expression_columns';
import { get_arrow_table } from '../read_parquet/get_arrow_table';

function processExpression(exp_value, max_exp) {
  const log_exp_value = Math.log1p(exp_value);
  const log_max_exp = Math.log1p(max_exp);
  return (log_exp_value / log_max_exp) * 255;
}

function ensureExpressionArray(cats) {
  const requiredLength = cats.cell_names_array.length;

  if (
    !(cats.cell_exp_array instanceof Uint8Array) ||
    cats.cell_exp_array.length !== requiredLength
  ) {
    cats.cell_exp_array = new Uint8Array(requiredLength);
  } else {
    cats.cell_exp_array.fill(0);
  }

  return cats.cell_exp_array;
}

// Exported for reuse by neighborhood-cloud gene-shapes coloring
// (nbhd_cloud_shapes_layer.js), which normalizes shape opacity the same way
// per-cell gene coloring does -- log1p ratio against a whole-tissue max, not
// a plain linear ratio, so opacity doesn't wash out toward 0 for typical
// (non-outlier) expression values.
export function toExpressionByte(exp_value, max_exp) {
  if (
    !Number.isFinite(exp_value) ||
    !Number.isFinite(max_exp) ||
    max_exp <= 0
  ) {
    return 0;
  }

  const normalized = processExpression(exp_value, max_exp);
  if (!Number.isFinite(normalized)) {
    return 0;
  }

  return Math.max(0, Math.min(255, Math.round(normalized)));
}

/**
 * Read gene expression from row group reader
 * @param {Object} cbgReader - CBGRowGroupReader instance
 * @param {string} geneName - Gene name to read
 * @returns {Promise<{cell_names: Array, cell_exp: Array}>}
 */
async function readGeneFromRowGroups(cbgReader, geneName) {
  const table = await cbgReader.readGene(geneName);

  if (!table) {
    return { cell_names: [], cell_exp: [] };
  }

  return getGeneExpressionColumns(table, geneName);
}

export const update_cell_exp_array = async (
  cats,
  genes,
  base_url,
  inst_gene,
  version,
  vector_name_integer,
  aws,
  cbgReader = null // Optional: row group reader for CBG data
) => {
  let cell_names;
  let cell_exp;

  // Check if using row group mode
  if (cbgReader) {
    ({ cell_names, cell_exp } = await readGeneFromRowGroups(
      cbgReader,
      inst_gene
    ));
  } else {
    // Traditional mode: fetch individual gene file
    let file_path;
    if (version === 'default') {
      file_path = `${base_url}/cbg/${inst_gene}.parquet`;
    } else {
      file_path = `${base_url}/cbg_${version}/${inst_gene}.parquet`;
    }

    const exp_table = await get_arrow_table(file_path, options.fetch, aws);
    ({ cell_names, cell_exp } = getGeneExpressionColumns(exp_table, inst_gene));
  }
  const new_exp_array = ensureExpressionArray(cats);
  const max_exp = Number(genes.meta_gene[inst_gene].max);

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

    if (!vector_name_integer) {
      if (cats.cell_name_to_index_map.has(name)) {
        const index = cats.cell_name_to_index_map.get(name);
        const shouldInclude = !allowedCellIds || allowedCellIds.has(name);

        if (shouldInclude) {
          new_exp_array[index] = toExpressionByte(exp_value, max_exp);
        }
      } else {
        missingCellNames1.add(name);
      }
    } else {
      const cellIndex = Number(name);
      if (
        Number.isInteger(cellIndex) &&
        cellIndex >= 0 &&
        cellIndex < cats.nameMapping_inv.length
      ) {
        const cellName = String(cats.nameMapping_inv[cellIndex]);
        const shouldInclude = !allowedCellIds || allowedCellIds.has(cellName);

        if (shouldInclude) {
          new_exp_array[cellIndex] = toExpressionByte(exp_value, max_exp);
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
