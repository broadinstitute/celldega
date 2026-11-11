/**
 * Snapshot cards open their view in a linked viewer through two traits linked in
 * the browser (see Python's `Snapshot`): the card writes `view_request`
 * (`{id, snapshot}`) and the viewer answers in `view_result` (`{id}` or
 * `{id, error}`). No kernel round trip, so cards work in saved notebooks too.
 *
 * @param {object} model - The viewer's widget model.
 * @param {(snapshot: object) => Promise<unknown>} restore - Opens a saved view.
 * @returns {() => void} Stop listening.
 */
export const listen_for_view_requests = (model, restore) => {
  if (typeof model?.on !== 'function') return () => {};
  let last = '';
  const on_request = async () => {
    const request = model.get('view_request') || {};
    if (!request.id || request.id === last || !request.snapshot) return;
    last = request.id;
    let result = { id: request.id };
    try {
      await restore(request.snapshot);
    } catch (error) {
      result = { id: request.id, error: String(error?.message || error) };
    }
    model.set('view_result', result);
    model.save_changes?.();
  };
  model.on('change:view_request', on_request);
  return () => model.off?.('change:view_request', on_request);
};
