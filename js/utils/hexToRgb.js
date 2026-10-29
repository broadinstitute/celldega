export const hexToRgb = (hex) => {
  hex = hex.replace(/^#/, '');
  if (hex.length === 3) hex = hex.replace(/./g, '$&$&');
  return hex.length === 6
    ? [0, 2, 4].map((i) => parseInt(hex.substr(i, 2), 16))
    : [0, 0, 0];
};

/**
 * Convert RGB array to hex color string.
 * @param {number[]} rgb - Array of [r, g, b] values (0-255)
 * @returns {string} Hex color string (e.g., "#ff0000")
 */
export const rgbToHex = (rgb) => {
  if (!rgb || !Array.isArray(rgb) || rgb.length < 3) {
    return '#808080'; // default gray if invalid input
  }
  const clamp = (val) => Math.max(0, Math.min(255, Math.round(val)));
  const r = clamp(rgb[0]).toString(16).padStart(2, '0');
  const g = clamp(rgb[1]).toString(16).padStart(2, '0');
  const b = clamp(rgb[2]).toString(16).padStart(2, '0');
  return `#${r}${g}${b}`;
};

/**
 * Generate a random hex color.
 * @returns {string} Random hex color string (e.g., "#a3f2c1")
 */
export const randomHexColor = () => {
  const r = Math.floor(Math.random() * 256);
  const g = Math.floor(Math.random() * 256);
  const b = Math.floor(Math.random() * 256);
  return rgbToHex([r, g, b]);
};
