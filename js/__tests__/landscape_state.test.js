/* global require */

// Landscape getters/setters (Viz API). Loaded from source with the selection
// helpers shimmed, so the tests check which code paths each setter takes.
const load_landscape_state = (shims) => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(path.join(__dirname, '../viz/landscape_state.js'), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
  return new Function(
    'shims',
    `const { force_set_selected_cats, update_cat, select_genes,
            force_set_selected_genes, refresh_layer } = shims;
     const get_landscape_layers = () => ({});
     const validate_landscape_layers = () => {};
     const apply_landscape_layers = async () => [];
     ${source}
     return { get_landscape_state, get_landscape_replay_state, apply_landscape_state, view_for_cells };`
  )(shims);
};

const observable = (value) => ({
  value,
  get() {
    return this.value;
  },
  set(next) {
    this.value = next;
  },
});

const make_viz_state = () => ({
  cats: {
    cat: 'cluster',
    selected_cats: ['4'],
    // Cells c0..c3: clusters 4, 4, 5, 6 at x = 0, 10, 50, 90; y = 0, 20, 40, 60.
    cell_cats: ['4', '4', '5', '6'],
    cell_name_to_index_map: new Map([
      ['c0', 0],
      ['c1', 1],
      ['c2', 2],
      ['c3', 3],
    ]),
  },
  genes: { selected_genes: [] },
  spatial: {
    cell_scatter_data: {
      attributes: {
        getPosition: {
          value: new Float64Array([0, 0, 10, 20, 50, 40, 90, 60]),
          size: 2,
        },
      },
    },
  },
  obs_store: {
    landscape_view: observable('spatial'),
    selected_cells: observable(['c9']),
    deck_check: observable({ cell_layer: true }),
    new_cell_bar_data: observable([
      { name: '4', value: 1203 },
      { name: '5', value: 980.12345 },
    ]),
    new_gene_bar_data: observable([{ name: 'MUC2', value: 512 }]),
  },
  current_view_state: { target: [1, 2, 0], zoom: 3 },
  initial_view_state: { target: [45, 30, 0], zoom: -1 },
  close_up: false,
});

const make_shims = () => ({
  force_set_selected_cats: jest.fn((cats, selected) => {
    cats.selected_cats = selected;
  }),
  update_cat: jest.fn((cats, cat) => {
    cats.cat = cat;
  }),
  select_genes: jest.fn(async (viz_state, genes) => {
    viz_state.genes.selected_genes = genes;
    viz_state.cats.cat = genes.join(' + ') || 'cluster';
  }),
  force_set_selected_genes: jest.fn((genes, selected) => {
    genes.selected_genes = selected;
  }),
  refresh_layer: jest.fn(),
});

describe('landscape state', () => {
  test('camera coordinates retain the precision needed for replay', () => {
    const { get_landscape_state } = load_landscape_state(make_shims());
    const viz = make_viz_state();
    viz.current_view_state = {
      target: [123.456789, 45.678912, 3.141592],
      zoom: -2.3456789,
    };
    expect(get_landscape_state(viz).view_state).toEqual(viz.current_view_state);
    viz.viewport_gene_summary = {
      mode: 'dataset',
      scope: 'dataset',
      units: null,
    };
    expect(get_landscape_state(viz).viewport.gene_summary).toEqual(
      viz.viewport_gene_summary
    );
  });
  test('get_landscape_state reports space, camera, selection and field of view', () => {
    const { get_landscape_state } = load_landscape_state(make_shims());
    expect(get_landscape_state(make_viz_state())).toEqual({
      kind: 'landscape',
      space: 'spatial',
      view_state: { target: [1, 2, 0], zoom: 3 },
      color_by: 'cluster',
      selected_clusters: ['4'],
      selected_genes: [],
      selected_cells: 1,
      selection: { cells: ['c9'], truncated: false },
      xy: { genes: [], scale: 'log1p' },
      viewport: {
        clusters: [
          { name: '4', value: 1203 },
          { name: '5', value: 980.123 },
        ],
        genes: [{ name: 'MUC2', value: 512 }],
      },
    });
  });

  test('clusters select exactly (no toggling) and clear genes and cells', async () => {
    const shims = make_shims();
    const { apply_landscape_state } = load_landscape_state(shims);
    const viz_state = make_viz_state();
    const done = await apply_landscape_state(
      viz_state,
      { layers_obj: {}, update_view_state: jest.fn(), size: {} },
      { clusters: ['4', '5'] }
    );
    expect(done).toEqual(['highlighted clusters 4, 5']);
    expect(viz_state.cats.selected_cats).toEqual(['4', '5']);
    expect(viz_state.obs_store.selected_cells.get()).toEqual([]);
    expect(shims.force_set_selected_genes).toHaveBeenCalled();
    expect(shims.refresh_layer).toHaveBeenCalledWith(
      viz_state,
      {},
      'cell_layer'
    );
  });

  test('genes go through select_genes, like the gene search', async () => {
    const shims = make_shims();
    const { apply_landscape_state } = load_landscape_state(shims);
    const viz_state = make_viz_state();
    const done = await apply_landscape_state(
      viz_state,
      { layers_obj: {}, update_view_state: jest.fn(), size: {} },
      { genes: ['MUC2', 'TFF3'] }
    );
    expect(shims.select_genes).toHaveBeenCalledWith(viz_state, [
      'MUC2',
      'TFF3',
    ]);
    expect(done).toEqual(['colored cells by MUC2, TFF3']);
  });

  test('zoom_to frames a cluster; reset_view returns to the start', async () => {
    const { apply_landscape_state, view_for_cells } =
      load_landscape_state(make_shims());
    // Cluster 4 spans x 0..10, y 0..20: center (5, 10). 200x200 px canvas:
    // zoom = log2(min(200 / (10 * 1.15), 200 / (20 * 1.15))).
    const framed = view_for_cells(
      make_viz_state(),
      { clusters: ['4'] },
      { width: 200, height: 200 }
    );
    expect(framed.target).toEqual([5, 10, 0]);
    expect(framed.zoom).toBeCloseTo(Math.log2(200 / 23));

    const viz_state = make_viz_state();
    const update_view_state = jest.fn(async () => {});
    const context = {
      layers_obj: {},
      update_view_state,
      size: { width: 200, height: 200 },
    };
    await apply_landscape_state(viz_state, context, {
      zoom_to: { clusters: ['4'] },
    });
    expect(update_view_state.mock.calls[0][0].target).toEqual([5, 10, 0]);
    expect(viz_state.current_view_state.target).toEqual([5, 10, 0]);

    const done = await apply_landscape_state(viz_state, context, {
      reset_view: true,
    });
    expect(done).toEqual(['reset the view']);
    expect(viz_state.current_view_state).toEqual(viz_state.initial_view_state);
  });

  test('zoom_to needs the spatial view and matching cells', async () => {
    const { apply_landscape_state } = load_landscape_state(make_shims());
    const viz_state = make_viz_state();
    const context = { layers_obj: {}, update_view_state: jest.fn(), size: {} };
    await expect(
      apply_landscape_state(viz_state, context, {
        zoom_to: { clusters: ['99'] },
      })
    ).rejects.toThrow('no matching cells');
    viz_state.obs_store.landscape_view.set('umap');
    await expect(
      apply_landscape_state(viz_state, context, {
        zoom_to: { clusters: ['4'] },
      })
    ).rejects.toThrow('spatial view');
  });
});

describe('apply_landscape_state: space and unknown settings', () => {
  test('switches space through the model, like the view buttons', async () => {
    const shims = make_shims();
    const { apply_landscape_state } = load_landscape_state(shims);
    const viz_state = make_viz_state();
    // The UMAP / XY module listens to landscape_state and switches the view.
    viz_state.model = {
      set: jest.fn((key, value) => {
        if (key === 'landscape_state')
          viz_state.obs_store.landscape_view.set(value);
      }),
      save_changes: jest.fn(),
    };
    const done = await apply_landscape_state(viz_state, {}, { space: 'umap' });
    expect(done).toEqual(['switched to the umap view']);
    expect(viz_state.model.set).toHaveBeenCalledWith('landscape_state', 'umap');
    // Already there: nothing to do.
    expect(
      await apply_landscape_state(viz_state, {}, { space: 'umap' })
    ).toEqual([]);
  });

  test('a space the Landscape lacks, or an unknown setting, is an error', async () => {
    const { apply_landscape_state } = load_landscape_state(make_shims());
    const viz_state = make_viz_state();
    viz_state.model = { set: jest.fn(), save_changes: jest.fn() }; // no UMAP here
    await expect(
      apply_landscape_state(viz_state, {}, { space: 'umap' })
    ).rejects.toThrow('has no umap view');
    await expect(
      apply_landscape_state(viz_state, {}, { space: 'tsne' })
    ).rejects.toThrow("space must be 'spatial', 'umap' or 'xy'");
    await expect(
      apply_landscape_state(viz_state, {}, { clusters: ['4'], explode: true })
    ).rejects.toThrow('unknown Landscape setting(s): explode');
    expect(viz_state.cats.selected_cats).toEqual(['4']); // unchanged
  });
});

test('invalid zoom targets and genes leave the existing selection intact', async () => {
  const shims = make_shims();
  const { apply_landscape_state } = load_landscape_state(shims);
  const state = make_viz_state();
  state.genes.gene_names = ['MUC2'];
  const context = { layers_obj: {}, size: { width: 200, height: 200 } };
  for (const changes of [
    { clusters: ['5'], zoom_to: { clusters: ['missing'] } },
    { clusters: ['5'], genes: ['unmeasured'] },
    { clusters: ['5'], view: { target: [1], zoom: 2 } },
    { clusters: ['5'], view: { zoom: NaN } },
    { clusters: ['5'], reset_view: true, view: { zoom: 2 } },
  ]) {
    // eslint-disable-next-line no-await-in-loop -- each rejection must leave this same state intact
    await expect(
      apply_landscape_state(state, context, changes)
    ).rejects.toThrow();
    expect(state.cats.selected_cats).toEqual(['4']);
    expect(state.obs_store.selected_cells.get()).toEqual(['c9']);
  }
  expect(shims.refresh_layer).not.toHaveBeenCalled();
});

test('complete Landscape replay restores selection IDs, XY axes and orbit camera', async () => {
  const api = load_landscape_state(make_shims());
  const state = make_viz_state();
  const cells = Array.from({ length: 150 }, (_, i) => `c${i}`);
  state.cats.cell_name_to_index_map = new Map(
    cells.map((name, i) => [name, i])
  );
  state.genes.gene_names = ['A', 'B'];
  state.expression_scatter_enabled = true;
  const model = { xy_genes: ['A', 'B'], xy_scale: 'linear' };
  state.model = {
    get: (key) => model[key],
    set: (key, value) => {
      model[key] = value;
      if (key === 'landscape_state') state.obs_store.landscape_view.set(value);
    },
    save_changes() {},
  };
  state.obs_store.selected_cells.set(cells);
  state.initial_view_state = {
    target: [0, 0, 0],
    zoom: 0,
    rotationX: 0,
    rotationOrbit: 0,
  };
  state.current_view_state = {
    target: [10.25, 50.75, 6],
    zoom: 2.125,
    rotationX: 35,
    rotationOrbit: 120,
  };
  const context = {
    layers_obj: {},
    update_view_state: jest.fn(async (view) => {
      state.current_view_state = view;
    }),
  };
  const saved = JSON.parse(
    JSON.stringify(api.get_landscape_replay_state(state))
  );
  expect(saved.selected_cells).toHaveLength(150);
  expect(api.get_landscape_state(state).selection.cells).toHaveLength(100);
  await api.apply_landscape_state(state, context, {
    selected_cells: [],
    xy: { genes: ['B'], scale: 'log1p' },
    view: { target: [0, 0], zoom: 0, rotationX: 0, rotationOrbit: 0 },
  });
  expect(api.get_landscape_replay_state(state)).not.toEqual(saved);
  await api.apply_landscape_state(state, context, saved);
  expect(api.get_landscape_replay_state(state)).toEqual(saved);
});

test('XY loading must finish successfully before the setter acknowledges', async () => {
  const { apply_landscape_state } = load_landscape_state(make_shims());
  const state = make_viz_state();
  let finish;
  state.expression_ready = new Promise((resolve) => {
    finish = resolve;
  });
  const context = { layers_obj: {}, update_view_state: jest.fn() };
  let complete = false;
  const pending = apply_landscape_state(state, context, {
    view: { zoom: 2 },
  }).then(() => {
    complete = true;
  });
  await Promise.resolve();
  expect(complete).toBe(false);
  expect(context.update_view_state).not.toHaveBeenCalled();
  finish({ error: 'expression unavailable' });
  await expect(pending).rejects.toThrow('expression unavailable');
  expect(complete).toBe(false);
});
