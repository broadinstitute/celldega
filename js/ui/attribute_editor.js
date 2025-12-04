const DEFAULT_COLORS = {
  row: '#2f74ff',
  col: '#ff7f0e',
};

const hsl_to_hex = (h, s, l) => {
  const a = s * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h * 12) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color)
      .toString(16)
      .padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
};

const get_used_colors = (viz_state) => {
  const mapping = viz_state.attr?.category_colors || {};
  return new Set(
    Object.values(mapping)
      .filter((color) => Boolean(color))
      .map((color) => color.toLowerCase())
  );
};

const allocate_color = (viz_state) => {
  viz_state.manual_cat = viz_state.manual_cat || {};
  if (typeof viz_state.manual_cat.color_cursor !== 'number') {
    viz_state.manual_cat.color_cursor = 0;
  }

  const used = get_used_colors(viz_state);

  for (let attempt = 0; attempt < 720; attempt += 1) {
    const idx = viz_state.manual_cat.color_cursor + attempt;
    const hue = ((idx * 137.508) % 360) / 360;
    const candidate = hsl_to_hex(hue, 0.65, 0.55);
    if (!used.has(candidate.toLowerCase())) {
      viz_state.manual_cat.color_cursor = idx + 1;
      return candidate;
    }
  }

  viz_state.manual_cat.color_cursor += 1;
  return '#3b82f6';
};

const create_labeled_input = (label_text, input) => {
  const wrapper = document.createElement('label');
  wrapper.style.display = 'block';
  wrapper.style.fontSize = '12px';
  wrapper.style.fontWeight = '600';
  wrapper.style.marginBottom = '8px';
  wrapper.style.color = '#47515b';
  wrapper.textContent = label_text;

  input.style.display = 'block';
  input.style.width = '100%';
  input.style.marginTop = '4px';
  input.style.padding = '6px';
  input.style.border = '1px solid #d3d3d3';
  input.style.borderRadius = '4px';
  input.style.fontSize = '12px';

  wrapper.appendChild(input);
  return wrapper;
};

const clamp_position = (value, min, max) => Math.min(Math.max(value, min), max);

export const initialize_attribute_editor = (
  viz_state,
  _deck_mat,
  _layers_mat
) => {
  const container = document.createElement('div');
  container.style.position = 'absolute';
  container.style.width = '240px';
  container.style.background = '#ffffff';
  container.style.border = '1px solid #d3d3d3';
  container.style.borderRadius = '8px';
  container.style.padding = '12px';
  container.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
  container.style.zIndex = '20';
  container.style.display = 'none';

  const header = document.createElement('div');
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.marginBottom = '8px';

  const title = document.createElement('span');
  title.style.fontSize = '13px';
  title.style.fontWeight = '700';
  title.style.color = '#333333';
  title.textContent = 'Manual category';

  const close_button = document.createElement('button');
  close_button.type = 'button';
  close_button.textContent = '×';
  close_button.style.border = 'none';
  close_button.style.background = 'transparent';
  close_button.style.cursor = 'pointer';
  close_button.style.fontSize = '16px';
  close_button.style.lineHeight = '16px';
  close_button.style.padding = '0';

  header.appendChild(title);
  header.appendChild(close_button);

  const selection_info = document.createElement('div');
  selection_info.style.fontSize = '11px';
  selection_info.style.marginBottom = '8px';
  selection_info.style.color = '#5b6770';

  const value_input = document.createElement('input');
  value_input.type = 'text';
  value_input.placeholder = 'Category value';
  const value_field = create_labeled_input('Category value', value_input);

  const color_input = document.createElement('input');
  color_input.type = 'color';
  color_input.value = DEFAULT_COLORS.row;
  color_input.style.padding = '0';
  color_input.style.height = '32px';
  color_input.style.cursor = 'pointer';
  const color_field = create_labeled_input('Color', color_input);

  const button_row = document.createElement('div');
  button_row.style.display = 'flex';
  button_row.style.gap = '8px';
  button_row.style.marginTop = '12px';

  const apply_button = document.createElement('button');
  apply_button.type = 'button';
  apply_button.textContent = 'Apply';
  apply_button.style.flex = '1';
  apply_button.style.background = '#2f74ff';
  apply_button.style.color = '#ffffff';
  apply_button.style.border = 'none';
  apply_button.style.borderRadius = '4px';
  apply_button.style.padding = '8px';
  apply_button.style.cursor = 'pointer';
  apply_button.style.fontWeight = '600';

  const cancel_button = document.createElement('button');
  cancel_button.type = 'button';
  cancel_button.textContent = 'Cancel';
  cancel_button.style.flex = '1';
  cancel_button.style.background = '#f5f5f5';
  cancel_button.style.color = '#47515b';
  cancel_button.style.border = '1px solid #d3d3d3';
  cancel_button.style.borderRadius = '4px';
  cancel_button.style.padding = '8px';
  cancel_button.style.cursor = 'pointer';

  button_row.appendChild(apply_button);
  button_row.appendChild(cancel_button);

  container.appendChild(header);
  container.appendChild(selection_info);
  container.appendChild(value_field);
  container.appendChild(color_field);
  container.appendChild(button_row);

  viz_state.el.appendChild(container);

  let context = null;

  const get_stored_color = (value) => {
    if (!value) return null;
    const color_map = viz_state.attr?.category_colors || {};
    return color_map[String(value)] || null;
  };

  const axis_is_enabled = (axis) => {
    const flags = viz_state.manual_cat?.flags || {};
    const config = viz_state.manual_cat?.config?.[axis];
    return Boolean(flags?.[axis] && config?.attribute);
  };

  const close = () => {
    container.style.display = 'none';
    context = null;
  };

  const ensure_color_for_value = (raw_value, axis) => {
    const trimmed = (raw_value || '').trim();
    if (!trimmed) {
      color_input.value = DEFAULT_COLORS[axis] || DEFAULT_COLORS.row;
      return color_input.value;
    }

    const stored = get_stored_color(trimmed);
    if (stored) {
      color_input.value = stored;
      return stored;
    }

    const generated = allocate_color(viz_state);
    color_input.value = generated;
    return generated;
  };

  const position_container = (position) => {
    const el_bounds = viz_state.el.getBoundingClientRect();
    const root_bounds = viz_state.root.getBoundingClientRect();
    const width = container.offsetWidth || 240;
    const height = container.offsetHeight || 200;

    const relative_x =
      (position?.x ?? root_bounds.width - width - 24) +
      (root_bounds.left - el_bounds.left);
    const relative_y = (position?.y ?? 24) + (root_bounds.top - el_bounds.top);

    const x = clamp_position(relative_x, 8, el_bounds.width - width - 8);
    const y = clamp_position(relative_y, 8, el_bounds.height - height - 8);

    container.style.left = `${x}px`;
    container.style.top = `${y}px`;
  };

  const open = ({
    axis,
    selection,
    initial_value,
    initial_color,
    position,
  }) => {
    if (
      !Array.isArray(selection) ||
      selection.length === 0 ||
      !axis_is_enabled(axis)
    ) {
      return;
    }

    context = {
      axis,
      selection: selection.map((name) => String(name)),
    };

    const axis_label = axis === 'col' ? 'columns' : 'rows';
    const configured_name = viz_state.manual_cat?.config?.[axis]?.attribute;
    if (!configured_name) {
      return;
    }

    selection_info.textContent = `${selection.length} ${axis_label} selected`;
    value_input.value = initial_value ? String(initial_value) : '';

    const stored_color = get_stored_color(value_input.value.trim());
    color_input.value =
      initial_color ||
      stored_color ||
      DEFAULT_COLORS[axis] ||
      DEFAULT_COLORS.row;

    container.style.display = 'block';
    position_container(position);
  };

  const apply_changes = () => {
    if (!context) return;

    const attribute_name =
      viz_state.manual_cat?.config?.[context.axis]?.attribute;
    if (!attribute_name) {
      close();
      return;
    }

    const value = value_input.value.trim();
    const color_hex =
      color_input.value || DEFAULT_COLORS[context.axis] || DEFAULT_COLORS.row;

    const manual_store = viz_state.obs_store?.manual_cat?.[context.axis];
    if (!manual_store) {
      close();
      return;
    }

    // Update store; downstream subscribers (matrix_viz / attr_state) handle
    // rebuilding the cat layers and syncing to Python
    manual_store.setAttribute(attribute_name);
    manual_store.updateSelection({
      selection: context.selection,
      value,
      color: color_hex,
    });

    close();
  };

  apply_button.addEventListener('click', apply_changes);
  cancel_button.addEventListener('click', close);
  close_button.addEventListener('click', close);

  viz_state.attr.editor = {
    open,
    close,
  };

  value_input.addEventListener('input', () => {
    const axis = context?.axis || 'row';
    ensure_color_for_value(value_input.value, axis);
  });
};
