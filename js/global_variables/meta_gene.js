import { get_arrow_table } from "../read_parquet/get_arrow_table"
import { options } from '../global_variables/fetch_options.js';

export const set_meta_gene = async (genes, base_url) => {

    let meta_gene_table = await get_arrow_table(base_url + '/meta_gene.parquet', options.fetch)

    let gene_names = meta_gene_table.getChild('__index_level_0__').toArray()
    let gene_mean = meta_gene_table.getChild('mean').toArray()
    let gene_std = meta_gene_table.getChild('std').toArray()
    let gene_max = meta_gene_table.getChild('max').toArray()

    gene_names.forEach((name, index) => {
        genes.meta_gene[name] = {
            mean: gene_mean[index],
            std: gene_std[index],
            max: gene_max[index],
        }

        genes.gene_counts.push({
            name: name,
            value: Number(gene_mean[index])
        })
    })

    genes.gene_counts.sort((a, b) => b.value - a.value)

    // Create a set of unique names
    const g_uniqueNames = [...new Set(gene_names)];

    // Create a mapping from gene name to a unique integer index
    const g_nameMapping = g_uniqueNames.reduce((acc, name, idx) => {
    acc[name] = idx;
    return acc;
    }, {});

    // Create the reverse mapping: integer index to gene name
    const g_nameMapping_inv = g_uniqueNames.reduce((acc, name, idx) => {
        acc[idx] = name;
        return acc;
    }, {});

    // Save the mapping and inverse mapping as cats.nameMapping_inv
    genes.g_nameMapping = g_nameMapping;
    genes.g_nameMapping_inv = g_nameMapping_inv;

    genes.gene_names = genes.gene_counts.map(gene => gene.name);

}
