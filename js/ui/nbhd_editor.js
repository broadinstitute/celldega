import { randomHexColor } from '../utils/hexToRgb';

import {
  clamp_position,
  create_button_row,
  create_color_input,
  create_dialog_container,
  create_dialog_header,
  create_labeled_input,
  create_text_input,
} from './editor_common';

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
 * Initialize the neighborhood editor dialog.
 * This dialog allows users to set/edit neighborhood names and colors.
 *
 * @param {Object} viz_state - Visualization state
 * @param {Object} _deck_ist - Deck.gl instance (unused, kept for API consistency)
 * @param {Object} _layers_obj - Layers object (unused, kept for API consistency)
 * @returns {Object} Editor API with open/close methods
 */
export const initialize_nbhd_editor = (viz_state, _deck_ist, _layers_obj) => {
  const container = create_dialog_container();
  const { header, close_button } = create_dialog_header('Neighborhood');

  // Name input
  const name_input = create_text_input('Neighborhood name');
  const name_field = create_labeled_input('Name', name_input);

  // Color input
  const color_input = create_color_input('#3b82f6');
  const color_field = create_labeled_input('Color', color_input);

  // Buttons
  const { button_row, apply_button, cancel_button } = create_button_row();

  // Assemble dialog
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

  // Allow Enter key to apply, Escape to close
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
