const Observable = (initialValue) => {
  let value = initialValue;
  const subscribers = new Set();

  return {
    get: () => value,
    getDefault: () => initialValue,
    set: (newValue) => {
      if (value !== newValue) {
        value = newValue;
        subscribers.forEach((fn) => fn(value));
      }
    },
    subscribe: (fn, options = { immediate: true }) => {
      subscribers.add(fn);
      if (options.immediate) {
        fn(value);
      }
      return () => subscribers.delete(fn);
    },
  };
};

export const create_clustergram_store = () => ({
  selected_genes: Observable([]),
  focused_dendro: Observable(null),
  // Tracks the current attribute-based reorder state
  // { axis: 'row'|'col', attr_index: number, attr_name: string, order_key: string }
  attr_reorder_state: Observable(null),
});
