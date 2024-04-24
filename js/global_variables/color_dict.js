import { get_arrow_table } from '../read_parquet/get_arrow_table.js'
import { options } from './fetch_options.js'
import { hexToRgb } from '../utils/hexToRgb.js'

export let color_dict = {}

export const set_color_dict = async ( base_url ) => {

    const meta_gene_url = base_url + `/gene_metadata.parquet`;
    var meta_gene = await get_arrow_table(meta_gene_url, options.fetch)

    let geneNames = [];
    let colors = [];

    const geneNameColumn = meta_gene.getChild('__index_level_0__');
    const colorColumn = meta_gene.getChild('color');

    if (geneNameColumn && colorColumn) {
        geneNames = geneNameColumn.toArray();
        colors = colorColumn.toArray();
    }    

    geneNames.forEach((geneName, index) => {
        color_dict[geneName] = hexToRgb(colors[index]);
    });

}