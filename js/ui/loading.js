/**
 * A quiet loading placeholder: the Celldega awning mark with "Loading…" below it,
 * shown while a widget fetches its data, so a slow load doesn't look like a blank
 * or broken cell.
 */
import { logo } from './logo';

const STYLE_ID = 'celldega-loading-style';
const CSS = `
.celldega-loading { display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 8px; box-sizing: border-box; width: 100%;
  color: #8a929b; font: 12px -apple-system, BlinkMacSystemFont, "Helvetica Neue",
  Helvetica, Arial, sans-serif; letter-spacing: 0.04em; }
.celldega-loading img { height: 28px; animation: celldega-loading-pulse 1.6s ease-in-out infinite; }
@keyframes celldega-loading-pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 0.9; } }
@media (prefers-reduced-motion: reduce) { .celldega-loading img { animation: none; opacity: 0.7; } }
`;

const ensure_style = (doc) => {
  if (doc.getElementById(STYLE_ID)) return;
  const style = doc.createElement('style');
  style.id = STYLE_ID;
  style.textContent = CSS;
  doc.head.appendChild(style);
};

/**
 * Show the placeholder in `el` until `remove()` is called.
 * @param {HTMLElement} el - The widget's element.
 * @param {{height?: number, label?: string, delay?: number}} [options] - Height (px)
 *   of the space the widget will take, so the cell doesn't jump when it appears;
 *   `delay` (ms) waits before showing anything, so widgets that render at once
 *   never flash the placeholder.
 * @returns {() => void} remove
 */
export const show_loading = (
  el,
  { height = 300, label = 'Loading…', delay = 0 } = {}
) => {
  const doc = el.ownerDocument || document;
  let box = null;
  const show = () => {
    ensure_style(doc);
    box = doc.createElement('div');
    box.className = 'celldega-loading';
    box.setAttribute('role', 'status');
    box.style.height = `${Math.max(Number(height) || 0, 120)}px`;

    const img = doc.createElement('img');
    img.src = `data:image/png;base64,${logo}`;
    img.alt = '';
    const text = doc.createElement('div');
    text.textContent = label;

    box.append(img, text);
    el.prepend(box);
  };
  const timer = delay > 0 ? setTimeout(show, delay) : (show(), null);
  return () => {
    if (timer !== null) clearTimeout(timer);
    box?.remove();
  };
};
