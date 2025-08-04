import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';

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

  const gene_names = meta_gene_table.getChild('__index_level_0__').toArray();
  const gene_mean = meta_gene_table.getChild('mean').toArray();
  const gene_std = meta_gene_table.getChild('std').toArray();
  const gene_max = meta_gene_table.getChild('max').toArray();

  gene_names.forEach((name, index) => {
    genes.meta_gene[name] = {
      mean: gene_mean[index],
      std: gene_std[index],
      max: gene_max[index],
    };

    genes.gene_counts.push({
      name,
      value: Number(gene_mean[index]),
    });
  });

  genes.gene_counts.sort((a, b) => b.value - a.value);
  genes.top_gene_counts = genes.gene_counts.slice(0, 1000);

  // Create the reverse mapping: integer index to gene name
  const g_nameMapping_inv = gene_names.reduce((acc, name, idx) => {
    acc[idx] = name;
    return acc;
  }, {});

  // Save the mapping as cats.nameMapping_inv
  genes.g_nameMapping_inv = g_nameMapping_inv;

  genes.gene_names = gene_names;
};
