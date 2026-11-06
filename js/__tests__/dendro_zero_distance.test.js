/* global require */

const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../matrix/dendro.js'), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const { alt_slice_linkage, ini_dendro } = new Function(`
  const is_axis_index_visible = () => false;
  ${source}
  return { alt_slice_linkage, ini_dendro };
`)();

const linkage = [
  [0, 2, 0, 2],
  [1, 4, 1, 3],
  [5, 3, 2, 4],
];
const groups = (nodes, map) => {
  const result = new Map();
  map.forEach((index, leaf) => {
    const id = nodes[index].group_links;
    if (!result.has(id)) result.set(id, []);
    result.get(id).push(leaf);
  });
  return [...result.values()].sort((a, b) => a[0] - b[0]);
};

test.each(
  ['row', 'col'].flatMap((axis) => [false, true].map((rank) => [axis, rank]))
)(
  '%s duplicate leaves remain in their parent clusters (rank=%s)',
  (axis, rank) => {
    const map = rank ? [4, 1, 5, 2] : [0, 1, 2, 3];
    const nodes = Array.from({ length: rank ? 6 : 4 }, () => ({
      group_links: 'untouched',
    }));
    const state = {
      [`${axis}_nodes`]: nodes,
      linkage: { [axis]: linkage },
      rank_view: rank ? { leaf_map: { [axis]: map } } : undefined,
    };
    [
      [0, [[0], [1], [2], [3]]],
      [0.5, [[0, 2], [1], [3]]],
      [1.5, [[0, 1, 2], [3]]],
      [3, [[0, 1, 2, 3]]],
    ].forEach(([cut, expected]) => {
      alt_slice_linkage(state, axis, cut);
      expect(groups(nodes, map)).toEqual(expected);
    });
    if (rank) expect(nodes[0].group_links).toBe('untouched');
  }
);

test('an entirely identical axis becomes one group at any positive cut', () => {
  const state = {
    row_nodes: [{}, {}, {}, {}],
    linkage: { row: linkage.map((merge) => [merge[0], merge[1], 0, merge[3]]) },
  };
  alt_slice_linkage(state, 'row', 0.005);
  expect(groups(state.row_nodes, [0, 1, 2, 3])).toEqual([[0, 1, 2, 3]]);
});

test('an empty linkage can initialize without breaking the matrix', () => {
  const state = {
    row_nodes: [{}],
    col_nodes: [{}],
    linkage: { row: [], col: [] },
    mat: { viz_mode: 'heatmap' },
  };
  expect(() => ini_dendro(state)).not.toThrow();
});
