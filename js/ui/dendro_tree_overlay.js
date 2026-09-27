import { has_axis_crop_filter } from '../matrix/crop_filter';
import {
  build_dendro_tree,
  dendro_tree_point,
  get_dendro_tree_groups,
} from '../matrix/dendro_tree';

const RELEASE_DELAY_MS = 450;
const FADE_MS = 180;
const SLICE_KEYS = new Set([
  'ArrowLeft',
  'ArrowRight',
  'ArrowUp',
  'ArrowDown',
  'Home',
  'End',
  'PageUp',
  'PageDown',
]);

/** Temporary, full-tree overview. Canvas avoids thousands of SVG DOM nodes. */
export const initialize_dendro_tree_overlay = (viz_state) => {
  const overlay = document.createElement('div');
  overlay.className = 'dendro-tree-overlay';
  overlay.setAttribute('aria-hidden', 'true');
  Object.assign(overlay.style, {
    position: 'absolute',
    display: 'none',
    opacity: '0',
    pointerEvents: 'none',
    zIndex: '3',
    overflow: 'hidden',
    background: 'rgba(255, 255, 255, 0.82)',
    transition: `opacity ${FADE_MS}ms ease-out`,
  });
  const canvas = document.createElement('canvas');
  Object.assign(canvas.style, {
    display: 'block',
    width: '100%',
    height: '100%',
  });
  const caption = document.createElement('div');
  Object.assign(caption.style, {
    position: 'absolute',
    top: '8px',
    left: '10px',
    font: '12px system-ui, sans-serif',
    color: '#184e89',
    background: 'rgba(255, 255, 255, 0.9)',
    padding: '4px 7px',
    borderRadius: '4px',
  });
  overlay.append(canvas, caption);
  viz_state.root.appendChild(overlay);

  let active_axis = null;
  let pointer_slider = null;
  let frame = null;
  let hide_timer = null;
  let fade_timer = null;
  let destroyed = false;
  let cached = null;
  const cleanups = [];

  const listen = (target, event, callback, options) => {
    target.addEventListener(event, callback, options);
    cleanups.push(() => target.removeEventListener(event, callback, options));
  };
  const eligible = (axis) =>
    !destroyed &&
    !viz_state.finalized &&
    viz_state.order.current[axis] === 'clust' &&
    !has_axis_crop_filter(viz_state, axis) &&
    viz_state.linkage[axis]?.length > 0;

  const hide = (immediate = false) => {
    clearTimeout(hide_timer);
    clearTimeout(fade_timer);
    cancelAnimationFrame(frame);
    frame = null;
    active_axis = null;
    pointer_slider = null;
    overlay.style.opacity = '0';
    if (immediate) overlay.style.display = 'none';
    else
      fade_timer = setTimeout(() => {
        overlay.style.display = 'none';
      }, FADE_MS);
  };

  const paint = () => {
    frame = null;
    const axis = active_axis;
    if (!axis || !eligible(axis)) {
      hide(true);
      return;
    }
    const nodes = viz_state[`${axis}_nodes`];
    const linkage = viz_state.linkage[axis];
    const map_ref = viz_state.rank_view?.leaf_map?.[axis];
    const order = viz_state.mat.orders[axis].clust;
    if (
      cached?.axis !== axis ||
      cached.linkage !== linkage ||
      cached.map_ref !== map_ref ||
      cached.order !== order
    ) {
      const leaf_map = map_ref || nodes.map((_, i) => i);
      cached = {
        axis,
        linkage,
        map_ref,
        order,
        tree: build_dendro_tree(linkage, leaf_map, order),
      };
    }
    if (!cached.tree) {
      hide(true);
      return;
    }
    const { tree } = cached;
    const groups = get_dendro_tree_groups(tree, nodes);
    const width = viz_state.viz.mat_width;
    const height = viz_state.viz.mat_height;
    const max_distance = viz_state.dendro.max_linkage_dist[axis];
    const percent = Number(viz_state.dendro.sliders[`${axis}_percent`] ?? 50);
    const cut = (max_distance * percent) / 100;
    if (!(width > 0 && height > 0 && max_distance > 0)) {
      hide(true);
      return;
    }

    Object.assign(overlay.style, {
      left: `${viz_state.viz.row_region + viz_state.viz.label_buffer}px`,
      top: `${viz_state.viz.col_region + viz_state.viz.label_buffer}px`,
      width: `${width}px`,
      height: `${height}px`,
    });
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const pixel_width = Math.round(width * ratio);
    const pixel_height = Math.round(height * ratio);
    if (canvas.width !== pixel_width) canvas.width = pixel_width;
    if (canvas.height !== pixel_height) canvas.height = pixel_height;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      hide(true);
      return;
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    // Inset branches just enough that strokes at the zero/maximum cut remain visible.
    const point = (leaf, distance) => {
      const [x, y] = dendro_tree_point(
        axis,
        leaf,
        distance,
        max_distance,
        width - 8,
        height - 8
      );
      return [x + 4, y + 4];
    };
    const path = (points, close = false) => {
      ctx.moveTo(...points[0]);
      points.slice(1).forEach((p) => ctx.lineTo(...p));
      if (close) ctx.closePath();
    };

    ctx.beginPath();
    tree.nodes.slice(tree.leaf_count).forEach((node) => {
      const left = tree.nodes[node.left];
      const right = tree.nodes[node.right];
      path([
        point(left.center, left.distance),
        point(left.center, node.distance),
        point(right.center, node.distance),
        point(right.center, right.distance),
      ]);
    });
    ctx.strokeStyle = 'rgba(48, 65, 84, 0.8)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Rising water covers every branch below the cut, showing the region
    // whose leaves have merged without adding separate group polygons.
    ctx.beginPath();
    path([point(0, 0), point(1, 0), point(1, cut), point(0, cut)], true);
    ctx.fillStyle = 'rgba(37, 126, 220, 0.18)';
    ctx.fill();
    // White edging keeps the blue water line readable over dense branches.
    ctx.beginPath();
    path([point(0, cut), point(1, cut)]);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.lineWidth = 5;
    ctx.stroke();
    ctx.strokeStyle = '#1677df';
    ctx.lineWidth = 2.5;
    ctx.stroke();
    const group_label = `${groups.length} ${groups.length === 1 ? 'group' : 'groups'}`;
    const label = `${axis === 'row' ? 'Row' : 'Column'} tree · ${group_label} · cut ${Number(cut.toPrecision(3))}`;
    caption.textContent = label;
    viz_state.dendro.sliders[axis].setAttribute(
      'aria-valuetext',
      `${percent}% — ${group_label}`
    );
  };

  const show = (axis) => {
    if (!eligible(axis)) {
      hide(true);
      return;
    }
    clearTimeout(hide_timer);
    clearTimeout(fade_timer);
    active_axis = axis;
    overlay.style.display = 'block';
    overlay.style.opacity = '1';
    if (frame === null) frame = requestAnimationFrame(paint);
  };
  const release = () => {
    pointer_slider = null;
    clearTimeout(hide_timer);
    if (active_axis) hide_timer = setTimeout(() => hide(), RELEASE_DELAY_MS);
  };

  ['row', 'col'].forEach((axis) => {
    const slider = viz_state.dendro.sliders[axis];
    slider.setAttribute(
      'aria-label',
      `${axis === 'row' ? 'Row' : 'Column'} dendrogram cut`
    );
    listen(slider, 'pointerdown', () => {
      show(axis);
      pointer_slider = slider;
    });
    listen(slider, 'focus', () => show(axis));
    // Registered after the normal slice handler, so the count uses its new groups.
    listen(slider, 'input', () => {
      show(axis);
      if (!pointer_slider) release();
    });
    listen(slider, 'change', release);
    listen(slider, 'blur', () => hide());
    listen(slider, 'keydown', (event) => {
      if (event.key === 'Escape') hide(true);
      else if (SLICE_KEYS.has(event.key)) show(axis);
    });
    listen(slider, 'keyup', (event) => {
      if (SLICE_KEYS.has(event.key)) release();
    });
  });
  listen(window, 'pointerup', () => {
    if (pointer_slider) release();
  });
  listen(window, 'pointercancel', () => {
    if (pointer_slider) hide(true);
  });
  listen(window, 'blur', () => hide(true));
  listen(
    viz_state.el,
    'pointerdown',
    (event) => {
      if (
        !['row', 'col'].some(
          (axis) => event.target === viz_state.dendro.sliders[axis]
        )
      )
        hide(true);
    },
    true
  );

  const controller = {
    show,
    hide,
    refresh: () => {
      if (active_axis) show(active_axis);
    },
    destroy: () => {
      if (destroyed) return;
      hide(true);
      destroyed = true;
      cached = null;
      cleanups.splice(0).forEach((cleanup) => cleanup());
      overlay.remove();
    },
  };
  viz_state.dendro.tree_overlay = controller;
  return controller;
};
