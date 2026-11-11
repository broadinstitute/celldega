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
import {
  get_replay_controls,
  validate_replay_controls,
  restore_annotations,
} from './replay_controls';

export const CLUSTERGRAM_STATE_VERSION = 1;

const AXES = ['row', 'col'];
const NAMED_ORDERS = ['clust', 'rank', 'rankvar', 'ini', 'alpha'];
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

/** Raw indices for names (in the given order), plus the names not found. */
const indices_for_names = (viz_state, axis, names) => {
  const index_by_name = new Map(
    nodes(viz_state, axis).map((node, index) => [String(node?.name), index])
  );
  const indices = [];
  const missing = [];
  names.forEach((name) => {
    const index = index_by_name.get(String(name));
    if (index === undefined) missing.push(String(name));
    else indices.push(index);
  });
  return { indices, missing: missing.slice(0, MAX_LISTED) };
};

/**
 * Pick the raw indices to report for one axis.
 * @param {'viewport'|'ranked'|string[]} spec - On screen, the top of the current
 *   display order, or explicit names (in the given order).
 * @param {string[]} [extra] - Names to add after the main selection (e.g. genes the
 *   user asked about that are not on screen); they don't count toward max_items.
 */
const pick_axis = (viz_state, axis, spec, max_items, bounds, extra = []) => {
  let indices;
  let mode;
  let missing = [];
  if (Array.isArray(spec)) {
    mode = 'names';
    ({ indices, missing } = indices_for_names(viz_state, axis, spec));
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
  const picked = indices.slice(0, limit);

  const added = [];
  if (Array.isArray(extra) && extra.length) {
    const already = new Set(picked);
    const found = indices_for_names(
      viz_state,
      axis,
      extra.slice(0, MAX_LISTED)
    );
    found.indices.forEach((index) => {
      if (!already.has(index)) {
        already.add(index);
        picked.push(index);
        added.push(index);
      }
    });
    missing = [...missing, ...found.missing].slice(0, MAX_LISTED);
  }

  return {
    mode,
    indices: picked,
    added,
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

const DEFAULT_MARKERS_PER_CLUSTER = 10;
const MAX_MARKERS_PER_CLUSTER = 100;

/**
 * Each requested cluster's ranked markers (rank_genes_groups), read from the
 * front end, with the gene's value and dot size in that cluster's column.
 * @param {{clusters?: string[], n?: number}} spec - Clusters (default: all) and
 *   markers per cluster.
 */
const markers_for = (viz_state, spec) => {
  const markers = viz_state.rank_view?.markers || {};
  const groups = Object.keys(markers);
  if (!spec || !groups.length) return null;
  const n = Math.min(
    MAX_MARKERS_PER_CLUSTER,
    Math.max(1, Number(spec.n) || DEFAULT_MARKERS_PER_CLUSTER)
  );
  const wanted =
    Array.isArray(spec.clusters) && spec.clusters.length
      ? spec.clusters.map(String)
      : groups;
  const col_by_name = new Map(
    nodes(viz_state, 'col').map((node, index) => [String(node?.name), index])
  );
  const net = viz_state.mat?.net_mat;

  // Dot sizes only live on the per-cell render data; collect the needed cells.
  const sizes = new Map();
  wanted.forEach((group) => {
    const col = col_by_name.get(group);
    if (col === undefined) return;
    (markers[group] || [])
      .slice(0, n)
      .forEach((row) => sizes.set(`${row},${col}`, null));
  });
  if (sizes.size && Array.isArray(viz_state.mat?.mat_data)) {
    for (const point of viz_state.mat.mat_data) {
      const key = `${point.row},${point.col}`;
      if (sizes.has(key)) sizes.set(key, round(point.size_value));
    }
  }

  return wanted.map((group) => {
    const col = col_by_name.get(group);
    return {
      cluster: group,
      found: group in markers,
      genes: (markers[group] || []).slice(0, n).map((row, i) => ({
        name: name_at(viz_state, 'row', row),
        rank: i + 1,
        value: col === undefined ? null : round(net?.[row]?.[col]),
        size: col === undefined ? null : (sizes.get(`${row},${col}`) ?? null),
      })),
    };
  });
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

const camera_for = (viz_state) => {
  const camera = viz_state.zoom?.zoom_data?.matrix;
  return camera
    ? {
        target: [camera.pan_x, camera.pan_y],
        zoom: [camera.zoom_x, camera.zoom_y],
      }
    : null;
};

const current_order = (viz_state, axis) =>
  viz_state.order?.current?.[axis] || 'clust';

const crop_filter = (viz_state, axis) =>
  Array.isArray(viz_state.crop?.filter?.[axis])
    ? viz_state.crop.filter[axis]
    : null;

/** Replayable controls, complete: every name of an explicit order or crop. */
export const get_clustergram_controls = (viz_state) => ({
  view: camera_for(viz_state),
  crop: Object.fromEntries(
    AXES.map((axis) => [
      axis,
      crop_filter(viz_state, axis)?.map((index) =>
        name_at(viz_state, axis, index)
      ) ?? null,
    ])
  ),
  order: Object.fromEntries(
    AXES.map((axis) => {
      const current = current_order(viz_state, axis);
      if (NAMED_ORDERS.includes(current)) return [axis, current];
      const ranks = viz_state.mat?.orders?.[axis]?.[current] || [];
      return [
        axis,
        nodes(viz_state, axis)
          .map((_, index) => index)
          .sort((a, b) => (ranks[b] ?? 0) - (ranks[a] ?? 0))
          .map((index) => name_at(viz_state, axis, index)),
      ];
    })
  ),
});

/**
 * The same controls, bounded for observations: named orders only (an explicit order
 * is labeled in rows/cols.order) and crops of at most MAX_LISTED names (larger crops
 * are counted in selection.crop). Complete settings: get_clustergram_replay_state.
 */
const observed_controls = (viz_state) => ({
  view: camera_for(viz_state),
  crop: Object.fromEntries(
    AXES.flatMap((axis) => {
      const filter = crop_filter(viz_state, axis);
      if (filter && filter.length > MAX_LISTED) return [];
      return [
        [axis, filter?.map((index) => name_at(viz_state, axis, index)) ?? null],
      ];
    })
  ),
  order: Object.fromEntries(
    AXES.map((axis) => [axis, current_order(viz_state, axis)]).filter(
      ([, order]) => NAMED_ORDERS.includes(order)
    )
  ),
});

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
 * @param {string[]} [options.extra_rows] - Row names to add after the main
 *   selection (e.g. genes asked about that are not on screen).
 * @param {string[]} [options.extra_cols] - Same for columns.
 * @param {{clusters?: string[], n?: number}} [options.markers] - Also report these
 *   clusters' top-n ranked markers (rank_genes_groups), whether or not they are
 *   shown at the current marker level.
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
    extra_rows = [],
    extra_cols = [],
    include_values = true,
    markers = null,
  } = options;
  const bounds = visible_world_bounds(viz_state);
  const picks = {
    row: pick_axis(viz_state, 'row', rows, max_rows, bounds, extra_rows),
    col: pick_axis(viz_state, 'col', cols, max_cols, bounds, extra_cols),
  };

  const axis_state = (axis) => {
    const pick = picks[axis];
    return {
      selection_mode: pick.mode,
      names: pick.indices.map((index) => name_at(viz_state, axis, index)),
      // Names appended because they were asked about (not part of the selection).
      added: pick.added.map((index) => name_at(viz_state, axis, index)),
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
    ...observed_controls(viz_state),
    on_screen_known: bounds !== null,
    rows: axis_state('row'),
    cols: axis_state('col'),
    marker_level: marker_level_for(viz_state),
    // Whether per-cluster marker rankings can be requested (options.markers).
    marker_ranking: Object.keys(viz_state.rank_view?.markers || {}).length > 0,
    cluster_markers: markers ? markers_for(viz_state, markers) : null,
    display: {
      mode: viz_state.mat?.viz_mode ?? null,
      size:
        viz_state.mat?.viz_mode === 'dotplot'
          ? viz_state.mat?.dot_size_encoded === false
            ? 'unit'
            : 'prop'
          : null,
      focused_row:
        viz_state.labels?.focused_row_index != null
          ? name_at(viz_state, 'row', viz_state.labels.focused_row_index)
          : null,
    },
    selection: selection_for(viz_state),
    values: include_values
      ? values_for(viz_state, picks.row.indices, picks.col.indices)
      : null,
  };
};

/** Full replay inputs: no observation caps or displayed-row sampling. */
export const get_clustergram_replay_state = (state) => ({
  ...get_clustergram_controls(state),
  ...(marker_level_for(state)
    ? { marker_level: state.rank_view.current ?? 'all' }
    : {}),
  mode: state.mat.viz_mode,
  ...(state.mat.viz_mode === 'dotplot'
    ? { size: state.mat.dot_size_encoded === false ? 'unit' : 'prop' }
    : {}),
  focus_gene:
    state.labels?.focused_row_index != null
      ? name_at(state, 'row', state.labels.focused_row_index)
      : '',
  ...get_replay_controls(state),
});

/** Settings `apply_clustergram_state` understands (the Python apply_state keys). */
export const CLUSTERGRAM_APPLY_KEYS = [
  'marker_level',
  'mode',
  'size',
  'focus_gene',
  'categories',
  'annotations',
  'dendrogram',
  'selection',
  'view',
  'order',
  'crop',
];

const prepare_controls = (viz_state, changes) => {
  const prepared = {};
  for (const key of ['crop', 'order']) {
    if (!(key in changes)) continue;
    const value = changes[key];
    if (
      !value ||
      typeof value !== 'object' ||
      Array.isArray(value) ||
      Object.keys(value).some((axis) => !AXES.includes(axis))
    ) {
      throw new Error(`${key} must be an object with row and/or col`);
    }
    prepared[key] = {};
    for (const [axis, spec] of Object.entries(value)) {
      if (key === 'crop' && spec === null) {
        prepared[key][axis] = null;
      } else if (key === 'order' && typeof spec === 'string') {
        if (
          !NAMED_ORDERS.includes(spec) ||
          !viz_state.mat?.orders?.[axis]?.[spec]
        ) {
          throw new Error(`unavailable ${axis} order: ${spec}`);
        }
        prepared[key][axis] = spec;
      } else {
        if (
          !Array.isArray(spec) ||
          !spec.length ||
          new Set(spec.map(String)).size !== spec.length
        ) {
          throw new Error(
            `${key}.${axis} must be a nonempty list of unique names`
          );
        }
        const { indices, missing } = indices_for_names(viz_state, axis, spec);
        if (missing.length)
          throw new Error(`unknown ${axis} names: ${missing.join(', ')}`);
        if (
          key === 'order' &&
          indices.length !== nodes(viz_state, axis).length
        ) {
          throw new Error(
            `order.${axis} must contain every ${axis} name exactly once`
          );
        }
        prepared[key][axis] = indices;
      }
    }
  }
  if ('view' in changes) {
    const { view } = changes;
    if (
      !view ||
      typeof view !== 'object' ||
      Array.isArray(view) ||
      !Object.keys(view).length ||
      Object.keys(view).some((key) => !['target', 'zoom'].includes(key))
    ) {
      throw new Error('view must contain target and/or zoom');
    }
    for (const [key, values] of Object.entries(view)) {
      if (
        !Array.isArray(values) ||
        values.length !== 2 ||
        !values.every((v) => typeof v === 'number' && Number.isFinite(v)) ||
        (key === 'zoom' && values.some((v) => v < 0))
      ) {
        throw new Error(
          `view.${key} must contain two finite ${key === 'zoom' ? 'nonnegative ' : ''}numbers`
        );
      }
    }
    prepared.view = view;
  }
  if (Object.keys(prepared).length && !viz_state.state_controls) {
    throw new Error('Clustergram view controls are not ready');
  }
  return prepared;
};

/**
 * Change what a Clustergram shows, as its controls would, through the same model
 * values the controls and Python's `Clustergram.apply_state` set. Everything is
 * validated before anything changes.
 *
 * @param {object} model - The Clustergram's model (anywidget or standalone).
 * @param {object} viz_state - The Clustergram's visualization state.
 * @param {object} changes - Any of `CLUSTERGRAM_APPLY_KEYS`: `marker_level`
 *   (markers per cluster, the DIM slider, or `'all'`); `mode` (`'heatmap'` or
 *   `'dotplot'`); `size` (`'prop'` or `'unit'`); `focus_gene` (a row name to zoom to
 *   and bold; `''` clears it); `categories` (`{values, axis, attribute, colors,
 *   replace}`, see `apply_manual_categories`); `annotations` (replace each given
 *   axis's manual annotations; `null` clears it); `dendrogram` (`{row, col}` cut
 *   percentages); `selection` (`{rows, cols, genes, highlighted_genes,
 *   dendrogram}`); `order` (`{row, col}`: a named order or every name in display
 *   order); `crop` (`{row, col}`: names, or `null` to uncrop); `view` (`{target:
 *   [x, y], zoom: [x_zoom, y_zoom]}`).
 * @param {(viz_state: object) => string} [apply_categories] - Applies
 *   `categories` (the Clustergram passes its manual-category editor).
 * @returns {string[]} A short description of each change.
 */
export const apply_clustergram_state = (
  model,
  viz_state,
  changes = {},
  apply_categories = null
) => {
  if (!changes || typeof changes !== 'object' || Array.isArray(changes)) {
    throw new Error('changes must be an object');
  }
  const unknown = Object.keys(changes).filter(
    (key) => !CLUSTERGRAM_APPLY_KEYS.includes(key)
  );
  if (unknown.length) {
    throw new Error(
      `unknown Clustergram setting(s): ${unknown.join(', ')}; supported: ${CLUSTERGRAM_APPLY_KEYS.join(', ')}`
    );
  }

  validate_replay_controls(viz_state, changes);
  if ('categories' in changes && 'annotations' in changes)
    throw new Error('Use categories or annotations, not both');
  const updates = [];
  const controls = prepare_controls(viz_state, changes);
  if ('marker_level' in changes) {
    const level = changes.marker_level;
    if (level === null || String(level).toLowerCase() === 'all') {
      updates.push(['rank_dim', 0, 'DIM -> all rows']);
    } else {
      const n = Number.parseInt(level, 10);
      if (!Number.isFinite(n)) {
        throw new Error(`marker_level must be a number or 'all', not ${level}`);
      }
      if (n <= 0) throw new Error("marker_level must be positive (or 'all')");
      updates.push(['rank_dim', n, `DIM -> ${n} markers per cluster`]);
    }
  }
  if ('mode' in changes) {
    if (!['heatmap', 'dotplot'].includes(changes.mode)) {
      throw new Error("mode must be 'heatmap' or 'dotplot'");
    }
    updates.push(['viz_mode', changes.mode, `mode -> ${changes.mode}`]);
  }
  if ('size' in changes) {
    const size = String(changes.size).toLowerCase();
    if (!['prop', 'unit'].includes(size)) {
      throw new Error("size must be 'prop' or 'unit'");
    }
    updates.push([
      'dot_size_encoded',
      size === 'prop',
      `dot size -> ${size.toUpperCase()}`,
    ]);
  }
  if ('focus_gene' in changes) {
    const gene = String(changes.focus_gene ?? '');
    const rows = (viz_state.row_nodes || []).map((node) => String(node.name));
    if (gene && rows.length && !rows.includes(gene)) {
      throw new Error(`${gene} is not a row of this Clustergram`);
    }
    updates.push([
      'focused_gene',
      gene,
      gene ? `zoomed to ${gene}` : 'cleared focus',
    ]);
  }
  const { categories } = changes;
  if (categories !== undefined && categories !== null) {
    if (
      typeof categories !== 'object' ||
      typeof categories.values !== 'object'
    ) {
      throw new Error(
        "categories must be like {values: {'<name>': '<category>'}, axis: 'col'}"
      );
    }
    if (!apply_categories)
      throw new Error('this Clustergram has no categories');
  }

  // The category editor also validates its configured attribute. Let that fail
  // before changing mode, marker level or focus.
  const applied = categories ? apply_categories(categories) : null;
  if (changes.annotations) restore_annotations(viz_state, changes.annotations);
  updates.forEach(([key, value]) => {
    // Re-focusing the same gene should zoom to it again.
    if (key === 'focused_gene' && value && model.get(key) === value) {
      model.set(key, '');
    }
    model.set(key, value);
  });
  model.save_changes?.();
  const done = updates.map(([, , description]) => description);
  if (categories) {
    const axis = categories.axis === 'row' ? 'rows' : 'columns';
    done.push(`labeled ${applied} ${axis}`);
  }
  if (changes.annotations) done.push('restored annotations');
  if (changes.dendrogram) {
    viz_state.state_controls.dendrogram(changes.dendrogram);
    done.push('updated dendrogram');
  }
  // Apply selection after crop (which clears it), and camera after any focus change.
  if (changes.selection) controls.selection = changes.selection;
  for (const key of ['order', 'crop', 'selection', 'view']) {
    if (controls[key]) {
      viz_state.state_controls[key](controls[key]);
      done.push(`updated ${key}`);
    }
  }
  return done;
};
