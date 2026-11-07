/**
 * Manual categories set programmatically (Python's Clustergram.set_categories, e.g.
 * Clerk's tentative cell types). Uses the same store calls as the category editor,
 * so the store's subscribers redraw category strips, bars and labels and sync the
 * result back to Python's `manual_cat`.
 */

/**
 * @param {object} viz_state - Clustergram visualization state.
 * @param {{axis?: string, attribute?: string, values?: object, colors?: object,
 *   replace?: boolean}} request - `values` maps row/column names to categories (an
 *   empty category removes the assignment); `colors` maps categories to hex.
 * @param {(viz_state: object) => string} allocate_color - Picks the next distinct
 *   color for a new category (the editor's allocator).
 * @returns {number} How many names were assigned.
 */
export const apply_manual_categories = (
  viz_state,
  { axis, attribute, values = {}, colors = {}, replace = false },
  allocate_color
) => {
  const ax = axis === 'row' ? 'row' : 'col';
  const store = viz_state.obs_store?.manual_cat?.[ax];
  if (!store) throw new Error('this Clustergram has no manual categories');
  viz_state.manual_cat = viz_state.manual_cat || { config: {}, flags: {} };
  viz_state.manual_cat.config = viz_state.manual_cat.config || {};
  viz_state.manual_cat.flags = viz_state.manual_cat.flags || {};
  const name =
    attribute || viz_state.manual_cat.config[ax]?.attribute || store.attribute;
  if (!name) {
    throw new Error(`no manual ${ax} category is set up; pass an attribute`);
  }
  // Turn manual categories on for this axis if it wasn't created with them.
  viz_state.manual_cat.flags[ax] = true;
  viz_state.manual_cat.config[ax] = {
    ...(viz_state.manual_cat.config[ax] || {}),
    attribute: name,
  };
  store.setAttribute(name); // no-op unless the attribute changes
  if (replace && store.values.size) {
    store.updateSelection({ selection: [...store.values.keys()], value: null });
  }
  // One update (one repaint) per category value.
  const by_value = new Map();
  Object.entries(values).forEach(([node, value]) => {
    const key = value === null || value === undefined ? '' : String(value);
    if (!by_value.has(key)) by_value.set(key, []);
    by_value.get(key).push(String(node));
  });
  let applied = 0;
  by_value.forEach((names, value) => {
    const color = value
      ? colors[value] ||
        viz_state.attr?.category_colors?.[value] ||
        allocate_color(viz_state)
      : undefined;
    store.updateSelection({ selection: names, value: value || null, color });
    applied += names.length;
  });
  return applied;
};
