import { get_arrow_table } from '../read_parquet/get_arrow_table.js'
import { options } from './fetch_options.js'
import { hexToRgb } from '../utils/hexToRgb.js'

export const set_color_dict_gene = async (genes, base_url, seg_version='default') => {

    let meta_gene_url

    console.log('seg_version', seg_version)

    if (seg_version === 'default'){
        meta_gene_url = base_url + '/meta_gene.parquet';
    } else {
        meta_gene_url = base_url + '/meta_gene_' + seg_version + '.parquet';
    }

    console.log('meta_gene_url', meta_gene_url)

    let tmp_meta_gene = await get_arrow_table(meta_gene_url, options.fetch)

    let gene_names = [];
    let colors = [];

    const geneNameColumn = tmp_meta_gene.getChild('__index_level_0__');
    const colorColumn = tmp_meta_gene.getChild('color');

    if (geneNameColumn && colorColumn) {
        gene_names = geneNameColumn.toArray();
        colors = colorColumn.toArray();
    }

    gene_names.forEach((geneName, index) => {
        genes.color_dict_gene[geneName] = hexToRgb(colors[index]);
    })

    genes.gene_names = gene_names

}