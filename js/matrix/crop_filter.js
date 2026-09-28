const axis_count = (viz_state, axis) =>
  axis === 'row' ? viz_state.mat.num_rows : viz_state.mat.num_cols;

const axis_span = (viz_state, axis) =>
  axis === 'row' ? viz_state.viz.mat_height : viz_state.viz.mat_width;

const MAX_FILTER_FONT_SIZE = 24;
// TextLayer uses `sizeScale: 2`, so a 10-unit cap renders at roughly 20 px.
// Stop label growth at that readable density; subsequent scroll zoom reveals
// more rows/columns instead of enlarging the labels until they are clipped.
const MAX_ZOOM_FONT_SIZE = 10;
const FILTER_FONT_SLOT_FACTOR = 0.45;
const CROP_FADE_ALPHA = 0;

const axis_filter_array = (viz_state, axis) => {
  const filter = viz_state.crop?.filter?.[axis];
  return Array.isArray(filter) && filter.length > 0 ? filter : null;
};

export const has_axis_filter = (viz_state, axis) =>
  Boolean(axis_filter_array(viz_state, axis));

const axis_order_info = (viz_state, axis) => {
  const order_name = viz_state.order.current[axis];
  const order = viz_state.mat.orders[axis][order_name] || [];
  return { order_name, order };
};

const axis_filter_key = (viz_state, axis) => {
  const filter = axis_filter_array(viz_state, axis);
  return filter ? filter.join(',') : 'all';
};

const axis_order_key = (viz_state, axis) => {
  const { order_name, order } = axis_order_info(viz_state, axis);
  return `${order_name}:${order.join(',')}`;
};

const axis_visual_rank = (viz_state, axis, index) => {
  const count = axis_count(viz_state, axis);
  const { order } = axis_order_info(viz_state, axis);
  return count - (order[index] ?? 0);
};

const uncropped_axis_slot_size = (viz_state, axis) =>
  axis === 'row' ? viz_state.viz.row_offset : viz_state.viz.col_offset;

const uncropped_axis_center_position = (viz_state, axis, raw_index) => {
  const rank = axis_visual_rank(viz_state, axis, raw_index);
  const slot_size = uncropped_axis_slot_size(viz_state, axis);
  return axis === 'row' ? slot_size * (rank + 1.5) : slot_size * (rank + 0.5);
};

export const crop_filter_signature = (viz_state) => {
  const inputs = ['row', 'col'].map((axis) => {
    const { order_name, order } = axis_order_info(viz_state, axis);
    return {
      axis,
      order_name,
      order,
      filter: axis_filter_array(viz_state, axis),
    };
  });
  const cache_owner = viz_state.crop || viz_state.mat;
  const cached = cache_owner?._crop_signature_cache;

  if (
    cached &&
    inputs.every(
      ({ axis, order_name, order, filter }) =>
        cached[axis].order_name === order_name &&
        cached[axis].order_ref === order &&
        cached[axis].filter_ref === filter
    )
  ) {
    return cached.signature;
  }

  const signature = inputs
    .map(
      ({ axis }) =>
        `${axis}:${axis_order_key(viz_state, axis)}:${axis_filter_key(
          viz_state,
          axis
        )}`
    )
    .join('|');

  if (cache_owner) {
    cache_owner._crop_signature_cache = {
      signature,
      row: {
        order_name: inputs[0].order_name,
        order_ref: inputs[0].order,
        filter_ref: inputs[0].filter,
      },
      col: {
        order_name: inputs[1].order_name,
        order_ref: inputs[1].order,
        filter_ref: inputs[1].filter,
      },
    };
  }

  return signature;
};

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
  const { order_name, order } = axis_order_info(viz_state, axis);
  const span = axis_span(viz_state, axis);
  const cached = viz_state.crop._display_cache[axis];

  if (
    cached &&
    cached.count === count &&
    cached.span === span &&
    cached.order_name === order_name &&
    cached.order_ref === order &&
    cached.filter_ref === filter
  ) {
    return cached.state;
  }

  const visible_indices = (
    filter ? filter.slice() : Array.from({ length: count }, (_, index) => index)
  ).sort(
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

  viz_state.crop._display_cache[axis] = {
    count,
    span,
    order_name,
    order_ref: order,
    filter_ref: filter,
    state,
  };
  return state;
};

export const get_axis_display_count = (viz_state, axis) =>
  has_axis_filter(viz_state, axis)
    ? get_axis_display_state(viz_state, axis).display_count
    : axis_count(viz_state, axis);

export const is_axis_index_visible = (viz_state, axis, index) =>
  !has_axis_filter(viz_state, axis) ||
  get_axis_display_state(viz_state, axis).visible_set.has(index);

export const is_matrix_cell_visible = (viz_state, cell) =>
  is_axis_index_visible(viz_state, 'row', cell.row) &&
  is_axis_index_visible(viz_state, 'col', cell.col);

const filter_membership_cache = new WeakMap();

const get_filter_axis_set = (filter, axis) => {
  const axis_filter = Array.isArray(filter?.[axis]) ? filter[axis] : null;
  if (!axis_filter) return null;

  if (filter === null || typeof filter !== 'object') {
    return new Set(axis_filter);
  }

  const cached = filter_membership_cache.get(filter);
  const ref_key = `${axis}_ref`;
  if (cached && cached[ref_key] === axis_filter) {
    return cached[axis];
  }

  const next = {
    ...(cached || {}),
    [axis]: new Set(axis_filter),
    [ref_key]: axis_filter,
  };
  filter_membership_cache.set(filter, next);
  return next[axis];
};

export const is_axis_index_in_filter = (filter, axis, index) => {
  const axis_set = get_filter_axis_set(filter, axis);
  return !axis_set || axis_set.has(index);
};

export const is_matrix_cell_in_filter = (filter, cell) =>
  is_axis_index_in_filter(filter, 'row', cell.row) &&
  is_axis_index_in_filter(filter, 'col', cell.col);

export const filter_matrix_data = (viz_state) => {
  const row_filter = axis_filter_array(viz_state, 'row');
  const col_filter = axis_filter_array(viz_state, 'col');
  const source = viz_state.mat.mat_data;

  if (!row_filter && !col_filter) return source;

  viz_state.crop = viz_state.crop || {};
  const cached = viz_state.crop._filtered_matrix_cache;
  if (
    cached &&
    cached.source_ref === source &&
    cached.row_filter_ref === row_filter &&
    cached.col_filter_ref === col_filter
  ) {
    return cached.data;
  }

  const row_set = row_filter ? new Set(row_filter) : null;
  const col_set = col_filter ? new Set(col_filter) : null;
  const data = source.filter(
    (cell) =>
      (!row_set || row_set.has(cell.row)) && (!col_set || col_set.has(cell.col))
  );

  viz_state.crop._filtered_matrix_cache = {
    source_ref: source,
    row_filter_ref: row_filter,
    col_filter_ref: col_filter,
    data,
  };

  return data;
};

export const filter_label_data = (viz_state, axis) => {
  const labels_key = axis === 'row' ? 'row_label_data' : 'col_label_data';
  const source = viz_state.labels[labels_key];
  const filter = axis_filter_array(viz_state, axis);
  if (!filter) return source;

  const filter_set = new Set(filter);
  return source.filter((label) => filter_set.has(label.index));
};

export const filter_cat_data = (viz_state, axis) => {
  const data_key = axis === 'row' ? 'row_cat_data' : 'col_cat_data';
  const source = viz_state.cats[data_key];
  const filter = axis_filter_array(viz_state, axis);
  if (!filter) return source;

  const filter_set = new Set(filter);
  return source.filter((entry) => filter_set.has(entry.original_index));
};

export const get_axis_display_index = (viz_state, axis, raw_index) => {
  const display_index = get_axis_display_state(
    viz_state,
    axis
  ).display_index_by_raw.get(raw_index);
  return display_index ?? null;
};

export const get_axis_slot_size = (viz_state, axis) =>
  has_axis_filter(viz_state, axis)
    ? get_axis_display_state(viz_state, axis).slot_size
    : uncropped_axis_slot_size(viz_state, axis);

export const get_axis_center_position = (viz_state, axis, raw_index) => {
  if (!has_axis_filter(viz_state, axis)) {
    return uncropped_axis_center_position(viz_state, axis, raw_index);
  }

  const display_index = get_axis_display_index(viz_state, axis, raw_index);
  if (display_index === null) return null;

  const slot_size = get_axis_slot_size(viz_state, axis);
  return axis === 'row'
    ? slot_size * (display_index + 1.5)
    : slot_size * (display_index + 0.5);
};

export const get_axis_edge_positions = (viz_state, axis, raw_index) => {
  if (!has_axis_filter(viz_state, axis)) {
    const rank = axis_visual_rank(viz_state, axis, raw_index);
    const slot_size = uncropped_axis_slot_size(viz_state, axis);
    const start = axis === 'row' ? slot_size * (rank + 1) : slot_size * rank;
    return [start, start + slot_size];
  }

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
  const min = Math.min(min_pos, max_pos);
  const max = Math.max(min_pos, max_pos);

  if (!has_axis_filter(viz_state, axis)) {
    return Array.from(
      { length: axis_count(viz_state, axis) },
      (_, index) => index
    )
      .filter((raw_index) => {
        const center = uncropped_axis_center_position(
          viz_state,
          axis,
          raw_index
        );
        return center >= min && center <= max;
      })
      .sort(
        (a, b) =>
          axis_visual_rank(viz_state, axis, a) -
          axis_visual_rank(viz_state, axis, b)
      );
  }

  const state = get_axis_display_state(viz_state, axis);
  return state.visible_indices.filter((raw_index, display_index) => {
    const center =
      axis === 'row'
        ? state.slot_size * (display_index + 1.5)
        : state.slot_size * (display_index + 0.5);
    return center >= min && center <= max;
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
  const label_scale = viz_state.viz.label_scale?.[font_key] ?? 1;
  const original_size = viz_state.viz.font_size[font_key];
  const filtered_size = Math.max(
    viz_state.viz.base_font_size / get_axis_display_count(viz_state, axis),
    get_axis_slot_size(viz_state, axis) * FILTER_FONT_SLOT_FACTOR
  );

  return (
    label_scale *
    Math.max(original_size, Math.min(MAX_FILTER_FONT_SIZE, filtered_size))
  );
};

export const get_zoomed_axis_label_font_size = (
  viz_state,
  axis,
  zoom_value
) => {
  const base_size = get_axis_label_font_size(viz_state, axis);
  const font_key = axis === 'row' ? 'rows' : 'cols';
  const label_scale = viz_state.viz.label_scale?.[font_key] ?? 1;
  const max_size = Math.max(base_size, MAX_ZOOM_FONT_SIZE * label_scale);
  return Math.min(max_size, base_size * Math.pow(2, zoom_value));
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
    viz_state.crop._filtered_matrix_cache = null;
  }
  if (viz_state.mat) {
    viz_state.mat._comp_cache = null;
  }
};
