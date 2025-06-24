
const Observable = (initialValue) => {

  let value = initialValue;
  const subscribers = new Set()

  return {
    get: () => value,
    getDefault: () => initialValue,
    set: newValue => {
      if (value !== newValue) {
        value = newValue;
        subscribers.forEach(fn => fn(value));
      }
    },
    subscribe: (fn, options = { immediate: true }) => {
      subscribers.add(fn);
      if (options.immediate) {
          fn(value);
      }
      return () => subscribers.delete(fn);
    }
  }

}

export const create_obs_store = () => {

    return {
        cat: Observable("cluster"),
        selected_cats: Observable([]),
        new_cell_bar_data: Observable([]),
        new_gene_bar_data: Observable([]),
        selected_genes: Observable([]),
        viz_image_layers: Observable(true),
        deck_check: Observable({
            backgroukd_layer: true,
            image_layers: true,
            cell_layer: true,
            path_layer: true,
            trx_layer: true
        }),
    }

}

