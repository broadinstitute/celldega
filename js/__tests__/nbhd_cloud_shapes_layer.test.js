/* global require */

describe('neighborhood-cloud shapes fill color', () => {
  let is_nbhd_cloud_gene_color_mode;
  let get_nbhd_cloud_fill_color;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import .*$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = [
      readStripped('../utils/hexToRgb.js'),
      readStripped('../deck-gl/layers/nbhd_cloud_shapes_layer.js'),
    ].join('\n');

    const code = `${source}\nmodule.exports = { is_nbhd_cloud_gene_color_mode, get_nbhd_cloud_fill_color };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ is_nbhd_cloud_gene_color_mode, get_nbhd_cloud_fill_color } =
      module.exports);
  });

  const feature = (color, neighborhood_id = 'n1') => ({
    properties: { color, neighborhood_id },
  });

  test('is_nbhd_cloud_gene_color_mode is false when no gene selected', () => {
    expect(is_nbhd_cloud_gene_color_mode({})).toBe(false);
    expect(is_nbhd_cloud_gene_color_mode({ selected_gene: null })).toBe(false);
  });

  test('is_nbhd_cloud_gene_color_mode is true once a gene is selected', () => {
    expect(is_nbhd_cloud_gene_color_mode({ selected_gene: 'Gene0' })).toBe(
      true
    );
  });

  test('cluster-color mode: fill uses the neighborhood color with crossfade alpha baked in', () => {
    const viz_state = { nbhd_cloud: {} };
    expect(get_nbhd_cloud_fill_color(feature('#ff0000'), viz_state, 1)).toEqual(
      [255, 0, 0, 255]
    );
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000'), viz_state, 0.5)
    ).toEqual([255, 0, 0, 128]);
    expect(get_nbhd_cloud_fill_color(feature('#ff0000'), viz_state, 0)).toEqual(
      [255, 0, 0, 0]
    );
  });

  test('gene-color mode: alpha is expression fraction times the crossfade fraction', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Gene0',
        selected_gene_max_mean: 10,
        gene_stats: new Map([['n1', { mean: 5, variance: 0 }]]),
      },
    };

    // fully faded in (fillOpacityFraction=1): alpha = 255 * (5/10) * 1
    expect(
      get_nbhd_cloud_fill_color(feature('#00ff00', 'n1'), viz_state, 1)
    ).toEqual([255, 0, 0, 128]);
    // mid-crossfade (fillOpacityFraction=0.5): alpha = 255 * (5/10) * 0.5
    expect(
      get_nbhd_cloud_fill_color(feature('#00ff00', 'n1'), viz_state, 0.5)
    ).toEqual([255, 0, 0, 64]);
  });

  test('gene-color mode: neighborhoods with no stats for the selected gene get zero alpha', () => {
    const viz_state = {
      nbhd_cloud: {
        selected_gene: 'Gene0',
        selected_gene_max_mean: 10,
        gene_stats: new Map(),
      },
    };

    expect(
      get_nbhd_cloud_fill_color(feature('#00ff00', 'missing'), viz_state, 1)
    ).toEqual([255, 0, 0, 0]);
  });

  test('a selected neighborhood stays fully opaque regardless of the ambient crossfade fraction', () => {
    const viz_state = {
      nbhd_cloud: { selected_neighborhood_ids: new Set(['n1']) },
    };

    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', 'n1'), viz_state, 0)
    ).toEqual([255, 0, 0, 255]);
    // an unselected neighborhood still respects the crossfade fraction
    expect(
      get_nbhd_cloud_fill_color(feature('#ff0000', 'n2'), viz_state, 0)
    ).toEqual([255, 0, 0, 0]);
  });
});
