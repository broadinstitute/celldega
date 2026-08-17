/* global require */

describe('compute_crop_filter', () => {
  let compute_crop_filter;
  let crop_fade_alpha_factor;
  let crop_fade_axis_alpha_factor;
  let filter_matrix_data;
  let get_axis_center_position;
  let get_axis_display_count;
  let get_axis_label_font_size;
  let get_zoomed_axis_label_font_size;
  let get_default_pan;
  let initialize_matrix_crop;
  let normalize_crop_filter;
  let screen_to_matrix_world;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const stripModules = (source) =>
      source
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const cropFilterSource = stripModules(
      fs.readFileSync(path.join(__dirname, '../matrix/crop_filter.js'), 'utf8')
    );
    const cropSource = stripModules(
      fs.readFileSync(path.join(__dirname, '../deck-gl/matrix/crop.js'), 'utf8')
    );

    const shims = `
      const calc_dendro_polygons = () => {};
      const calc_dendro_triangles = () => {};
      const refresh_row_label_visibility = () => {};
      const refresh_matrix_cat_bars = () => {};
      const clear_dendro_focus = () => {};
      const clear_dendro_selection = () => {};
      const update_dendro_layer_data = () => {};
      const get_mat_layers_list = () => [];
      const mat_reorder_triggers = () => ({});
      const redefine_global_view_state = () => ({});
      const ini_views = () => {};
      const update_zoom_data = () => {};
    `;

    const code = `${shims}\n${cropFilterSource}\n${cropSource}\nmodule.exports = { compute_crop_filter, crop_fade_alpha_factor, crop_fade_axis_alpha_factor, filter_matrix_data, get_axis_center_position, get_axis_display_count, get_axis_label_font_size, get_zoomed_axis_label_font_size, get_default_pan, initialize_matrix_crop, normalize_crop_filter, screen_to_matrix_world };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({
      compute_crop_filter,
      crop_fade_alpha_factor,
      crop_fade_axis_alpha_factor,
      filter_matrix_data,
      get_axis_center_position,
      get_axis_display_count,
      get_axis_label_font_size,
      get_zoomed_axis_label_font_size,
      get_default_pan,
      initialize_matrix_crop,
      normalize_crop_filter,
      screen_to_matrix_world,
    } = module.exports);
  });

  const makeVizState = (filter = null) => ({
    viz: {
      mat_width: 100,
      mat_height: 80,
      row_region: 20,
      col_region: 30,
      label_buffer: 2,
      base_font_size: 50,
      font_size: {
        rows: 50 / 4,
        cols: 50 / 5,
      },
    },
    order: {
      current: { row: 'clust', col: 'clust' },
    },
    mat: {
      num_rows: 4,
      num_cols: 5,
      orders: {
        row: { clust: [1, 2, 3, 4] },
        col: { clust: [1, 2, 3, 4, 5] },
      },
      mat_data: [
        { row: 0, col: 0 },
        { row: 0, col: 1 },
        { row: 1, col: 2 },
        { row: 2, col: 3 },
        { row: 3, col: 4 },
      ],
    },
    labels: {
      row_label_data: [],
      col_label_data: [],
    },
    cats: {
      row_cat_data: [],
      col_cat_data: [],
    },
    crop: {
      filter,
    },
  });

  test('converts a brushed rectangle into visible row and column filters', () => {
    const viz_state = makeVizState();

    const filter = compute_crop_filter(viz_state, [20, 40], [70, 80]);

    expect(filter.row).toEqual([2, 1]);
    expect(filter.col).toEqual([3, 2, 1]);
  });

  test('filters matrix data and rescales display positions after crop', () => {
    const viz_state = makeVizState({ row: [1, 2], col: [1, 2, 3] });

    expect(get_axis_display_count(viz_state, 'row')).toBe(2);
    expect(get_axis_display_count(viz_state, 'col')).toBe(3);
    expect(filter_matrix_data(viz_state)).toEqual([
      { row: 1, col: 2 },
      { row: 2, col: 3 },
    ]);
    expect(get_axis_center_position(viz_state, 'row', 2)).toBeCloseTo(60);
    expect(get_axis_center_position(viz_state, 'col', 3)).toBeCloseTo(100 / 6);
    expect(get_default_pan(viz_state)).toEqual([50, 80]);
  });

  test('nested crops are computed within the current visible filter', () => {
    const viz_state = makeVizState({ row: [1, 2], col: [1, 2, 3] });

    const filter = compute_crop_filter(viz_state, [40, 40], [80, 80]);

    expect(normalize_crop_filter(viz_state, filter)).toEqual({
      row: [2],
      col: [2],
    });
  });

  test('screen crop coordinates are unprojected relative to the matrix viewport', () => {
    const viz_state = makeVizState();
    const unproject = jest.fn((point) => point);
    const deck_mat = {
      viewManager: {
        getViewports: () => [
          {
            id: 'matrix',
            x: 22,
            y: 32,
            width: 100,
            height: 80,
            unproject,
          },
        ],
      },
    };

    const coord = screen_to_matrix_world(deck_mat, viz_state, 42, 72);

    expect(unproject).toHaveBeenCalledWith([20, 40]);
    expect(coord).toEqual([20, 40]);
  });

  test('crop-aware label sizing grows filtered labels without shrinking defaults', () => {
    const unfiltered = makeVizState();
    expect(get_axis_label_font_size(unfiltered, 'row')).toBeCloseTo(12.5);

    const filtered = makeVizState({ row: [1, 2], col: [1, 2, 3] });
    expect(get_axis_label_font_size(filtered, 'row')).toBe(24);
    expect(get_axis_label_font_size(filtered, 'col')).toBeCloseTo(50 / 3);
  });

  test('zoomed label sizing is capped but still grows from the crop-aware base', () => {
    const viz_state = makeVizState({ row: [1, 2], col: [1, 2, 3] });

    expect(get_zoomed_axis_label_font_size(viz_state, 'row', 0)).toBe(24);
    expect(get_zoomed_axis_label_font_size(viz_state, 'row', 4)).toBe(28);
  });

  test('crop fade helpers hide marks outside the pending filter', () => {
    const viz_state = makeVizState();
    viz_state.crop.fade_filter = { row: [1, 2], col: [2, 3] };

    expect(crop_fade_alpha_factor(viz_state, 1, 2)).toBe(1);
    expect(crop_fade_alpha_factor(viz_state, 0, 2)).toBe(0);
    expect(crop_fade_axis_alpha_factor(viz_state, 'col', 3)).toBe(1);
    expect(crop_fade_axis_alpha_factor(viz_state, 'col', 4)).toBe(0);
  });

  test('crop mode cannot be enabled while a crop filter is active', () => {
    const viz_state = {
      ...makeVizState({ row: [1, 2], col: null }),
      root: document.createElement('div'),
      dendro: {},
      mat: {
        ...makeVizState().mat,
        comp_hover_row: null,
        comp_hover_col: null,
      },
      obs_store: {},
    };
    const controls = {
      active: null,
      cropEnabled: null,
      undoEnabled: null,
      setActive(value) {
        this.active = value;
      },
      setCropEnabled(value) {
        this.cropEnabled = value;
      },
      setUndoEnabled(value) {
        this.undoEnabled = value;
      },
    };

    initialize_matrix_crop({}, {}, viz_state);
    viz_state.crop.setControls(controls);
    viz_state.crop.toggle();

    expect(viz_state.crop.active).toBe(false);
    expect(controls.active).toBe(false);
    expect(controls.cropEnabled).toBe(false);
  });
});
