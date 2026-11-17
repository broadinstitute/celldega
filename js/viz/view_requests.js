/**
 * Snapshot cards open their view in a linked viewer through two traits linked in
 * the browser (see Python's `Snapshot`): a card writes `view_request`
 * (`{id, name, at, snapshot}`) and the viewer answers in `view_result`. No kernel
 * round trip, so cards work in saved notebooks too.
 *
 * `view_result` is also how the viewer tells every linked card which Snapshot it
 * shows: `{id, shown}` after opening one (`shown` is its name), `{id: null, shown}`
 * when a pin opened it, and `{id: null, shown: ''}` once the scientist moves the
 * view themselves. Each card marks itself shown, or clears its status, from that.
 */

/**
 * Tell the linked cards which Snapshot is shown (`''`: none, e.g. after the
 * scientist moved the view).
 * @param {object} model - The viewer's widget model.
 * @param {string} shown
 */
export const announce_view = (model, shown) => {
  if (typeof model?.set !== 'function') return;
  if ((model.get('view_result') || {}).shown === shown && !shown) return;
  model.set('view_result', { id: null, shown });
  model.save_changes?.();
};

/**
 * @param {object} model - The viewer's widget model.
 * @param {(snapshot: object) => Promise<unknown>} restore - Opens a saved view.
 * @param {{since?: number}} [options] - Requests made before `since` (ms) are
 *   ignored: when a page reloads, its links copy each card's last request into the
 *   viewer, which must not reopen old views.
 * @returns {() => void} Stop listening.
 */
export const listen_for_view_requests = (
  model,
  restore,
  { since = Date.now() } = {}
) => {
  if (typeof model?.on !== 'function') return () => {};
  let last = '';
  const on_request = async () => {
    const request = model.get('view_request') || {};
    if (!request.id || request.id === last || !request.snapshot) return;
    if (Number.isFinite(request.at) && request.at < since) return;
    last = request.id;
    const shown = String(request.name || '');
    let result = { id: request.id, shown };
    try {
      await restore(request.snapshot);
    } catch (error) {
      result = {
        id: request.id,
        shown: '',
        error: String(error?.message || error),
      };
    }
    model.set('view_result', result);
    model.save_changes?.();
  };
  model.on('change:view_request', on_request);
  return () => model.off?.('change:view_request', on_request);
};
