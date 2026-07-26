/**
 * Minimal observable value used by the widget state stores.
 *
 * Historically each store (obs_store, clustergram_store, enrich_store) defined
 * its own copy of this factory, and they had drifted apart (some used reference
 * equality, one used a deep JSON comparison). This module is the single source
 * of truth so every store shares identical, well-defined semantics.
 */

const referenceEquals = (a, b) => a === b;

/**
 * Structural equality for the array/object values many observables hold.
 * Falls back to a JSON comparison, which is sufficient for the plain,
 * serializable state stored here (arrays of names, flag objects, etc.).
 */
export const deepEquals = (a, b) => {
  if (a === b) return true;

  const aIsObject = typeof a === 'object' && a !== null;
  const bIsObject = typeof b === 'object' && b !== null;
  if (!aIsObject || !bIsObject) return false;

  return JSON.stringify(a) === JSON.stringify(b);
};

/**
 * Create an observable value.
 *
 * @param {*} initialValue - The starting value (also returned by getDefault).
 * @param {object} [options]
 * @param {(a: *, b: *) => boolean} [options.equals] - Equality check used to
 *   decide whether a `set`/`update` should notify subscribers. Defaults to
 *   reference equality; pass `deepEquals` for values compared by content.
 */
export const Observable = (initialValue, options = {}) => {
  const equals = options.equals || referenceEquals;

  let value = initialValue;
  const subscribers = new Set();

  const set = (newValue) => {
    if (equals(value, newValue)) return;
    value = newValue;
    subscribers.forEach((fn) => fn(value));
  };

  return {
    get: () => value,
    getDefault: () => initialValue,
    set,
    /**
     * Derive the next value from the current one, e.g.
     * `store.selected_genes.update((genes) => [...genes, name])`.
     */
    update: (fn) => set(fn(value)),
    subscribe: (fn, subscribeOptions = { immediate: true }) => {
      subscribers.add(fn);
      if (subscribeOptions.immediate) {
        fn(value);
      }
      return () => subscribers.delete(fn);
    },
  };
};
