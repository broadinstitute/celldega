/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const get_composition_layout = jest.fn();
const rightmost_composition_col = jest.fn();
const initialize_dendro_tree_overlay = new Function(
  'get_composition_layout',
  'rightmost_composition_col',
  `
  ${read('matrix/crop_filter.js')}
  ${read('matrix/dendro_tree.js')}
  ${read('ui/dendro_tree_overlay.js')}
  return initialize_dendro_tree_overlay;
`
)(get_composition_layout, rightmost_composition_col);

// Match deck.gl's orthographic projection in local viewport pixels. The
// nonzero viewport offsets deliberately do not enter project()'s result.
const matrix_viewport = (zoom = [0, 0], target = [150, 200]) => ({
  id: 'matrix',
  x: 80,
  y: 65,
  width: 300,
  height: 200,
  project: jest.fn(([x, y]) => [
    150 + (x - target[0]) * 2 ** zoom[0],
    100 + (y - target[1]) * 2 ** zoom[1],
  ]),
});

describe('temporary dendrogram tree overlay', () => {
  let state;
  let overlay;
  let controller;
  let context;
  let viewport;
  let deck;
  const paint = () => jest.advanceTimersByTime(20);
  const event = (target, type, options = {}) =>
    target.dispatchEvent(new Event(type, { bubbles: true, ...options }));

  beforeEach(() => {
    jest.useFakeTimers();
    context = Object.fromEntries(
      [
        'setTransform',
        'clearRect',
        'beginPath',
        'moveTo',
        'lineTo',
        'closePath',
        'fill',
        'stroke',
      ].map((key) => [key, jest.fn()])
    );
    jest
      .spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockReturnValue(context);
    const el = document.createElement('div');
    const root = document.createElement('div');
    const row = document.createElement('input');
    const col = document.createElement('input');
    el.append(row, col, root);
    document.body.append(el);
    state = {
      el,
      root,
      order: { current: { row: 'clust', col: 'clust' } },
      crop: { filter: { row: null, col: null } },
      mat: {
        num_rows: 2,
        num_cols: 2,
        viz_mode: 'heatmap',
        orders: { row: { clust: [2, 1] }, col: { clust: [2, 1] } },
      },
      row_nodes: [{ group_links: 0 }, { group_links: 1 }],
      col_nodes: [{ group_links: 0 }, { group_links: 1 }],
      linkage: { row: [[0, 1, 1, 2]], col: [[0, 1, 1, 2]] },
      viz: {
        mat_width: 300,
        mat_height: 200,
        row_offset: 100,
        col_offset: 150,
        row_region: 75,
        col_region: 60,
        label_buffer: 5,
      },
      dendro: {
        max_linkage_dist: { row: 1.01, col: 1.01 },
        sliders: { row, col, row_percent: 50, col_percent: 50 },
      },
    };
    viewport = matrix_viewport();
    deck = {
      getViewports: jest.fn(() => [{ id: 'rows' }, viewport]),
    };
    controller = initialize_dendro_tree_overlay(state, deck);
    overlay = root.querySelector('.dendro-tree-overlay');
  });
  afterEach(() => {
    controller.destroy();
    state.el.remove();
    jest.restoreAllMocks();
    get_composition_layout.mockReset();
    rightmost_composition_col.mockReset();
    jest.useRealTimers();
  });

  test('dragging shows a translucent backdrop, rising water, and the live merged group', () => {
    expect(overlay.style.display).toBe('none');
    expect(overlay.style.background).toContain('0.82');
    expect(overlay.style.pointerEvents).toBe('none');
    event(state.dendro.sliders.col, 'pointerdown');
    paint();
    expect(overlay.style.opacity).toBe('1');
    expect(overlay.textContent).toContain('Column tree · 2 groups');
    // The only filled canvas shape is the water rectangle.
    expect(context.fill).toHaveBeenCalledTimes(1);
    expect(overlay.style.left).toBe('80px');
    expect(overlay.style.top).toBe('65px');
    // Follow the real slider's state and grouping; the preview never reslices independently.
    state.dendro.sliders.col_percent = 100;
    state.col_nodes.forEach((node) => {
      node.group_links = 2;
    });
    event(state.dendro.sliders.col, 'input');
    paint();
    expect(overlay.textContent).toContain('Column tree · 1 group');
    expect(state.dendro.sliders.col.getAttribute('aria-valuetext')).toBe(
      '100% — 1 group'
    );
    expect(context.lineTo).toHaveBeenCalledWith(296, 4);
    jest.advanceTimersByTime(2000);
    expect(overlay.style.opacity).toBe('1'); // Still dragging.
    event(window, 'pointerup');
    jest.advanceTimersByTime(700);
    expect(overlay.style.display).toBe('none');
  });

  test('keyboard slicing previews the row tree and Escape dismisses it', () => {
    state.dendro.sliders.row.focus();
    paint();
    expect(overlay.textContent).toContain('Row tree');
    state.dendro.sliders.row.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowRight' })
    );
    event(state.dendro.sliders.row, 'input');
    paint();
    state.dendro.sliders.row.dispatchEvent(
      new KeyboardEvent('keyup', { key: 'ArrowRight' })
    );
    jest.advanceTimersByTime(700);
    expect(overlay.style.display).toBe('none');
    controller.show('row');
    paint();
    state.dendro.sliders.row.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape' })
    );
    expect(overlay.style.display).toBe('none');
  });

  test('the other slider can reopen the overlay during a pending fade', () => {
    controller.show('row');
    paint();
    controller.hide();
    controller.show('col');
    jest.advanceTimersByTime(250);
    expect(overlay.style.display).toBe('block');
    expect(overlay.textContent).toContain('Column tree');
  });

  test('cropped or non-clustered axes do not show a misleading tree', () => {
    state.crop.filter.row = [0];
    controller.show('row');
    paint();
    expect(overlay.style.display).toBe('none');
    state.order.current.col = 'rank';
    controller.show('col');
    paint();
    expect(overlay.style.display).toBe('none');
  });

  test('RANK linkage replacement rebuilds the full overview', () => {
    controller.show('row');
    paint();
    state.row_nodes.push({ group_links: 1 });
    state.mat.num_rows = 3;
    state.viz.row_offset = 200 / 3;
    state.rank_view = {
      leaf_map: { row: [0, 2] },
      filter: { row: [0, 2], col: null },
    };
    state.linkage.row = [[0, 1, 0, 2]];
    state.mat.orders.row.clust = [2, 0, 1];
    state.row_nodes[0].group_links = 2;
    state.row_nodes[2].group_links = 2;
    controller.refresh();
    paint();
    expect(overlay.textContent).toContain('Row tree · 1 group');
  });

  test.each([
    ['row', [0, 1], [150, 175], [296, 50], [296, 250]],
    ['col', [2, 0], [187.5, 200], [-300, 196], [300, 196]],
  ])(
    '%s branches track zoom and pan without moving the water rectangle',
    (axis, zoom, target, left_leaf, right_leaf) => {
      controller.show(axis);
      paint();
      context.moveTo.mockClear();
      context.lineTo.mockClear();
      viewport = matrix_viewport(zoom, target);
      controller.sync_viewport();
      paint();
      expect(context.moveTo.mock.calls[0]).toEqual(left_leaf);
      expect(context.lineTo.mock.calls[2]).toEqual(right_leaf);
      // Water remains fitted to the viewport, even when branches extend
      // beyond it; the overlay's overflow clips the zoomed tree.
      expect(context.moveTo.mock.calls[1]).toEqual(
        axis === 'row' ? [296, 4] : [4, 196]
      );
      expect(context.lineTo.mock.calls[3]).toEqual([296, 196]);
      expect(overlay.style.overflow).toBe('hidden');
    }
  );

  test.each([
    ['row', [3, 0], [205, 200]],
    ['col', [0, 3], [150, 170]],
  ])('%s tree ignores zoom and pan on the other axis', (axis, zoom, target) => {
    controller.show(axis);
    paint();
    const original_moves = context.moveTo.mock.calls.slice();
    const original_lines = context.lineTo.mock.calls.slice();
    context.moveTo.mockClear();
    context.lineTo.mockClear();
    viewport = matrix_viewport(zoom, target);
    controller.sync_viewport();
    paint();
    expect(context.moveTo.mock.calls).toEqual(original_moves);
    expect(context.lineTo.mock.calls).toEqual(original_lines);
  });

  test('reduced RANK leaves use their displayed slots and full-matrix identities', () => {
    state.mat.num_rows = 4;
    state.viz.row_offset = 50;
    state.row_nodes = Array.from({ length: 4 }, (_, i) => ({ group_links: i }));
    state.mat.orders.row.clust = [0, 1, 0, 2];
    state.rank_view = {
      leaf_map: { row: [1, 3] },
      filter: { row: [1, 3], col: null },
    };
    viewport = matrix_viewport([0, 1], [150, 175]);
    controller.show('row');
    paint();
    // Linkage leaf 0 is raw row 1, which is the lower displayed row. The
    // filtered row slot is 100 (not the full matrix's original 50).
    expect(context.moveTo.mock.calls[0]).toEqual([296, 250]);
    expect(context.lineTo.mock.calls[2]).toEqual([296, 50]);
  });

  test('composition leaves and internal branches follow nonuniform rightmost-bar segments', () => {
    state.mat.viz_mode = 'composition';
    state.mat.num_rows = 3;
    state.viz.row_offset = 200 / 3;
    state.mat.orders.row.clust = [3, 2, 1];
    state.row_nodes.push({ group_links: 2 });
    state.linkage.row = [
      [0, 1, 0.5, 2],
      [3, 2, 1, 3],
    ];
    rightmost_composition_col.mockReturnValue(1);
    get_composition_layout.mockReturnValue({
      '0_1': { position: [225, 270] },
      '1_1': { position: [225, 150] },
      '2_1': { position: [225, 120] },
    });
    viewport = matrix_viewport([0, 1], [150, 200]);
    controller.show('row');
    paint();
    expect(rightmost_composition_col).toHaveBeenCalledWith(state);
    expect(context.moveTo.mock.calls[0]).toEqual([296, 240]);
    expect(context.lineTo.mock.calls[2]).toEqual([296, 0]);
    // Root starts at the mean of its child branch's actual centers.
    expect(context.moveTo.mock.calls[1][1]).toBe(120);
    expect(context.lineTo.mock.calls[5]).toEqual([296, -60]);
  });

  test('viewport synchronization does not repaint inactive or unchanged trees', () => {
    controller.sync_viewport();
    paint();
    expect(context.clearRect).not.toHaveBeenCalled();
    controller.show('row');
    paint();
    context.clearRect.mockClear();
    controller.sync_viewport();
    paint();
    expect(context.clearRect).not.toHaveBeenCalled();
    viewport = matrix_viewport([0, 1]);
    controller.sync_viewport();
    paint();
    expect(context.clearRect).toHaveBeenCalledTimes(1);
    controller.hide(true);
    context.clearRect.mockClear();
    viewport = matrix_viewport([0, 2]);
    controller.sync_viewport();
    paint();
    expect(context.clearRect).not.toHaveBeenCalled();
  });

  test('rendered transition frames override destination bookkeeping without delaying release', () => {
    state.zoom = {
      zoom_data: { matrix: { zoom_y: 4, pan_y: 250 } },
      _programmatic_view_transition: true,
    };
    event(state.dendro.sliders.row, 'pointerdown');
    paint();
    // Bookkeeping points at a future destination; initial pixels still use
    // the viewport that deck.gl actually rendered.
    expect(context.moveTo.mock.calls[0]).toEqual([296, 50]);
    event(window, 'pointerup');
    for (let i = 1; i <= 4; i++) {
      viewport = matrix_viewport([0, i / 4], [150, 200]);
      controller.sync_viewport();
      jest.advanceTimersByTime(100);
    }
    expect(overlay.style.opacity).toBe('1');
    jest.advanceTimersByTime(60);
    expect(overlay.style.opacity).toBe('0');
    viewport = matrix_viewport([0, 2], [150, 200]);
    controller.sync_viewport();
    jest.advanceTimersByTime(200);
    expect(overlay.style.display).toBe('none');
  });

  test('pointer cancellation and outside clicks dismiss the preview', () => {
    event(state.dendro.sliders.row, 'pointerdown');
    paint();
    event(window, 'pointercancel');
    expect(overlay.style.display).toBe('none');
    controller.show('col');
    paint();
    event(state.root, 'pointerdown');
    expect(overlay.style.display).toBe('none');
  });

  test('destroy removes pending frames, timers, and global/slider listeners', () => {
    event(state.dendro.sliders.row, 'pointerdown');
    event(window, 'pointerup');
    controller.destroy();
    controller.destroy();
    context.stroke.mockClear();
    event(state.dendro.sliders.row, 'input');
    event(window, 'pointerup');
    jest.runAllTimers();
    expect(context.stroke).not.toHaveBeenCalled();
    expect(state.root.querySelector('.dendro-tree-overlay')).toBeNull();
    expect(jest.getTimerCount()).toBe(0);
  });
});
