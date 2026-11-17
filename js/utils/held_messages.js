/**
 * Python's requests to a widget (apply_state, Snapshots, state reads, close) are
 * one-off custom messages. A widget can take a while to render (fetching its data)
 * before its handlers listen, and a message that arrives in the meantime would be
 * dropped: e.g. `landscape.apply_state(...)` run right after the cell that displays
 * the Landscape. This holds them until the widget has rendered, then delivers them
 * in order.
 *
 * Widgets render with the returned `model`, which is the real model except that
 * custom-message handlers register here; `open()` (after rendering) delivers what
 * was held and everything after it.
 *
 * @param {object} model - The widget's model.
 * @returns {{model: object, open: () => void, close: () => void}}
 */
export const hold_custom_messages = (model) => {
  const handlers = new Set();
  const held = [];
  let open = false;
  const deliver = (msg, buffers) => {
    [...handlers].forEach((handler) => handler(msg, buffers));
  };
  const listener = (msg, buffers) => {
    if (open) deliver(msg, buffers);
    else held.push([msg, buffers]);
  };
  model.on?.('msg:custom', listener);

  const view = new Proxy(model, {
    get(target, prop) {
      if (prop === 'on') {
        return (name, handler, context) => {
          if (name === 'msg:custom') {
            handlers.add(handler);
            return undefined;
          }
          return target.on?.(name, handler, context);
        };
      }
      if (prop === 'off') {
        return (name, handler, context) => {
          if (name === 'msg:custom') {
            if (handler) handlers.delete(handler);
            else handlers.clear();
            return undefined;
          }
          return target.off?.(name, handler, context);
        };
      }
      const value = Reflect.get(target, prop, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });

  return {
    model: view,
    open: () => {
      if (open) return;
      open = true;
      held.splice(0).forEach(([msg, buffers]) => deliver(msg, buffers));
    },
    close: () => {
      model.off?.('msg:custom', listener);
      handlers.clear();
      held.length = 0;
    },
  };
};
