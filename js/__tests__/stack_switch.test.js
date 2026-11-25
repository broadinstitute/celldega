/* global require */

const fs = require('fs');
const path = require('path');

const strip = (source) =>
  source
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

const { make_options_model } = new Function(
  `${strip(fs.readFileSync(path.join(__dirname, '../utils/options_model.js'), 'utf8'))}; return { make_options_model };`
)();
const { render_stack_switch, stack } = new Function(
  'CONTROL_FONT_SIZE',
  `${strip(fs.readFileSync(path.join(__dirname, '../widgets/stack_switch.js'), 'utf8'))}; return { render_stack_switch, stack };`
)('9px');

describe('stack switch', () => {
  test('buttons switch the shown widget; newer view requests bring one forward', () => {
    const model = make_options_model({
      labels: ['Tissue', 'Cells'],
      selected: 0,
      display_0: '',
      display_1: 'none',
      // A request saved before the page loaded is old news.
      request_1: { id: 'old', at: Date.now() - 60_000 },
    });
    const el = document.createElement('div');
    const cleanup = render_stack_switch({ model, el });
    const buttons = el.querySelectorAll('button');
    expect([...buttons].map((b) => b.textContent)).toEqual(['TISSUE', 'CELLS']);

    buttons[1].click();
    expect(model.get('selected')).toBe(1);
    expect([model.get('display_0'), model.get('display_1')]).toEqual([
      'none',
      '',
    ]);

    // A Clerk link or pin opens a view in the Landscape: it comes forward.
    model.set('request_0', { id: 'r1', at: Date.now() + 1 });
    expect(model.get('selected')).toBe(0);
    model.set('request_1', { id: 'r0', at: Date.now() - 60_000 });
    expect(model.get('selected')).toBe(0);

    // Python sets `selected`.
    model.set('selected', 1);
    expect(model.get('display_1')).toBe('');
    cleanup();
    expect(el.querySelector('button')).toBeNull();
  });

  test('a web page stack shows one panel and follows view requests', () => {
    const el = document.createElement('div');
    const page = stack(el, ['Tissue', 'Cells']);
    expect(page.panels.map((p) => p.style.display)).toEqual(['', 'none']);
    const model = make_options_model({});
    page.watch(1, model);
    model.set('view_request', { id: 'x', at: Date.now() + 1 });
    expect(page.selected()).toBe(1);
    expect(page.panels.map((p) => p.style.display)).toEqual(['none', '']);
    el.querySelectorAll('button')[0].click();
    expect(page.selected()).toBe(0);
  });
});
