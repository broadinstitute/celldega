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

// Recently loaded gene expression, so adding a gene to a multi-gene selection
// doesn't refetch the genes already shown. Holds promises, so concurrent
// requests for one gene share a fetch.
const expression_cache = new Map();
const EXPRESSION_CACHE_LIMIT = 20;

const load_gene_expression = (base_url, version, gene, aws, cbgReader) => {
  const key = `${base_url}|${version}|${gene}`;
  if (expression_cache.has(key)) return expression_cache.get(key);

  const request = (async () => {
    if (cbgReader) return readGeneFromRowGroups(cbgReader, gene);
    // Traditional mode: fetch individual gene file
    const folder = version === 'default' ? 'cbg' : `cbg_${version}`;
    const exp_table = await get_arrow_table(
      `${base_url}/${folder}/${gene}.parquet`,
      options.fetch,
      aws
    );
    return getGeneExpressionColumns(exp_table, gene);
  })();

  expression_cache.set(key, request);
  request.catch(() => expression_cache.delete(key));
  if (expression_cache.size > EXPRESSION_CACHE_LIMIT) {
    expression_cache.delete(expression_cache.keys().next().value);
  }
  return request;
};

/**
 * Expression at which cells reach full opacity: the max, times the
 * zoomed-out TRX slider's scale (`cats.cell_exp_scale`, 1 by default).
 */
export const cell_exp_display_max = (cats) =>
  (cats.cell_exp_max ?? 0) * (cats.cell_exp_scale ?? 1);

/** Recompute `cats.cell_exp_array` from the kept raw expression. */
export const rescale_cell_exp_array = (cats) => {
  const { cell_exp_raw: summed, cell_exp_included: included } = cats;
  if (!summed) return;

  const max_exp = cell_exp_display_max(cats);
  const new_exp_array = ensureExpressionArray(cats);
  for (let index = 0; index < summed.length; index += 1) {
    if (included[index]) {
      new_exp_array[index] = toExpressionByte(summed[index], max_exp);
    }
  }
  cats.cell_exp_array = new_exp_array;
};

/**
 * Fill `cats.cell_exp_array` with the expression of `inst_gene`, a gene name
 * or a list of genes. Several genes are summed per cell (raw values), and the
 * sum is scaled like a single gene, against the largest summed value instead
 * of one gene's meta_gene max.
 *
 * @returns {Promise<boolean>} false when a newer call replaced this one while
 *   it was loading (the array is then left to that call).
 */
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
  const gene_list = Array.isArray(inst_gene) ? inst_gene : [inst_gene];
  const request_id = (cats.exp_request_id = (cats.exp_request_id ?? 0) + 1);

  const expression = await Promise.all(
    gene_list.map((gene) =>
      load_gene_expression(base_url, version, gene, aws, cbgReader)
    )
  );
  if (cats.exp_request_id !== request_id) return false;

  // An empty metadata selection means no cells, not an unrestricted view.
  const allowedCellIds = cats.meta_cell_id_set ?? null;
  const num_cells = cats.cell_names_array.length;
  const summed = new Float64Array(num_cells);
  const included = new Uint8Array(num_cells);

  expression.forEach(({ cell_names, cell_exp }) => {
    cell_names.forEach((raw_name, i) => {
      const name = String(raw_name);
      let index = -1;
      let cell_name = name;

      if (!vector_name_integer) {
        index = cats.cell_name_to_index_map.get(name) ?? -1;
      } else {
        const cellIndex = Number(name);
        if (
          Number.isInteger(cellIndex) &&
          cellIndex >= 0 &&
          cellIndex < cats.nameMapping_inv.length
        ) {
          index = cellIndex;
          cell_name = String(cats.nameMapping_inv[cellIndex]);
        }
      }

      if (index < 0 || index >= num_cells) return;
      summed[index] += Number(cell_exp[i]) || 0;
      if (!allowedCellIds || allowedCellIds.has(cell_name)) {
        included[index] = 1;
      }
    });
  });

  // One gene keeps its whole-dataset max from meta_gene; a sum uses the
  // largest summed value over all cells (the same whole-dataset reference).
  cats.cell_exp_max =
    gene_list.length === 1
      ? Number(genes.meta_gene[gene_list[0]].max)
      : summed.reduce((max, value) => Math.max(max, value), 0);
  // Kept so the zoomed-out TRX slider can rescale opacity without refetching.
  cats.cell_exp_raw = summed;
  cats.cell_exp_included = included;
  rescale_cell_exp_array(cats);
  return true;
};
