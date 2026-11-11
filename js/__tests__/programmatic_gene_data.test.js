/* global require */

const fs = require('fs');
const path = require('path');

// Exercise the public handler with an asynchronous expression source: point
// filtering happens at selection time, before the gene's values are available.
const makeHandler = (readExpression) => {
  const source = fs.readFileSync(
    path.join(__dirname, '../viz/landscape_ist.js'),
    'utf8'
  );
  const start = source.indexOf('update_matrix_gene: async (inst_gene) => {');
  const end = source.indexOf('    update_matrix_col:', start);
  const handlerSource = source.slice(start, end).trim().replace(/,$/, '');
  const viz = {
    cats: { cat: 'cluster', values: [] },
    genes: {},
    obs_store: {},
    seg: { version: 'default' },
    row_group_readers: {},
  };
  const layers = { rows: [0, 1] };
  const repaintRows = [];
  const rebuild = jest.fn(() => {
    layers.rows =
      viz.cats.cat === 'cluster'
        ? [0, 1]
        : viz.cats.values.flatMap((value, row) => (value > 0 ? [row] : []));
  });
  const handler = new Function(
    'viz_state',
    'layers_obj',
    'callbacks',
    'update_cat',
    'update_selected_genes',
    'update_selected_cats',
    'update_cell_exp_array',
    'refresh_cell_layer',
    'refresh_layer',
    `return ({${handlerSource}}).update_matrix_gene;`
  )(
    viz,
    layers,
    { on_gene_select: [] },
    (cats, category) => {
      cats.cat = category;
    },
    () => {},
    () => rebuild(),
    readExpression,
    rebuild,
    () => repaintRows.push([...layers.rows])
  );
  return { handler, viz, layers, rebuild, repaintRows };
};

test('a gene read rebuilds initially empty point data before repainting', async () => {
  let resolve;
  const loaded = new Promise((done) => {
    resolve = done;
  });
  const fixture = makeHandler(async () => {
    await loaded;
    fixture.viz.cats.values = [0, 7];
    return true;
  });
  const pending = fixture.handler('Dcx');
  expect(fixture.layers.rows).toEqual([]);
  resolve();
  await pending;
  expect(fixture.layers.rows).toEqual([1]);
  expect(fixture.repaintRows).toEqual([[1], [1]]);
  await fixture.handler('Dcx');
  expect(fixture.layers.rows).toEqual([0, 1]);
});

test('a superseded gene read does not rebuild or repaint stale data', async () => {
  const fixture = makeHandler(async () => false);
  await fixture.handler('Dcx');
  expect(fixture.rebuild).toHaveBeenCalledTimes(1); // selection, before the read
  expect(fixture.repaintRows).toEqual([]);
});

// Cluster selections from an embedding app (update_matrix_col and
// update_matrix_dendro_col) must leave every layer ready: deck_ready repaints only
// when all of them are, so a layer left not-ready blocks every later zoom.
test.each([
  ['update_matrix_col', '    update_matrix_dendro_col:', '4'],
  ['update_matrix_dendro_col', '    update_view_state:', ['4', '5']],
])('%s leaves the deck ready to repaint', async (name, next, arg) => {
  const source = fs.readFileSync(
    path.join(__dirname, '../viz/landscape_ist.js'),
    'utf8'
  );
  const start = source.indexOf(`    ${name}: async`);
  const end = source.indexOf(next, start);
  const handlerSource = source.slice(start, end).trim().replace(/,$/, '');
  const storeSource = fs
    .readFileSync(path.join(__dirname, '../obs_store/obs_store.js'), 'utf8')
    .replace(/^export const /gm, 'const ');
  const obs_store = new Function(
    `${storeSource}\nreturn create_obs_store();`
  )();
  const refreshSource = fs
    .readFileSync(path.join(__dirname, '../utils/refresh_layer.js'), 'utf8')
    .replace(/^export const /gm, 'const ');
  const refresh_layer = new Function(
    `${refreshSource}\nreturn refresh_layer;`
  )();
  const viz = { cats: {}, genes: {}, obs_store };
  const repaints = [];
  obs_store.deck_ready.subscribe((ready) => ready && repaints.push(ready), {
    immediate: false,
  });
  const handler = new Function(
    'viz_state',
    'layers_obj',
    'callbacks',
    'update_cat',
    'update_selected_genes',
    'update_selected_cats',
    'refresh_layer',
    `return ({${handlerSource}})[${JSON.stringify(name)}];`
  )(
    viz,
    {},
    { on_cluster_select: [], on_clusters_select: [] },
    () => {},
    () => {},
    () => {},
    refresh_layer
  );
  await handler(arg);
  expect(obs_store.deck_ready.get()).toBe(true);
  expect(repaints.length).toBeGreaterThan(0);
});
