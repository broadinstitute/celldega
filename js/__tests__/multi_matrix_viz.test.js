/* global require */

const fs = require('fs');
const path = require('path');

const read = (name) =>
  fs.readFileSync(path.join(__dirname, '..', name), 'utf8');

const strip = (source) =>
  source
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const { make_options_model } = new Function(
  `${strip(read('utils/options_model.js'))}; return { make_options_model };`
)();

// Two matrices about the same clusters: genes x clusters, and clusters x clusters.
const EXPRESSION = {
  name: 'expr',
  row_entity: { entity: 'gene', attr: 'name' },
  col_entity: { entity: 'cell', attr: 'leiden' },
  row_nodes: [{ name: 'GENE1' }, { name: 'GENE2' }],
  col_nodes: [{ name: '0' }, { name: '1' }, { name: '2' }],
  size_mat: [[1]],
};
const ENRICHMENT = {
  name: 'nhood',
  row_entity: { entity: 'cell', attr: 'leiden' },
  col_entity: { entity: 'cell', attr: 'leiden' },
  row_nodes: [{ name: '0' }, { name: '1' }],
  col_nodes: [{ name: '0' }, { name: '1' }],
};

describe('multi_matrix_viz', () => {
  let module;
  let views;
  let view_handlers;
  let model;

  // A stand-in for matrix_viz: shows labels for its axis names (like the
  // manual-category bootstrap) and exports them back (sync_axes_to_traitlets).
  const fake_matrix_viz = jest.fn(async (view_model, el, network) => {
    const listeners = new Set();
    const names = {
      row: network.row_nodes.map((node) => node.name),
      col: network.col_nodes.map((node) => node.name),
    };
    view_model.set('row_names', names.row);
    view_model.set('col_names', names.col);
    const shown = JSON.parse(view_model.get('manual_cat') || '{}');
    const labels = {};
    ['row', 'col'].forEach((axis) => {
      labels[axis] = {};
      Object.entries(shown[axis] || {}).forEach(([attribute, spec]) => {
        labels[axis][attribute] = {
          values: Object.fromEntries(
            Object.entries(spec.values || {}).filter(([name]) =>
              names[axis].includes(name)
            )
          ),
          colors: { ...(spec.colors || {}) },
        };
      });
    });
    const export_labels = () =>
      view_model.set('manual_cat', JSON.stringify(labels));
    export_labels();
    const view = {
      network,
      model: view_model,
      messages: [],
      api: {
        get_state: () => ({ shown: network.name }),
        get_replay_state: () => ({
          view: { target: [network.name.length, 0], zoom: [1, 1] },
          annotations: { col: null },
        }),
        apply_state: jest.fn(() => [`applied to ${network.name}`]),
        restore_snapshot: jest.fn(async () => ['restored']),
        set_categories: jest.fn(({ axis, attribute, values, colors }) => {
          const spec = (labels[axis][attribute] = labels[axis][attribute] || {
            values: {},
            colors: {},
          });
          Object.entries(values).forEach(([name, value]) => {
            if (value) spec.values[name] = value;
            else delete spec.values[name];
          });
          Object.assign(spec.colors, colors || {});
          export_labels();
        }),
        finalize: jest.fn(() => {
          listeners.forEach((listener) =>
            view_model.off('msg:custom', listener)
          );
        }),
      },
      label: (axis, attribute, name, value) => {
        labels[axis][attribute] = labels[axis][attribute] || {
          values: {},
          colors: {},
        };
        labels[axis][attribute].values[name] = value;
        export_labels();
      },
    };
    const listener = (msg) => view.messages.push(msg);
    listeners.add(listener);
    view_model.on('msg:custom', listener);
    views.push(view);
    return view.api;
  });

  const entries = () => [
    {
      name: 'Gene expression',
      description: 'Mean expression per cluster.',
      viz_mode: 'dotplot',
      load: async () => EXPRESSION,
    },
    {
      name: 'Neighborhood enrichment',
      description: 'Squidpy z-scores.',
      viz_mode: 'heatmap',
      load: async () => ENRICHMENT,
    },
  ];

  const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

  beforeEach(() => {
    views = [];
    view_handlers = null;
    fake_matrix_viz.mockClear();
    const dependencies = {
      matrix_viz: fake_matrix_viz,
      consume_initial_snapshot: jest.fn(),
      identity_differences: (saved, current) =>
        Object.keys(saved).filter(
          (key) =>
            key in current &&
            JSON.stringify(saved[key]) !== JSON.stringify(current[key])
        ),
      names_signature: (names) => ({
        count: names.length,
        hash: names.join(','),
      }),
      listen_for_view_requests: (_model, restore, { apply }) => {
        view_handlers = { restore, apply };
        return jest.fn();
      },
      handleValidationWarning: jest.fn(),
    };
    module = new Function(
      ...Object.keys(dependencies),
      `${strip(read('viz/multi_matrix_viz.js'))}; return { multi_matrix_viz, axis_map_for, label_changes };`
    )(...Object.values(dependencies));

    model = make_options_model({
      active_matrix: 'Gene expression',
      viz_mode: 'dotplot',
      rank_dim: 10,
      manual_row_cat: 'info',
      manual_col_cat: 'cell_type',
      manual_cat_config: JSON.stringify({
        row: { attribute: 'info' },
        col: { attribute: 'cell_type' },
      }),
      manual_cat: JSON.stringify({
        row: { info: { values: { GENE1: 'marker' }, colors: {} } },
        col: {
          cell_type: {
            values: { 0: 'Podocyte', 1: 'Endothelial', 2: 'Tubule' },
            colors: { Podocyte: '#ff0000' },
          },
        },
      }),
    });
    model.send = jest.fn();
  });

  test('shows the active matrix with its values and a dropdown of all', async () => {
    const viz = await module.multi_matrix_viz(
      model,
      document.createElement('div'),
      entries(),
      400,
      400
    );
    expect(fake_matrix_viz).toHaveBeenCalledTimes(1);
    const options = fake_matrix_viz.mock.calls[0][8];
    expect(options.matrix_menu.names).toEqual([
      'Gene expression',
      'Neighborhood enrichment',
    ]);
    expect(options.matrix_menu.descriptions['Neighborhood enrichment']).toBe(
      'Squidpy z-scores.'
    );
    expect(options.view_requests).toBe(false);
    expect(model.get('viz_mode')).toBe('dotplot');
    expect(JSON.parse(model.get('col_entity'))).toEqual(EXPRESSION.col_entity);
    expect(views[0].model.get('active_matrix')).toBe('Gene expression');
    expect(viz.matrix_names).toHaveLength(2);
  });

  test('switches with the dropdown and remembers each matrix view', async () => {
    const el = document.createElement('div');
    const viz = await module.multi_matrix_viz(model, el, entries(), 400, 400);
    fake_matrix_viz.mock.calls[0][8].matrix_menu.on_change(
      'Neighborhood enrichment'
    );
    await viz.switch_matrix('Neighborhood enrichment');
    expect(views[0].api.finalize).toHaveBeenCalled();
    expect(views).toHaveLength(2);
    expect(model.get('active_matrix')).toBe('Neighborhood enrichment');
    expect(model.get('viz_mode')).toBe('heatmap');
    expect(JSON.parse(model.get('row_entity'))).toEqual(ENRICHMENT.row_entity);

    model.set('rank_dim', 0);
    model.set('active_matrix', 'Gene expression');
    await viz.switch_matrix('Gene expression');
    expect(views).toHaveLength(3);
    // Back to the expression matrix's own settings and view (labels excluded).
    expect(model.get('viz_mode')).toBe('dotplot');
    expect(model.get('rank_dim')).toBe(10);
    expect(views[2].api.apply_state).toHaveBeenCalledWith({
      view: { target: [4, 0], zoom: [1, 1] },
    });
  });

  test('labels follow clusters: shown on both axes, edits kept in the first matrix', async () => {
    const viz = await module.multi_matrix_viz(
      model,
      document.createElement('div'),
      entries(),
      400,
      400
    );
    await viz.switch_matrix('Neighborhood enrichment');
    const enrichment = views[1];
    // Cluster labels on both axes; no gene labels; cluster 2 isn't in this matrix.
    expect(JSON.parse(enrichment.model.get('manual_cat'))).toEqual({
      row: {
        cell_type: {
          values: { 0: 'Podocyte', 1: 'Endothelial', 2: 'Tubule' },
          colors: { Podocyte: '#ff0000' },
        },
      },
      col: {
        cell_type: {
          values: { 0: 'Podocyte', 1: 'Endothelial', 2: 'Tubule' },
          colors: { Podocyte: '#ff0000' },
        },
      },
    });
    expect(enrichment.model.get('manual_row_cat')).toBe('cell_type');
    // Exporting the filtered labels changed nothing.
    expect(JSON.parse(model.get('manual_cat')).col.cell_type.values).toEqual({
      0: 'Podocyte',
      1: 'Endothelial',
      2: 'Tubule',
    });

    // Label a row cluster here: it reaches the first matrix's columns, keeps the
    // gene labels and cluster 2, and shows on this matrix's columns too.
    enrichment.label('row', 'cell_type', '1', 'Glomerular endothelium');
    const manual = JSON.parse(model.get('manual_cat'));
    expect(manual.col.cell_type.values).toEqual({
      0: 'Podocyte',
      1: 'Glomerular endothelium',
      2: 'Tubule',
    });
    expect(manual.row.info.values).toEqual({ GENE1: 'marker' });
    expect(enrichment.api.set_categories).toHaveBeenCalledWith(
      expect.objectContaining({
        axis: 'col',
        attribute: 'cell_type',
        values: { 1: 'Glomerular endothelium' },
      })
    );
  });

  test('Python messages about another matrix switch first', async () => {
    // Capture the wrapper's own message listener on the real model.
    const listeners = [];
    const original_on = model.on;
    model.on = (event, listener) => {
      if (event === 'msg:custom') listeners.push(listener);
      original_on(event, listener);
    };
    await module.multi_matrix_viz(
      model,
      document.createElement('div'),
      entries(),
      400,
      400
    );
    const wrapper_listener = listeners[0];
    await wrapper_listener({
      event: 'apply_state',
      id: 7,
      changes: { matrix: 'Neighborhood enrichment', view: { zoom: [2, 2] } },
    });
    const enrichment = views[views.length - 1];
    expect(enrichment.network.name).toBe('nhood');
    expect(enrichment.messages).toEqual([
      { event: 'apply_state', id: 7, changes: { view: { zoom: [2, 2] } } },
    ]);

    // Python labels while another matrix is shown: replied to, then synced.
    await wrapper_listener({ event: 'set_categories', id: 8, axis: 'col' });
    expect(model.send).toHaveBeenCalledWith({
      event: 'categories_set',
      id: 8,
      applied: 0,
    });
    const manual = JSON.parse(model.get('manual_cat'));
    manual.col.cell_type.values['0'] = 'Mesangial';
    model.set('manual_cat', JSON.stringify(manual));
    expect(enrichment.api.set_categories).toHaveBeenCalledWith(
      expect.objectContaining({ axis: 'row', values: { 0: 'Mesangial' } })
    );
    expect(enrichment.api.set_categories).toHaveBeenCalledWith(
      expect.objectContaining({ axis: 'col', values: { 0: 'Mesangial' } })
    );

    // Unknown matrices are refused with an error reply.
    await wrapper_listener({
      event: 'apply_state',
      id: 9,
      changes: { matrix: 'nope' },
    });
    expect(model.send).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'apply_error', id: 9 })
    );
  });

  test('links: a matrix, a gene only another matrix has, or a saved view', async () => {
    const viz = await module.multi_matrix_viz(
      model,
      document.createElement('div'),
      entries(),
      400,
      400
    );
    await view_handlers.apply({ matrix: 'Neighborhood enrichment' });
    expect(viz.active_matrix()).toBe('Neighborhood enrichment');

    // A gene link while clusters x clusters is shown goes to the gene matrix.
    const done = await view_handlers.apply({ focus_gene: 'GENE2' });
    expect(done[0]).toBe('matrix -> Gene expression');
    expect(views[views.length - 1].api.apply_state).toHaveBeenCalledWith({
      focus_gene: 'GENE2',
    });

    // A saved view of the enrichment matrix, recognized by its names.
    await view_handlers.restore({
      identity: {
        rows: { count: 2, hash: '0,1' },
        cols: { count: 2, hash: '0,1' },
      },
    });
    expect(viz.active_matrix()).toBe('Neighborhood enrichment');
    expect(views[views.length - 1].api.restore_snapshot).toHaveBeenCalled();
    await flush();
  });

  test('maps axes by entity', () => {
    expect(
      module.axis_map_for(
        {
          row_entity: ENRICHMENT.row_entity,
          col_entity: ENRICHMENT.col_entity,
        },
        { row_entity: EXPRESSION.row_entity, col_entity: EXPRESSION.col_entity }
      )
    ).toEqual({ row: 'col', col: 'col' });
    expect(
      module.label_changes(
        { a: { values: { 1: 'x', 2: 'y' } } },
        { a: { values: { 1: 'z' } } },
        new Set(['1'])
      )
    ).toEqual([['a', '1', 'z']]);
  });
});
