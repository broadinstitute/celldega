// import * as d3 from 'd3-color';

// const colorToRgba = (colorStr, alpha = 255) => {
//   const d3col = d3.color(colorStr);
//   if (!d3col) {
//     console.warn(`Invalid color: ${colorStr}`);
//     return [0, 0, 0, alpha]; // fallback: black
//   }
//   return [
//     d3col.r,
//     d3col.g,
//     d3col.b,
//     alpha
//   ];
// };

import * as d3 from 'd3-color';

const colorToRgba = (colorStr, alpha = 255) => {
  const d3col = d3.color(colorStr);
  if (!d3col) {
    console.warn(`Invalid color: ${colorStr}`);
    return [0, 0, 0, alpha]; // fallback: black
  }
  return [d3col.r, d3col.g, d3col.b, alpha];
};





// export const set_row_cat_data = (network, viz_state) => {
//   const row_cat_data = network.row_nodes.map((node, index_row) => {
//     // Get the cat-0 value (e.g., 'type: low')
//     const ini_cat = node['cat-0'];

//     if (!ini_cat) {
//       console.warn(`Missing cat-0 for row node ${node.name}`);
//       return null;  // skip if missing
//     }

//     // Parse out the actual type value
//     const clean_cat = ini_cat.split(': ')[1];

//     // Get the color from cat_colors
//     const ini_color = network.global_cat_colors[clean_cat]

//     // Convert hex to rgba
//     const color_rgba = colorToRgba(ini_color, 255);

//     // Create point
//     return {
//       position: [
//         viz_state.viz.row_cat_offset * 0.5 + 20,  // adjust x position for row cat
//         viz_state.viz.row_offset * (index_row + 0.5)
//       ],
//       color: color_rgba,
//       name: clean_cat
//     };
//   }).filter(Boolean);  // Remove nulls

//   return row_cat_data;
// };


// export const set_col_cat_data = (network, viz_state) => {

//   let index_row = 0;
//   let matrix_index = 0;

//   const col_cat_data = network.col_nodes.map((node, index_col) => {

//     if (matrix_index % viz_state.mat.num_cols === 0) {
//       index_row += 1;
//     }

//     // Get the cat-0 info for this node
//     const ini_cat = node['cat-0']; // e.g., 'type: low'

//     // Parse the type if needed (remove 'type: ' prefix)
//     const clean_cat = ini_cat.split(': ')[1];

//     // Get the color from network.cat_colors.col
//     const ini_color = network.global_cat_colors[clean_cat]

//     // Convert hex to rgba
//     const color_rgba = colorToRgba(ini_color, 255); // helper function below

//     const p = {
//       position: [
//         viz_state.viz.col_offset * (index_col + 0.5),
//         // move cats down
//         viz_state.viz.col_cat_offset * (index_row + 1.5) - 30,
//       ],
//       color: color_rgba,
//       name: clean_cat
//     };

//     matrix_index += 1;

//     return p;
//   });

//   return col_cat_data;
// };

const set_cat_data = (network, viz_state, axis) => {
  const isRow = axis === 'row';
  const nodes = isRow ? network.row_nodes : network.col_nodes;
  const num_cats = isRow ? viz_state.cats.num_cats.row : viz_state.cats.num_cats.col;
  const cat_offset = isRow ? viz_state.viz.row_cat_offset : viz_state.viz.col_cat_offset;
  const node_offset = isRow ? viz_state.viz.row_offset : viz_state.viz.col_offset;

  const cat_data = nodes.flatMap((node, node_index) => {
    return Array.from({ length: num_cats }).map((_, cat_index) => {
      const cat_name = `cat-${cat_index}`;
      const ini_cat = node[cat_name];

      if (!ini_cat) {
        console.warn(`Missing ${cat_name} for ${axis} node ${node.name}`);
        return null;
      }

      const clean_cat = ini_cat.split(': ')[1];
      const ini_color = network.global_cat_colors[clean_cat];

      const color_rgba = colorToRgba(ini_color, 255);

      return {
        position: isRow
          ? [
              cat_offset * (cat_index + 0.5) + 20,
              node_offset * (node_index + 0.5)
            ]
          : [
              node_offset * (node_index + 0.5),
              cat_offset * (cat_index + 1.5) - 30
            ],
        color: color_rgba,
        name: clean_cat
      };
    });
  }).filter(Boolean); // remove nulls

  return cat_data;
};


export const set_row_cat_data = (network, viz_state) => {
  return set_cat_data(network, viz_state, 'row');
};

export const set_col_cat_data = (network, viz_state) => {
  return set_cat_data(network, viz_state, 'col');
};
