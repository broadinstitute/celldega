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
    selected_cells: Observable([]),
    new_cell_bar_data: Observable([]),
    new_gene_bar_data: Observable([]),
    selected_genes: Observable([]),
    selected_nbhds: Observable([]),
    viz_image_layers: Observable(true),
    viz_background_layer: Observable(true),
    viz_nbhd_layer: Observable(false),
    viz_edit_layer: Observable(false),
    landscape_view: Observable('spatial'),
    umap_state: Observable(false),
    scale_bar_view_state: Observable(null),
    // Zoom state - true when zoomed in enough to see transcripts
    close_up: Observable(false),
    // Dataset switching observables
    current_dataset_index: Observable(0),
    dataset_switching: Observable(false),
    // Persistent state across dataset switches
    // This allows users to compare the same cluster/gene across datasets
    persistent_state: Observable({
      selected_cats: [],
      selected_genes: [],
      cat: 'cluster', // 'cluster' or gene name
      viz_image_layers: true,
      landscape_view: 'spatial', // 'spatial' or 'umap'
    }),
    // to do utilize for setProps
    deck_check: Observable({
      background_layer: true,
      image_layers: true,
      cell_layer: true,
      path_layer: true,
      trx_layer: true,
      nbhd_layer: true,
      edit_layer: true,
      trx_data: true,
      path_data: true,
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

  /**
   * Set up centralized image visibility management.
   * Call this once during landscape initialization to enable automatic
   * image visibility based on gene/cluster selection and zoom level.
   *
   * @param {Function} get_img_layer_visible - Function to check if IMG button is enabled
   */
  store.setup_image_visibility_manager = (get_img_layer_visible) => {
    const update_viz_image_layers = () => {
      // Don't change if IMG button is toggled off
      if (get_img_layer_visible && !get_img_layer_visible()) {
        return;
      }

      const hasCats = store.selected_cats.get().length > 0;
      const hasGenes = store.selected_genes.get().length > 0;
      const isCloseUp = store.close_up.get();
      const isUmap = store.umap_state.get();

      if (hasCats || hasGenes) {
        // When focused on gene/cluster:
        // - Zoomed in (close_up): show images to see transcripts in context
        // - Zoomed out: hide images to see the colored cell overlay
        store.viz_image_layers.set(isCloseUp);
      } else {
        // No gene/cluster selected - show images if not in umap view
        if (!isUmap) {
          store.viz_image_layers.set(true);
        }
      }
    };

    // Subscribe to all relevant state changes
    store.selected_cats.subscribe(update_viz_image_layers, {
      immediate: false,
    });
    store.selected_genes.subscribe(update_viz_image_layers, {
      immediate: false,
    });
    store.close_up.subscribe(update_viz_image_layers, { immediate: false });

    // Return the function so it can be called manually if needed
    return update_viz_image_layers;
  };

  return store;
};
