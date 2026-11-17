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
    const start = source.indexOf('async function render(');
    const end = source.indexOf('/**\n * Load and render a Clustergram', start);
    const render_source = source.slice(start, end);
    const held_source = fs
      .readFileSync(path.join(__dirname, '../utils/held_messages.js'), 'utf8')
      .replace(/^export const /gm, 'const ');

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
      'handleValidationWarning',
      'handleAsyncError',
      'show_loading',
      'LOADING_DELAY_MS',
      `${held_source}\n${render_source}; return render;`
    );
    render = factory(
      renderer,
      renderer,
      renderer,
      renderer,
      renderer,
      renderer,
      jest.fn(),
      (error) => ({ message: error.message }),
      jest.fn(() => jest.fn()),
      0
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

  test('a request sent while rendering reaches the rendered widget', async () => {
    // The renderer resolves on a later tick; Python closes the widget first.
    const pending = render({ model, el: document.createElement('div') });
    listeners.get('msg:custom')({ event: 'finalize' });
    expect(visualization_cleanup).not.toHaveBeenCalled();
    await pending;
    expect(visualization_cleanup).toHaveBeenCalledTimes(1);
  });

  test('explicit finalize and later view disposal share one cleanup', async () => {
    const dispose = await render({ model, el: document.createElement('div') });

    listeners.get('msg:custom')({ event: 'finalize' });
    dispose();

    expect(visualization_cleanup).toHaveBeenCalledTimes(1);
  });
});
