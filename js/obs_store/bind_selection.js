/**
 * Make an observable the single source of truth for a field that legacy code
 * reads and writes directly (e.g. `viz_state.cats.selected_cats`).
 *
 * Historically selection state lived in two places at once: the observable in
 * `obs_store` (which the UI subscribes to) and a plain mirror field on
 * `viz_state.cats` / `viz_state.genes` (which layer accessors read). The two had
 * to be kept in sync by hand, which is fragile and has already produced
 * stale-read bugs.
 *
 * Instead of rewriting every read/write site at once, we replace the plain
 * field with a getter/setter that delegates to the observable. Existing code
 * that does `cats.selected_cats` or `cats.selected_cats = [...]` keeps working
 * verbatim, but there is now exactly one place the value lives.
 */

/**
 * Replace `target[key]` with a live view onto `observable`.
 *
 * Any pre-existing value on the target is used to seed the observable before
 * the property is redefined, so no state is lost when binding.
 *
 * @param {object} target - Object owning the field (e.g. viz_state.cats).
 * @param {string} key - Field name (e.g. 'selected_cats').
 * @param {{get: () => *, set: (value: *) => void}} observable
 */
export const bind_observable_field = (target, key, observable) => {
  if (!target || !observable) return;

  if (Object.prototype.hasOwnProperty.call(target, key)) {
    const existing = target[key];
    if (existing !== undefined) {
      observable.set(existing);
    }
    delete target[key];
  }

  Object.defineProperty(target, key, {
    configurable: true,
    enumerable: true,
    get: () => observable.get(),
    set: (value) => {
      observable.set(value);
    },
  });
};

/**
 * Bind the landscape selection fields to their obs_store observables so the
 * store is the single source of truth.
 *
 * Safe to call once `viz_state.obs_store`, `viz_state.cats`, and
 * `viz_state.genes` exist.
 *
 * @param {object} viz_state
 */
export const bind_selection_to_store = (viz_state) => {
  const { obs_store, cats, genes } = viz_state || {};

  if (cats && obs_store?.selected_cats) {
    bind_observable_field(cats, 'selected_cats', obs_store.selected_cats);
  }

  if (genes && obs_store?.selected_genes) {
    bind_observable_field(genes, 'selected_genes', obs_store.selected_genes);
  }
};
