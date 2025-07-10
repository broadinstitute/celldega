import * as d3 from 'd3-color';

const colorToRgba = (colorStr, alpha = 255) => {
  const d3col = d3.color(colorStr);
  if (!d3col) {
    return [0, 0, 0, alpha]; // fallback: black
  }
  return [d3col.r, d3col.g, d3col.b, alpha];
};

export const set_cat_data = (network, viz_state, axis) => {

  console.log('set_cat_data', axis);

  const isRow = axis === 'row';
  const nodes = isRow ? network.row_nodes : network.col_nodes;
  const num_attr = isRow
    ? viz_state.attr.num.row
    : viz_state.attr.num.col;
  const max_abs = isRow
    ? viz_state.attr.maxabs.row
    : viz_state.attr.maxabs.col;
  const cat_offset = isRow
    ? viz_state.viz.row_cat_offset
    : viz_state.viz.col_cat_offset;
  const node_offset = isRow
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;

  console.log('num_attr', num_attr);
  console.log('max_abs', max_abs);

  // // 👇 Shift rows down by one row_offset (or fraction if needed)
  // const row_shift = isRow ? node_offset : 0;

  console.log(nodes)

  const cat_data = nodes
    .flatMap((node, node_index) => {
      return Array.from({ length: num_attr }).map((_, attr_index) => {
        let value;
        let color_rgba;
        const maxVal = max_abs[attr_index];
        const isNumeric = maxVal !== null && maxVal !== undefined;

        if (isNumeric) {
          const attr_name = `num-${attr_index}`;
          value = node[attr_name];
          if (value === undefined || value === null || isNaN(value)) {
            return null;
          }
          const pos = [255, 0, 0];
          const neg = [0, 0, 255];
          const color = value >= 0 ? pos : neg;
          const scale = maxVal === 0 ? 1 : maxVal;
          const alpha = Math.min(1, Math.abs(value) / scale);
          color_rgba = [...color, Math.round(alpha * 255)];
        } else {
          const cat_name = `cat-${attr_index}`;
          value = node[cat_name];
          if (!value) {
            return null;
          }
          const ini_color = network.global_cat_colors[value];
          color_rgba = colorToRgba(ini_color, 255);
        }

        return {
          position: isRow
            ? [cat_offset * (attr_index + 0.5) + 20, node_offset * (node_index + 0.5)]
            : [node_offset * (node_index + 0.5), cat_offset * (attr_index + 1.5) - 30],
          color: color_rgba,
          name: value,
          level: attr_index,
          original_index: node_index,
        };
      });
    })
    .filter(Boolean);

  console.log('cat_data', cat_data);

  return cat_data;

};