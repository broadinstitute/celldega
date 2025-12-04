const index_offset = 1;

const normalizeAxis = (axis) => (axis === 'col' ? 'col' : 'row');

const labelKeyForAxis = (axis) =>
  normalizeAxis(axis) === 'col' ? 'col_label_data' : 'row_label_data';

const formatDisplayName = (name, manualValue) => {
  if (!name) return '';
  return manualValue ? `${name} (${manualValue})` : name;
};

export const update_label_display_names = (viz_state, axis) => {
  if (!viz_state || !viz_state.labels) return;

  const normalizedAxis = normalizeAxis(axis);
  const labels_key = labelKeyForAxis(normalizedAxis);
  const labels = viz_state.labels[labels_key];
  if (!Array.isArray(labels)) return;

  const flags = viz_state.manual_cat?.flags || {};
  const store = viz_state.obs_store?.manual_cat?.[normalizedAxis];
  const can_show = !!(
    store?.getValueFor &&
    store?.attribute &&
    flags[normalizedAxis]
  );

  const updated = labels.map((entry) => {
    const manualValue =
      can_show && entry?.name ? store.getValueFor(entry.name) : null;
    return {
      ...entry,
      display_name: formatDisplayName(entry?.name, manualValue),
    };
  });

  viz_state.labels[labels_key] = updated;
};

export const set_col_label_data = (network, viz_state) => {
  const col_label_data = [];

  network.col_nodes.forEach((node, index) => {
    const p = {
      name: node.name,
      ini: node.ini,
      clust: node.clust,
      rank: node.rank,
      rankvar: node.rankvar,
      index,
    };
    col_label_data.push(p);
  });

  viz_state.labels.col_label_data = col_label_data;

  viz_state.labels.clicks.col = 0;

  viz_state.mat.orders.col = {};
  viz_state.mat.orders.col.ini = col_label_data.map((d) => d.ini);
  viz_state.mat.orders.col.clust = col_label_data.map(
    (d) => d.clust + index_offset
  );
  viz_state.mat.orders.col.rank = col_label_data.map(
    (d) => d.rank + index_offset
  );
  viz_state.mat.orders.col.rankvar = col_label_data.map(
    (d) => d.rankvar + index_offset
  );

  update_label_display_names(viz_state, 'col');
};

export const set_row_label_data = (network, viz_state) => {
  const row_label_data = [];

  network.row_nodes.forEach((node, index) => {
    const p = {
      name: node.name,
      ini: node.ini,
      clust: node.clust,
      rank: node.rank,
      rankvar: node.rankvar,
      index,
    };
    row_label_data.push(p);
  });

  viz_state.labels.row_label_data = row_label_data;
  viz_state.labels.clicks.row = 0;

  viz_state.mat.orders.row = {};
  viz_state.mat.orders.row.ini = row_label_data.map((d) => d.ini);
  viz_state.mat.orders.row.clust = row_label_data.map(
    (d) => d.clust + index_offset
  );
  viz_state.mat.orders.row.rank = row_label_data.map(
    (d) => d.rank + index_offset
  );
  viz_state.mat.orders.row.rankvar = row_label_data.map(
    (d) => d.rankvar + index_offset
  );

  update_label_display_names(viz_state, 'row');
};
