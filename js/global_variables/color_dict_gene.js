import { get_arrow_table } from '../read_parquet/get_arrow_table';
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

  let gene_names = [];
  let colors = [];

  const geneNameColumn = tmp_meta_gene.getChild('__index_level_0__');
  const colorColumn = tmp_meta_gene.getChild('color');

  if (geneNameColumn && colorColumn) {
    gene_names = geneNameColumn.toArray();
    colors = colorColumn.toArray();
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
