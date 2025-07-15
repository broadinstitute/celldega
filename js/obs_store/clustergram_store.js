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
});
