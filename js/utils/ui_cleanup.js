/**
 * Per-widget teardown for UI pieces created outside the widget root (e.g.
 * body-level tooltips) or that hold timers/subscriptions. The widget's
 * `finalize` calls {@link run_ui_cleanups}.
 */

/**
 * @param {object} viz_state
 * @param {() => void} cleanup
 */
export const register_ui_cleanup = (viz_state, cleanup) => {
  if (!viz_state || typeof cleanup !== 'function') return;
  viz_state.ui_cleanups ??= [];
  viz_state.ui_cleanups.push(cleanup);
};

/** Run and clear every registered cleanup; safe to call more than once. */
export const run_ui_cleanups = (viz_state) => {
  const cleanups = viz_state?.ui_cleanups?.splice(0) ?? [];
  cleanups.forEach((cleanup) => {
    try {
      cleanup();
    } catch {
      // A failed cleanup must not block the rest of teardown.
    }
  });
};
