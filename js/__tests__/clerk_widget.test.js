/* global require */

// The Clerk chat panel: model picker <-> `model` trait, image preview, and listener
// cleanup. Loaded from source like the other widget tests (no Babel transform).
describe('Clerk panel', () => {
  let render_clerk;

  const make_model = (initial) => {
    const state = { ...initial };
    const listeners = new Map();
    return {
      get: (key) => state[key],
      set: (key, value) => {
        state[key] = value;
        (listeners.get(`change:${key}`) || []).forEach((handler) => handler());
      },
      save_changes: jest.fn(),
      on: (event, handler) => {
        listeners.set(event, [...(listeners.get(event) || []), handler]);
      },
      off: (event, handler) => {
        listeners.set(
          event,
          (listeners.get(event) || []).filter((h) => h !== handler)
        );
      },
      listener_count: () =>
        [...listeners.values()].reduce((n, handlers) => n + handlers.length, 0),
    };
  };

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../widgets/clerk_widget.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    const factory = new Function(
      'postGeneList',
      'fetchEnrichment',
      'handleAsyncError',
      `${source}\nreturn render_clerk;`
    );
    render_clerk = factory(jest.fn(), jest.fn(), jest.fn());
  });

  const render = async (initial = {}) => {
    const model = make_model({
      width: 0,
      height: 400,
      gene_list: [],
      messages: [],
      pending: false,
      model: '',
      image_thumb_b64: '',
      has_image: false,
      ...initial,
    });
    const el = document.createElement('div');
    const view = await render_clerk({ model, el });
    return { model, el, view, select: el.querySelector('select') };
  };

  test('the model picker reflects and sets the model trait', async () => {
    const { model, select } = await render({ model: 'sonnet' });
    expect(select.value).toBe('sonnet');
    expect([...select.options].map((o) => o.value)).toEqual([
      '',
      'opus',
      'sonnet',
      'haiku',
    ]);

    select.value = 'haiku';
    select.dispatchEvent(new Event('change'));
    expect(model.get('model')).toBe('haiku');
    expect(model.save_changes).toHaveBeenCalled();

    // Changes made from Python show up in the picker.
    model.set('model', 'opus');
    expect(select.value).toBe('opus');
  });

  test('a custom model id set from Python stays selectable', async () => {
    const { select } = await render({ model: 'claude-sonnet-5-5' });
    expect(select.value).toBe('claude-sonnet-5-5');
    expect(select.options).toHaveLength(5);
  });

  test('shows the synced preview, or a note when only the full image exists', async () => {
    const withThumb = await render({
      image_thumb_b64: 'VEhN',
      has_image: true,
    });
    expect(withThumb.el.querySelector('img').src).toContain('VEhN');

    const noThumb = await render({ has_image: true });
    expect(noThumb.el.querySelector('img')).toBeNull();
    expect(noThumb.el.textContent).toContain('Image attached (no preview).');
  });

  test('finalize removes every model listener', async () => {
    const { model, view } = await render();
    expect(model.listener_count()).toBeGreaterThan(0);
    view.finalize();
    expect(model.listener_count()).toBe(0);
  });
});
