import { get_arrow_table } from "../read_parquet/get_arrow_table"
import { options } from '../global_variables/fetch_options.js';
import { set_gene_names } from "./gene_names.js";

export let meta_gene = {}

export let gene_counts = []

export const set_meta_gene = async (base_url) => {

    let meta_gene_table = await get_arrow_table(base_url + '/meta_gene.parquet', options.fetch)
    let gene_names = meta_gene_table.getChild('__index_level_0__').toArray()
    let gene_mean = meta_gene_table.getChild('mean').toArray()
    let gene_std = meta_gene_table.getChild('std').toArray()
    let gene_max = meta_gene_table.getChild('max').toArray()

    gene_names.forEach((name, index) => {
        meta_gene[name] = {
            mean: gene_mean[index],
            std: gene_std[index],
            max: gene_max[index],
        }

        gene_counts.push({
            name: name,
            value: Number(gene_mean[index])
        })
    })

    gene_counts.sort((a, b) => b.value - a.value)

    set_gene_names(gene_names)
}