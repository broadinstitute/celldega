import * as d3 from 'd3-color';

const colorToRgba = (colorStr, alpha = 255) => {
  const d3col = d3.color(colorStr);
  if (!d3col) {
    return [0, 0, 0, alpha]; // fallback: black
  }
  return [d3col.r, d3col.g, d3col.b, alpha];
};

const set_cat_data = (network, viz_state, axis) => {

  const isRow = axis === 'row';
  const nodes = isRow ? network.row_nodes : network.col_nodes;
  const num_cats = isRow
    ? viz_state.cats.num_cats.row
    : viz_state.cats.num_cats.col;
  const cat_offset = isRow
    ? viz_state.viz.row_cat_offset
    : viz_state.viz.col_cat_offset;
  const node_offset = isRow
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;

  // // 👇 Shift rows down by one row_offset (or fraction if needed)
  // const row_shift = isRow ? node_offset : 0;

  const cat_data = nodes
    .flatMap((node, node_index) => {
      return Array.from({ length: num_cats }).map((_, cat_index) => {

        const cat_name = `cat-${cat_index}`;
        const inst_cat = node[cat_name];

        if (!inst_cat) {
          return null;
        }

        const ini_color = network.global_cat_colors[inst_cat];
        const color_rgba = colorToRgba(ini_color, 255);

        return {
          position: isRow
            ? [
                cat_offset * (cat_index + 0.5) + 20,
                node_offset * (node_index + 0.5),
              ]
            : [
                node_offset * (node_index + 0.5),
                cat_offset * (cat_index + 1.5) - 30,
              ],
          color: color_rgba,
          name: inst_cat,
          level: cat_index,
          original_index: node_index,
        };
      });
    })
    .filter(Boolean);

  return cat_data;
};

export const set_row_cat_data = (network, viz_state) => {
  return set_cat_data(network, viz_state, 'row');
};

export const set_col_cat_data = (network, viz_state) => {
  return set_cat_data(network, viz_state, 'col');
};
