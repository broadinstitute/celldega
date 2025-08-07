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

export const create_obs_store = () => {
  const store = {
    cat: Observable('cluster'),
    selected_cats: Observable([]),
    new_cell_bar_data: Observable([]),
    new_gene_bar_data: Observable([]),
    selected_genes: Observable([]),
    selected_nbhds: Observable([]),
    viz_image_layers: Observable(true),
    viz_background_layer: Observable(true),
    viz_nbhd_layer: Observable(false),
    landscape_view: Observable('spatial'),
    umap_state: Observable(false),
    // to do utilize for setProps
    deck_check: Observable({
      background_layer: true,
      image_layers: true,
      cell_layer: true,
      path_layer: true,
      trx_layer: true,
      nbhd_layer: true,
      trx_data: true,
      path_data: true,
      square_scatter_data: true,
    }),
    deck_ready: Observable(false),
  };

  store.deck_check.subscribe(
    (check) => {
      const ready = Object.values(check).every((v) => v === true);
      store.deck_ready.set(ready);
    },
    { immediate: false }
  );

  return store;
};
