/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../matrix/dendro_tree.js'), 'utf8')
  .replace(/^export const /gm, 'const ');
const { build_dendro_tree, get_dendro_tree_groups, dendro_tree_point } =
  new Function(
    `${source}; return { build_dendro_tree, get_dendro_tree_groups, dendro_tree_point };`
  )();
const slice_source = fs
  .readFileSync(path.join(__dirname, '../matrix/dendro.js'), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const alt_slice_linkage = new Function(
  `${slice_source}; return alt_slice_linkage;`
)();

const linkage = [
  [0, 2, 0, 2],
  [1, 4, 1, 3],
  [5, 3, 2, 4],
];

test.each(['row', 'col'])(
  '%s tree preserves duplicate leaves, current cut, and RANK mapping',
  (axis) => {
    const map = [4, 1, 5, 2];
    // Display order: raw nodes 1, 4, 5, 2 (scipy leaves 1, 0, 2, 3).
    const order = [0, 4, 1, 0, 3, 2];
    const tree = build_dendro_tree(linkage, map, order);
    expect(tree.nodes[0].raw_index).toBe(4);
    expect(tree.nodes[0].center).toBe(0.375);
    expect(tree.nodes[4]).toMatchObject({
      start: 0.25,
      end: 0.75,
      count: 2,
      distance: 0,
    });
    expect(tree.nodes[6]).toMatchObject({
      start: 0,
      end: 1,
      count: 4,
      distance: 2,
    });
    const state = {
      [`${axis}_nodes`]: Array.from({ length: 6 }, () => ({})),
      linkage: { [axis]: linkage },
      rank_view: { leaf_map: { [axis]: map } },
    };
    [
      [0, 4],
      [0.5, 3],
      [1.5, 2],
      [2.01, 1],
    ].forEach(([cut, expected]) => {
      alt_slice_linkage(state, axis, cut);
      const groups = get_dendro_tree_groups(tree, state[`${axis}_nodes`]);
      expect(groups).toHaveLength(expected);
      expect(groups.reduce((sum, group) => sum + group.count, 0)).toBe(4);
      // Every cut partitions the leaf edge with no gaps or overlapping vials.
      const sorted = groups.sort((a, b) => a.start - b.start);
      expect(sorted[0].start).toBe(0);
      expect(sorted[sorted.length - 1].end).toBe(1);
      sorted
        .slice(1)
        .forEach((group, i) => expect(group.start).toBe(sorted[i].end));
    });
  }
);

test('water rises from the leaves on both axes', () => {
  expect(dendro_tree_point('col', 0.5, 0, 2, 300, 200)).toEqual([150, 200]);
  expect(dendro_tree_point('col', 0.5, 1, 2, 300, 200)).toEqual([150, 100]);
  expect(dendro_tree_point('col', 0.5, 2, 2, 300, 200)).toEqual([150, 0]);
  expect(dendro_tree_point('row', 0.5, 0, 2, 300, 200)).toEqual([300, 100]);
  expect(dendro_tree_point('row', 0.5, 1, 2, 300, 200)).toEqual([150, 100]);
  expect(dendro_tree_point('row', 0.5, 2, 2, 300, 200)).toEqual([0, 100]);
});

test('all-zero linkage remains finite and merges into one vial', () => {
  const zero_links = linkage.map(([a, b, _d, n]) => [a, b, 0, n]);
  const tree = build_dendro_tree(zero_links, [0, 1, 2, 3], [3, 4, 2, 1]);
  const state = { row_nodes: [{}, {}, {}, {}], linkage: { row: zero_links } };
  alt_slice_linkage(state, 'row', 0.005);
  expect(get_dendro_tree_groups(tree, state.row_nodes)).toHaveLength(1);
  expect(dendro_tree_point('col', 0.5, 0.005, 0.01, 100, 100)).toEqual([
    50, 50,
  ]);
});

test('a deep 20,000-leaf tree builds without recursion or descendant lists', () => {
  const count = 20000;
  const links = [[0, 1, 0, 2]];
  for (let i = 1; i < count - 1; i++)
    links.push([count + i - 1, i + 1, i, i + 2]);
  const map = Array.from({ length: count }, (_, i) => i);
  const tree = build_dendro_tree(links, map, map);
  expect(tree.nodes).toHaveLength(2 * count - 1);
  expect(tree.nodes.at(-1)).toMatchObject({ start: 0, end: 1, count });
});

test('missing or malformed trees do not produce geometry', () => {
  expect(build_dendro_tree([], [0], [1])).toBeNull();
  expect(build_dendro_tree([[0, 7, 1, 2]], [0, 1], [2, 1])).toBeNull();
});
