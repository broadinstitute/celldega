/* global require */

describe('compute_crop_view', () => {
  let compute_crop_view;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(path.join(__dirname, '../deck-gl/matrix/crop.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const shims = `
      const LinearInterpolator = function () {};
      const get_mat_layers_list = () => [];
      const redefine_global_view_state = () => ({});
      const update_zoom_data = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { compute_crop_view };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ compute_crop_view } = module.exports);
  });

  const makeVizState = () => ({
    viz: {
      mat_width: 100,
      mat_height: 80,
      row_offset: 10,
      col_offset: 20,
    },
    zoom: {
      zoom_data: {
        matrix: {
          zoom_x: 1.5,
          zoom_y: 2.5,
          pan_x: 44,
          pan_y: 55,
        },
      },
    },
  });

  test('fits the dragged rectangle in both axes for heatmap-style crops', () => {
    const viz_state = makeVizState();

    const view = compute_crop_view(viz_state, [20, 20], [80, 60]);

    expect(view.zoom_curated[0]).toBeCloseTo(Math.log2(100 / 60));
    expect(view.zoom_curated[1]).toBeCloseTo(Math.log2(80 / 40));
    expect(view.pan_curated).toEqual([50, 40]);
  });

  test('composition crops preserve the current x zoom/pan and only crop rows', () => {
    const viz_state = makeVizState();

    const view = compute_crop_view(viz_state, [20, 20], [80, 60], {
      preserve_x: true,
    });

    expect(view.zoom_curated[0]).toBe(1.5);
    expect(view.pan_curated[0]).toBe(44);
    expect(view.zoom_curated[1]).toBeCloseTo(Math.log2(80 / 40));
    expect(view.pan_curated[1]).toBe(40);
  });
});
