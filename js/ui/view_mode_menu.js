/**
 * The Landscape's view modes (SPATIAL, UMAP, XY) as a small menu: only the current
 * mode shows, with a caret; clicking the caret lists the others. Frees room in the
 * image row for IMG, the image source, SNAP and PINS.
 *
 * The mode buttons themselves are unchanged (their handlers and colors still
 * belong to text_buttons.js and umap/expression_scatter.js); this only moves them
 * into one place and hides the ones not in use.
 */

const MODES = ['spatial', 'umap', 'xy'];

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
  const caret = document.createElement('div');
  caret.className = 'view_mode_caret';
  caret.textContent = '▾';
  caret.setAttribute('role', 'button');
  caret.tabIndex = 0;
  Object.assign(caret.style, {
    cursor: 'pointer',
    fontSize: '9px',
    color: 'gray',
    margin: '5px 0 0 2px',
    userSelect: 'none',
  });
  row.insertBefore(menu, row.firstChild);
  present.forEach((mode) => menu.appendChild(buttons[mode]));
  menu.appendChild(caret);

  let open = false;
  const current = () => {
    const view = viz_state.obs_store.landscape_view?.get?.() || 'spatial';
    return present.includes(view) ? view : present[0];
  };
  const sync = () => {
    const active = current();
    present.forEach((mode) => {
      buttons[mode].style.display = open || mode === active ? '' : 'none';
    });
    caret.textContent = open ? '◂' : '▾';
    caret.title = open
      ? 'Hide the other views'
      : `Other views: ${present
          .filter((mode) => mode !== active)
          .map((mode) => mode.toUpperCase())
          .join(', ')}`;
  };
  const toggle = () => {
    open = !open;
    sync();
  };
  caret.addEventListener('click', toggle);
  caret.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggle();
    }
  });
  // Picking a mode closes the menu (after the button's own handler runs).
  const close = () => {
    open = false;
    setTimeout(sync, 0);
  };
  present.forEach((mode) => buttons[mode].addEventListener('click', close));
  const unsubscribe = viz_state.obs_store.landscape_view?.subscribe?.(sync, {
    immediate: false,
  });
  sync();

  return () => {
    unsubscribe?.();
    present.forEach((mode) =>
      buttons[mode].removeEventListener('click', close)
    );
  };
};
