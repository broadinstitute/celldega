/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../matrix/replay_controls.js'), 'utf8')
  .replace(/^export const /gm, 'const ');
const { get_replay_controls, validate_replay_controls, restore_annotations } =
  new Function(
    `${source}; return { get_replay_controls, validate_replay_controls, restore_annotations };`
  )();
const fixture = () => {
  const names = Array.from({ length: 150 }, (_, i) => `g${i}`);
  const store = () => ({
    attribute: null,
    values: new Map(),
    colors: new Map(),
    emit: jest.fn(),
  });
  return {
    row_nodes: names.map((name) => ({ name })),
    col_nodes: [{ name: 'C' }],
    model: { get: () => [] },
    labels: { highlighted_genes: new Set(names) },
    dendro: { sliders: { row_percent: 35, col_percent: 65 } },
    manual_cat: { config: {}, flags: {} },
    obs_store: {
      selected_genes: { get: () => names },
      manual_cat: { row: store(), col: store() },
    },
    state_controls: { selection() {}, dendrogram() {} },
  };
};

test('manual annotations replace both axes and uncapped selections survive capture', () => {
  const state = fixture();
  const annotations = {
    row: {
      attribute: 'review',
      values: { g1: 'marker' },
      colors: { marker: '#aa1122' },
    },
    col: null,
  };
  validate_replay_controls(state, { annotations });
  restore_annotations(state, annotations);
  const saved = JSON.parse(JSON.stringify(get_replay_controls(state)));
  expect(saved.selection.genes).toHaveLength(150);
  expect(saved.selection.highlighted_genes).toHaveLength(150);
  restore_annotations(state, {
    row: null,
    col: {
      attribute: 'new',
      values: { C: 'other' },
      colors: { other: '#123456' },
    },
  });
  expect(get_replay_controls(state).annotations).not.toEqual(saved.annotations);
  validate_replay_controls(state, saved);
  restore_annotations(state, saved.annotations);
  expect(get_replay_controls(state)).toEqual(saved);
});

test('invalid cuts, selection names and annotations fail before changing state', () => {
  const state = fixture();
  const before = get_replay_controls(state);
  for (const changes of [
    { dendrogram: { row: NaN } },
    { selection: { rows: ['unknown'] } },
    {
      annotations: {
        row: { attribute: 'review', values: { unknown: 'x' }, colors: {} },
      },
    },
  ])
    expect(() => validate_replay_controls(state, changes)).toThrow();
  expect(get_replay_controls(state)).toEqual(before);
});
