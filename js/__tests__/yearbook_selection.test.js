/* global require */

const fs = require('node:fs');
const path = require('node:path');

// Exercise the actual D3 joins and event handlers in jsdom. Its UMD build is
// loaded by path because d3's package exports expose its ESM entry point.
const d3Module = { exports: {} };
new Function(
  'module',
  'exports',
  fs.readFileSync(
    path.resolve(path.dirname(require.resolve('d3')), '../dist/d3.min.js'),
    'utf8'
  )
)(d3Module, d3Module.exports);
const d3 = d3Module.exports;

const helperSource = fs
  .readFileSync(path.join(__dirname, '../ui/yearbook_selection.js'), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const make_yearbook_selection = new Function(
  'd3',
  `${helperSource}\nreturn make_yearbook_selection;`
)(d3);

const makeModel = (selected_cells = []) => {
  const values = { selected_cells };
  const observers = new Map();
  const model = {
    get: jest.fn((key) => values[key]),
    set: jest.fn((key, value) => {
      values[key] = value;
      observers
        .get(`change:${key}`)
        ?.forEach((callback) => callback(model, value));
    }),
    save_changes: jest.fn(),
    on: jest.fn((event, callback) => {
      if (!observers.has(event)) observers.set(event, new Set());
      observers.get(event).add(callback);
    }),
    off: jest.fn((event, callback) => observers.get(event)?.delete(callback)),
  };
  return model;
};

const helpers = [];
const create = ({
  selected = [],
  cells = ['a', 'b', 'c', 'd'],
  model,
} = {}) => {
  const root = document.createElement('div');
  document.body.appendChild(root);
  const state = {
    model: model === null ? null : model || makeModel(selected),
    yearbook: {
      cells,
      num_rows: 1,
      num_cols: 2,
      portrait_pixel_size: 100,
      portrait_gap: 4,
      current_page: 0,
    },
  };
  const selection = make_yearbook_selection(root, state);
  helpers.push(selection);
  selection.render();
  return { root, state, model: state.model, selection };
};

const checkbox = (root, cell) =>
  root.querySelector(`[role="checkbox"][aria-label="Select cell ${cell}"]`);

afterEach(() => {
  helpers.splice(0).forEach((helper) => helper.dispose());
  document.body.replaceChildren();
});

test('starts from synced IDs and marks only checked portraits with a blue outline', () => {
  const { root, selection, model } = create({ selected: ['b', 'off-page'] });
  expect(selection.get_selected_cells()).toEqual(['b', 'off-page']);
  expect(checkbox(root, 'a')).toHaveAttribute('aria-checked', 'false');
  expect(checkbox(root, 'b')).toHaveAttribute('aria-checked', 'true');
  expect(
    d3.color(checkbox(root, 'b').parentElement.style.borderColor).formatHex()
  ).toBe('#2563eb');
  expect(checkbox(root, 'a').parentElement.style.borderColor).toBe(
    'transparent'
  );
  expect(checkbox(root, 'a').style.background).toBe('transparent');
  expect(Number(checkbox(root, 'a').style.opacity)).toBeLessThan(
    Number(checkbox(root, 'b').style.opacity)
  );
  expect(model.save_changes).not.toHaveBeenCalled();
});

test('clicks publish a fresh ordered list of original IDs once per toggle', () => {
  const original = ['b'];
  const { root, selection, model } = create({ selected: original });
  checkbox(root, 'a').click();
  expect(model.set).toHaveBeenLastCalledWith('selected_cells', ['b', 'a']);
  expect(model.save_changes).toHaveBeenCalledTimes(1);
  expect(original).toEqual(['b']);
  const returned = selection.get_selected_cells();
  returned.push('outside');
  expect(selection.get_selected_cells()).toEqual(['b', 'a']);

  checkbox(root, 'b').click();
  expect(selection.get_selected_cells()).toEqual(['a']);
  expect(model.set).toHaveBeenLastCalledWith('selected_cells', ['a']);
  expect(model.save_changes).toHaveBeenCalledTimes(2);
});

test('keeps checked IDs while changing pages and replacing query candidates', () => {
  const { root, state, selection } = create();
  checkbox(root, 'a').click();
  state.yearbook.current_page = 1;
  selection.render();
  expect(checkbox(root, 'a')).toBeNull();
  checkbox(root, 'd').click();

  state.yearbook.current_page = 0;
  selection.render();
  expect(checkbox(root, 'a')).toHaveAttribute('aria-checked', 'true');
  state.yearbook.cells = ['new-query-cell'];
  selection.render();
  expect(selection.get_selected_cells()).toEqual(['a', 'd']);
  expect(checkbox(root, 'new-query-cell')).toHaveAttribute(
    'aria-checked',
    'false'
  );
});

test('Python model changes update checks without an echo save', () => {
  const { root, selection, model } = create({ selected: ['a'] });
  model.set('selected_cells', ['b', '细胞_1_é']);
  expect(checkbox(root, 'a')).toHaveAttribute('aria-checked', 'false');
  expect(checkbox(root, 'b')).toHaveAttribute('aria-checked', 'true');
  expect(selection.get_selected_cells()).toEqual(['b', '细胞_1_é']);
  expect(model.set).toHaveBeenCalledTimes(1);
  expect(model.save_changes).not.toHaveBeenCalled();
});

test('does not add controls to empty slots on the last page', () => {
  const { root, state, selection } = create({
    cells: ['a', 'b', 'c', 'd', 'e'],
  });
  state.yearbook.num_rows = 2;
  state.yearbook.current_page = 1;
  selection.render();
  expect(root.querySelectorAll('[role="checkbox"]')).toHaveLength(1);
  expect(checkbox(root, 'e')).toBeInTheDocument();
  expect(checkbox(root, 'e').parentElement).toHaveAttribute(
    'data-cell-id',
    'e'
  );
});

test('duplicate portraits share one checked original ID', () => {
  const { root, selection, model } = create({ cells: ['a', 'a'] });
  const buttons = root.querySelectorAll('[role="checkbox"]');
  buttons[0].click();
  expect(selection.get_selected_cells()).toEqual(['a']);
  expect(model.get('selected_cells')).toEqual(['a']);
  buttons.forEach((button) =>
    expect(button).toHaveAttribute('aria-checked', 'true')
  );
  buttons[1].click();
  expect(selection.get_selected_cells()).toEqual([]);
  buttons.forEach((button) =>
    expect(button).toHaveAttribute('aria-checked', 'false')
  );
});

test('Space and Enter toggle once, prevent scrolling, and ignore key repeats', () => {
  const { root, selection, model } = create();
  const button = checkbox(root, 'a');
  const space = new KeyboardEvent('keydown', {
    key: ' ',
    bubbles: true,
    cancelable: true,
  });
  button.dispatchEvent(space);
  expect(space.defaultPrevented).toBe(true);
  expect(selection.get_selected_cells()).toEqual(['a']);
  button.dispatchEvent(
    new KeyboardEvent('keydown', { key: ' ', repeat: true, bubbles: true })
  );
  expect(selection.get_selected_cells()).toEqual(['a']);
  const enter = new KeyboardEvent('keydown', {
    key: 'Enter',
    bubbles: true,
    cancelable: true,
  });
  button.dispatchEvent(enter);
  expect(enter.defaultPrevented).toBe(true);
  expect(selection.get_selected_cells()).toEqual([]);
  expect(model.save_changes).toHaveBeenCalledTimes(2);
});

test('works without a notebook model and copies programmatic ID lists', () => {
  const { root, selection } = create({ model: null });
  const ids = ['b', 'b', 'a'];
  selection.set_selected_cells(ids);
  ids.push('later');
  expect(selection.get_selected_cells()).toEqual(['b', 'a']);
  expect(checkbox(root, 'b')).toHaveAttribute('aria-checked', 'true');
});

test('dispose removes portrait controls and unsubscribes the model observer', () => {
  const { root, selection, model } = create();
  const listener = model.on.mock.calls[0][1];
  selection.dispose();
  expect(model.off).toHaveBeenCalledWith('change:selected_cells', listener);
  expect(root.querySelector('.yearbook-selection-overlay')).toBeNull();
  model.set('selected_cells', ['b']);
  selection.render();
  expect(root.querySelector('[role="checkbox"]')).toBeNull();
  selection.dispose();
  expect(model.off).toHaveBeenCalledTimes(1);
});
