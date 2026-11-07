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
    // The real Markdown renderer, loaded the same way.
    const markdown_source = fs
      .readFileSync(path.join(__dirname, '../ui/markdown.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    const render_markdown = new Function(
      `${markdown_source}\nreturn render_markdown;`
    )();
    const factory = new Function(
      'postGeneList',
      'fetchEnrichment',
      'handleAsyncError',
      'render_markdown',
      `${source}\nreturn render_clerk;`
    );
    render_clerk = factory(jest.fn(), jest.fn(), jest.fn(), render_markdown);
  });

  const render = async (initial = {}) => {
    const model = make_model({
      width: 0,
      height: 400,
      gene_list: [],
      messages: [],
      pending: false,
      model: '',
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

  test('answers render as Markdown; questions and errors stay plain text', async () => {
    const { el } = await render({
      messages: [
        { role: 'user', content: '**not bold** <b>raw</b>' },
        { role: 'assistant', content: '## Findings\n- **MUC2** high' },
        { role: 'error', content: '<i>oops</i>' },
      ],
    });
    const answer = el.querySelector('.clerk-md');
    expect(answer.querySelector('h2').textContent).toBe('Findings');
    expect(answer.querySelector('li strong').textContent).toBe('MUC2');
    // User text and errors are shown literally, never as HTML.
    expect(el.querySelector('b')).toBeNull();
    expect(el.querySelector('i')).toBeNull();
    expect(el.textContent).toContain('**not bold** <b>raw</b>');
  });

  test('a question shows the screenshot and evidence it was sent with', async () => {
    const { el } = await render({
      messages: [
        {
          role: 'user',
          content: "What's in view?",
          image: 'VEhN',
          evidence: ['Landscape view', 'Clustergram: 25 rows x 15 columns'],
        },
        { role: 'assistant', content: 'Goblet cells.' },
      ],
    });
    const img = el.querySelector('img');
    expect(img.src).toContain('VEhN');
    expect(el.textContent).toContain(
      'Sent with: Landscape view · Clustergram: 25 rows x 15 columns'
    );
    // Only the one screenshot; the evidence strip has none.
    expect(el.querySelectorAll('img')).toHaveLength(1);
  });

  test('a full-width panel is capped for readability', async () => {
    const { el } = await render({ width: 0 });
    expect(el.firstChild.style.maxWidth).toBe('900px');
    const fixed = await render({ width: 600 });
    expect(fixed.el.firstChild.style.maxWidth).toBe('');
  });

  test('finalize removes every model listener', async () => {
    const { model, view } = await render();
    expect(model.listener_count()).toBeGreaterThan(0);
    view.finalize();
    expect(model.listener_count()).toBe(0);
  });
});
