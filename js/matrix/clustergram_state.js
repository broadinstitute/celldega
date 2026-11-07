/**
 * Read-only snapshot of what a Clustergram is showing: the getter half of the
 * Clustergram's Viz API. Clerk (and any agent or web app) uses it to see the same
 * rows, columns, order, groups, attributes and values as the user, including what
 * is currently on screen.
 *
 * Indices inside viz_state are "raw" (positions in row_nodes / col_nodes). The
 * snapshot reports everything by name, in display order, as plain JSON.
 */
import {
  get_axis_display_state,
  get_axis_indices_in_range,
} from './crop_filter';

export const CLUSTERGRAM_STATE_VERSION = 1;

const AXES = ['row', 'col'];
const DEFAULT_MAX_ITEMS = 50;
const MAX_GROUPS = 40;
const MAX_GROUP_MEMBERS = 30;
const MAX_LISTED = 100;

const ORDER_LABELS = {
  clust: 'clustered',
  rank: 'sum',
  rankvar: 'variance',
  ini: 'initial',
  alpha: 'alphabetical',
  custom: 'custom',
};

const round = (value, digits = 3) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const factor = 10 ** digits;
  return Math.round(number * factor) / factor;
};

const json_safe = (value) => {
  if (value === undefined) return null;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return String(value);
  }
};

const nodes = (viz_state, axis) => viz_state[`${axis}_nodes`] || [];

const name_at = (viz_state, axis, index) =>
  String(nodes(viz_state, axis)[index]?.name ?? index);

const observable_value = (store, key) => {
  const observable = store?.[key];
  return typeof observable?.get === 'function' ? observable.get() : undefined;
};

/**
 * World-coordinate bounds of the part of the matrix currently on screen, or null
 * when the deck has no matrix viewport yet (e.g. not rendered).
 * @param {object} viz_state
 * @returns {{min_x: number, max_x: number, min_y: number, max_y: number}|null}
 */
export const visible_world_bounds = (viz_state) => {
  const viewport = viz_state.deck_mat?.viewManager
    ?.getViewports?.()
    ?.find((candidate) => candidate.id === 'matrix');
  if (!viewport?.unproject) return null;
  const corner_a = viewport.unproject([0, 0]);
  const corner_b = viewport.unproject([viewport.width, viewport.height]);
  if (!Array.isArray(corner_a) || !Array.isArray(corner_b)) return null;
  return {
    min_x: Math.min(corner_a[0], corner_b[0]),
    max_x: Math.max(corner_a[0], corner_b[0]),
    min_y: Math.min(corner_a[1], corner_b[1]),
    max_y: Math.max(corner_a[1], corner_b[1]),
  };
};

/** Raw indices displayed after crop and marker-level filters, in display order. */
export const displayed_indices = (viz_state, axis) =>
  get_axis_display_state(viz_state, axis).visible_indices;

/**
 * Raw indices currently on screen, in display order. Falls back to every
 * displayed index when the on-screen bounds are unknown.
 */
export const viewport_indices = (
  viz_state,
  axis,
  bounds = visible_world_bounds(viz_state)
) => {
  const displayed = displayed_indices(viz_state, axis);
  if (!bounds) return displayed;
  const [min, max] =
    axis === 'row'
      ? [bounds.min_y, bounds.max_y]
      : [bounds.min_x, bounds.max_x];
  const shown = new Set(displayed);
  return get_axis_indices_in_range(viz_state, axis, min, max).filter((index) =>
    shown.has(index)
  );
};

/**
 * Pick the raw indices to report for one axis.
 * @param {'viewport'|'ranked'|string[]} spec - On screen, the top of the current
 *   display order, or explicit names (in the given order).
 */
const pick_axis = (viz_state, axis, spec, max_items, bounds) => {
  let indices;
  let mode;
  let missing = [];
  if (Array.isArray(spec)) {
    mode = 'names';
    const index_by_name = new Map(
      nodes(viz_state, axis).map((node, index) => [String(node?.name), index])
    );
    indices = [];
    spec.forEach((name) => {
      const index = index_by_name.get(String(name));
      if (index === undefined) missing.push(String(name));
      else indices.push(index);
    });
    missing = missing.slice(0, MAX_LISTED);
  } else if (spec === 'ranked') {
    mode = 'ranked';
    indices = displayed_indices(viz_state, axis);
  } else {
    mode = 'viewport';
    indices = viewport_indices(viz_state, axis, bounds);
  }
  const limit = Number.isFinite(Number(max_items))
    ? Math.max(0, Number(max_items))
    : DEFAULT_MAX_ITEMS;
  return {
    mode,
    indices: indices.slice(0, limit),
    total: indices.length,
    truncated: indices.length > limit,
    missing,
  };
};

const order_for = (viz_state, axis) => {
  const current = viz_state.order?.current?.[axis] ?? null;
  let label = ORDER_LABELS[current] ?? current;
  if (typeof current === 'string' && current.startsWith('attr_')) {
    const attr_name = viz_state.attr?.names?.[axis]?.[Number(current.slice(5))];
    label = `by attribute ${attr_name ?? current}`;
  }
  const order = { name: current, label };
  const driver = viz_state.labels?.reorder_driver;
  if (current === 'custom' && driver != null) {
    order.driver =
      typeof driver === 'string' ? driver : String(driver.name ?? driver);
  }
  return order;
};

const attributes_for = (viz_state, axis, indices) =>
  (viz_state.attr?.all_defs?.[axis] || []).map((definition) => {
    const values = indices.map((index) => {
      const value = definition.values?.[index];
      if (value == null) return null;
      return definition.type === 'numeric' ? round(value) : String(value);
    });
    const attribute = {
      name: String(definition.name),
      type: definition.type,
      values,
    };
    if (definition.type === 'categorical' && definition.color_map) {
      const present = new Set(values);
      attribute.colors = Object.fromEntries(
        Object.entries(definition.color_map).filter(([category]) =>
          present.has(category)
        )
      );
    }
    return attribute;
  });

const groups_for = (viz_state, axis) => {
  const info = viz_state.dendro?.group_info?.[axis];
  if (!Array.isArray(info)) return null;
  const sorted = [...info].sort((a, b) => (a.pos_mid ?? 0) - (b.pos_mid ?? 0));
  return {
    cut_percent: viz_state.dendro?.sliders?.[`${axis}_percent`] ?? null,
    n_groups: sorted.length,
    truncated: sorted.length > MAX_GROUPS,
    groups: sorted.slice(0, MAX_GROUPS).map((group) => ({
      name: String(group.name),
      size: group.all_names?.length ?? 0,
      members: (group.all_names || []).slice(0, MAX_GROUP_MEMBERS).map(String),
    })),
  };
};

const marker_level_for = (viz_state) => {
  const { rank_view } = viz_state;
  if (!rank_view || !Array.isArray(rank_view.views) || !rank_view.views.length)
    return null;
  return {
    current: rank_view.current ?? null, // null = all rows
    unit: rank_view.level_unit ?? null,
    view_type: rank_view.view_type ?? null,
    levels: rank_view.views.map((view) => view.level),
  };
};

const selection_for = (viz_state) => {
  const store = viz_state.obs_store;
  const dendro = observable_value(store, 'dendro_selection');
  const highlighted = viz_state.labels?.highlighted_genes;
  const crop = viz_state.crop?.filter || {};
  return {
    click: viz_state.click
      ? {
          type: viz_state.click.type ?? null,
          value: json_safe(viz_state.click.value),
        }
      : null,
    selected_genes: (observable_value(store, 'selected_genes') || [])
      .slice(0, MAX_LISTED)
      .map(String),
    dendro_group: dendro
      ? {
          axis: dendro.axis ?? null,
          name: dendro.name != null ? String(dendro.name) : null,
          members: (dendro.selected_names || [])
            .slice(0, MAX_LISTED)
            .map(String),
        }
      : null,
    enrich_term_genes:
      highlighted instanceof Set
        ? [...highlighted].slice(0, MAX_LISTED).map(String)
        : [],
    crop: Object.fromEntries(
      AXES.map((axis) => [
        axis,
        Array.isArray(crop[axis]) ? crop[axis].length : null,
      ])
    ),
  };
};

const values_for = (viz_state, row_indices, col_indices) => {
  const net = viz_state.mat?.net_mat;
  if (!Array.isArray(net)) return null;
  const values = row_indices.map((row) =>
    col_indices.map((col) => round(net[row]?.[col]))
  );

  // Dot sizes live only on the per-cell render data (cells with value ~0 are
  // skipped there), so collect them for just this window.
  let sizes = null;
  const mat_data = viz_state.mat?.mat_data;
  if (Array.isArray(mat_data) && row_indices.length && col_indices.length) {
    const row_pos = new Map(row_indices.map((row, i) => [row, i]));
    const col_pos = new Map(col_indices.map((col, j) => [col, j]));
    const grid = row_indices.map(() => col_indices.map(() => null));
    let has_size = false;
    for (const point of mat_data) {
      const i = row_pos.get(point.row);
      if (i === undefined) continue;
      const j = col_pos.get(point.col);
      if (j === undefined) continue;
      if (point.size_value) has_size = true;
      grid[i][j] = round(point.size_value);
    }
    if (has_size) sizes = grid;
  }
  return { values, sizes };
};

/**
 * Snapshot of the Clustergram as the user sees it.
 *
 * @param {object} viz_state - Clustergram visualization state.
 * @param {object} [options]
 * @param {'viewport'|'ranked'|string[]} [options.rows='viewport'] - Which rows:
 *   on screen, the top of the current order, or these names.
 * @param {'viewport'|'ranked'|string[]} [options.cols='viewport'] - Same for columns.
 * @param {number} [options.max_rows=50] - Cap on reported rows.
 * @param {number} [options.max_cols=50] - Cap on reported columns.
 * @param {boolean} [options.include_values=true] - Include the value (and dot
 *   size) block for the reported rows x columns.
 * @returns {object} JSON-safe snapshot.
 */
export const get_clustergram_state = (viz_state, options = {}) => {
  const {
    rows = 'viewport',
    cols = 'viewport',
    max_rows = DEFAULT_MAX_ITEMS,
    max_cols = DEFAULT_MAX_ITEMS,
    include_values = true,
  } = options;
  const bounds = visible_world_bounds(viz_state);
  const picks = {
    row: pick_axis(viz_state, 'row', rows, max_rows, bounds),
    col: pick_axis(viz_state, 'col', cols, max_cols, bounds),
  };

  const axis_state = (axis) => {
    const pick = picks[axis];
    return {
      selection_mode: pick.mode,
      names: pick.indices.map((index) => name_at(viz_state, axis, index)),
      total: pick.total,
      truncated: pick.truncated,
      missing: pick.missing,
      displayed: displayed_indices(viz_state, axis).length,
      count: nodes(viz_state, axis).length,
      order: order_for(viz_state, axis),
      attributes: attributes_for(viz_state, axis, pick.indices),
      groups: groups_for(viz_state, axis),
    };
  };

  return {
    kind: 'clustergram',
    version: CLUSTERGRAM_STATE_VERSION,
    on_screen_known: bounds !== null,
    rows: axis_state('row'),
    cols: axis_state('col'),
    marker_level: marker_level_for(viz_state),
    selection: selection_for(viz_state),
    values: include_values
      ? values_for(viz_state, picks.row.indices, picks.col.indices)
      : null,
  };
};
