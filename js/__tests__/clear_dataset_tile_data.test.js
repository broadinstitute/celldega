/* global require */

// Switching datasets must not discard the rebuilt cell_compact: the zoomed-in
// cell bars count from it, so clearing it froze the cell bars after any switch.

const fs = require('fs');
const path = require('path');

// Same loading pattern as the other tests here: evaluate the ES module source
// with its `export`s stripped (compact_data.js has no imports).
const source = fs
  .readFileSync(path.join(__dirname, '../utils/compact_data.js'), 'utf8')
  .replace(/^export const /gm, 'const ');
const { buildCellCompactData, clearDatasetTileData, createEmptyTrxCompact } =
  new Function(
    `${source}\nreturn { buildCellCompactData, clearDatasetTileData, createEmptyTrxCompact };`
  )();

const makeVizState = () => ({
  genes: {
    trx_data: [{ name: 1 }],
    trx_gene_ids: new Int32Array([1, 2]),
  },
  cats: { polygon_cell_names: ['a'] },
  combo_data: {
    trx: [{ name: 1 }],
    trx_compact: {
      geneIds: new Int32Array([1]),
      positions: new Float64Array([0, 0]),
      size: 2,
    },
    cell_compact: buildCellCompactData(
      ['cell-1', 'cell-2'],
      new Float64Array([1, 1, 2, 2]),
      2,
      { 'cell-1': '0', 'cell-2': '1' }
    ),
  },
  viewport_cache: {
    visibleTileKey: '0:0',
    lastGeneBarData: [{ name: 'A', value: 1 }],
    lastCellBarData: [{ name: '0', value: 1 }],
  },
});

describe('clearDatasetTileData', () => {
  test('clears transcript/path data and the viewport bar cache', () => {
    const viz_state = makeVizState();
    clearDatasetTileData(viz_state);

    expect(viz_state.genes.trx_data).toEqual([]);
    expect(viz_state.genes.trx_gene_ids).toHaveLength(0);
    expect(viz_state.cats.polygon_cell_names).toEqual([]);
    expect(viz_state.combo_data.trx).toEqual([]);
    expect(viz_state.combo_data.trx_compact).toEqual(createEmptyTrxCompact());
    expect(viz_state.viewport_cache.visibleTileKey).toBeNull();
    expect(viz_state.viewport_cache.lastGeneBarData).toBeNull();
    expect(viz_state.viewport_cache.lastCellBarData).toBeNull();
  });

  test('keeps the rebuilt cell_compact so viewport cell bars still count cells', () => {
    // Regression: switching datasets used to reset cell_compact after rebuilding
    // it, so zoomed-in cell bars stopped updating after any dataset switch.
    const viz_state = makeVizState();
    const cellCompact = viz_state.combo_data.cell_compact;
    clearDatasetTileData(viz_state);

    expect(viz_state.combo_data.cell_compact).toBe(cellCompact);
    expect(viz_state.combo_data.cell_compact.categoryIds).toHaveLength(2);
    expect(viz_state.combo_data.cell_compact.categoryNames).toEqual(['0', '1']);
  });

  test('works before the viewport cache exists', () => {
    const viz_state = makeVizState();
    delete viz_state.viewport_cache;
    expect(() => clearDatasetTileData(viz_state)).not.toThrow();
  });
});
