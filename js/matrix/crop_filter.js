const axis_count = (viz_state, axis) =>
  axis === 'row' ? viz_state.mat.num_rows : viz_state.mat.num_cols;

const axis_span = (viz_state, axis) =>
  axis === 'row' ? viz_state.viz.mat_height : viz_state.viz.mat_width;

const MAX_FILTER_FONT_SIZE = 18;
const CROP_FADE_ALPHA = 0;

const axis_filter_array = (viz_state, axis) => {
  const filter = viz_state.crop?.filter?.[axis];
  return Array.isArray(filter) && filter.length > 0 ? filter : null;
};

const axis_filter_key = (viz_state, axis) => {
  const filter = axis_filter_array(viz_state, axis);
  return filter ? filter.join(',') : 'all';
};

const axis_order_key = (viz_state, axis) => {
  const order_name = viz_state.order.current[axis];
  const order = viz_state.mat.orders[axis][order_name] || [];
  return `${order_name}:${order.join(',')}`;
};

const axis_visual_rank = (viz_state, axis, index) => {
  const count = axis_count(viz_state, axis);
  const order_name = viz_state.order.current[axis];
  const order = viz_state.mat.orders[axis][order_name] || [];
  return count - (order[index] ?? 0);
};

export const crop_filter_signature = (viz_state) =>
  ['row', 'col']
    .map(
      (axis) =>
        `${axis}:${axis_order_key(viz_state, axis)}:${axis_filter_key(
          viz_state,
          axis
        )}`
    )
    .join('|');

export const has_crop_filter = (viz_state) =>
  Boolean(
    axis_filter_array(viz_state, 'row') || axis_filter_array(viz_state, 'col')
  );

export const clone_crop_filter = (filter) => ({
  row: Array.isArray(filter?.row) ? filter.row.slice() : null,
  col: Array.isArray(filter?.col) ? filter.col.slice() : null,
});

export const normalize_crop_filter = (viz_state, filter) => {
  const normalize_axis = (axis) => {
    const count = axis_count(viz_state, axis);
    const values = Array.isArray(filter?.[axis]) ? filter[axis] : [];
    const unique = Array.from(
      new Set(
        values
          .map((value) => Number(value))
          .filter(
            (value) => Number.isInteger(value) && value >= 0 && value < count
          )
      )
    ).sort(
      (a, b) =>
        axis_visual_rank(viz_state, axis, a) -
        axis_visual_rank(viz_state, axis, b)
    );

    return unique.length > 0 && unique.length < count ? unique : null;
  };

  return {
    row: normalize_axis('row'),
    col: normalize_axis('col'),
  };
};

export const get_axis_display_state = (viz_state, axis) => {
  viz_state.crop = viz_state.crop || {};
  viz_state.crop._display_cache = viz_state.crop._display_cache || {};

  const count = axis_count(viz_state, axis);
  const filter = axis_filter_array(viz_state, axis);
  const filter_set = filter ? new Set(filter) : null;
  const key = `${axis}|${axis_order_key(viz_state, axis)}|${axis_filter_key(viz_state, axis)}`;

  const cached = viz_state.crop._display_cache[key];
  if (cached) return cached;

  const visible_indices = Array.from({ length: count }, (_, index) => index)
    .filter((index) => !filter_set || filter_set.has(index))
    .sort(
      (a, b) =>
        axis_visual_rank(viz_state, axis, a) -
        axis_visual_rank(viz_state, axis, b)
    );

  const display_index_by_raw = new Map();
  visible_indices.forEach((raw_index, display_index) => {
    display_index_by_raw.set(raw_index, display_index);
  });

  const display_count = Math.max(visible_indices.length, 1);
  const slot_size = axis_span(viz_state, axis) / display_count;

  const state = {
    visible_indices,
    visible_set: new Set(visible_indices),
    display_index_by_raw,
    display_count,
    slot_size,
  };

  viz_state.crop._display_cache[key] = state;
  return state;
};

export const get_axis_display_count = (viz_state, axis) =>
  get_axis_display_state(viz_state, axis).display_count;

export const is_axis_index_visible = (viz_state, axis, index) =>
  get_axis_display_state(viz_state, axis).visible_set.has(index);

export const is_matrix_cell_visible = (viz_state, cell) =>
  is_axis_index_visible(viz_state, 'row', cell.row) &&
  is_axis_index_visible(viz_state, 'col', cell.col);

export const is_axis_index_in_filter = (filter, axis, index) => {
  const axis_filter = Array.isArray(filter?.[axis]) ? filter[axis] : null;
  return !axis_filter || axis_filter.includes(index);
};

export const is_matrix_cell_in_filter = (filter, cell) =>
  is_axis_index_in_filter(filter, 'row', cell.row) &&
  is_axis_index_in_filter(filter, 'col', cell.col);

export const filter_matrix_data = (viz_state) =>
  viz_state.mat.mat_data.filter((cell) =>
    is_matrix_cell_visible(viz_state, cell)
  );

export const filter_label_data = (viz_state, axis) => {
  const labels_key = axis === 'row' ? 'row_label_data' : 'col_label_data';
  return viz_state.labels[labels_key].filter((label) =>
    is_axis_index_visible(viz_state, axis, label.index)
  );
};

export const filter_cat_data = (viz_state, axis) => {
  const data_key = axis === 'row' ? 'row_cat_data' : 'col_cat_data';
  return viz_state.cats[data_key].filter((entry) =>
    is_axis_index_visible(viz_state, axis, entry.original_index)
  );
};

export const get_axis_display_index = (viz_state, axis, raw_index) => {
  const display_index = get_axis_display_state(
    viz_state,
    axis
  ).display_index_by_raw.get(raw_index);
  return display_index ?? null;
};

export const get_axis_slot_size = (viz_state, axis) =>
  get_axis_display_state(viz_state, axis).slot_size;

export const get_axis_center_position = (viz_state, axis, raw_index) => {
  const display_index = get_axis_display_index(viz_state, axis, raw_index);
  if (display_index === null) return null;

  const slot_size = get_axis_slot_size(viz_state, axis);
  return axis === 'row'
    ? slot_size * (display_index + 1.5)
    : slot_size * (display_index + 0.5);
};

export const get_axis_edge_positions = (viz_state, axis, raw_index) => {
  const display_index = get_axis_display_index(viz_state, axis, raw_index);
  if (display_index === null) return null;

  const slot_size = get_axis_slot_size(viz_state, axis);
  const start =
    axis === 'row'
      ? slot_size * (display_index + 1)
      : slot_size * display_index;

  return [start, start + slot_size];
};

export const get_axis_indices_in_range = (
  viz_state,
  axis,
  min_pos,
  max_pos
) => {
  const state = get_axis_display_state(viz_state, axis);
  const min = Math.min(min_pos, max_pos);
  const max = Math.max(min_pos, max_pos);

  return state.visible_indices.filter((raw_index) => {
    const center = get_axis_center_position(viz_state, axis, raw_index);
    return center !== null && center >= min && center <= max;
  });
};

export const get_default_pan_x = (viz_state) => viz_state.viz.mat_width / 2;

export const get_default_pan_y = (viz_state) =>
  viz_state.viz.mat_height / 2 + get_axis_slot_size(viz_state, 'row');

export const get_default_pan = (viz_state) => [
  get_default_pan_x(viz_state),
  get_default_pan_y(viz_state),
];

export const get_axis_label_font_size = (viz_state, axis) => {
  const font_key = axis === 'row' ? 'rows' : 'cols';
  const original_size = viz_state.viz.font_size[font_key];
  const filtered_size =
    viz_state.viz.base_font_size / get_axis_display_count(viz_state, axis);

  return Math.max(original_size, Math.min(MAX_FILTER_FONT_SIZE, filtered_size));
};

export const get_crop_fade_filter = (viz_state) =>
  viz_state.crop?.fade_filter || null;

export const crop_fade_signature = (viz_state) =>
  viz_state.crop?._fade_rev || 0;

export const crop_fade_alpha_factor = (viz_state, row, col) => {
  const fade_filter = get_crop_fade_filter(viz_state);
  if (!fade_filter) return 1;

  return is_matrix_cell_in_filter(fade_filter, { row, col })
    ? 1
    : CROP_FADE_ALPHA;
};

export const crop_fade_axis_alpha_factor = (viz_state, axis, index) => {
  const fade_filter = get_crop_fade_filter(viz_state);
  if (!fade_filter) return 1;

  return is_axis_index_in_filter(fade_filter, axis, index)
    ? 1
    : CROP_FADE_ALPHA;
};

export const clear_crop_display_cache = (viz_state) => {
  if (viz_state.crop) {
    viz_state.crop._display_cache = {};
  }
  if (viz_state.mat) {
    viz_state.mat._comp_cache = null;
  }
};
