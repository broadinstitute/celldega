import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import {
  getRowKeyArray,
  getTableColumnArray,
} from '../read_parquet/table_accessors';

/**
 * Store per-gene statistics (arrays in gene_names order) on `genes`. A missing
 * `max` is left undefined; update_cell_exp_array then uses the loaded values.
 */
export const apply_meta_gene = (genes, gene_names, { mean, std, max }) => {
  gene_names.forEach((name, index) => {
    genes.meta_gene[name] = {
      mean: mean[index],
      std: std?.[index],
      max: max?.[index],
    };

    genes.gene_counts.push({
      name,
      value: Number(mean[index]),
    });
  });

  genes.gene_counts.sort((a, b) => b.value - a.value);
  genes.top_gene_counts = genes.gene_counts.slice(0, 100);

  // Create the reverse mapping: integer index to gene name
  const g_nameMapping_inv = gene_names.reduce((acc, name, idx) => {
    acc[idx] = name;
    return acc;
  }, {});

  const g_nameMapping = gene_names.reduce((acc, name, idx) => {
    acc[name] = idx;
    return acc;
  }, {});

  // Save the mapping as cats.nameMapping_inv
  genes.g_nameMapping_inv = g_nameMapping_inv;
  genes.g_nameMapping = g_nameMapping;

  genes.gene_names = gene_names;
};

export const set_meta_gene = async (
  genes,
  base_url,
  seg_version = 'default',
  aws
) => {
  let meta_gene_url;

  if (seg_version === 'default') {
    meta_gene_url = `${base_url}/meta_gene.parquet`;
  } else {
    meta_gene_url = `${base_url}/meta_gene_${seg_version}.parquet`;
  }

  const meta_gene_table = await get_arrow_table(
    meta_gene_url,
    options.fetch,
    aws
  );

  // meta_gene_table is [] (not a real Arrow table) when the dataset has no
  // meta_gene.parquet (e.g. a gene-less point-cloud dataset) — get_arrow_table
  // already logged/handled that fetch failure, so fall through to empty genes.
  const gene_names = getRowKeyArray(meta_gene_table, ['__index_level_0__'], {
    fallbackToRangeIndex: false,
  });
  apply_meta_gene(genes, gene_names, {
    mean: getTableColumnArray(meta_gene_table, 'mean'),
    std: getTableColumnArray(meta_gene_table, 'std'),
    max: getTableColumnArray(meta_gene_table, 'max'),
  });
};
