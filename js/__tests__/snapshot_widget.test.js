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
  test('linked cards hear which Snapshot the viewer shows', () => {
    const state = model({
      js_link: true,
      view: { kind: 'landscape', state: {} },
    });
    state.set = (key, value) => state.change(key, value);
    state.save_changes = jest.fn();
    const el = document.createElement('div');
    document.body.appendChild(el);
    widget.render({ model: state, el });
    const card = el.querySelector('.celldega-snapshot');
    const status = el.querySelector('.status');

    el.querySelector('button').click();
    const request = state.get('view_request');
    expect(request).toMatchObject({
      name: 'Glomerulus',
      snapshot: state.get('view'),
    });
    expect(Number.isFinite(request.at)).toBe(true);
    // Opening a view first clears every card's mark; this one keeps waiting.
    state.change('view_result', { id: null, shown: '' });
    expect(status.textContent).toBe('Opening this view…');
    state.change('view_result', { id: request.id, shown: 'Glomerulus' });
    expect(status.textContent).toBe('View opened in Landscape.');
    expect(card.classList.contains('shown')).toBe(true);

    // Another card (or a pin) opens its view: this one clears.
    state.change('view_result', { id: 'other', shown: 'Medulla' });
    expect(status.textContent).toBe('');
    expect(card.classList.contains('shown')).toBe(false);
    // A pin of the same name opens this view: marked again.
    state.change('view_result', { id: null, shown: 'Glomerulus' });
    expect(status.textContent).toBe('Shown in the Landscape.');
    expect(card.classList.contains('shown')).toBe(true);
    // The scientist moves the view: cleared.
    state.change('view_result', { id: null, shown: '' });
    expect(card.classList.contains('shown')).toBe(false);
  });
});
