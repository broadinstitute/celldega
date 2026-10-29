import * as d3 from 'd3-color';

export const colorToRgba = (colorStr, alpha = 255) => {
  const d3col = d3.color(colorStr);
  if (!d3col) {
    return [0, 0, 0, alpha]; // fallback: black
  }
  return [d3col.r, d3col.g, d3col.b, alpha];
};

export const set_cat_data = (network, viz_state, axis) => {
  const isRow = axis === 'row';
  const nodes = isRow ? network.row_nodes : network.col_nodes;
  const num_attr = isRow ? viz_state.attr.num.row : viz_state.attr.num.col;
  const max_abs = isRow ? viz_state.attr.maxabs.row : viz_state.attr.maxabs.col;
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
          // Use customizable colors for value attributes
          // Default: gray for positive, orange for negative
          const value_colors = viz_state.value_colors || {};
          const pos_color = colorToRgba(
            value_colors.positive || '#a9a9a9',
            255
          );
          const neg_color = colorToRgba(
            value_colors.negative || '#ffa500',
            255
          );
          const color = value >= 0 ? pos_color : neg_color;
          const scale = maxVal === 0 ? 1 : maxVal;
          const alpha = Math.min(1, Math.abs(value) / scale);
          color_rgba = [color[0], color[1], color[2], Math.round(alpha * 255)];
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
            ? [
                cat_offset * (attr_index + 0.5) + 20,
                node_offset * (node_index + 0.5),
              ]
            : [
                node_offset * (node_index + 0.5),
                cat_offset * (attr_index + 1.5) - 30,
              ],
          color: color_rgba,
          name: value,
          level: attr_index,
          original_index: node_index,
        };
      });
    })
    .filter(Boolean);

  return cat_data;
};
