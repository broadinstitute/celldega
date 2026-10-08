/* global require */

// The gene set a column click sends to enrichment scales with the *visible*
// rows. A flat "top 50" silently breaks under a rank view -- 50 of a 45-row
// view is the whole view, which enriches a gene set against itself.

const fs = require('fs');
const path = require('path');

describe('resolve_top_gene_count', () => {
  let resolve_top_gene_count;
  let top_gene_names_for_column;

  beforeAll(() => {
    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/label_layers.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ')
      .replace(/^export function /gm, 'function ');

    const shims = `
      class TextLayer {
        constructor(props) { this.props = props; this.id = props.id; }
        clone(next = {}) { return new TextLayer({ ...this.props, ...next }); }
      }
      const d3 = { easeCubic: (t) => t };
      const sync_selected_genes = () => {};
      const sync_selected_rows = () => {};
      const sync_selected_cols = () => {};
      const composition_row_label_position = () => [0, 0];
      const refresh_row_label_visibility = () => {};
      const crop_fade_axis_alpha_factor = () => 1;
      const crop_filter_signature = () => 0;
      const filter_label_data = () => [];
      const get_axis_center_position = () => 0;
      // The single input under test: how many rows are actually on screen.
      const get_axis_display_count = (viz_state) => viz_state.visible_rows;
      const get_axis_label_font_size = () => 10;
      const get_zoomed_axis_label_font_size = () => 10;
      const is_axis_index_visible = (viz_state, _axis, index) =>
        !viz_state.hidden_rows?.has(index);
      const buildColAxisSlice = (viz_state, col_index, max_entries, filter) => ({
        entries: viz_state.mat.net_mat
          .map((row, row_index) => ({
            counterpart_name: viz_state.row_nodes[row_index].name,
            row_index,
            value: Number(row[col_index]),
          }))
          .filter((entry) =>
            Number.isFinite(entry.value) &&
            entry.value !== 0 &&
            (!filter || filter(entry.row_index))
          )
          .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
          .slice(0, max_entries),
      });
      const emitMatrixSliceRequest = () => {};
      const deselect_reorder_buttons = () => {};
      const apply_composition_hover_col = () => {};
      const apply_composition_hover_row = () => {};
      const clear_composition_hover = () => {};
      const HOVER_HIGHLIGHT_DELAY_MS = 0;
      const clear_dendro_hover = () => {};
      const refresh_composition_dendro = () => {};
      const toggle_dendro_layer_visibility = () => {};
      const get_layer_update_triggers = (layer) => layer.props.updateTriggers || {};
      const get_mat_layers_list = () => [];
      const row_label_color_triggers = () => [];
      const col_label_color_triggers = () => [];
      const mat_reorder_triggers = () => ({});
      const with_focus_zoom_transitions = (state) => state;
      const redefine_global_view_state = () => ({});
      const update_zoom_data = () => {};
      const ini_views = () => {};
      const hide_tooltip = () => {};
    `;

    const module = { exports: {} };
    new Function(
      'module',
      `${shims}\n${source}\nmodule.exports = { resolve_top_gene_count, top_gene_names_for_column };`
    )(module);
    ({ resolve_top_gene_count, top_gene_names_for_column } = module.exports);
  });

  const count = (visible_rows, overrides = {}) =>
    resolve_top_gene_count({ visible_rows, ...overrides });

  test('a full matrix still yields the top_n_genes cap', () => {
    // 10% of 1284 is 128, above the cap — unchanged from the fixed-count rule.
    expect(count(1284, { top_n_genes: 50 })).toBe(50);
    expect(count(600, { top_n_genes: 50 })).toBe(50);
  });

  test('a reduced view takes a share of the rows instead of all of them', () => {
    expect(count(450, { top_n_genes: 50 })).toBe(45);
    expect(count(45, { top_n_genes: 50 })).toBe(5);
  });

  test('narrow views fall back to the floor rather than a token gene or two', () => {
    // 10% of 15 rounds to 2, which is useless for enrichment.
    expect(count(15, { top_n_genes: 50 })).toBe(5);
    expect(count(12, { top_n_genes: 50 })).toBe(5);
  });

  test('never asks for more genes than are on screen', () => {
    expect(count(3, { top_n_genes: 50 })).toBe(3);
    expect(count(1, { top_n_genes: 50 })).toBe(1);
  });

  test('honours a custom percentage', () => {
    expect(count(1000, { top_n_genes: 500, top_gene_percent: 5 })).toBe(50);
    expect(count(1000, { top_n_genes: 500, top_gene_percent: 20 })).toBe(200);
  });

  test('falls back to sane defaults for missing or invalid settings', () => {
    expect(count(1284)).toBe(50);
    expect(count(1284, { top_n_genes: 0, top_gene_percent: -1 })).toBe(50);
    expect(count(450, { top_n_genes: null, top_gene_percent: undefined })).toBe(
      45
    );
  });

  test('column genes must be above the minimum value', () => {
    const viz_state = {
      visible_rows: 4,
      top_n_genes: 50,
      top_gene_percent: 100,
      top_gene_min_value: 0,
      mat: { net_mat: [[1], [-0.1], [0.5], [2]] },
      row_nodes: [
        { name: 'g0' },
        { name: 'g1' },
        { name: 'g2' },
        { name: 'g3' },
      ],
    };

    expect(top_gene_names_for_column(viz_state, 0)).toEqual(['g3', 'g0', 'g2']);
  });

  test('a null minimum value disables the filter', () => {
    const viz_state = {
      visible_rows: 3,
      top_n_genes: 50,
      top_gene_percent: 100,
      top_gene_min_value: null,
      mat: { net_mat: [[1], [-2], [0.5]] },
      row_nodes: [{ name: 'g0' }, { name: 'g1' }, { name: 'g2' }],
    };

    // Unfiltered, the slice ranks by magnitude, so the negative gene leads.
    expect(top_gene_names_for_column(viz_state, 0)).toEqual(['g1', 'g0', 'g2']);
  });
});
