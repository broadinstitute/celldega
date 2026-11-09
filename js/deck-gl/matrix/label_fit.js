/**
 * Fit a label into the space it has, keeping its beginning.
 *
 * Row labels are right-aligned against the heatmap, so a label too long for the
 * label area used to run off its left edge and lose its *beginning* (the gene or
 * cluster name). Instead, keep the beginning and end it with "…".
 */

export const ELLIPSIS = '…';

/**
 * Characters a label layer can draw: deck.gl's TextLayer only rasterizes its
 * character set (printable ASCII by default), so add the ellipsis.
 */
export const LABEL_CHARACTER_SET = [
  ...Array.from({ length: 95 }, (_, i) => String.fromCharCode(32 + i)),
  ELLIPSIS,
];

// Average Arial glyph width as a share of the font size; used where there is no
// canvas to measure with (e.g. tests).
const FALLBACK_CHAR_WIDTH = 0.55;
const MAX_CACHED = 20000;

let context = null;
const widths = new Map();

const measure = (text, font_px, font_weight, font_family) => {
  const key = `${font_weight}|${font_px}|${text}`;
  let width = widths.get(key);
  if (width !== undefined) return width;
  if (context === null && typeof document !== 'undefined') {
    try {
      context = document.createElement('canvas').getContext('2d') || false;
    } catch {
      context = false;
    }
  }
  if (context) {
    context.font = `${font_weight} ${font_px}px ${font_family}`;
    ({ width } = context.measureText(text));
  } else {
    width = text.length * font_px * FALLBACK_CHAR_WIDTH;
  }
  if (widths.size > MAX_CACHED) widths.clear();
  widths.set(key, width);
  return width;
};

/**
 * `text` if it fits in `max_px`, else its longest beginning that fits with "…".
 *
 * @param {string} text
 * @param {number} max_px - Room for the label, in screen pixels.
 * @param {number} font_px - Rendered font size, in pixels.
 * @param {{font_weight?: string, font_family?: string}} [options]
 * @returns {string}
 */
export const fit_label = (
  text,
  max_px,
  font_px,
  { font_weight = 'normal', font_family = 'Arial' } = {}
) => {
  const label = String(text ?? '');
  if (!label || !(max_px > 0) || !(font_px > 0)) return label;
  // Half-pixel font steps share measurements across zoom ticks.
  const px = Math.round(font_px * 2) / 2;
  const width = (s) => measure(s, px, font_weight, font_family);
  if (width(label) <= max_px) return label;

  let low = 0;
  let high = label.length - 1;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    if (width(`${label.slice(0, mid).trimEnd()}${ELLIPSIS}`) <= max_px) {
      low = mid;
    } else {
      high = mid - 1;
    }
  }
  return `${label.slice(0, low).trimEnd()}${ELLIPSIS}`;
};
