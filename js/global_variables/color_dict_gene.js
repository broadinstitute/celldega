import { get_arrow_table } from '../read_parquet/get_arrow_table';
import {
  getRowKeyArray,
  getTableColumnArray,
} from '../read_parquet/table_accessors';
import { hexToRgb } from '../utils/hexToRgb';

import { options } from './fetch_options';

export const set_color_dict_gene = async (
  genes,
  base_url,
  seg_version,
  aws
) => {
  let meta_gene_url;

  if (seg_version === 'default') {
    meta_gene_url = `${base_url}/meta_gene.parquet`;
  } else {
    meta_gene_url = `${base_url}/meta_gene_${seg_version}.parquet`;
  }

  const tmp_meta_gene = await get_arrow_table(
    meta_gene_url,
    options.fetch,
    aws
  );

  // tmp_meta_gene is [] (not a real Arrow table) when the dataset has no
  // meta_gene.parquet (e.g. a gene-less point-cloud dataset) — fall through
  // to empty gene colors rather than crashing on a missing .getChild.
  let gene_names = getRowKeyArray(tmp_meta_gene, ['__index_level_0__'], {
    fallbackToRangeIndex: false,
  });
  let colors = getTableColumnArray(tmp_meta_gene, 'color');

  if (gene_names.length !== colors.length) {
    gene_names = [];
    colors = [];
  }

  genes.g_colorMapping_inv = [];

  gene_names.forEach((geneName, index) => {
    const rgb = hexToRgb(colors[index]);
    genes.color_dict_gene[geneName] = rgb;

    const geneId = genes.g_nameMapping?.[geneName];
    if (geneId !== undefined) {
      genes.g_colorMapping_inv[geneId] = rgb;
    }
  });

  genes.gene_names = gene_names;
};
