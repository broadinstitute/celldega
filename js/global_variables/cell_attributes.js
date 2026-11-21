/**
 * What a Landscape's cells are shown by: its clusters (the default), another
 * per-cell attribute (a `cell_attr` column), or a label set that names clusters
 * (the model's `label_sets`, e.g. Clustergram cell-type labels or Clerk's
 * proposed cell types).
 *
 * - A per-cell attribute replaces the cells' categories: colors, bars and bar
 *   selections are its values.
 * - A label set only changes how clusters are shown: each labeled cluster takes
 *   its label's color and the bar graph has one bar per label, while selections
 *   stay clusters. So cluster links (Clustergram, Clerk, saved views) keep
 *   working under a label set.
 *
 * The clusters are kept as `cats.base` so switching back is exact, and the loaded
 * data's identity (snapshot.js) always uses them.
 */
import * as d3 from 'd3';

import { hexToRgb } from '../utils/hexToRgb';

const meta_cell_attrs = (name, meta_cell, cell_name_prefix) => {
  if (meta_cell[name] !== undefined) return meta_cell[name];
  if (cell_name_prefix && typeof name === 'string') {
    const idx = name.indexOf('_');
    if (idx >= 0) return meta_cell[name.substring(idx + 1)];
  }
  return undefined;
};

const to_rgb = (color) => {
  if (Array.isArray(color)) return color.slice(0, 3);
  if (typeof color !== 'string' || !color) return null;
  if (color.startsWith('#')) return hexToRgb(color);
  const rgb = d3.rgb(color);
  return Number.isFinite(rgb.r) ? [rgb.r, rgb.g, rgb.b] : null;
};

// Evenly spaced hues, like the Python HSV fallback for uncolored categories.
const palette_color = (i, n) => {
  const rgb = d3.rgb(d3.interpolateRainbow(i / Math.max(n, 1)));
  return [rgb.r, rgb.g, rgb.b];
};

const replace_in_place = (target, source) => {
  Object.keys(target).forEach((key) => delete target[key]);
  Object.assign(target, source);
};

/** The model's label sets: `{name: {labels: {cluster: label}, colors: {label: hex}}}`. */
export const get_label_sets = (viz_state) => {
  const sets = viz_state.model?.get?.('label_sets');
  return sets && typeof sets === 'object' && !Array.isArray(sets) ? sets : {};
};

/** The clusters' attribute (what `cluster_attr` colors cells by). */
export const base_attribute = (cats) =>
  cats.base?.attribute ?? cats.inst_cell_attr;

const capture_base = (cats) => {
  if (cats.base) return cats.base;
  cats.base = {
    attribute: cats.inst_cell_attr,
    cell_cats: cats.cell_cats,
    colors: { ...(cats.color_dict_cluster || {}) },
    cluster_counts: cats.cluster_counts,
  };
  return cats.base;
};

/**
 * The attributes the CELL menu offers: `{value, label, kind}`; `value` '' is the
 * clusters, `kind` 'cell' a per-cell attribute, 'labels' a label set.
 */
export const cell_attribute_options = (viz_state) => {
  const { cats } = viz_state;
  const base = base_attribute(cats);
  const options = [
    {
      value: '',
      label: cats.has_meta_cell && base && base !== 'N.A.' ? base : 'cluster',
      kind: null,
    },
  ];
  if (cats.has_meta_cell) {
    (cats.meta_cell_attr || [])
      .filter((attr) => attr !== base && attr !== 'color')
      .forEach((attr) =>
        options.push({ value: attr, label: attr, kind: 'cell' })
      );
  }
  Object.keys(get_label_sets(viz_state)).forEach((name) => {
    if (name && !options.some((option) => option.value === name))
      options.push({ value: name, label: name, kind: 'labels' });
  });
  return options;
};

/** Normalized: the clusters' own attribute name means the clusters (''). */
export const normalize_cell_attribute = (viz_state, name) => {
  const value = String(name ?? '');
  return value === base_attribute(viz_state.cats) ? '' : value;
};

/** `{cluster: label}` of the label set shown, or null. */
export const active_labels = (viz_state) => {
  const { cats } = viz_state;
  if (cats.attribute_kind !== 'labels') return null;
  return get_label_sets(viz_state)[cats.attribute]?.labels || null;
};

/** The bar a cluster belongs to: its label under a label set, else itself. */
export const bar_name_of = (viz_state, cluster) => {
  const labels = active_labels(viz_state);
  const name = String(cluster);
  return labels?.[name] ? String(labels[name]) : name;
};

/** Cluster counts grouped into one bar per label (largest first) under a label set. */
export const group_bar_data = (viz_state, bars = []) => {
  if (!active_labels(viz_state)) return bars;
  const totals = new Map();
  bars.forEach(({ name, value }) => {
    const label = bar_name_of(viz_state, name);
    totals.set(label, (totals.get(label) || 0) + (Number(value) || 0));
  });
  return [...totals]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
};

/** The clusters a bar stands for (just itself unless a label set is shown). */
export const clusters_of_bar = (viz_state, name) => {
  // As given (bar names may be numbers; selections compare them exactly).
  if (!active_labels(viz_state)) return [name];
  const clusters = Object.keys(viz_state.cats.base?.colors || {});
  return clusters.filter(
    (cluster) => bar_name_of(viz_state, cluster) === String(name)
  );
};

/** Bars to highlight for the selected clusters. */
export const selected_bar_names = (viz_state, selected = []) => [
  ...new Set(selected.map((cluster) => bar_name_of(viz_state, cluster))),
];

const count_categories = (cell_cats) => {
  const counts = new Map();
  cell_cats.forEach((cat) => {
    const key = cat == null ? 'N.A.' : String(cat);
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return [...counts]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
};

/**
 * Show cells by `name` (see {@link cell_attribute_options}); '' (or the clusters'
 * attribute) returns to the clusters. Updates the categories, colors and counts in
 * `viz_state.cats`; the caller redraws (see Landscape `refresh_cell_attribute`).
 *
 * @returns {{changed_categories: boolean}} Whether the cells' categories changed
 *   (a per-cell attribute entered or left): selections then no longer apply.
 */
export const set_cell_attribute = (viz_state, name) => {
  const { cats } = viz_state;
  const value = normalize_cell_attribute(viz_state, name);
  const option = cell_attribute_options(viz_state).find(
    (item) => item.value === value
  );
  if (!option) throw new Error(`unknown cell attribute: ${value}`);
  const was_cell = cats.attribute_kind === 'cell';
  if (!value && !cats.base) {
    cats.attribute = '';
    cats.attribute_kind = null;
    return { changed_categories: false };
  }
  const base = capture_base(cats);

  // Back to the clusters, then on to the choice.
  cats.cell_cats = base.cell_cats;
  cats.inst_cell_attr = base.attribute;
  cats.cluster_counts = base.cluster_counts;
  const colors = { ...base.colors };

  if (option.kind === 'cell') {
    const index = cats.meta_cell_attr.indexOf(value);
    const prefix = viz_state.cell_name_prefix || false;
    cats.cell_cats = cats.cell_names_array.map((cell) => {
      const attrs = meta_cell_attrs(cell, cats.meta_cell, prefix);
      const cat = attrs?.[index];
      return cat == null || cat === 'nan' ? 'N.A.' : String(cat);
    });
    cats.inst_cell_attr = value;
    cats.cluster_counts = count_categories(cats.cell_cats);
    const given = viz_state.model?.get?.('cell_attr_colors')?.[value] || {};
    replace_in_place(colors, {});
    cats.cluster_counts.forEach(({ name: cat }, i, all) => {
      colors[cat] = to_rgb(given[cat]) || palette_color(i, all.length);
    });
  } else if (option.kind === 'labels') {
    const set = get_label_sets(viz_state)[value] || {};
    const labels = set.labels || {};
    const label_colors = set.colors || {};
    Object.keys(base.colors).forEach((cluster) => {
      const label = labels[cluster];
      if (!label) return;
      // A label's own color, else that of its first cluster.
      colors[label] ??= to_rgb(label_colors[label]) || base.colors[cluster];
      colors[cluster] = colors[label];
    });
  }
  // In place: the bar graph and layers hold this object.
  replace_in_place(cats.color_dict_cluster, colors);
  cats.attribute = value;
  cats.attribute_kind = option.kind;
  return { changed_categories: was_cell || option.kind === 'cell' };
};

/** Back to the clusters' attribute, forgetting the kept clusters (before their
 * data is replaced, e.g. a dataset switch). The caller reloads the categories. */
export const reset_cell_attribute = (cats) => {
  if (cats.base) cats.inst_cell_attr = cats.base.attribute;
  cats.base = null;
  cats.attribute = '';
  cats.attribute_kind = null;
};
