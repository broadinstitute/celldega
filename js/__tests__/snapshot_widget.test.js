/* global require */
const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(
  path.join(__dirname, '../../src/celldega/viz/_snapshot.js'),
  'utf8'
);
const widget = new Function(source.replace('export default', 'return'))();

const model = (values = {}) => {
  const state = {
    image: 'UE5H',
    name: 'Glomerulus',
    description: 'Podocyte ring',
    metadata: { kind: 'landscape' },
    can_restore: true,
    target_label: 'Landscape',
    ...values,
  };
  const listeners = new Map();
  return {
    get: (key) => state[key],
    send: jest.fn(),
    on: (event, callback) => listeners.set(event, callback),
    off: (event) => listeners.delete(event),
    change: (key, value) => {
      state[key] = value;
      listeners.get(`change:${key}`)?.();
    },
    listeners,
  };
};

describe('Snapshot postcard', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    jest.useFakeTimers();
  });
  afterEach(() => jest.useRealTimers());

  test('renders memo as text and expands metadata without loading a viewer', () => {
    const m = model({ description: '<script>unsafe()</script>\nSecond line' });
    const el = document.createElement('div');
    const cleanup = widget.render({ model: m, el });
    expect(el.querySelector('img').getAttribute('src')).toBe(
      'data:image/png;base64,UE5H'
    );
    expect(el.querySelector('h3').textContent).toBe('Glomerulus');
    expect(el.querySelector('script')).toBeNull();
    expect(el.querySelector('.memo').textContent).toContain('<script>');
    expect(el.querySelector('details').open).toBe(false);
    expect(el.querySelector('pre').textContent).toContain('landscape');
    cleanup();
    expect(m.listeners.size).toBe(0);
    expect(el.children.length).toBe(0);
  });

  test('navigates only its own linked model and reflects acknowledgement', () => {
    const m = model();
    const other = model();
    const el = document.createElement('div');
    const cleanup = widget.render({ model: m, el });
    const cleanupOther = widget.render({ model: other, el });
    const button = el.querySelector('button');
    button.click();
    button.click();
    expect(m.send).toHaveBeenCalledTimes(1);
    expect(m.send).toHaveBeenCalledWith({ event: 'restore' });
    expect(other.send).not.toHaveBeenCalled();
    m.change('busy', true);
    expect(button.disabled).toBe(true);
    m.change('busy', false);
    m.change('status', 'View opened in Landscape.');
    expect(el.querySelector('.status').textContent).toBe(
      'View opened in Landscape.'
    );
    expect(button.disabled).toBe(false);
    cleanup();
    cleanupOther();
  });

  test('explains an unavailable kernel and hides navigation on an unlinked PNG', () => {
    const el = document.createElement('div');
    const m = model();
    const cleanup = widget.render({ model: m, el });
    el.querySelector('button').click();
    jest.advanceTimersByTime(40001);
    expect(el.querySelector('.status').textContent).toContain('live kernel');
    m.change('can_restore', false);
    expect(el.querySelector('button').hidden).toBe(true);
    cleanup();
  });
});
