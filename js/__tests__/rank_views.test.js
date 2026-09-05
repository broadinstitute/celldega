/* global require */

describe('rank views', () => {
  let ini_rank_views;
  let resolve_rank_view_level;
  let set_rank_view_state;
  let get_rank_view_stops;
  let has_rank_views;
  let alt_slice_linkage;
  let has_axis_filter;
  let has_axis_crop_filter;
  let get_axis_display_state;
  let get_axis_display_count;
  let filter_matrix_data;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const stripModules = (source) =>
      source
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const read = (relative) =>
      stripModules(fs.readFileSync(path.join(__dirname, relative), 'utf8'));

    const shims = `
      const get_composition_layout = () => ({});
      const rightmost_composition_col = () => 0;
    `;

    const factory = new Function(`
      ${shims}
      ${read('../matrix/crop_filter.js')}
      ${read('../matrix/dendro.js')}
      ${read('../matrix/rank_views.js')}
      return {
        ini_rank_views,
        resolve_rank_view_level,
        set_rank_view_state,
        get_rank_view_stops,
        has_rank_views,
        alt_slice_linkage,
        has_axis_filter,
        has_axis_crop_filter,
        get_axis_display_state,
        get_axis_display_count,
        filter_matrix_data,
      };
    `);

    ({
      ini_rank_views,
      resolve_rank_view_level,
      set_rank_view_state,
      get_rank_view_stops,
      has_rank_views,
      alt_slice_linkage,
      has_axis_filter,
      has_axis_crop_filter,
      get_axis_display_state,
      get_axis_display_count,
      filter_matrix_data,
    } = factory());
  });

  const NUM_ROWS = 6;
  const NUM_COLS = 3;

  // Level-3 view keeping rows 1, 3 and 5 (ascending, as the exporter emits).
  const makeView = (overrides = {}) => ({
    level: 3,
    view_type: 'rank_genes_groups',
    level_unit: 'per_cluster',
    row_indices: [1, 3, 5],
    row_clust: [0, 2, 0, 1, 0, 3],
    col_clust: [2, 1, 3],
    row_linkage: [
      [0, 1, 0.1, 2],
      [2, 3, 0.9, 3],
    ],
    col_linkage: [
      [0, 1, 0.2, 2],
      [2, 3, 0.8, 3],
    ],
    ...overrides,
  });

  const makeVizState = (views) => {
    const viz_state = {
      viz: {
        mat_width: 90,
        mat_height: 60,
        row_offset: 10,
        col_offset: 30,
        base_font_size: 50,
        font_size: { rows: 50 / NUM_ROWS, cols: 50 / NUM_COLS },
      },
      order: { current: { row: 'clust', col: 'clust' } },
      mat: {
        num_rows: NUM_ROWS,
        num_cols: NUM_COLS,
        orders: {
          row: { clust: [1, 2, 3, 4, 5, 6] },
          col: { clust: [1, 2, 3] },
        },
        mat_data: [
          { row: 0, col: 0 },
          { row: 1, col: 1 },
          { row: 3, col: 2 },
          { row: 5, col: 0 },
        ],
      },
      linkage: {
        row: [[0, 1, 0.5, 2]],
        col: [[0, 1, 0.5, 2]],
      },
      row_nodes: Array.from({ length: NUM_ROWS }, (_, index) => ({
        name: `row-${index}`,
      })),
      col_nodes: Array.from({ length: NUM_COLS }, (_, index) => ({
        name: `col-${index}`,
      })),
      crop: {},
    };

    ini_rank_views(viz_state, { views });
    return viz_state;
  };

  test('parses, sorts and exposes precomputed view levels', () => {
    const viz_state = makeVizState([
      makeView({ level: 10, row_indices: [0, 1, 2, 3, 4] }),
      makeView({ level: 3 }),
    ]);

    expect(has_rank_views(viz_state)).toBe(true);
    expect(viz_state.rank_view.views.map((view) => view.level)).toEqual([
      3, 10,
    ]);
    expect(viz_state.rank_view.view_type).toBe('rank_genes_groups');
    // Drives whether the slider reads a level as "per cluster" or "total rows".
    expect(viz_state.rank_view.level_unit).toBe('per_cluster');
    expect(viz_state.rank_view.by_level.get(3).n_rows).toBe(3);
    // "all" is always the last stop.
    expect(get_rank_view_stops(viz_state)).toEqual([3, 10, null]);
  });

  test('metric views report their level as a total row count', () => {
    const viz_state = makeVizState([
      makeView({ view_type: 'var', level_unit: 'rows' }),
    ]);

    expect(viz_state.rank_view.level_unit).toBe('rows');
    expect(viz_state.rank_view.view_type).toBe('var');
  });

  test('an unknown level unit falls back to total rows', () => {
    const viz_state = makeVizState([makeView({ level_unit: undefined })]);
    expect(viz_state.rank_view.level_unit).toBe('rows');
  });

  test('drops views whose geometry does not match the matrix', () => {
    const viz_state = makeVizState([
      makeView({ row_clust: [1, 2, 3] }), // wrong length for num_rows
      makeView({ level: 4, col_clust: [1, 2] }), // wrong length for num_cols
      makeView({ level: 5, row_linkage: [] }), // unusable dendrogram
      makeView({ level: 6, row_indices: [] }), // nothing to show
    ]);

    expect(has_rank_views(viz_state)).toBe(false);
    expect(get_rank_view_stops(viz_state)).toEqual([null]);
  });

  test('snaps a requested row count onto an available level', () => {
    const viz_state = makeVizState([
      makeView({ level: 3 }),
      makeView({ level: 10, row_indices: [0, 1, 2, 3, 4] }),
    ]);

    expect(resolve_rank_view_level(viz_state, 3)).toBe(3);
    expect(resolve_rank_view_level(viz_state, 4)).toBe(3);
    expect(resolve_rank_view_level(viz_state, 9)).toBe(10);
    // 0 means "all", as does anything past the coarsest level.
    expect(resolve_rank_view_level(viz_state, 0)).toBeNull();
    expect(resolve_rank_view_level(viz_state, 50)).toBeNull();
    expect(resolve_rank_view_level(viz_state, undefined)).toBeNull();
  });

  test('applying a view swaps filter, orders and linkage, and restores them', () => {
    const viz_state = makeVizState([makeView()]);
    const base_row_clust = viz_state.mat.orders.row.clust;
    const base_row_linkage = viz_state.linkage.row;

    expect(set_rank_view_state(viz_state, 3)).toBe(true);
    expect(viz_state.rank_view.current).toBe(3);
    expect(viz_state.rank_view.filter.row).toEqual([1, 3, 5]);
    expect(viz_state.mat.orders.row.clust).toEqual([0, 2, 0, 1, 0, 3]);
    expect(viz_state.mat.orders.col.clust).toEqual([2, 1, 3]);
    expect(viz_state.linkage.row).toEqual(makeView().row_linkage);
    // Only rows are filtered, so column leaf ids still are column indices.
    expect(viz_state.rank_view.leaf_map.col).toBeNull();

    // Re-applying the same level is a no-op.
    expect(set_rank_view_state(viz_state, 3)).toBe(false);

    expect(set_rank_view_state(viz_state, null)).toBe(true);
    expect(viz_state.rank_view.current).toBeNull();
    expect(viz_state.rank_view.filter.row).toBeNull();
    expect(viz_state.mat.orders.row.clust).toBe(base_row_clust);
    expect(viz_state.linkage.row).toBe(base_row_linkage);
  });

  test('an active view narrows the rendered rows', () => {
    const viz_state = makeVizState([makeView()]);
    set_rank_view_state(viz_state, 3);

    expect(has_axis_filter(viz_state, 'row')).toBe(true);
    // The view is not a crop, so crop-only controls stay enabled.
    expect(has_axis_crop_filter(viz_state, 'row')).toBe(false);
    expect(get_axis_display_count(viz_state, 'row')).toBe(3);
    expect(get_axis_display_count(viz_state, 'col')).toBe(NUM_COLS);
    expect(filter_matrix_data(viz_state)).toEqual([
      { row: 1, col: 1 },
      { row: 3, col: 2 },
      { row: 5, col: 0 },
    ]);
  });

  test('a crop inside a view renders the intersection of the two', () => {
    const viz_state = makeVizState([makeView()]);
    set_rank_view_state(viz_state, 3);

    viz_state.crop.filter = { row: [1, 2, 3], col: null };

    expect(has_axis_crop_filter(viz_state, 'row')).toBe(true);
    // Row 2 is outside the view and row 5 is outside the crop.
    expect(
      get_axis_display_state(viz_state, 'row').visible_indices.sort()
    ).toEqual([1, 3]);
    expect(filter_matrix_data(viz_state)).toEqual([
      { row: 1, col: 1 },
      { row: 3, col: 2 },
    ]);
  });

  test('clearing the crop leaves the view standing', () => {
    // What a level switch does: crop row indices point at unrelated rows once
    // the row set changes, so `apply_rank_view` drops the crop and the new
    // view alone decides what renders.
    const viz_state = makeVizState([makeView()]);
    set_rank_view_state(viz_state, 3);
    viz_state.crop.filter = { row: [1, 2, 3], col: null };
    expect(get_axis_display_count(viz_state, 'row')).toBe(2);

    viz_state.crop.filter = { row: null, col: null };
    viz_state._combined_filter_cache = {};
    viz_state.crop._display_cache = {};

    expect(has_axis_crop_filter(viz_state, 'row')).toBe(false);
    expect(has_axis_filter(viz_state, 'row')).toBe(true);
    // Display order, driven by this view's own row_clust ([_, 2, _, 1, _, 3]),
    // not matrix index order.
    expect(get_axis_display_state(viz_state, 'row').visible_indices).toEqual([
      5, 1, 3,
    ]);
  });

  test('the intersection keeps a stable reference so downstream caches hold', () => {
    const viz_state = makeVizState([makeView()]);
    set_rank_view_state(viz_state, 3);
    viz_state.crop.filter = { row: [1, 2, 3], col: null };

    const first = get_axis_display_state(viz_state, 'row');
    expect(get_axis_display_state(viz_state, 'row')).toBe(first);
  });

  test('a view linkage is sliced through its leaf map, not raw row indices', () => {
    const viz_state = makeVizState([makeView()]);
    set_rank_view_state(viz_state, 3);

    // Cuts below 0.9 so only the first merge (leaves 0 and 1) applies. Those
    // leaves are view positions, mapping to rows 1 and 3.
    alt_slice_linkage(viz_state, 'row', 0.5);

    const group_of = (index) => viz_state.row_nodes[index].group_links;
    expect(group_of(1)).toBe(group_of(3));
    expect(group_of(1)).not.toBe(group_of(5));
  });

  test('without a view, leaf ids are node indices as before', () => {
    const viz_state = makeVizState([]);

    alt_slice_linkage(viz_state, 'row', 0.9);

    const group_of = (index) => viz_state.row_nodes[index].group_links;
    expect(group_of(0)).toBe(group_of(1));
    expect(group_of(0)).not.toBe(group_of(2));
  });
});
