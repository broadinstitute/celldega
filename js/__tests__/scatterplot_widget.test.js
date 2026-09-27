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

describe('Scatterplot widget lifecycle and interaction', () => {
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
      'COORDINATE_SYSTEM',
      'Deck',
      'OrthographicView',
      'ScatterplotLayer',
      'create_obs_store',
      'arrayBufferToArrowTable',
      'getTableColumnArray',
      'cellsInPolygon',
      'prepareScatterplot',
      `${sourceWithoutModules('../widgets/scatterplot_widget.js')}; return render_scatterplot;`
    )(
      {},
      Deck,
      Layer,
      Layer,
      create_obs_store,
      decode,
      (data, name) => data[name],
      cellsInPolygon,
      prepareScatterplot
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
});
