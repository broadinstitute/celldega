import { randomHexColor } from '../utils/hexToRgb';

/**
 * Allocate a unique color for a new neighborhood, avoiding colors already in use.
 * @param {Object} viz_state - Visualization state
 * @returns {string} Hex color string
 */
const allocate_nbhd_color = (viz_state) => {
  const used_colors = new Set();

  // Collect colors already used by neighborhoods
  if (viz_state.edit?.feature_collection?.features) {
    viz_state.edit.feature_collection.features.forEach((f) => {
      if (f.properties?.color) {
        used_colors.add(f.properties.color.toLowerCase());
      }
    });
  }

  // Try to find a unique color
  for (let attempt = 0; attempt < 50; attempt++) {
    const candidate = randomHexColor();
    if (!used_colors.has(candidate.toLowerCase())) {
      return candidate;
    }
  }

  return randomHexColor(); // fallback
};

/**
 * Create a labeled input field wrapper.
 * @param {string} label_text - Label text
 * @param {HTMLElement} input - Input element
 * @returns {HTMLElement} Wrapper element
 */
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

/**
 * Clamp a position value within bounds.
 */
const clamp_position = (value, min, max) => Math.min(Math.max(value, min), max);

/**
 * Initialize the neighborhood editor dialog.
 * This dialog allows users to set/edit neighborhood names and colors.
 *
 * @param {Object} viz_state - Visualization state
 * @param {Object} deck_ist - Deck.gl instance
 * @param {Object} layers_obj - Layers object
 * @returns {Object} Editor API with open/close methods
 */
export const initialize_nbhd_editor = (viz_state, deck_ist, layers_obj) => {
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
  container.style.fontFamily =
    '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

  // Header
  const header = document.createElement('div');
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.marginBottom = '8px';

  const title = document.createElement('span');
  title.style.fontSize = '13px';
  title.style.fontWeight = '700';
  title.style.color = '#333333';
  title.textContent = 'Neighborhood';

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

  // Name input
  const name_input = document.createElement('input');
  name_input.type = 'text';
  name_input.placeholder = 'Neighborhood name';
  const name_field = create_labeled_input('Name', name_input);

  // Color input
  const color_input = document.createElement('input');
  color_input.type = 'color';
  color_input.value = '#3b82f6';
  color_input.style.padding = '0';
  color_input.style.height = '32px';
  color_input.style.cursor = 'pointer';
  const color_field = create_labeled_input('Color', color_input);

  // Buttons
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
  container.appendChild(name_field);
  container.appendChild(color_field);
  container.appendChild(button_row);

  // Append to root element
  viz_state.root.appendChild(container);

  let context = null;
  let on_apply_callback = null;

  /**
   * Position the container within viewport bounds.
   */
  const position_container = (position) => {
    const root_bounds = viz_state.root.getBoundingClientRect();
    const width = container.offsetWidth || 240;
    const height = container.offsetHeight || 180;

    const x = clamp_position(
      position?.x ?? root_bounds.width / 2 - width / 2,
      8,
      root_bounds.width - width - 8
    );
    const y = clamp_position(
      position?.y ?? root_bounds.height / 2 - height / 2,
      8,
      root_bounds.height - height - 8
    );

    container.style.left = `${x}px`;
    container.style.top = `${y}px`;
  };

  /**
   * Close the editor dialog.
   */
  const close = () => {
    container.style.display = 'none';
    context = null;
    on_apply_callback = null;
  };

  /**
   * Open the editor dialog.
   * @param {Object} options - Dialog options
   * @param {number} options.feature_index - Index of the feature being edited
   * @param {string} options.initial_name - Initial name value
   * @param {string} options.initial_color - Initial color value (hex)
   * @param {Object} options.position - Position {x, y} for the dialog
   * @param {Function} options.on_apply - Callback when apply is clicked
   */
  const open = ({
    feature_index,
    initial_name = '',
    initial_color = null,
    position = null,
    on_apply = null,
  }) => {
    context = { feature_index };
    on_apply_callback = on_apply;

    name_input.value = initial_name;
    color_input.value = initial_color || allocate_nbhd_color(viz_state);

    container.style.display = 'block';
    position_container(position);

    // Focus the name input
    setTimeout(() => name_input.focus(), 50);
  };

  /**
   * Apply the changes and close the dialog.
   */
  const apply_changes = () => {
    if (context === null) return;

    const name = name_input.value.trim() || `nbhd_${context.feature_index + 1}`;
    const color = color_input.value;

    if (on_apply_callback) {
      on_apply_callback({
        feature_index: context.feature_index,
        name,
        color,
      });
    }

    close();
  };

  // Event listeners
  apply_button.addEventListener('click', apply_changes);
  cancel_button.addEventListener('click', close);
  close_button.addEventListener('click', close);

  // Allow Enter key to apply
  name_input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      apply_changes();
    } else if (e.key === 'Escape') {
      close();
    }
  });

  return {
    open,
    close,
  };
};
