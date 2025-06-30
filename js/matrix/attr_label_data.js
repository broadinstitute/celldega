export const set_attr_label_data = (network, viz_state, axis) => {
  const isRow = axis === 'row';
  const nodes = isRow ? network.row_nodes : network.col_nodes;
  const numAttrs = isRow
    ? viz_state.cats.num_cats.row
    : viz_state.cats.num_cats.col;

  const titles = [];
  for (let i = 0; i < numAttrs; i++) {
    const catName = `cat-${i}`;
    let example = nodes.find((n) => n[catName]);
    let title = `attr-${i}`;
    if (example) {
      const val = example[catName];
      if (typeof val === 'string' && val.includes(':')) {
        title = val.split(':')[0];
      }
    }
    titles.push({ name: title, index: i });
  }

  if (!viz_state.cats.attr_titles) viz_state.cats.attr_titles = {};
  viz_state.cats.attr_titles[axis] = titles.map((d) => d.name);

  return titles;
};

export const set_row_attr_label_data = (network, viz_state) =>
  set_attr_label_data(network, viz_state, 'row');

export const set_col_attr_label_data = (network, viz_state) =>
  set_attr_label_data(network, viz_state, 'col');
