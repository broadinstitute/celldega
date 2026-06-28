const Observable = (initialValue) => {
  let value = initialValue;
  const subscribers = new Set();

  return {
    get: () => value,
    getDefault: () => initialValue,
    set: (newValue) => {
      // Deep comparison for objects/arrays
      const isDifferent =
        typeof newValue === 'object' && newValue !== null
          ? JSON.stringify(value) !== JSON.stringify(newValue)
          : value !== newValue;

      if (isDifferent) {
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

  // Selected matrix cell info
  // { row_name, col_name, row_index, col_index, value }
  selected_cell: Observable(null),

  // Selected category attribute info
  // { axis: 'row'|'col', attr_name: string, attr_index: number, value: string, node_names: string[] }
  selected_category: Observable(null),

  // Currently hovered category (for highlighting)
  // { axis: 'row'|'col', attr_name: string, value: string }
  hovered_category: Observable(null),

  // Dendro selection - which nodes are selected via dendrogram click
  // { axis: 'row'|'col', selected_names: string[] }
  dendro_selection: Observable(null),

  // Category breakdown data for bar graphs (updated on dendro click)
  // { row: { attr_name: [{name, value, color}], ... }, col: { ... } }
  category_breakdown: Observable({ row: {}, col: {} }),
});
