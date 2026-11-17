/**
 * Type sizes shared by the widgets' control panels, so the Landscape's and the
 * Clustergram's controls read as one set: bold capitals at the Clustergram's size.
 */

/** Font size of control-panel text buttons and labels (CELL, TRX, COL:, CROP...). */
export const CONTROL_FONT_SIZE = '9px';

/**
 * Button widths in the Landscape are given for 12px text (the size they were laid
 * out at); scaling them with the font keeps the rows' sliders aligned.
 */
const CONTROL_WIDTH_SCALE = 9 / 12;

/**
 * @param {number|string} width - A button width in px, for 12px text.
 * @returns {number} The width in px at {@link CONTROL_FONT_SIZE}.
 */
export const control_width = (width) =>
  Math.round(Number(width) * CONTROL_WIDTH_SCALE);
