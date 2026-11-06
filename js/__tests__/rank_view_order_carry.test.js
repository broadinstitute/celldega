/* global require */

// Changing the DIM (rank view) level keeps each axis's order rather than
// resetting to CLUST, except when the order is keyed on a gene the new view
// filters out.
const fs = require('fs');
const path = require('path');

describe('carry_order_across_view', () => {
  let carry_order_across_view;

  beforeAll(() => {
    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/rank_views.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    const shims = `
      const is_axis_index_visible = (viz_state, axis, index) =>
        axis === 'col' || visible_rows.has(index);
      const deselect_reorder_buttons = (viz_state, axis) => {
        viz_state.reorder_dropdowns[axis].value = 'custom';
      };
    `;
    carry_order_across_view = (viz_state, rows) => {
      return new Function(
        'visible_rows',
        `${shims}${source}; return carry_order_across_view;`
      )(rows)(viz_state);
    };
  });

  const make_state = (order, driver) => ({
    order: { current: { ...order } },
    labels: { reorder_driver: driver },
    buttons: { text_active: 'blue' },
    reorder_dropdowns: {
      row: { value: '', style: {} },
      col: { value: '', style: {} },
    },
  });

  test('keeps a column-driven row order (columns are never filtered)', () => {
    const viz_state = make_state(
      { row: 'custom', col: 'clust' },
      { axis: 'col', name: 'cluster 3', index: 3 }
    );
    carry_order_across_view(viz_state, new Set([0, 1]));
    expect(viz_state.order.current).toEqual({ row: 'custom', col: 'clust' });
    expect(viz_state.labels.reorder_driver).not.toBeNull();
    expect(viz_state.reorder_dropdowns.row.value).toBe('custom');
    expect(viz_state.reorder_dropdowns.col.value).toBe('clust');
  });

  test('keeps a gene-driven column order while that gene is shown', () => {
    const viz_state = make_state(
      { row: 'rankvar', col: 'custom' },
      { axis: 'row', name: 'EPCAM', index: 5 }
    );
    carry_order_across_view(viz_state, new Set([5, 6]));
    expect(viz_state.order.current).toEqual({ row: 'rankvar', col: 'custom' });
    expect(viz_state.reorder_dropdowns.row.value).toBe('rankvar');
  });

  test('falls back to CLUST when the driving gene leaves the view', () => {
    const viz_state = make_state(
      { row: 'clust', col: 'custom' },
      { axis: 'row', name: 'EPCAM', index: 5 }
    );
    carry_order_across_view(viz_state, new Set([0, 1]));
    expect(viz_state.order.current.col).toBe('clust');
    expect(viz_state.labels.reorder_driver).toBeNull();
    expect(viz_state.reorder_dropdowns.col.value).toBe('clust');
  });
});
