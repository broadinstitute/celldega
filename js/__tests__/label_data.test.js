/* global require */

describe('Clustergram display labels', () => {
  const loadLabelData = () => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../matrix/label_data.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    const module = { exports: {} };
    const shims = `
      const base_display_label = (value) =>
        String(value ?? '').split('::', 1)[0].trim();
    `;
    const code = `${shims}\n${source}\nmodule.exports = { set_row_label_data, set_col_label_data };`;
    new Function('module', 'exports', code)(module, module.exports);
    return module.exports;
  };

  const vizState = () => ({
    labels: {},
    mat: { orders: {} },
    manual_cat: { flags: {} },
    obs_store: { manual_cat: {} },
  });

  test('hides a multi-omic suffix in row labels but preserves the feature ID', () => {
    const { set_row_label_data } = loadLabelData();
    const viz_state = vizState();
    const network = {
      row_nodes: [
        { name: 'CDH1::rna', ini: 0, clust: 0, rank: 0, rankvar: 0 },
        {
          name: 'C38:5 PC::metabolomics',
          ini: 1,
          clust: 1,
          rank: 1,
          rankvar: 1,
        },
        { name: 'E-Cadherin', ini: 2, clust: 2, rank: 2, rankvar: 2 },
      ],
    };

    set_row_label_data(network, viz_state);

    expect(viz_state.labels.row_label_data.map((row) => row.name)).toEqual([
      'CDH1::rna',
      'C38:5 PC::metabolomics',
      'E-Cadherin',
    ]);
    expect(
      viz_state.labels.row_label_data.map((row) => row.display_name)
    ).toEqual(['CDH1', 'C38:5 PC', 'E-Cadherin']);
  });

  test('does not modify column identifiers', () => {
    const { set_col_label_data } = loadLabelData();
    const viz_state = vizState();
    const network = {
      col_nodes: [
        { name: 'source::cluster_1', ini: 0, clust: 0, rank: 0, rankvar: 0 },
      ],
    };

    set_col_label_data(network, viz_state);

    expect(viz_state.labels.col_label_data[0].display_name).toBe(
      'source::cluster_1'
    );
  });
});
