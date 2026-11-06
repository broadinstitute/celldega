/**
 * A widget model for the options-object entry points (`landscape`,
 * `clustergram`), used without a Python kernel. Like an anywidget model it
 * stores values and fires `change:<key>` events, so the visualizations behave
 * as they do in a notebook and can be linked with `link_models`.
 *
 * @param {object} [values] - Initial values, keyed like the Python traits.
 * @returns {{get: Function, set: Function, on: Function, off: Function,
 *   save_changes: Function}}
 */
export const make_options_model = (values = {}) => {
  const state = { ...values };
  const listeners = new Map();
  return {
    // Unset keys read as null, as in a static model.
    get: (key) => state[key] ?? null,
    set: (key, value) => {
      if (Object.is(state[key], value)) return;
      state[key] = value;
      [...(listeners.get(`change:${key}`) ?? [])].forEach((listener) =>
        listener()
      );
    },
    on: (event, listener) => {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event).add(listener);
    },
    off: (event, listener) => {
      if (listener) listeners.get(event)?.delete(listener);
      else listeners.delete(event);
    },
    save_changes: () => {},
  };
};

/**
 * Copy one model's value to another whenever it changes, like ipywidgets'
 * `jslink` in one direction. For example, Clustergram clicks drive a
 * Landscape: `link_models(cgm.model, 'click_info', ls.model, 'update_trigger')`.
 *
 * @returns {Function} Stops the link.
 */
export const link_models = (source, source_key, target, target_key) => {
  const listener = () => target.set(target_key, source.get(source_key));
  source.on(`change:${source_key}`, listener);
  return () => source.off(`change:${source_key}`, listener);
};
