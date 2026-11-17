/* global require */

// Requests Python sends while a widget renders are held, then delivered in order.
describe('hold_custom_messages', () => {
  let hold_custom_messages;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../utils/held_messages.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    hold_custom_messages = new Function(
      `${source}\nreturn hold_custom_messages;`
    )();
  });

  const make_model = () => {
    const listeners = new Map();
    return {
      id: 'model-1',
      get: (key) => `value of ${key}`,
      send: jest.fn(),
      on: (name, fn) => {
        if (!listeners.has(name)) listeners.set(name, new Set());
        listeners.get(name).add(fn);
      },
      off: (name, fn) => listeners.get(name)?.delete(fn),
      emit: (name, ...args) =>
        [...(listeners.get(name) || [])].forEach((fn) => fn(...args)),
      count: (name) => listeners.get(name)?.size || 0,
    };
  };

  it('delivers requests that arrived while rendering, in order, once open', () => {
    const model = make_model();
    const messages = hold_custom_messages(model);
    const seen = [];
    model.emit('msg:custom', { event: 'apply_state', id: 1 });
    // A handler registered during rendering hears nothing until the widget is ready.
    messages.model.on('msg:custom', (msg) => seen.push(msg.id));
    model.emit('msg:custom', { event: 'capture_snapshot', id: 2 });
    expect(seen).toEqual([]);
    messages.open();
    expect(seen).toEqual([1, 2]);
    model.emit('msg:custom', { event: 'get_state', id: 3 });
    expect(seen).toEqual([1, 2, 3]);
  });

  it('is otherwise the model, and stops listening when closed', () => {
    const model = make_model();
    const messages = hold_custom_messages(model);
    const changed = jest.fn();
    messages.model.on('change:value', changed);
    model.emit('change:value');
    expect(changed).toHaveBeenCalledTimes(1);
    expect(messages.model.get('height')).toBe('value of height');
    expect(messages.model.id).toBe('model-1');
    messages.model.send({ event: 'hi' });
    expect(model.send).toHaveBeenCalledWith({ event: 'hi' });

    const handler = jest.fn();
    messages.model.on('msg:custom', handler);
    messages.open();
    messages.model.off('msg:custom', handler);
    model.emit('msg:custom', { id: 1 });
    expect(handler).not.toHaveBeenCalled();
    messages.close();
    expect(model.count('msg:custom')).toBe(0);
  });
});
