/* global require */

describe('get_bar_highlight_opacity', () => {
  let get_bar_highlight_opacity;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    // bar_plot.js pulls in d3/deck imports; strip them and eval just the pure
    // helper under test.
    const source = fs
      .readFileSync(path.join(__dirname, '../ui/bar_plot.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const code = `${source}\nmodule.exports = { get_bar_highlight_opacity };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_bar_highlight_opacity } = module.exports);
  });

  it('keeps every bar full when nothing is selected', () => {
    expect(get_bar_highlight_opacity([], 'GAPDH')).toBe(1.0);
    expect(get_bar_highlight_opacity(null, 'GAPDH')).toBe(1.0);
  });

  it('highlights the selected bar and dims the rest (click regression)', () => {
    // Clicking GENE_B must set GENE_B to full and the others to dimmed.
    expect(get_bar_highlight_opacity(['GENE_B'], 'GENE_B')).toBe(1.0);
    expect(get_bar_highlight_opacity(['GENE_B'], 'GENE_A')).toBe(0.2);
    expect(get_bar_highlight_opacity(['GENE_B'], 'GENE_C')).toBe(0.2);
  });

  it('supports multiple selected bars', () => {
    expect(get_bar_highlight_opacity(['A', 'B'], 'A')).toBe(1.0);
    expect(get_bar_highlight_opacity(['A', 'B'], 'B')).toBe(1.0);
    expect(get_bar_highlight_opacity(['A', 'B'], 'C')).toBe(0.2);
  });

  it('compares by string so numeric cluster names still match', () => {
    expect(get_bar_highlight_opacity([1], '1')).toBe(1.0);
    expect(get_bar_highlight_opacity(['1'], 1)).toBe(1.0);
    expect(get_bar_highlight_opacity([1], 2)).toBe(0.2);
  });
});
