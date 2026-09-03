/* global require */

describe('compute_crop_filter', () => {
  let compute_crop_filter;
  let crop_filter_signature;
  let crop_fade_alpha_factor;
  let crop_fade_axis_alpha_factor;
  let filter_cat_data;
  let filter_label_data;
  let filter_matrix_data;
  let get_axis_center_position;
  let get_axis_display_count;
  let get_axis_label_font_size;
  let get_zoomed_axis_label_font_size;
  let get_default_pan;
  let initialize_matrix_crop;
  let normalize_crop_filter;
  let screen_to_matrix_world;
  let sync_gene_row_crop_selection;
  let crop_gene_sync_calls;

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
      const toggle_dendro_layer_visibility = () => {};
      const set_dendro_layer_onclick = () => {};
      const set_dendro_layer_onhover = () => {};
      const SNAP_ANNOTATION_LAYER_IDS = new Set([
        'row-layer',
        'col-layer',
        'row-label-layer',
        'col-label-layer',
        'row-attr-label-layer',
        'col-attr-label-layer',
      ]);
      const get_mat_layers_list = (layers_mat, options = {}) => {
        const layers = [
          layers_mat.mat_layer,
          layers_mat.row_cat_layer,
          layers_mat.col_cat_layer,
          layers_mat.row_label_layer,
          layers_mat.col_label_layer,
          layers_mat.row_dendro_layer,
          layers_mat.col_dendro_layer,
          layers_mat.col_attr_label_layer,
          layers_mat.row_attr_label_layer,
        ].filter(Boolean);

        return options.snap_annotations
          ? layers.map((layer) =>
              SNAP_ANNOTATION_LAYER_IDS.has(layer.id)
                ? layer.clone({ transitions: false })
                : layer
            )
          : layers;
      };
      const mat_reorder_triggers = () => ({});
      const redefine_global_view_state = () => ({});
      const ini_views = () => {};
      const update_zoom_data = () => {};
      const apply_mat_encoding = () => {};
      const make_layer = (id) => ({
        id,
        props: {
          transitions: {
            getPosition: { duration: 250 },
          },
        },
        clone(props = {}) {
          return {
            ...this,
            props: {
              ...this.props,
              ...props,
            },
            clone: this.clone,
          };
        },
      });
      const ini_mat_layer = () => make_layer('mat-layer');
      const ini_composition_layer = () => make_layer('composition-layer');
      const ini_row_label_layer = () => make_layer('row-label-layer');
      const refresh_row_label_focus_layer = (layers_mat) => {
        layers_mat.row_label_focus_layer = make_layer('row-label-layer-focus');
      };
      const ini_col_label_layer = () => make_layer('col-label-layer');
      const ini_row_cat_layer = () => make_layer('row-layer');
      const ini_col_cat_layer = () => make_layer('col-layer');
      const set_mat_layer_onclick = () => {};
      const set_mat_layer_onhover = () => {};
      const set_composition_layer_onhover = () => {};
      const set_row_label_layer_onclick = () => {};
      const set_col_label_layer_onclick = () => {};
      const set_row_label_layer_onhover = () => {};
      const set_col_label_layer_onhover = () => {};
      const set_cat_layer_handlers = () => {};
      const set_composition_colors = () => {};
      const crop_gene_sync_calls = [];
      const sync_selected_genes = (_viz_state, genes) => {
        crop_gene_sync_calls.push(genes);
      };
    `;

    const code = `${shims}\n${cropFilterSource}\n${cropSource}\nmodule.exports = { compute_crop_filter, crop_filter_signature, crop_fade_alpha_factor, crop_fade_axis_alpha_factor, filter_cat_data, filter_label_data, filter_matrix_data, get_axis_center_position, get_axis_display_count, get_axis_label_font_size, get_zoomed_axis_label_font_size, get_default_pan, initialize_matrix_crop, normalize_crop_filter, screen_to_matrix_world, sync_gene_row_crop_selection, crop_gene_sync_calls };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({
      compute_crop_filter,
      crop_filter_signature,
      crop_fade_alpha_factor,
      crop_fade_axis_alpha_factor,
      filter_cat_data,
      filter_label_data,
      filter_matrix_data,
      get_axis_center_position,
      get_axis_display_count,
      get_axis_label_font_size,
      get_zoomed_axis_label_font_size,
      get_default_pan,
      initialize_matrix_crop,
      normalize_crop_filter,
      screen_to_matrix_world,
      sync_gene_row_crop_selection,
      crop_gene_sync_calls,
    } = module.exports);
  });

  const makeVizState = (filter = null) => ({
    viz: {
      mat_width: 100,
      mat_height: 80,
      row_offset: 20,
      col_offset: 20,
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
      row_label_data: Array.from({ length: 4 }, (_, index) => ({
        index,
        name: `row-${index}`,
      })),
      col_label_data: Array.from({ length: 5 }, (_, index) => ({
        index,
        name: `col-${index}`,
      })),
    },
    cats: {
      row_cat_data: Array.from({ length: 4 }, (_, original_index) => ({
        original_index,
      })),
      col_cat_data: Array.from({ length: 5 }, (_, original_index) => ({
        original_index,
      })),
    },
    crop: {
      filter,
    },
  });

  const make_test_layer = (id) => ({
    id,
    props: {
      transitions: {
        getPosition: { duration: 250 },
      },
    },
    clone(props = {}) {
      return {
        ...this,
        props: {
          ...this.props,
          ...props,
        },
        clone: this.clone,
      };
    },
  });

  test('converts a brushed rectangle into visible row and column filters', () => {
    const viz_state = makeVizState();

    const filter = compute_crop_filter(viz_state, [20, 40], [70, 80]);

    expect(filter.row).toEqual([2, 1]);
    expect(filter.col).toEqual([3, 2, 1]);
  });

  test('forwards only gene-row crop selections to the shared gene state', () => {
    crop_gene_sync_calls.length = 0;
    const viz_state = makeVizState({ row: [2, 1], col: [1, 2] });
    viz_state.row_entity = { entity: 'gene', attr: 'symbol' };
    viz_state.row_nodes = Array.from({ length: 4 }, (_, index) => ({
      name: `gene-${index}`,
    }));
    viz_state.model = { set: jest.fn(), save_changes: jest.fn() };

    expect(sync_gene_row_crop_selection(viz_state)).toEqual([
      'gene-2',
      'gene-1',
    ]);
    expect(crop_gene_sync_calls).toEqual([['gene-2', 'gene-1']]);
    expect(viz_state.click.type).toBe('row_crop');
    expect(viz_state.click.value.selected_names).toEqual(['gene-2', 'gene-1']);

    viz_state.row_entity = { entity: 'cell', attr: 'leiden' };
    expect(sync_gene_row_crop_selection(viz_state)).toEqual([]);
    expect(crop_gene_sync_calls).toEqual([['gene-2', 'gene-1']]);
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

  test('leaves uncropped data arrays and position lookup on the fast path', () => {
    const viz_state = makeVizState();

    expect(filter_matrix_data(viz_state)).toBe(viz_state.mat.mat_data);
    expect(filter_label_data(viz_state, 'row')).toBe(
      viz_state.labels.row_label_data
    );
    expect(filter_cat_data(viz_state, 'col')).toBe(viz_state.cats.col_cat_data);
    expect(get_axis_center_position(viz_state, 'row', 0)).toBeCloseTo(90);
    expect(viz_state.crop._display_cache).toBeUndefined();
  });

  test('crop signatures are cached and refresh when an order or filter changes', () => {
    const viz_state = makeVizState();

    const initial = crop_filter_signature(viz_state);
    expect(viz_state.crop._crop_signature_cache.signature).toBe(initial);
    expect(crop_filter_signature(viz_state)).toBe(initial);

    viz_state.order.current.row = 'rank';
    viz_state.mat.orders.row.rank = [4, 3, 2, 1];
    const reordered = crop_filter_signature(viz_state);
    expect(reordered).not.toBe(initial);

    viz_state.crop.filter = { row: [1, 2], col: null };
    expect(crop_filter_signature(viz_state)).not.toBe(reordered);
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

  test('zoomed label sizing caps at a readable density', () => {
    const viz_state = makeVizState({ row: [1, 2], col: [1, 2, 3] });

    expect(get_zoomed_axis_label_font_size(viz_state, 'row', 0)).toBe(24);
    // A crop's base size can already exceed the normal zoom cap.
    expect(get_zoomed_axis_label_font_size(viz_state, 'row', 4)).toBe(24);

    const dense_gene_matrix = makeVizState();
    dense_gene_matrix.mat.num_rows = 100;
    dense_gene_matrix.viz.row_offset = 0.8;
    dense_gene_matrix.viz.font_size.rows = 0.5;
    expect(get_zoomed_axis_label_font_size(dense_gene_matrix, 'row', 6)).toBe(
      10
    );

    dense_gene_matrix.viz.label_scale = { rows: 1, cols: 0.8 };
    dense_gene_matrix.viz.font_size.cols = 0.5;
    expect(get_zoomed_axis_label_font_size(dense_gene_matrix, 'col', 6)).toBe(
      8
    );
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
      crop_enabled: null,
      undo_enabled: null,
      set_active(value) {
        this.active = value;
      },
      set_crop_enabled(value) {
        this.crop_enabled = value;
      },
      set_undo_enabled(value) {
        this.undo_enabled = value;
      },
    };

    initialize_matrix_crop({}, {}, viz_state);
    viz_state.crop.set_controls(controls);
    viz_state.crop.toggle();

    expect(viz_state.crop.active).toBe(false);
    expect(controls.active).toBe(false);
    expect(controls.crop_enabled).toBe(false);
  });

  test('axis crop composes filters while only displayed crop annotations snap', () => {
    const base_mat = makeVizState().mat;
    const viz_state = {
      ...makeVizState({ row: [1, 2], col: null }),
      root: document.createElement('div'),
      dendro: {},
      mat: {
        ...base_mat,
        viz_mode: 'heatmap',
        comp_hover_row: null,
        comp_hover_col: null,
      },
      obs_store: {},
      zoom: {
        ini_zoom_x: 0,
        ini_zoom_y: 0,
        zoom_data: {
          total_zoom: {},
        },
      },
      views: {
        views_list: [],
      },
      animate: {
        duration: 250,
      },
    };
    viz_state.dendro.sliders = {
      row: document.createElement('input'),
      col: document.createElement('input'),
    };
    const deck_mat = {
      setProps: jest.fn(),
    };
    const layers_mat = {};
    layers_mat.row_attr_label_layer = make_test_layer('row-attr-label-layer');
    layers_mat.col_attr_label_layer = make_test_layer('col-attr-label-layer');
    const controls = {
      set_active: jest.fn(),
      set_crop_enabled: jest.fn(),
      set_undo_enabled: jest.fn(),
    };

    initialize_matrix_crop(deck_mat, layers_mat, viz_state);
    viz_state.crop.set_controls(controls);

    expect(viz_state.dendro.sliders.row.disabled).toBe(true);
    expect(viz_state.dendro.sliders.col.disabled).toBe(false);

    expect(
      viz_state.crop.apply_axis_crop('col', [1, 2], {
        source: { name: 'cluster-c', indices: [1, 2] },
      })
    ).toBe(true);

    expect(viz_state.crop.filter).toEqual({ row: [2, 1], col: [2, 1] });
    expect(viz_state.crop.dendro_axes).toEqual({
      row: null,
      col: { name: 'cluster-c', indices: [1, 2] },
    });
    expect(viz_state.crop.history).toEqual([
      {
        filter: { row: [2, 1], col: null },
        dendro_axes: { row: null, col: null },
      },
    ]);
    expect(layers_mat.mat_layer.props.transitions).not.toBe(false);
    expect(layers_mat.row_label_layer.props.transitions).not.toBe(false);
    expect(layers_mat.col_label_layer.props.transitions).not.toBe(false);
    expect(layers_mat.row_cat_layer.props.transitions).not.toBe(false);
    expect(layers_mat.col_cat_layer.props.transitions).not.toBe(false);
    expect(layers_mat.row_attr_label_layer.props.transitions).not.toBe(false);
    expect(layers_mat.col_attr_label_layer.props.transitions).not.toBe(false);
    expect(viz_state.dendro.sliders.row.disabled).toBe(true);
    expect(viz_state.dendro.sliders.col.disabled).toBe(true);

    const displayed_layers =
      deck_mat.setProps.mock.calls[deck_mat.setProps.mock.calls.length - 1][0]
        .layers;
    const displayed_by_id = new Map(
      displayed_layers.map((layer) => [layer.id, layer])
    );
    expect(displayed_by_id.get('mat-layer').props.transitions).not.toBe(false);
    expect(displayed_by_id.get('row-label-layer').props.transitions).toBe(
      false
    );
    expect(displayed_by_id.get('col-label-layer').props.transitions).toBe(
      false
    );
    expect(displayed_by_id.get('row-layer').props.transitions).toBe(false);
    expect(displayed_by_id.get('col-layer').props.transitions).toBe(false);
    expect(displayed_by_id.get('row-attr-label-layer').props.transitions).toBe(
      false
    );
    expect(displayed_by_id.get('col-attr-label-layer').props.transitions).toBe(
      false
    );
    expect(controls.set_undo_enabled).toHaveBeenLastCalledWith(true);
  });

  test('undo clears composed crops back to the uncropped state', () => {
    const base_mat = makeVizState().mat;
    const viz_state = {
      ...makeVizState(),
      root: document.createElement('div'),
      dendro: {},
      mat: {
        ...base_mat,
        viz_mode: 'heatmap',
        comp_hover_row: null,
        comp_hover_col: null,
      },
      obs_store: {},
      zoom: {
        ini_zoom_x: 0,
        ini_zoom_y: 0,
        zoom_data: {
          total_zoom: {},
        },
      },
      views: {
        views_list: [],
      },
      animate: {
        duration: 250,
      },
    };

    initialize_matrix_crop({ setProps: jest.fn() }, {}, viz_state);

    expect(
      viz_state.crop.apply_axis_crop('row', [1, 2], {
        source: { name: 'cluster-r', indices: [1, 2] },
      })
    ).toBe(true);
    expect(viz_state.crop.filter.row).toEqual([2, 1]);
    expect(viz_state.crop.dendro_axes.row).toEqual({
      name: 'cluster-r',
      indices: [1, 2],
    });

    expect(
      viz_state.crop.apply_axis_crop('col', [1, 2], {
        source: { name: 'cluster-c', indices: [1, 2] },
      })
    ).toBe(true);
    expect(viz_state.crop.filter).toEqual({ row: [2, 1], col: [2, 1] });

    viz_state.crop.undo();

    expect(viz_state.crop.filter).toEqual({ row: null, col: null });
    expect(viz_state.crop.dendro_axes).toEqual({ row: null, col: null });
    expect(viz_state.crop.history).toEqual([]);
  });

  test('double clicking an already cropped dendrogram axis clears all crops', () => {
    const base_mat = makeVizState().mat;
    const viz_state = {
      ...makeVizState(),
      root: document.createElement('div'),
      dendro: {},
      mat: {
        ...base_mat,
        viz_mode: 'heatmap',
        comp_hover_row: null,
        comp_hover_col: null,
      },
      obs_store: {},
      zoom: {
        ini_zoom_x: 0,
        ini_zoom_y: 0,
        zoom_data: {
          total_zoom: {},
        },
      },
      views: {
        views_list: [],
      },
      animate: {
        duration: 250,
      },
    };

    initialize_matrix_crop({ setProps: jest.fn() }, {}, viz_state);

    expect(
      viz_state.crop.apply_axis_crop('row', [1, 2], {
        source: { name: 'cluster-r', indices: [1, 2] },
      })
    ).toBe(true);
    expect(
      viz_state.crop.apply_axis_crop('col', [1, 2], {
        source: { name: 'cluster-c', indices: [1, 2] },
      })
    ).toBe(true);

    expect(viz_state.crop.apply_axis_crop('row', [1, 2])).toBe(true);
    expect(viz_state.crop.filter).toEqual({ row: null, col: null });
    expect(viz_state.crop.dendro_axes).toEqual({ row: null, col: null });
  });
});
