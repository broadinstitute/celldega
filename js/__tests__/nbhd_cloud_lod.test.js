/* global require */

describe('neighborhood-cloud zoom-driven LOD', () => {
  let compute_nbhd_cloud_lod;
  let compute_nearest_slices;
  let makeSliceSetKey;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/core/nbhd_cloud_lod.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { compute_nbhd_cloud_lod, compute_nearest_slices, makeSliceSetKey };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ compute_nbhd_cloud_lod, compute_nearest_slices, makeSliceSetKey } =
      module.exports);
  });

  const thresholds = {
    fade_in_start: 2.0,
    fade_in_end: 4.0,
    fade_out_start: 3.0,
    fade_out_end: 1.0,
  };

  test('below the fade-in band, shapes are opaque and cells are hidden', () => {
    const lodState = { band: 'shapes' };
    const result = compute_nbhd_cloud_lod(1.0, lodState, thresholds);

    expect(result).toEqual({ t: 0, fillOpacity: 1, cellOpacity: 0 });
    expect(lodState.band).toBe('shapes');
  });

  test('above the fade-in band, cells are fully opaque and shapes are transparent', () => {
    const lodState = { band: 'shapes' };
    const result = compute_nbhd_cloud_lod(5.0, lodState, thresholds);

    expect(result).toEqual({ t: 1, fillOpacity: 0, cellOpacity: 1 });
    expect(lodState.band).toBe('cells');
  });

  test('midway through the fade-in band, opacities crossfade linearly', () => {
    const lodState = { band: 'shapes' };
    const result = compute_nbhd_cloud_lod(3.0, lodState, thresholds);

    expect(result.t).toBeCloseTo(0.5);
    expect(result.fillOpacity).toBeCloseTo(0.5);
    expect(result.cellOpacity).toBeCloseTo(0.5);
    expect(lodState.band).toBe('crossfade');
  });

  test('hysteresis: once in cells band, zooming back out uses the lower fade-out thresholds', () => {
    const lodState = { band: 'cells' };

    // At zoom 2.5 the fade-in band (2-4) would say "still fading in"
    // (t=0.25), but since we're coming from 'cells', the fade-out band
    // (1-3) applies instead, and 2.5 is most of the way back down.
    const result = compute_nbhd_cloud_lod(2.5, lodState, thresholds);

    expect(result.t).toBeCloseTo(0.25);
    expect(lodState.band).toBe('crossfade');
  });

  test('hysteresis prevents flicker exactly at the fade-in start boundary', () => {
    // Simulate hovering right at zoom=2 (fade_in_start) after having reached
    // 'cells' at some point — with fade-out thresholds (3 -> 1) in effect,
    // zoom=2 is still mid-crossfade, not back to 'shapes'.
    const lodState = { band: 'cells' };
    const result = compute_nbhd_cloud_lod(2.0, lodState, thresholds);

    expect(result.t).toBeCloseTo(0.5);
    expect(lodState.band).toBe('crossfade');
  });

  test('compute_nearest_slices sorts by 3D Euclidean distance and truncates to n', () => {
    const metaSlice = [
      { slice_id: 'far', centroid_x: 1000, centroid_y: 0, centroid_z: 0 },
      { slice_id: 'near', centroid_x: 1, centroid_y: 0, centroid_z: 0 },
      { slice_id: 'mid', centroid_x: 10, centroid_y: 0, centroid_z: 0 },
    ];

    expect(compute_nearest_slices([0, 0, 0], metaSlice, 2)).toEqual([
      'near',
      'mid',
    ]);
  });

  test('compute_nearest_slices defaults target z to 0 when omitted', () => {
    const metaSlice = [
      { slice_id: 'a', centroid_x: 0, centroid_y: 0, centroid_z: 5 },
      { slice_id: 'b', centroid_x: 0, centroid_y: 0, centroid_z: 50 },
    ];

    expect(compute_nearest_slices([0, 0], metaSlice, 1)).toEqual(['a']);
  });

  test('makeSliceSetKey is order-independent', () => {
    expect(makeSliceSetKey(['b', 'a', 'c'])).toBe(
      makeSliceSetKey(['c', 'a', 'b'])
    );
    expect(makeSliceSetKey(['a'])).not.toBe(makeSliceSetKey(['a', 'b']));
  });
});
