import { Observable, deepEquals } from './observable';

// Clustergram state is compared by content: callers frequently rebuild the same
// selection/breakdown objects, and we only want subscribers to fire on real
// changes.
const deep = { equals: deepEquals };

export const create_clustergram_store = () => ({
  selected_genes: Observable([], deep),
  focused_dendro: Observable(null, deep),
  // Tracks the current attribute-based reorder state
  // { axis: 'row'|'col', attr_index: number, attr_name: string, order_key: string }
  attr_reorder_state: Observable(null, deep),

  // Selected matrix cell info
  // { row_name, col_name, row_index, col_index, value }
  selected_cell: Observable(null, deep),

  // Selected category attribute info
  // { axis: 'row'|'col', attr_name: string, attr_index: number, value: string, node_names: string[] }
  selected_category: Observable(null, deep),

  // Currently hovered category (for highlighting)
  // { axis: 'row'|'col', attr_name: string, value: string }
  hovered_category: Observable(null, deep),

  // Dendro selection - which nodes are selected via dendrogram click
  // { axis: 'row'|'col', selected_names: string[] }
  dendro_selection: Observable(null, deep),

  // Category breakdown data for bar graphs (updated on dendro click)
  // { row: { attr_name: [{name, value, color}], ... }, col: { ... } }
  category_breakdown: Observable({ row: {}, col: {} }, deep),
});
