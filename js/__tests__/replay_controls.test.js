/* global require */
const fs = require('fs');
const path = require('path');

const source = fs
  .readFileSync(path.join(__dirname, '../matrix/replay_controls.js'), 'utf8')
  .replace(/^export const /gm, 'const ');
const {
  get_replay_controls,
  validate_replay_controls,
  restore_annotations,
  annotations_to_restore,
} = new Function(
  `${source}; return { get_replay_controls, validate_replay_controls, restore_annotations, annotations_to_restore };`
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

test('a saved-view restore never discards annotations made since the capture', () => {
  const state = fixture();
  const review = {
    attribute: 'review',
    values: { g1: 'marker' },
    colors: { marker: '#aa1122' },
  };
  // A fresh view: the saved annotations apply, and empty axes stay empty.
  expect(annotations_to_restore(state, { row: review, col: null })).toEqual({
    annotations: { row: review },
    kept: [],
  });
  // Labels added after the capture are kept, not replaced or cleared.
  restore_annotations(state, {
    row: {
      attribute: 'review',
      values: { g1: 'marker', g2: 'new label' },
      colors: {},
    },
    col: { attribute: 'cell_type', values: { C: 'other' }, colors: {} },
  });
  expect(annotations_to_restore(state, { row: review, col: null })).toEqual({
    annotations: {},
    kept: ['row'],
  });
  // Matching annotations restore as-is (e.g. to bring back their colors).
  restore_annotations(state, { row: review });
  expect(annotations_to_restore(state, { row: review }).annotations).toEqual({
    row: review,
  });
});

test('a dendrogram group can be selected by its members or by its name', () => {
  const state = fixture();
  validate_replay_controls(state, {
    selection: { dendrogram: { axis: 'row', members: ['g1', 'g2'] } },
  });
  // By the name the Clustergram state lists it under (resolved at the current cut).
  validate_replay_controls(state, {
    selection: { dendrogram: { axis: 'row', name: '39' } },
  });
  for (const dendrogram of [
    { axis: 'row', name: '' },
    { axis: 'row', name: '39', members: ['g1'] },
    { axis: 'side', name: '39' },
    { axis: 'row', members: ['unknown'] },
  ])
    expect(() =>
      validate_replay_controls(state, { selection: { dendrogram } })
    ).toThrow();
});
