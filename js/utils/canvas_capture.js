/**
 * Canvas capture helpers for raster snapshots (e.g. Landscape -> Clerk).
 *
 * Captures read a deck.gl canvas without enabling `preserveDrawingBuffer`, which
 * would cost performance on every frame for every deck. Instead, a capture forces a
 * synchronous redraw and reads the pixels in the same task, before the browser
 * composites the frame and clears the WebGL drawing buffer.
 */

// Captures sit on this color where the deck draws nothing (its canvas is
// transparent there), so a saved PNG looks the same in light and dark viewers.
export const CAPTURE_BACKGROUND = 'white';

/**
 * Copy a canvas into a new 2D canvas whose longest side is at most `max_size` px.
 * Returns the source unchanged if a 2D context is unavailable.
 * @param {HTMLCanvasElement} source
 * @param {number} max_size
 * @param {string|null} [background] - A CSS color to fill behind the image, or
 *   null to keep transparency.
 * @returns {HTMLCanvasElement}
 */
export const downscale_canvas = (source, max_size, background = null) => {
  const longest = Math.max(source.width, source.height);
  const scale = longest > 0 ? Math.min(1, max_size / longest) : 1;
  const out = document.createElement('canvas');
  out.width = Math.max(1, Math.round(source.width * scale));
  out.height = Math.max(1, Math.round(source.height * scale));
  const ctx = out.getContext('2d');
  if (!ctx) return source;
  if (background) {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, out.width, out.height);
  }
  ctx.drawImage(source, 0, 0, out.width, out.height);
  return out;
};

/**
 * Encode a canvas as base64 PNG without the `data:` prefix.
 * @param {HTMLCanvasElement} canvas
 * @returns {string}
 */
export const canvas_to_base64_png = (canvas) => {
  const data_url = canvas.toDataURL('image/png');
  const comma = data_url.indexOf(',');
  return comma >= 0 ? data_url.slice(comma + 1) : data_url;
};

/**
 * Capture a deck.gl view as a downscaled base64 PNG plus a small thumbnail.
 * @param {object} deck - deck.gl Deck instance.
 * @param {HTMLElement} [fallback_root] - Element to search for a canvas if the deck
 *   does not expose one.
 * @param {{max_size?: number, thumb_size?: number, background?: string|null}}
 *   [options] - `background` is a CSS color behind the image (white by
 *   default); null keeps the canvas's transparency.
 * @returns {{png: string, thumb: string, width: number, height: number}|null}
 */
export const capture_deck = (
  deck,
  fallback_root,
  { max_size = 1024, thumb_size = 192, background = CAPTURE_BACKGROUND } = {}
) => {
  // Draw now, then read back immediately (same task) -- see module docstring.
  deck?.redraw?.('raster-capture');
  const canvas = deck?.getCanvas?.() || fallback_root?.querySelector('canvas');
  if (!canvas || !canvas.width || !canvas.height) return null;

  // Copy once from the WebGL canvas; derive the thumbnail from the 2D copy.
  const image = downscale_canvas(canvas, max_size, background);
  const thumb = downscale_canvas(image, thumb_size);
  return {
    png: canvas_to_base64_png(image),
    thumb: canvas_to_base64_png(thumb),
    width: image.width,
    height: image.height,
  };
};
