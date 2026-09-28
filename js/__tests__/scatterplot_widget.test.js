/* global require */

const fs = require('fs');
const path = require('path');

const sourceWithoutModules = (relativePath) =>
  fs
    .readFileSync(path.join(__dirname, relativePath), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export (const|function) /gm, '$1 ');

const { prepareScatterplot, cellsInPolygon } = new Function(
  `${sourceWithoutModules('../scatterplot/scatterplot_data.js')}; return {prepareScatterplot, cellsInPolygon};`
)();
const create_obs_store = new Function(
  `${sourceWithoutModules('../obs_store/obs_store.js')}; return create_obs_store;`
)();
const editorHelpers = new Function(
  `${sourceWithoutModules('../ui/editor_common.js')}; return {create_button_row, create_color_input, create_dialog_container, create_dialog_header, create_labeled_input, create_text_input, position_dialog};`
)();
const { create_scatter_category_panel } = new Function(
  `${sourceWithoutModules('../scatterplot/category_panel.js')}; return { create_scatter_category_panel };`
)();

const table = (rows) =>
  Object.fromEntries(
    ['cell_id', 'x', 'y', 'color', 'label'].map((name) => [
      name,
      rows.map((row) => row[name]),
    ])
  );
const defaultRows = [
  { cell_id: 'a', x: 0, y: 0 },
  { cell_id: 'b', x: 10, y: 10 },
  { cell_id: 'c', x: 20, y: 20 },
];
const flush = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

const makeModel = (overrides = {}) => {
  const values = {
    view: 'genes',
    x: 'G1',
    y: 'G2',
    x_scale: 'linear',
    y_scale: 'linear',
    color_by: '',
    layer: '',
    available_views: ['genes', 'umap'],
    gene_names: ['G1', 'G2'],
    obs_columns: ['cluster'],
    layers: [],
    points_parquet: new Uint8Array([1]),
    selected_cells: [],
    selected_categories: [],
    animation_duration: 0,
    plot_meta: {
      view: 'genes',
      x_label: 'G1',
      y_label: 'G2',
      x_nonnegative: true,
      y_nonnegative: true,
    },
    ...overrides,
  };
  const listeners = new Map();
  const model = {
    get: (key) => values[key],
    set: jest.fn((key, value) => {
      if (values[key] === value) return;
      values[key] = value;
      [...(listeners.get(`change:${key}`) || [])].forEach((listener) =>
        listener()
      );
    }),
    on: jest.fn((event, listener) => {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(listener);
    }),
    off: jest.fn((event, listener) => listeners.get(event).delete(listener)),
    save_changes: jest.fn(),
  };
  return { model, values, listeners };
};

describe('Scatter widget lifecycle and interaction', () => {
  let render;
  let decode;
  let decks;
  let observers;
  let cleanups;

  beforeEach(() => {
    jest.useFakeTimers();
    decks = [];
    observers = [];
    cleanups = [];
    decode = jest.fn().mockResolvedValue(table(defaultRows));
    const Deck = function (props) {
      this.props = props;
      this.setProps = jest.fn((next) => {
        this.props = { ...this.props, ...next };
      });
      this.finalize = jest.fn();
      this.redraw = jest.fn(() => this.props.onAfterRender());
      decks.push(this);
    };
    const Layer = function (props) {
      this.props = props;
    };
    global.ResizeObserver = function () {
      this.observe = jest.fn();
      this.disconnect = jest.fn();
      observers.push(this);
    };
    render = new Function(
      'DrawPolygonMode',
      'EditableGeoJsonLayer',
      'ViewMode',
      'COORDINATE_SYSTEM',
      'Deck',
      'OrthographicView',
      'ScatterplotLayer',
      'create_obs_store',
      'arrayBufferToArrowTable',
      'getTableColumnArray',
      'cellsInPolygon',
      'prepareScatterplot',
      'create_scatter_category_panel',
      ...Object.keys(editorHelpers),
      `${sourceWithoutModules('../widgets/scatterplot_widget.js')}; return render_scatter;`
    )(
      () => {},
      Layer,
      () => {},
      {},
      Deck,
      Layer,
      Layer,
      create_obs_store,
      decode,
      (data, name) => data[name],
      cellsInPolygon,
      prepareScatterplot,
      create_scatter_category_panel,
      ...Object.values(editorHelpers)
    );
  });

  afterEach(() => {
    cleanups.forEach((widget) => widget.finalize());
    document.body.replaceChildren();
    delete global.ResizeObserver;
    jest.useRealTimers();
  });

  const mount = (model) => {
    const el = document.createElement('div');
    document.body.appendChild(el);
    const widget = render({ model, el });
    cleanups.push(widget);
    return { el, widget };
  };

  test('finalize releases the instance and ignores an in-flight decode', async () => {
    let resolve;
    decode.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      })
    );
    const { model, listeners } = makeModel();
    const { el, widget } = mount(model);
    const deck = decks[0];
    widget.finalize();
    widget.finalize();
    const drawCount = deck.setProps.mock.calls.length;
    resolve(table(defaultRows));
    await flush();

    expect(deck.finalize).toHaveBeenCalledTimes(1);
    expect(deck.setProps).toHaveBeenCalledTimes(drawCount);
    expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
    expect([...listeners.values()].every((set) => set.size === 0)).toBe(true);
    expect(el.childElementCount).toBe(0);
  });

  test('newer decode wins even if an older payload finishes last', async () => {
    const resolvers = [];
    decode.mockImplementation(
      () => new Promise((resolve) => resolvers.push(resolve))
    );
    const { model } = makeModel();
    mount(model);
    model.set('points_parquet', new Uint8Array([2]));
    resolvers[1](table([{ cell_id: 'new', x: 2, y: 3 }]));
    await flush();
    resolvers[0](table([{ cell_id: 'old', x: 1, y: 1 }]));
    await flush();
    expect(
      decks[0].props.layers[0].props.data.map((point) => point.id)
    ).toEqual(['new']);
  });

  test('metadata changes update labels even with identical parquet bytes', async () => {
    const { model, values } = makeModel();
    const { el } = mount(model);
    await flush();
    model.set('plot_meta', {
      ...values.plot_meta,
      x_label: 'Identical vector gene',
      revision: 2,
      x_nonnegative: false,
    });
    await flush();
    expect(el.querySelector('svg').textContent).toContain(
      'Identical vector gene'
    );
    expect(
      el.querySelector('[aria-label="X scale"] option[value="log1p"]').disabled
    ).toBe(true);
  });

  test('only stable ordered identities animate and gating waits for the transition', async () => {
    const { model } = makeModel({ animation_duration: 450 });
    const { el } = mount(model);
    await flush();
    expect(decks[0].props.layers[0].props.transitions.getPosition).toBe(0);
    model.set('x_scale', 'log1p');
    expect(decks[0].props.layers[0].props.transitions.getPosition).toBe(450);
    expect(
      [...el.querySelectorAll('button')].find(
        (button) => button.textContent === 'GATE'
      ).disabled
    ).toBe(true);
    jest.advanceTimersByTime(480);
    expect(decks[0].props.layers[0].props.pickable).toBe(true);

    decode.mockResolvedValue(
      table([
        { cell_id: 'c', x: 20, y: 20 },
        { cell_id: 'a', x: 0, y: 0 },
      ])
    );
    model.set('points_parquet', new Uint8Array([2]));
    await flush();
    expect(decks[0].props.layers[0].props.transitions.getPosition).toBe(0);
    expect(decks[0].props.layers[0].props.pickable).toBe(true);
  });

  test('click and rectangle gates emit cell IDs, preserving other widget instances', async () => {
    const first = makeModel();
    const second = makeModel();
    const { el } = mount(first.model);
    mount(second.model);
    await flush();
    const [a, b] = decks[0].props.layers[0].props.data;
    decks[0].props.onClick({ object: a }, { srcEvent: {} });
    decks[0].props.onClick({ object: b }, { srcEvent: { shiftKey: true } });
    expect(first.values.selected_cells).toEqual(['a', 'b']);
    expect(second.values.selected_cells).toEqual([]);
    [...el.querySelectorAll('button')]
      .find((button) => button.textContent === 'GATE')
      .click();
    const overlay = el.querySelector(
      '[aria-label="Drag a rectangle to select cells"]'
    );
    overlay.dispatchEvent(
      new MouseEvent('pointerdown', { clientX: 240, clientY: 180, button: 0 })
    );
    overlay.dispatchEvent(
      new MouseEvent('pointerup', { clientX: 274, clientY: 220, button: 0 })
    );
    expect(first.values.selected_cells).toEqual(['b']);
    expect(first.values.click_info).toEqual({
      type: 'cells_selection',
      value: { cell_ids: ['b'] },
    });
  });

  test('screenshot requests capture in the render callback and stop on finalize', async () => {
    const { model, values } = makeModel();
    const { el, widget } = mount(model);
    await flush();
    const canvas = el.querySelector('canvas');
    canvas.toDataURL = jest.fn(() => 'data:image/png;base64,PNGDATA');
    model.set('raster_request', 1);
    expect(values.raster_png).toBe('PNGDATA');
    expect(values.raster_view_state.x_label).toBe('G1');
    widget.finalize();
    model.set('raster_request', 2);
    expect(canvas.toDataURL).toHaveBeenCalledTimes(1);
  });

  test('decodes only the synchronized byte view, respecting its offset', async () => {
    const buffer = new Uint8Array([9, 1, 2, 9]);
    const { model } = makeModel({
      points_parquet: new DataView(buffer.buffer, 1, 2),
    });
    mount(model);
    await flush();
    expect(Array.from(new Uint8Array(decode.mock.calls[0][0]))).toEqual([1, 2]);
  });

  test('SKTCH uses Landscape polygon mode to select cells and clears on scale changes', async () => {
    const { model, values } = makeModel();
    const { el } = mount(model);
    await flush();
    const sketchButton = [...el.querySelectorAll('button')].find(
      (button) => button.textContent === 'SKTCH'
    );
    sketchButton.click();
    const edit = decks[0].props.layers[1].props;
    expect(edit.mode.name).toBe('DrawPolygonMode');
    expect(edit.modeConfig.preventOverlappingLines).toBe(true);
    expect(decks[0].props.controller.dragPan).toBe(false);
    expect(decks[0].props.controller.doubleClickZoom).toBe(false);
    expect(decks[0].props.layers[0].props.pickable).toBe(false);
    decks[0].props.onClick(
      { object: decks[0].props.layers[0].props.data[0] },
      {}
    );
    expect(values.selected_cells).toEqual([]);
    edit.onEdit({
      editType: 'addFeature',
      updatedData: {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [-0.1, -0.1],
                  [0.1, -0.1],
                  [0.1, 0.1],
                  [-0.1, 0.1],
                  [-0.1, -0.1],
                ],
              ],
            },
          },
        ],
      },
    });
    expect(values.selected_cells).toEqual(['b']);
    expect(decks[0].props.layers[1].props.mode.name).toBe('ViewMode');
    expect(decks[0].props.controller.dragPan).toBe(true);
    model.set('x_scale', 'log1p');
    expect(decks[0].props.layers[1]).toBe(false);
    expect(values.selected_cells).toEqual(['b']);
  });

  test('LABEL submits the captured cell IDs and displays backend results', async () => {
    const { model, values } = makeModel({ selected_cells: ['a', 'b'] });
    const { el } = mount(model);
    await flush();
    [...el.querySelectorAll('button')]
      .find((button) => button.textContent === 'LABEL')
      .click();
    const dialog = el.querySelector('[role="dialog"]');
    const value = dialog.querySelector('[aria-label="Annotation value"]');
    value.value = 'My gate';
    value.dispatchEvent(new Event('input'));
    model.set('selected_cells', ['c']);
    [...dialog.querySelectorAll('button')]
      .find((button) => button.textContent === 'Apply')
      .click();
    const request = values.annotation_request;
    expect(request).toMatchObject({
      column: 'manual_gate',
      value: 'My gate',
      color: '#3b82f6',
      cell_ids: ['a', 'b'],
    });
    expect(request.request_id).toEqual(expect.any(String));
    expect(values.selected_cells).toEqual(['c']);
    expect(el.querySelector('[role="status"]').textContent).toContain(
      'Saving labels'
    );
    model.set('annotation_result', {
      request_id: 'obsolete',
      ok: true,
      count: 99,
    });
    expect(el.querySelector('[role="status"]').textContent).toContain(
      'Saving labels'
    );
    model.set('annotation_result', {
      request_id: request.request_id,
      ok: true,
      count: 2,
      column: 'manual_gate',
      value: 'My gate',
    });
    expect(el.querySelector('[role="status"]').textContent).toContain(
      'Labeled 2 cells: manual_gate = My gate'
    );
  });

  test('canceling a label or sketch has no annotation side effects, and disposal removes their listeners', async () => {
    const { model, values } = makeModel({ selected_cells: ['a'] });
    const { el, widget } = mount(model);
    await flush();
    const buttons = [...el.querySelectorAll('button')];
    buttons.find((button) => button.textContent === 'LABEL').click();
    buttons.find((button) => button.textContent === 'Cancel').click();
    expect(values.annotation_request).toBeUndefined();
    buttons.find((button) => button.textContent === 'SKTCH').click();
    const edit = decks[0].props.layers[1].props;
    el.firstElementChild.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })
    );
    expect(decks[0].props.layers[1]).toBe(false);
    expect(values.selected_cells).toEqual(['a']);
    buttons.find((button) => button.textContent === 'LABEL').click();
    widget.finalize();
    buttons.find((button) => button.textContent === 'Apply').click();
    edit.onEdit({ editType: 'addFeature', updatedData: { features: [] } });
    expect(values.annotation_request).toBeUndefined();
    expect(el.childElementCount).toBe(0);
  });

  test('annotation errors remain visible and allow a subsequent label attempt', async () => {
    const { model, values } = makeModel({ selected_cells: ['a'] });
    const { el } = mount(model);
    await flush();
    const labelButton = [...el.querySelectorAll('button')].find(
      (button) => button.textContent === 'LABEL'
    );
    labelButton.click();
    const value = el.querySelector('[aria-label="Annotation value"]');
    value.value = 'Bad column';
    value.dispatchEvent(new Event('input'));
    [...el.querySelectorAll('button')]
      .find((button) => button.textContent === 'Apply')
      .click();
    model.set('annotation_result', {
      request_id: values.annotation_request.request_id,
      ok: false,
      error: 'Column is read-only',
    });
    expect(el.querySelector('[role="status"]').textContent).toContain(
      'Unable to label cells: Column is read-only'
    );
    expect(labelButton.disabled).toBe(false);
  });

  test('raster capture waits for coordinates and their scale transition to settle', async () => {
    let resolve;
    decode.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      })
    );
    const { model, values } = makeModel({ animation_duration: 450 });
    const { el } = mount(model);
    const capture = jest.fn(() => 'data:image/png;base64,PNG');
    el.querySelector('canvas').toDataURL = capture;
    model.set('raster_request', 1);
    expect(capture).not.toHaveBeenCalled();
    resolve(table(defaultRows));
    await flush();
    model.set('x_scale', 'log1p');
    decks[0].props.onAfterRender();
    expect(capture).not.toHaveBeenCalled();
    jest.advanceTimersByTime(480);
    decks[0].props.onAfterRender();
    expect(capture).toHaveBeenCalledTimes(1);
    expect(values.raster_view_state.raster_request).toBe(1);
    expect(values.raster_view_state.x_scale).toBe('log1p');
  });

  test('category bars count the viewport and Shift-click selects global category cells', async () => {
    decode.mockResolvedValue(
      table(
        defaultRows.map((row, index) => ({
          ...row,
          label: index === 1 ? 'B cells' : 'T cells',
          color: '#3b82f6',
        }))
      )
    );
    const { model, values } = makeModel({
      color_by: 'cluster',
      plot_meta: {
        view: 'genes',
        x_label: 'G1',
        y_label: 'G2',
        color_by: 'cluster',
        color_type: 'categorical',
        color_categories: [
          { name: 'T cells', color: '#3b82f6' },
          { name: 'B cells', color: '#ff5555' },
        ],
      },
    });
    const { el } = mount(model);
    await flush();
    const category = (name) =>
      [...el.querySelectorAll('button[data-category]')].find(
        (button) => button.dataset.category === name
      );
    expect(category('T cells').textContent).toBe('T cells2');
    expect(category('B cells').textContent).toBe('B cells1');
    decks[0].props.onViewStateChange({
      viewState: { target: [0, 0, 0], zoom: 10 },
    });
    expect(category('T cells').textContent).toBe('T cells0');
    expect(category('B cells').textContent).toBe('B cells1');
    category('T cells').click();
    expect(values.selected_cells).toEqual(['a', 'c']);
    expect(values.selected_categories).toEqual(['T cells']);
    category('B cells').dispatchEvent(
      new MouseEvent('click', { bubbles: true, shiftKey: true })
    );
    expect(values.selected_cells).toEqual(['a', 'b', 'c']);
    expect(values.selected_categories).toEqual(['T cells', 'B cells']);
    category('T cells').dispatchEvent(
      new MouseEvent('click', { bubbles: true, shiftKey: true })
    );
    expect(values.selected_cells).toEqual(['b']);
    expect(values.selected_categories).toEqual(['B cells']);
    category('T cells').dispatchEvent(
      new MouseEvent('click', { bubbles: true, shiftKey: true })
    );
    [...el.querySelectorAll('button')]
      .find((button) => button.textContent === 'GATE')
      .click();
    const overlay = el.querySelector(
      '[aria-label="Drag a rectangle to select cells"]'
    );
    overlay.dispatchEvent(
      new MouseEvent('pointerdown', { clientX: 240, clientY: 180, button: 0 })
    );
    overlay.dispatchEvent(
      new MouseEvent('pointerup', { clientX: 274, clientY: 220, button: 0 })
    );
    expect(values.selected_cells).toEqual(['b']);
    expect(values.selected_categories).toEqual([]);
    expect(
      [...el.querySelectorAll('button[data-category]')].every(
        (button) => button.getAttribute('aria-pressed') === 'false'
      )
    ).toBe(true);
    category('T cells').click();
    model.set('color_by', '');
    expect(values.selected_categories).toEqual([]);
  });

  test('numeric color displays a continuous range instead of category buttons', async () => {
    const { model } = makeModel({
      color_by: 'counts',
      plot_meta: {
        view: 'genes',
        x_label: 'G1',
        y_label: 'G2',
        color_type: 'numeric',
        color_by: 'counts',
        color_min: 0,
        color_max: 125.5,
        color_scale: ['#440154', '#21918c', '#fde725'],
      },
    });
    const { el } = mount(model);
    await flush();
    expect(el.querySelectorAll('button[data-category]')).toHaveLength(0);
    expect(el.textContent).toContain('125.5');
    expect(el.textContent).toContain('3 cells in view');
  });
});
