/**
 * The Landscape's view modes (SPATIAL, UMAP, XY) as one dropdown, like the
 * Clustergram's order control: a native <select> showing the current mode in
 * bold blue text (no arrow); picking another mode switches to it. Frees room in
 * the image row for IMG, the image source, SNAP and PINS.
 *
 * The mode buttons keep their handlers and colors (text_buttons.js and
 * umap/expression_scatter.js): they're kept, hidden, and picking a mode clicks
 * its button, so e.g. XY still takes the selected genes as its axes.
 */

import { CONTROL_FONT_SIZE } from './control_style';

const MODES = ['spatial', 'umap', 'xy'];

const FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

const element_of = (button) => button?.node?.() ?? button ?? null;

/**
 * @param {object} viz_state - Landscape state (`buttons.buttons`, `obs_store`).
 * @param {HTMLElement} row - The view-mode row (`containers.view_modes`).
 * @returns {() => void} Undo (for finalize).
 */
export const collapse_view_modes = (viz_state, row) => {
  const buttons = Object.fromEntries(
    MODES.map((mode) => [mode, element_of(viz_state.buttons?.buttons?.[mode])])
  );
  const present = MODES.filter((mode) => buttons[mode]?.parentNode === row);
  if (!row || present.length < 2) return () => {};

  const menu = document.createElement('div');
  menu.className = 'view_mode_menu';
  Object.assign(menu.style, {
    display: 'inline-flex',
    alignItems: 'baseline',
    flexShrink: '0',
  });
  const select = document.createElement('select');
  select.className = 'view_mode_select';
  select.title = 'View';
  select.setAttribute('aria-label', 'View');
  present.forEach((mode) => {
    const option = document.createElement('option');
    option.value = mode;
    option.textContent = mode.toUpperCase();
    if (buttons[mode].title) option.title = buttons[mode].title;
    select.appendChild(option);
  });
  Object.assign(select.style, {
    appearance: 'none',
    webkitAppearance: 'none',
    MozAppearance: 'none',
    border: 'none',
    background: 'transparent',
    padding: '0',
    margin: '5px 0 0 5px',
    fontFamily: FONT_FAMILY,
    fontSize: CONTROL_FONT_SIZE,
    fontWeight: 'bold',
    color: 'blue',
    cursor: 'pointer',
    outline: 'none',
    userSelect: 'none',
  });
  // The buttons stay in the page (their handlers, colors and other code use
  // them) but out of sight.
  const hidden = document.createElement('div');
  hidden.style.display = 'none';
  present.forEach((mode) => hidden.appendChild(buttons[mode]));
  menu.append(select, hidden);
  row.insertBefore(menu, row.firstChild);

  const current = () => {
    const view = viz_state.obs_store.landscape_view?.get?.() || 'spatial';
    return present.includes(view) ? view : present[0];
  };
  const sync = () => {
    select.value = current();
  };
  const on_change = () => {
    const mode = select.value;
    // Show the current mode until the switch lands (sync runs on the change).
    sync();
    buttons[mode].click();
  };
  select.addEventListener('change', on_change);
  const unsubscribe = viz_state.obs_store.landscape_view?.subscribe?.(sync, {
    immediate: false,
  });
  sync();

  return () => {
    unsubscribe?.();
    select.removeEventListener('change', on_change);
  };
};
