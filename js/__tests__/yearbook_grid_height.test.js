/* global require */

describe('yearbook grid pixel height', () => {
  let get_grid_pixel_height;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    // yearbook_viewports.js imports d3 at the top; strip imports and eval just
    // the pure helpers we need.
    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/core/yearbook_viewports.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const code = `${source}\nmodule.exports = { get_grid_pixel_height };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_grid_pixel_height } = module.exports);
  });

  it('sums rows plus inter-row gaps (matches create_yearbook_views layout)', () => {
    // 3 rows of 100px portraits with 4px gaps -> 300 + 2*4 = 308
    expect(get_grid_pixel_height(3, 100, 4)).toBe(308);
  });

  it('has no trailing gap for a single row', () => {
    expect(get_grid_pixel_height(1, 120, 4)).toBe(120);
  });

  it('is shorter than the reserved canvas height when width-limited (regression)', () => {
    // Simulate the dead-space scenario: 6 columns, 3 rows, total height 800,
    // control panel 100, gap 4.
    const num_rows = 3;
    const num_cols = 6;
    const height = 800;
    const gap = 4;
    const actual_width = 1000;

    const available_width = actual_width - (num_cols - 1) * gap;
    const available_height = height - 100 - (num_rows - 1) * gap;
    const portrait_pixel_size = Math.min(
      available_width / num_cols,
      available_height / num_rows
    );

    const grid_height = get_grid_pixel_height(
      num_rows,
      portrait_pixel_size,
      gap
    );

    // Width-limited here: portrait size is capped by the 6 columns, so the grid
    // is meaningfully shorter than the old fixed canvas height (height - 100).
    expect(portrait_pixel_size).toBeCloseTo(available_width / num_cols);
    expect(grid_height).toBeLessThan(height - 100);
  });

  it('equals the reserved canvas height when height-limited', () => {
    // Tall/narrow: portrait size capped by rows, so the grid fills height - 100.
    const num_rows = 4;
    const num_cols = 1;
    const height = 800;
    const gap = 4;
    const actual_width = 1000;

    const available_width = actual_width - (num_cols - 1) * gap;
    const available_height = height - 100 - (num_rows - 1) * gap;
    const portrait_pixel_size = Math.min(
      available_width / num_cols,
      available_height / num_rows
    );

    const grid_height = get_grid_pixel_height(
      num_rows,
      portrait_pixel_size,
      gap
    );
    expect(grid_height).toBeCloseTo(height - 100);
  });

  it('returns 0 for non-positive rows', () => {
    expect(get_grid_pixel_height(0, 100, 4)).toBe(0);
  });
});
