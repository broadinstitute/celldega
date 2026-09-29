import {
  empty_dendro_tree_data,
  remove_dendro_tree_layers,
  update_dendro_tree_layers,
} from '../deck-gl/matrix/dendro_tree_layers';
import { get_mat_layers_list } from '../deck-gl/matrix/matrix_layers';
import {
  with_dendro_tree_views,
  without_dendro_tree_views,
} from '../deck-gl/matrix/views';
import {
  get_composition_layout,
  rightmost_composition_col,
} from '../matrix/composition_data';
import {
  get_axis_center_position,
  has_axis_crop_filter,
} from '../matrix/crop_filter';
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

/** Temporary full-tree preview rendered entirely by the existing deck_mat. */
export const initialize_dendro_tree_overlay = (
  viz_state,
  deck_mat,
  layers_mat
) => {
  let active_axis = null;
  let pointer_slider = null;
  let hide_timer = null;
  let fade_timer = null;
  let destroyed = false;
  let fading = false;
  let views_mounted = false;
  let revision = 0;
  let cached = null;
  let current_data = empty_dendro_tree_data();
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
  const commit = () =>
    deck_mat.setProps({
      views: viz_state.views.views_list,
      layers: get_mat_layers_list(layers_mat),
    });
  const mount_views = () => {
    if (views_mounted) return;
    views_mounted = true;
    viz_state.views.views_list = with_dendro_tree_views(
      viz_state.views.views_list,
      viz_state
    );
  };
  const unmount_views = () => {
    if (!views_mounted) return;
    views_mounted = false;
    viz_state.views.views_list = without_dendro_tree_views(
      viz_state.views.views_list
    );
  };

  const hide = (immediate = false) => {
    clearTimeout(hide_timer);
    clearTimeout(fade_timer);
    active_axis = null;
    pointer_slider = null;
    if (!views_mounted) return;

    revision += 1;
    if (immediate) {
      fading = false;
      current_data = empty_dendro_tree_data();
      update_dendro_tree_layers(layers_mat, current_data, {
        opacity: 0,
        revision,
      });
      unmount_views();
      commit();
      return;
    }

    fading = true;
    update_dendro_tree_layers(layers_mat, current_data, {
      opacity: 0,
      revision,
      duration: FADE_MS,
    });
    commit();
    fade_timer = setTimeout(() => {
      fading = false;
      current_data = empty_dendro_tree_data();
      revision += 1;
      update_dendro_tree_layers(layers_mat, current_data, {
        opacity: 0,
        revision,
      });
      unmount_views();
      commit();
    }, FADE_MS);
  };

  const render = (duration = 0) => {
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
      cached = {
        axis,
        linkage,
        map_ref,
        order,
        tree: build_dendro_tree(
          linkage,
          map_ref || nodes.map((_, i) => i),
          order
        ),
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

    const composition_rows =
      axis === 'row' && viz_state.mat.viz_mode === 'composition';
    const composition_layout = composition_rows
      ? get_composition_layout(viz_state)
      : null;
    const rightmost_col = composition_rows
      ? rightmost_composition_col(viz_state)
      : null;
    const positions = new Array(tree.nodes.length);
    tree.nodes.forEach((node) => {
      if (node.id < tree.leaf_count) {
        positions[node.id] = composition_rows
          ? composition_layout[`${node.raw_index}_${rightmost_col}`].position[1]
          : get_axis_center_position(viz_state, axis, node.raw_index);
      } else {
        positions[node.id] = (positions[node.left] + positions[node.right]) / 2;
      }
    });
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
    const dimension = axis === 'row' ? 1 : 0;
    const branch_point = (node, distance) => {
      const position = point(0, distance);
      position[dimension] = positions[node.id];
      return position;
    };
    const branches = tree.nodes.slice(tree.leaf_count).map((node) => {
      const left = tree.nodes[node.left];
      const right = tree.nodes[node.right];
      return {
        path: [
          branch_point(left, left.distance),
          branch_point(left, node.distance),
          branch_point(right, node.distance),
          branch_point(right, right.distance),
        ],
        color: [48, 65, 84, 204],
        width: 1,
      };
    });
    const cut_start = point(0, cut);
    const cut_end = point(1, cut);
    const group_label = `${groups.length} ${groups.length === 1 ? 'group' : 'groups'}`;

    current_data = {
      background: [
        {
          polygon: [
            [0, 0],
            [width, 0],
            [width, height],
            [0, height],
          ],
          color: [255, 255, 255, 209],
        },
      ],
      row_branches: axis === 'row' ? branches : [],
      col_branches: axis === 'col' ? branches : [],
      water: [
        {
          polygon: [point(0, 0), point(1, 0), cut_end, cut_start],
          color: [37, 126, 220, 46],
        },
      ],
      cut_outline: [
        {
          path: [cut_start, cut_end],
          color: [255, 255, 255, 242],
          width: 5,
        },
      ],
      cut: [
        {
          path: [cut_start, cut_end],
          color: [22, 119, 223, 255],
          width: 2.5,
        },
      ],
      caption: [
        {
          position: [17, 12],
          text: `${axis === 'row' ? 'Row' : 'Column'} tree · ${group_label} · cut ${Number(cut.toPrecision(3))}`,
          color: [24, 78, 137, 255],
          background_color: [255, 255, 255, 230],
        },
      ],
    };
    revision += 1;
    update_dendro_tree_layers(layers_mat, current_data, {
      opacity: 1,
      revision,
      duration,
    });
    viz_state.dendro.sliders[axis].setAttribute(
      'aria-valuetext',
      `${percent}% — ${group_label}`
    );
    commit();
  };

  const show = (axis) => {
    if (!eligible(axis)) {
      hide(true);
      return;
    }
    clearTimeout(hide_timer);
    clearTimeout(fade_timer);
    const resume_fade = fading;
    fading = false;
    active_axis = axis;
    mount_views();
    render(resume_fade ? FADE_MS : 0);
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
      if (active_axis) render();
    },
    has_views: () => views_mounted,
    destroy: () => {
      if (destroyed) return;
      hide(true);
      destroyed = true;
      cached = null;
      cleanups.splice(0).forEach((cleanup) => cleanup());
      remove_dendro_tree_layers(layers_mat);
      commit();
    },
  };
  viz_state.dendro.tree_overlay = controller;
  return controller;
};
