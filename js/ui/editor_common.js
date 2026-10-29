/**
 * Common utilities and UI components for editor dialogs.
 * Shared between attribute_editor.js and nbhd_editor.js
 */

/**
 * Clamp a position value within bounds.
 * @param {number} value - Value to clamp
 * @param {number} min - Minimum bound
 * @param {number} max - Maximum bound
 * @returns {number} Clamped value
 */
export const clamp_position = (value, min, max) =>
  Math.min(Math.max(value, min), max);

/**
 * Create a labeled input field wrapper with consistent styling.
 * @param {string} label_text - Label text
 * @param {HTMLElement} input - Input element
 * @returns {HTMLElement} Wrapper element
 */
export const create_labeled_input = (label_text, input) => {
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
 * Create a color input field with consistent styling.
 * @param {string} default_color - Default color value (hex)
 * @returns {HTMLInputElement} Color input element
 */
export const create_color_input = (default_color = '#3b82f6') => {
  const color_input = document.createElement('input');
  color_input.type = 'color';
  color_input.value = default_color;
  color_input.style.padding = '0';
  color_input.style.height = '32px';
  color_input.style.cursor = 'pointer';
  return color_input;
};

/**
 * Create a text input field.
 * @param {string} placeholder - Placeholder text
 * @returns {HTMLInputElement} Text input element
 */
export const create_text_input = (placeholder = '') => {
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = placeholder;
  return input;
};

/**
 * Create the dialog container with consistent styling.
 * @returns {HTMLElement} Container element
 */
export const create_dialog_container = () => {
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
  return container;
};

/**
 * Create the dialog header with title and close button.
 * @param {string} title_text - Title text
 * @returns {{ header: HTMLElement, close_button: HTMLButtonElement }}
 */
export const create_dialog_header = (title_text) => {
  const header = document.createElement('div');
  header.style.display = 'flex';
  header.style.justifyContent = 'space-between';
  header.style.alignItems = 'center';
  header.style.marginBottom = '8px';

  const title = document.createElement('span');
  title.style.fontSize = '13px';
  title.style.fontWeight = '700';
  title.style.color = '#333333';
  title.textContent = title_text;

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

  return { header, close_button };
};

/**
 * Create the button row with Apply and Cancel buttons.
 * @returns {{ button_row: HTMLElement, apply_button: HTMLButtonElement, cancel_button: HTMLButtonElement }}
 */
export const create_button_row = () => {
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

  return { button_row, apply_button, cancel_button };
};

/**
 * Position a dialog container within viewport bounds.
 * @param {HTMLElement} container - The dialog container
 * @param {DOMRect} bounds - The bounding rectangle to position within
 * @param {Object} position - Optional {x, y} position
 * @param {number} default_width - Default width if container width is 0
 * @param {number} default_height - Default height if container height is 0
 */
export const position_dialog = (
  container,
  bounds,
  position,
  default_width = 240,
  default_height = 200
) => {
  const width = container.offsetWidth || default_width;
  const height = container.offsetHeight || default_height;

  const x = clamp_position(
    position?.x ?? bounds.width / 2 - width / 2,
    8,
    bounds.width - width - 8
  );
  const y = clamp_position(
    position?.y ?? bounds.height / 2 - height / 2,
    8,
    bounds.height - height - 8
  );

  container.style.left = `${x}px`;
  container.style.top = `${y}px`;
};

/**
 * Convert HSL to hex color string.
 * @param {number} h - Hue (0-1)
 * @param {number} s - Saturation (0-1)
 * @param {number} l - Lightness (0-1)
 * @returns {string} Hex color string
 */
export const hsl_to_hex = (h, s, l) => {
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
