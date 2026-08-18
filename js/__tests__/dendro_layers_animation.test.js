/* global require */

// Dendrogram trapezoids should only ever morph/animate for composition
// mode's PROP/COUNTS toggle -- every other redraw (the cut-level/"slice"
// threshold slider, a row/col reorder, a viz-mode switch, composition
// weight changes) snaps instantly, since those change WHICH leaves are
// grouped together rather than smoothly repositioning the same group.
describe('dendrogram layer animation is opt-in, not default', () => {
  let update_dendro_layer_data;
  let refresh_composition_dendro;
  let refresh_dendro_for_viz_mode;
  const calls = { calc_triangles: [], calc_polygons: [] };

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    const source = readStripped('../deck-gl/matrix/dendro_layers.js');

    const shims = `
      const d3 = { easeCubic: 'easeCubic' };
      const PolygonLayer = function (props) { this.props = props; };
      const sync_selected_genes = () => {};
      const sync_selected_rows = () => {};
      const sync_selected_cols = () => {};
      const calc_dendro_triangles = (viz_state, axis) => { calls.calc_triangles.push(axis); };
      const calc_dendro_polygons = (viz_state, axis) => { calls.calc_polygons.push(axis); };
      const get_mat_layers_list = () => [];
    `;

    const code = `${shims}\n${source}\nmodule.exports = { update_dendro_layer_data, refresh_composition_dendro, refresh_dendro_for_viz_mode };`;
    const module = { exports: {} };
    new Function('module', 'exports', 'calls', code)(
      module,
      module.exports,
      calls
    );
    ({
      update_dendro_layer_data,
      refresh_composition_dendro,
      refresh_dendro_for_viz_mode,
    } = module.exports);
  });

  beforeEach(() => {
    calls.calc_triangles.length = 0;
    calls.calc_polygons.length = 0;
  });

  const makeLayerStub = () => ({
    clone(props) {
      return { ...this, lastCloneProps: props };
    },
  });

  const makeVizState = (overrides = {}) => ({
    dendro: { polygons: { row: ['r-poly'], col: ['c-poly'] } },
    animate: { duration: 2500 },
    mat: { viz_mode: 'composition' },
    ...overrides,
  });

  test('update_dendro_layer_data defaults to no transitions (instant snap)', () => {
    const layers_mat = { row_dendro_layer: makeLayerStub() };
    const viz_state = makeVizState();

    update_dendro_layer_data(layers_mat, viz_state, 'row');

    expect(layers_mat.row_dendro_layer.lastCloneProps.transitions).toBe(false);
    expect(layers_mat.row_dendro_layer.lastCloneProps.data).toEqual(['r-poly']);
  });

  test('update_dendro_layer_data(animate=true) sets a real getPolygon transition', () => {
    const layers_mat = { row_dendro_layer: makeLayerStub() };
    const viz_state = makeVizState();

    update_dendro_layer_data(layers_mat, viz_state, 'row', true);

    const { transitions } = layers_mat.row_dendro_layer.lastCloneProps;
    expect(transitions).not.toBe(false);
    expect(transitions.getPolygon.duration).toBe(2500);
  });

  test('refresh_composition_dendro defaults to no animation', () => {
    const layers_mat = { row_dendro_layer: makeLayerStub() };
    const viz_state = makeVizState();

    refresh_composition_dendro(layers_mat, viz_state);

    expect(layers_mat.row_dendro_layer.lastCloneProps.transitions).toBe(false);
  });

  test('refresh_composition_dendro(animate=true) -- the PROP/COUNTS toggle case -- animates', () => {
    const layers_mat = { row_dendro_layer: makeLayerStub() };
    const viz_state = makeVizState();

    refresh_composition_dendro(layers_mat, viz_state, true);

    const { transitions } = layers_mat.row_dendro_layer.lastCloneProps;
    expect(transitions).not.toBe(false);
    expect(transitions.getPolygon.duration).toBe(2500);
  });

  test('refresh_composition_dendro is still a no-op outside composition mode, regardless of animate', () => {
    const layers_mat = { row_dendro_layer: makeLayerStub() };
    const viz_state = makeVizState({ mat: { viz_mode: 'heatmap' } });

    refresh_composition_dendro(layers_mat, viz_state, true);

    expect(layers_mat.row_dendro_layer.lastCloneProps).toBeUndefined();
    expect(calls.calc_triangles).toEqual([]);
  });

  test('refresh_dendro_for_viz_mode (a viz-mode switch) never animates either axis', () => {
    const layers_mat = {
      row_dendro_layer: makeLayerStub(),
      col_dendro_layer: makeLayerStub(),
    };
    const viz_state = makeVizState();

    refresh_dendro_for_viz_mode(layers_mat, viz_state);

    expect(layers_mat.row_dendro_layer.lastCloneProps.transitions).toBe(false);
    expect(layers_mat.col_dendro_layer.lastCloneProps.transitions).toBe(false);
  });
});
