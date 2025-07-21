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

export const create_enrich_store = () => {
  const store = {
    available_libs: Observable([]),
    selected_lib: Observable('CellMarker_2024'),
    term_genes: Observable([]),
    gene_of_interest: Observable(''),
    selected_term: Observable('Select Term'),
  };

  return store;
};
