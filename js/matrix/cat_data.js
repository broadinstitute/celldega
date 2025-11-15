import * as d3 from 'd3-color';

export const color_to_rgba = (color_str, alpha = 255) => {
  const d3_color = d3.color(color_str);
  if (!d3_color) {
    return [0, 0, 0, alpha];
  }
  return [d3_color.r, d3_color.g, d3_color.b, alpha];
};

export const set_cat_data = (network, viz_state, axis) => {
  const is_row = axis === 'row';
  const nodes = is_row ? network.row_nodes : network.col_nodes;
  const num_attr = is_row ? viz_state.attr.num.row : viz_state.attr.num.col;
  const max_abs = is_row ? viz_state.attr.maxabs.row : viz_state.attr.maxabs.col;
  const cat_offset = is_row
    ? viz_state.viz.row_cat_offset
    : viz_state.viz.col_cat_offset;
  const node_offset = is_row
    ? viz_state.viz.row_offset
    : viz_state.viz.col_offset;

  const cat_data = nodes
    .flatMap((node, node_index) => {
      return Array.from({ length: num_attr }).map((_, attr_index) => {
        let value;
        let color_rgba;
        const max_val = max_abs[attr_index];
        const is_numeric = max_val !== null && max_val !== undefined;

        if (is_numeric) {
          const attr_name = `num-${attr_index}`;
          value = node[attr_name];
          if (value === undefined || value === null || isNaN(value)) {
            return null;
          }
          const neg = [255, 165, 0];
          const pos = [169, 169, 169];
          const color = value >= 0 ? pos : neg;
          const scale = max_val === 0 ? 1 : max_val;
          const alpha = Math.min(1, Math.abs(value) / scale);
          color_rgba = [...color, Math.round(alpha * 255)];
        } else {
          const cat_name = `cat-${attr_index}`;
          value = node[cat_name];
          if (!value) {
            return null;
          }
          const ini_color = network.global_cat_colors[value];
          color_rgba = color_to_rgba(ini_color, 255);
        }

        return {
          position: is_row
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
