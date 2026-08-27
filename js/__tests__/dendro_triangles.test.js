/* global require */

describe('calc_dendro_triangles', () => {
  let calc_dendro_triangles;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(path.join(__dirname, '../matrix/dendro.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const shims = `
      const get_composition_layout = () => ({});
      const rightmost_composition_col = () => null;
      const get_axis_center_position = (_viz_state, _axis, index) => index * 10 + 5;
      const get_axis_edge_positions = (_viz_state, _axis, index) => [index * 10, index * 10 + 10];
      const get_axis_slot_size = () => 10;
      const is_axis_index_visible = () => true;
    `;

    const code = `${shims}\n${source}\nmodule.exports = { calc_dendro_triangles };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ calc_dendro_triangles } = module.exports);
  });

  test('stores raw leaf indices alongside display names for each cluster', () => {
    const viz_state = {
      mat: { viz_mode: 'heatmap' },
      row_nodes: [
        { name: '0: duplicated', group_links: 'a' },
        { name: '1: unique', group_links: 'a' },
        { name: '2: duplicated', group_links: 'b' },
      ],
      dendro: {
        group_info: {},
      },
    };

    calc_dendro_triangles(viz_state, 'row');

    const cluster_a = viz_state.dendro.group_info.row.find(
      (group) => group.name === 'a'
    );
    const cluster_b = viz_state.dendro.group_info.row.find(
      (group) => group.name === 'b'
    );

    expect(cluster_a.all_names).toEqual(['duplicated', 'unique']);
    expect(cluster_a.all_indices).toEqual([0, 1]);
    expect(cluster_b.all_names).toEqual(['duplicated']);
    expect(cluster_b.all_indices).toEqual([2]);
  });
});
