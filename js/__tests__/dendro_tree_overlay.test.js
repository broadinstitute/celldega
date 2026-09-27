/* global require */
const fs = require('fs');
const path = require('path');

const read = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const initialize_dendro_tree_overlay = new Function(
  'has_axis_crop_filter',
  `
  ${read('matrix/dendro_tree.js')}
  ${read('ui/dendro_tree_overlay.js')}
  return initialize_dendro_tree_overlay;
`
)((state, axis) => Boolean(state.crop.filter[axis]));

describe('temporary dendrogram tree overlay', () => {
  let state;
  let overlay;
  let controller;
  let context;
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
      mat: { orders: { row: { clust: [2, 1] }, col: { clust: [2, 1] } } },
      row_nodes: [{ group_links: 0 }, { group_links: 1 }],
      col_nodes: [{ group_links: 0 }, { group_links: 1 }],
      linkage: { row: [[0, 1, 1, 2]], col: [[0, 1, 1, 2]] },
      viz: {
        mat_width: 300,
        mat_height: 200,
        row_region: 75,
        col_region: 60,
        label_buffer: 5,
      },
      dendro: {
        max_linkage_dist: { row: 1.01, col: 1.01 },
        sliders: { row, col, row_percent: 50, col_percent: 50 },
      },
    };
    controller = initialize_dendro_tree_overlay(state);
    overlay = root.querySelector('.dendro-tree-overlay');
  });
  afterEach(() => {
    controller.destroy();
    state.el.remove();
    jest.restoreAllMocks();
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
    state.rank_view = { leaf_map: { row: [0, 2] } };
    state.linkage.row = [[0, 1, 0, 2]];
    state.mat.orders.row.clust = [2, 0, 1];
    state.row_nodes[0].group_links = 2;
    state.row_nodes[2].group_links = 2;
    controller.refresh();
    paint();
    expect(overlay.textContent).toContain('Row tree · 1 group');
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
