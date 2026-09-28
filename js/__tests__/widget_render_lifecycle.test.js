/* global require */

describe('anywidget render lifecycle', () => {
  let render;
  let visualization_cleanup;
  let listeners;
  let model;

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs.readFileSync(
      path.join(__dirname, '../celldega.js'),
      'utf8'
    );
    const start = source.indexOf('async function render({ model, el })');
    const end = source.indexOf('/**\n * Load and render a Clustergram', start);
    const render_source = source.slice(start, end);

    visualization_cleanup = jest.fn();
    const visualization = { finalize: visualization_cleanup };
    const renderer = jest.fn(async () => visualization);
    const factory = new Function(
      'render_landscape',
      'render_landscape_ist',
      'render_yearbook',
      'render_matrix_new',
      'render_enrich',
      'render_landmark',
      'render_scatter',
      'handleValidationWarning',
      'handleAsyncError',
      `${render_source}; return render;`
    );
    render = factory(
      renderer,
      renderer,
      renderer,
      renderer,
      renderer,
      renderer,
      renderer,
      jest.fn(),
      (error) => ({ message: error.message })
    );

    listeners = new Map();
    model = {
      id: 'model-1',
      get: jest.fn((name) => (name === 'component' ? 'Matrix' : null)),
      on: jest.fn((event, listener) => listeners.set(event, listener)),
      off: jest.fn((event, listener) => {
        if (listeners.get(event) === listener) listeners.delete(event);
      }),
    };
  });

  test('returns an anywidget disposer that finalizes exactly once', async () => {
    const dispose = await render({ model, el: document.createElement('div') });

    expect(typeof dispose).toBe('function');
    dispose();
    dispose();

    expect(visualization_cleanup).toHaveBeenCalledTimes(1);
    expect(model.off).toHaveBeenCalledTimes(1);
    expect(listeners.has('msg:custom')).toBe(false);
  });

  test('explicit finalize and later view disposal share one cleanup', async () => {
    const dispose = await render({ model, el: document.createElement('div') });

    listeners.get('msg:custom')({ event: 'finalize' });
    dispose();

    expect(visualization_cleanup).toHaveBeenCalledTimes(1);
  });

  test('Scatter is dispatched through the shared lifecycle', async () => {
    model.get.mockImplementation((name) =>
      name === 'component' ? 'Scatter' : null
    );
    const dispose = await render({ model, el: document.createElement('div') });
    expect(typeof dispose).toBe('function');
    listeners.get('msg:custom')({ event: 'finalize' });
    dispose();
    expect(visualization_cleanup).toHaveBeenCalledTimes(1);
  });
});
