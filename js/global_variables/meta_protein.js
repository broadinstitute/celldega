import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import { hexToRgb } from '../utils/hexToRgb';

export const set_meta_protein = async (
  proteins,
  base_url,
  seg_version = 'default',
  aws
) => {
  let meta_protein_url;

  if (seg_version === 'default') {
    meta_protein_url = `${base_url}/meta_protein.parquet`;
  } else {
    meta_protein_url = `${base_url}/meta_protein_${seg_version}.parquet`;
  }

  try {
    const meta_protein_table = await get_arrow_table(
      meta_protein_url,
      options.fetch,
      aws
    );

    const proteinNamesColumn = meta_protein_table.getChild('__index_level_0__');
    const meanColumn = meta_protein_table.getChild('mean');
    const stdColumn = meta_protein_table.getChild('std');
    const maxColumn = meta_protein_table.getChild('max');
    const colorColumn = meta_protein_table.getChild('color');

    if (!proteinNamesColumn || !meanColumn || !stdColumn || !maxColumn) {
      throw new Error('Meta protein table missing required columns');
    }

    const protein_names = proteinNamesColumn.toArray();
    const protein_mean = meanColumn.toArray();
    const protein_std = stdColumn.toArray();
    const protein_max = maxColumn.toArray();
    const protein_colors = colorColumn ? colorColumn.toArray() : [];

    protein_names.forEach((name, index) => {
      proteins.meta_protein[name] = {
        mean: protein_mean[index],
        std: protein_std[index],
        max: protein_max[index],
      };

      proteins.protein_counts.push({
        name,
        value: Number(protein_mean[index]),
      });

      if (protein_colors[index]) {
        proteins.color_dict_protein[name] = hexToRgb(protein_colors[index]);
      }
    });

    proteins.protein_counts.sort((a, b) => b.value - a.value);
    proteins.top_protein_counts = proteins.protein_counts.slice(0, 100);
    proteins.protein_names = protein_names;
  } catch (error) {
    proteins.protein_counts = [];
    proteins.top_protein_counts = [];
    proteins.protein_names = [];
    proteins.load_error = error;
  }
};
