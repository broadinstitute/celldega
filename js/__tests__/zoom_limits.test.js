/* global require */

// Landscape zoom limits (zoom_limits.js) and how the 2D view applies them.

const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../deck-gl/core/zoom_limits.js'), 'utf8')
  .replace(/^export const /gm, 'const ');
const module_ = { exports: {} };
new Function(
  'module',
  `${source}\nmodule.exports = { MIN_ZOOM_MARGIN, MAX_ZOOM_VIEW_MICRONS, zoom_to_fit, landscape_zoom_limits };`
)(module_);
const {
  MIN_ZOOM_MARGIN,
  MAX_ZOOM_VIEW_MICRONS,
  zoom_to_fit,
  landscape_zoom_limits,
} = module_.exports;

describe('zoom_to_fit', () => {
  it('fits the tissue by its tighter side', () => {
    // 1000 x 600 canvas, 4000 x 1200 tissue: the width limits (1/4 scale).
    expect(zoom_to_fit(1000, 600, 4000, 1200)).toBe(-2);
    // A 4x wider tissue fits two zoom levels further out.
    expect(zoom_to_fit(1000, 600, 16000, 1200)).toBe(-4);
  });

  it('is not finite until both sizes are known', () => {
    expect(Number.isFinite(zoom_to_fit(0, 600, 4000, 1200))).toBe(false);
    expect(Number.isFinite(zoom_to_fit(1000, 600, 0, 0))).toBe(false);
    // ...so the matching limit is left open.
    expect(
      landscape_zoom_limits({
        fit_zoom: zoom_to_fit(0, 600, 4000, 1200),
        canvas_size: 600,
      }).minZoom
    ).toBe(-Infinity);
  });
});

describe('landscape_zoom_limits', () => {
  const xenium = {
    fit_zoom: -5.5,
    initial_zoom: -5.5,
    canvas_size: 600,
    microns_per_unit: 0.2125,
  };

  it('stops a zoom level past tissue-wide and at a few microns across', () => {
    const { minZoom, maxZoom } = landscape_zoom_limits(xenium);
    expect(minZoom).toBe(-5.5 - MIN_ZOOM_MARGIN);
    // At maxZoom the canvas's shorter side spans MAX_ZOOM_VIEW_MICRONS.
    const microns_across = (600 / 2 ** maxZoom) * 0.2125;
    expect(microns_across).toBeCloseTo(MAX_ZOOM_VIEW_MICRONS);
  });

  it('takes data units as microns when their size is unknown', () => {
    const { maxZoom } = landscape_zoom_limits({
      ...xenium,
      microns_per_unit: null,
    });
    expect(maxZoom).toBeCloseTo(Math.log2(600 / MAX_ZOOM_VIEW_MICRONS));
  });

  it('uses min_zoom/max_zoom when given', () => {
    expect(
      landscape_zoom_limits({ ...xenium, min_zoom: -8, max_zoom: 2 })
    ).toEqual({ minZoom: -8, maxZoom: 2 });
    // None from Python arrives as null.
    expect(
      landscape_zoom_limits({ ...xenium, min_zoom: null, max_zoom: null })
        .minZoom
    ).toBe(-6.5);
  });

  it('always allows the starting zoom', () => {
    expect(landscape_zoom_limits({ ...xenium, initial_zoom: -9 }).minZoom).toBe(
      -9
    );
    expect(landscape_zoom_limits({ ...xenium, initial_zoom: 6 }).maxZoom).toBe(
      6
    );
  });

  it('leaves a side unlimited when it cannot be computed', () => {
    const { minZoom, maxZoom } = landscape_zoom_limits({
      fit_zoom: Number.NaN,
      canvas_size: Infinity,
    });
    expect(minZoom).toBe(-Infinity);
    expect(maxZoom).toBe(Infinity);
  });
});
