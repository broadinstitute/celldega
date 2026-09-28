import { buildCellCompactData, createEmptyCellCompact } from '../utils/compact_data';
import { hexToRgb } from '../utils/hexToRgb';

export const MISSING_ATTRIBUTE_COLOR = [156, 163, 175];
export const NUMERIC_COLOR_START = [239, 243, 255];
export const NUMERIC_COLOR_END = [8, 48, 107];

export const numeric_attribute_color = (value, domain) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return MISSING_ATTRIBUTE_COLOR;
  }
  const [min, max] = domain || [0, 1];
  const fraction = max > min ? Math.max(0, Math.min(1, (value - min) / (max - min))) : 0.5;
  return NUMERIC_COLOR_START.map((start, index) =>
    Math.round(start + fraction * (NUMERIC_COLOR_END[index] - start))
  );
};

/** Rebuild active annotation values while retaining the shared category palette object. */
export const apply_cell_attribute = (viz_state, attribute) => {
  const cats = viz_state.cats;
  const index = cats.meta_cell_attr.indexOf(attribute);
  if (index < 0 || attribute === 'color') return false;
  const types = viz_state.model?.get?.('cell_attribute_types') || {};
  const palettes = viz_state.model?.get?.('cell_attribute_colors') || {};
  const values = cats.cell_names_array.map((name) => {
    const stripped = viz_state.cell_name_prefix ? name.slice(name.indexOf('_') + 1) : name;
    return (cats.meta_cell[name] || cats.meta_cell[stripped])?.[index] ?? null;
  });
  const observed = values.filter((value) => value !== null);
  const numeric = types[attribute]
    ? types[attribute] === 'numeric'
    : observed.length > 0 && observed.every((value) => typeof value === 'number');

  cats.attribute_palettes ||= {};
  if (!cats.attribute_numeric && cats.inst_cell_attr) {
    cats.attribute_palettes[cats.inst_cell_attr] = { ...cats.color_dict_cluster };
  }
  const previousPalette = cats.attribute_palettes[attribute] || {};
  const palette = cats.color_dict_cluster;
  Object.keys(palette).forEach((key) => delete palette[key]);
  cats.inst_cell_attr = attribute;
  cats.attribute_numeric = numeric;
  cats.cell_cats = numeric ? values : values.map((value) => value == null ? 'N.A.' : String(value));
  cats.dict_cell_cats = Object.fromEntries(cats.cell_names_array.map((name, i) => [name, cats.cell_cats[i]]));
  cats.has_dict_cell_cats = true;
  cats.selected_cats = [];
  cats.cat = 'cluster';

  if (numeric) {
    let min = Infinity;
    let max = -Infinity;
    values.forEach((value) => {
      if (typeof value === 'number' && Number.isFinite(value)) {
        min = Math.min(min, value);
        max = Math.max(max, value);
      }
    });
    cats.numeric_domain = min <= max ? [min, max] : [0, 1];
    cats.numeric_missing = values.filter((value) => typeof value !== 'number' || !Number.isFinite(value)).length;
    cats.cluster_counts = [];
    viz_state.combo_data.cell_compact = createEmptyCellCompact();
  } else {
    const counts = new Map();
    cats.cell_cats.forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
    const names = [...counts.keys()].sort();
    names.forEach((name, i) => {
      const hex = palettes[attribute]?.[name];
      palette[name] = name === 'N.A.' ? MISSING_ATTRIBUTE_COLOR : hex ? hexToRgb(hex) : previousPalette[name] || [70 + (i * 67) % 160, 70 + (i * 97) % 160, 70 + (i * 43) % 160];
    });
    cats.cluster_counts = [...counts].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
    const coordinates = viz_state.spatial.cell_scatter_data?.attributes?.getPosition;
    viz_state.combo_data.cell_compact = buildCellCompactData(cats.cell_names_array, coordinates?.value, coordinates?.size || 2, cats.dict_cell_cats);
  }
  if (viz_state.viewport_cache) viz_state.viewport_cache.lastCellBarData = null;
  return true;
};
