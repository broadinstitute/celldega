import {
  export_manual_category_payload,
  refresh_attribute_layers,
  update_manual_category_for_selection,
} from '../matrix/attr_state';

const DEFAULT_COLORS = {
  row: '#2f74ff',
  col: '#ff7f0e',
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

const build_preferred_section = () => {
  const section = document.createElement('div');
  section.style.marginTop = '6px';
  section.style.display = 'none';

  const title = document.createElement('div');
  title.textContent = 'Suggested categories';
  title.style.fontSize = '11px';
  title.style.fontWeight = '600';
  title.style.marginBottom = '4px';
  title.style.color = '#5b6770';

  const list = document.createElement('div');
  list.style.display = 'flex';
  list.style.flexWrap = 'wrap';
  list.style.gap = '4px';

  section.appendChild(title);
  section.appendChild(list);

  return { section, list };
};

export const initialize_attribute_editor = (viz_state, deck_mat, layers_mat) => {
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

  const attribute_input = document.createElement('input');
  attribute_input.type = 'text';
  attribute_input.placeholder = 'Attribute name';
  const attribute_field = create_labeled_input('Attribute name', attribute_input);

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

  const { section: preferred_section, list: preferred_list } =
    build_preferred_section();

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
  container.appendChild(attribute_field);
  container.appendChild(value_field);
  container.appendChild(color_field);
  container.appendChild(preferred_section);
  container.appendChild(button_row);

  viz_state.el.appendChild(container);

  let context = null;

  const close = () => {
    container.style.display = 'none';
    context = null;
  };

  const populate_preferred = (axis) => {
    preferred_list.innerHTML = '';
    const config = viz_state.manual_cat?.config?.[axis];
    const preferred = config?.preferred || [];
    if (!preferred.length) {
      preferred_section.style.display = 'none';
      return;
    }

    preferred_section.style.display = 'block';
    preferred.forEach((entry) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = entry.name;
      button.style.border = '1px solid #d3d3d3';
      button.style.borderRadius = '12px';
      button.style.padding = '2px 8px';
      button.style.fontSize = '11px';
      button.style.cursor = 'pointer';
      button.style.background = entry.color || '#f5f5f5';
      button.style.color = '#1f2a37';

      button.addEventListener('click', () => {
        value_input.value = entry.name;
        if (entry.color) {
          color_input.value = entry.color;
        }
      });

      preferred_list.appendChild(button);
    });
  };

  const position_container = (position) => {
    const el_bounds = viz_state.el.getBoundingClientRect();
    const root_bounds = viz_state.root.getBoundingClientRect();
    const width = container.offsetWidth || 240;
    const height = container.offsetHeight || 200;

    const relative_x =
      (position?.x ?? root_bounds.width - width - 24) +
      (root_bounds.left - el_bounds.left);
    const relative_y =
      (position?.y ?? 24) + (root_bounds.top - el_bounds.top);

    const x = clamp_position(relative_x, 8, el_bounds.width - width - 8);
    const y = clamp_position(relative_y, 8, el_bounds.height - height - 8);

    container.style.left = `${x}px`;
    container.style.top = `${y}px`;
  };

  const open = ({
    axis,
    selection,
    attribute_name,
    initial_value,
    initial_color,
    position,
  }) => {
    if (!Array.isArray(selection) || selection.length === 0) {
      return;
    }

    context = {
      axis,
      selection: selection.map((name) => String(name)),
    };

    const axis_label = axis === 'col' ? 'columns' : 'rows';
    const configured_name = viz_state.manual_cat?.config?.[axis]?.attribute;
    const default_attribute =
      attribute_name ||
      configured_name ||
      (axis === 'col' ? 'Manual column attribute' : 'Manual row attribute');

    populate_preferred(axis);

    selection_info.textContent = `${selection.length} ${axis_label} selected`;
    attribute_input.value = default_attribute;
    value_input.value = initial_value ? String(initial_value) : '';
    color_input.value =
      initial_color || DEFAULT_COLORS[axis] || DEFAULT_COLORS.row;

    container.style.display = 'block';
    position_container(position);
  };

  const apply_changes = () => {
    if (!context) {
      return;
    }

    const attribute_name = attribute_input.value.trim();
    if (!attribute_name) {
      attribute_input.style.borderColor = '#d9534f';
      return;
    }
    attribute_input.style.borderColor = '#d3d3d3';

    const value = value_input.value.trim();
    const color_hex = color_input.value || DEFAULT_COLORS[context.axis];

    const { frame, colors } = update_manual_category_for_selection(
      viz_state,
      context.axis,
      attribute_name,
      context.selection,
      value,
      color_hex
    );

    if (viz_state.model) {
      viz_state.model.set(`${context.axis}_attributes_df`, frame);
      viz_state.model.set(`${context.axis}_attribute_colors`, colors);
      viz_state.manual_cat.self_update = true;
      viz_state.model.set(
        'manual_cat',
        JSON.stringify(export_manual_category_payload(viz_state))
      );
      viz_state.model.save_changes();
    }

    refresh_attribute_layers(deck_mat, layers_mat, viz_state);
    close();
  };

  apply_button.addEventListener('click', apply_changes);
  cancel_button.addEventListener('click', close);
  close_button.addEventListener('click', close);

  viz_state.attr.editor = {
    open,
    close,
  };
};
