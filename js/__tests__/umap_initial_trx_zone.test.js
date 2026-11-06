/* global require */

const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(
    path.join(__dirname, '../deck-gl/core/calc_viewport.js'),
    'utf8'
  )
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');

const visibleTiles = jest.fn(() => [{}, {}]);
const sync_trx_button = jest.fn();
const module_ = { exports: {} };
new Function(
  'module',
  'visibleTiles',
  'sync_trx_button',
  `const trx_zone = (count) => count;
   const trx_force_tile_factor = () => 9;
   ${source}
   module.exports = { set_trx_zone_for_view, calc_viewport };`
)(module_, visibleTiles, sync_trx_button);
const { set_trx_zone_for_view, calc_viewport } = module_.exports;

describe('initial transcript zoom zone', () => {
  it.each([true, false, undefined])(
    'never enumerates Chromium tiles with UMAP state %s',
    async (umap) => {
      const state = {
        img: { landscape_parameters: { technology: 'Chromium', tile_size: 1 } },
        obs_store:
          umap === undefined ? undefined : { umap_state: { get: () => umap } },
      };
      // Enumerating this view's one-unit tiles would allocate ~200M objects.
      const view = {
        width: 600,
        height: 650,
        zoom: -4.5,
        target: [5000, 5000],
      };
      set_trx_zone_for_view(view, {}, state);
      await calc_viewport(view, null, {}, state);
      expect(visibleTiles).not.toHaveBeenCalled();
      expect(sync_trx_button).not.toHaveBeenCalled();
      expect(state.trx_zone).toBeUndefined();
    }
  );

  it('also skips spatial transcript tiles in a spatial dataset’s UMAP view', async () => {
    const state = {
      img: { landscape_parameters: { technology: 'Xenium', tile_size: 1000 } },
      obs_store: { umap_state: { get: () => true } },
    };
    const view = { width: 600, height: 650, zoom: -4.5, target: [5000, 5000] };
    set_trx_zone_for_view(view, {}, state);
    await calc_viewport(view, null, {}, state);
    expect(visibleTiles).not.toHaveBeenCalled();
    expect(sync_trx_button).not.toHaveBeenCalled();
    expect(state.trx_zone).toBeUndefined();
  });

  it('still classifies the initial transcript zone for a spatial view', () => {
    const layers = {};
    const state = {
      img: { landscape_parameters: { technology: 'Xenium', tile_size: 1000 } },
      obs_store: { umap_state: { get: () => false } },
      max_tiles_to_view: 50,
    };
    set_trx_zone_for_view(
      { width: 600, height: 650, zoom: 0, target: [500, 500] },
      layers,
      state
    );
    expect(visibleTiles).toHaveBeenCalledWith(200, 800, 175, 825, 1000);
    expect(state.trx_zone).toBe(2);
    expect(sync_trx_button).toHaveBeenCalledWith(state, layers);
  });
});
