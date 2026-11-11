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

test('point clouds with integer cell names select and frame cells by position', async () => {
  const api = load_landscape_state(make_shims());
  const state = make_viz_state();
  // Integer-named point clouds skip the name map: a cell's name is its position.
  state.vector_name_integer = true;
  state.cats.cell_name_to_index_map = new Map();
  state.cats.cell_names_array = ['0', '1', '2', '3'];
  state.model = { set: jest.fn(), save_changes: jest.fn() };
  const context = { layers_obj: {}, update_view_state: jest.fn() };
  await api.apply_landscape_state(state, context, {
    selected_cells: ['2', '3'],
  });
  expect(state.obs_store.selected_cells.get()).toEqual(['2', '3']);
  await expect(
    api.apply_landscape_state(state, context, { selected_cells: ['4'] })
  ).rejects.toThrow('unknown selected cell names');
  const framed = api.view_for_cells(
    state,
    { cells: ['2', '3'] },
    { width: 400, height: 400 }
  );
  expect(framed.target).toEqual([70, 50, 0]);
});

test('an XY request superseded by a later one is rejected, not acknowledged', async () => {
  const { apply_landscape_state } = load_landscape_state(make_shims());
  const state = make_viz_state();
  state.genes.gene_names = ['ACTA2', 'ACTG2', 'AMY2A', 'GATM'];
  state.expression_scatter_enabled = true;
  const values = { xy_genes: [], xy_scale: 'log1p' };
  let finish = null;
  state.expression_ready = Promise.resolve();
  state.model = {
    get: (key) => values[key],
    set: (key, value) => {
      values[key] = value;
      if (key === 'xy_genes') {
        // Like expression_scatter: new axes supersede the request in flight.
        finish?.({ error: 'Expression request was superseded or disposed' });
        state.expression_ready = new Promise((resolve) => {
          finish = resolve;
        });
      }
    },
    save_changes() {},
  };
  const context = { layers_obj: {}, update_view_state: jest.fn() };
  const first = apply_landscape_state(state, context, {
    xy: { genes: ['ACTA2', 'ACTG2'], scale: 'log1p' },
  });
  const second = apply_landscape_state(state, context, {
    xy: { genes: ['AMY2A', 'GATM'], scale: 'log1p' },
  });
  finish({});
  await expect(second).resolves.toContain('updated XY axes');
  await expect(first).rejects.toThrow('superseded');
});

test('orbit clouds frame cells in 3D, in view at any camera rotation', () => {
  const { OrbitViewport } = require('@deck.gl/core');
  const api = load_landscape_state(make_shims());
  const state = make_viz_state();
  state.initial_view_state = {
    target: [0, 0, 0],
    zoom: 0,
    rotationX: 0,
    rotationOrbit: 0,
  };
  state.cats.cell_name_to_index_map = new Map([
    ['a', 0],
    ['b', 1],
  ]);
  state.spatial.cell_scatter_data.attributes.getPosition = {
    value: new Float32Array([5, 5, 1000, 15, 15, 2000]),
    size: 3,
  };
  const size = { width: 800, height: 600 };
  const framed = api.view_for_cells(state, { cells: ['a', 'b'] }, size);
  expect(framed.target).toEqual([10, 10, 1500]);
  // Every corner of the cells' bounding box projects inside the canvas.
  const corners = [5, 15].flatMap((x) =>
    [5, 15].flatMap((y) => [1000, 2000].map((z) => [x, y, z]))
  );
  for (const [rotationX, rotationOrbit] of [
    [0, 0],
    [45, 45],
    [90, 0],
    [-60, 200],
  ]) {
    const viewport = new OrbitViewport({
      ...size,
      ...framed,
      rotationX,
      rotationOrbit,
    });
    for (const corner of corners) {
      const [x, y] = viewport.project(corner);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(size.width);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(size.height);
    }
  }
});

test('framing follows the dataset rotation the cell layer draws with', () => {
  const api = load_landscape_state(make_shims());
  const state = make_viz_state();
  // 90 degrees about the origin (column-major): (x, y) -> (-y, x).
  state.rotation = {
    modelMatrix: [0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
  };
  const framed = api.view_for_cells(
    state,
    { cells: ['c2', 'c3'] },
    { width: 400, height: 400 }
  );
  // c2 (50, 40) and c3 (90, 60) are drawn at (-40, 50) and (-60, 90).
  expect(framed.target).toEqual([-50, 70, 0]);
});

test('a 2D view at a custom zoom round-trips without camera rotation', async () => {
  const api = load_landscape_state(make_shims());
  const state = make_viz_state();
  state.obs_store.selected_cells.set([]);
  // After a pan or zoom, deck.gl's 2D camera state reports the orbit camera's
  // zero rotations (OrthographicState extends OrbitState).
  state.current_view_state = {
    target: [120.5, 80.25, 0],
    zoom: 4.75,
    rotationOrbit: 0,
    rotationX: 0,
  };
  const saved = JSON.parse(
    JSON.stringify(api.get_landscape_replay_state(state))
  );
  expect(saved.view).toEqual({ target: [120.5, 80.25, 0], zoom: 4.75 });

  const fresh = make_viz_state();
  fresh.obs_store.selected_cells.set([]);
  const context = {
    layers_obj: {},
    update_view_state: jest.fn(async (view) => {
      fresh.current_view_state = view;
    }),
  };
  await api.apply_landscape_state(fresh, context, saved);
  expect(fresh.current_view_state).toMatchObject({
    target: [120.5, 80.25, 0],
    zoom: 4.75,
  });

  // Views saved before the fix carry the zero rotations; they still restore.
  await api.apply_landscape_state(fresh, context, {
    view: { ...saved.view, rotationOrbit: 0, rotationX: 0 },
  });
  expect(fresh.current_view_state.zoom).toBe(4.75);
  // A real rotation still needs an orbit view.
  await expect(
    api.apply_landscape_state(fresh, context, {
      view: { ...saved.view, rotationX: 30 },
    })
  ).rejects.toThrow('Camera rotation requires an orbit view');
});
