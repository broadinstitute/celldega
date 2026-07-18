/* global require */

describe('neighborhood-cloud cell color buffer', () => {
  let build_nbhd_cloud_cell_color_buffer;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/layers/nbhd_cloud_cell_layer.js'),
        'utf8'
      )
      .replace(/^import .*$/gm, '')
      .replace(/^export const /gm, 'const ');
    const code = `${source}\nmodule.exports = { build_nbhd_cloud_cell_color_buffer };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ build_nbhd_cloud_cell_color_buffer } = module.exports);
  });

  test('colors each cell from the cluster color dict with full alpha', () => {
    const buffer = build_nbhd_cloud_cell_color_buffer(['0', '1'], {
      0: [10, 20, 30],
      1: [40, 50, 60],
    });

    expect(Array.from(buffer)).toEqual([10, 20, 30, 255, 40, 50, 60, 255]);
  });

  test('falls back to a default gray for clusters missing from the color dict', () => {
    const buffer = build_nbhd_cloud_cell_color_buffer(['unknown'], {});
    expect(Array.from(buffer)).toEqual([128, 128, 128, 255]);
  });

  test('handles an empty cluster id list', () => {
    const buffer = build_nbhd_cloud_cell_color_buffer([], {});
    expect(buffer.length).toBe(0);
  });
});
