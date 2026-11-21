/**
 * A small ▾ beside CELL: what cells are shown by (clusters, another per-cell
 * attribute, or a label set such as cell types). A native <select> lies over the
 * caret, so clicking it opens the list, like the view-mode and image dropdowns.
 * Shown only when there is more than one choice.
 */
import { cell_attribute_options } from '../global_variables/cell_attributes';

import { CONTROL_FONT_SIZE } from './control_style';

/**
 * @param {object} viz_state - Landscape state (`cats`, `model`).
 * @param {HTMLElement} cell_button - The CELL button; the caret goes after it.
 * @param {(name: string) => void} on_pick - Called with the picked attribute.
 * @returns {{update: () => void, element: HTMLElement}}
 */
export const make_cell_attribute_menu = (viz_state, cell_button, on_pick) => {
  const menu = document.createElement('div');
  menu.className = 'cell_attribute_menu';
  Object.assign(menu.style, {
    position: 'relative',
    display: 'inline-block',
    flexShrink: '0',
    margin: '5px 0 0 -4px',
  });
  const caret = document.createElement('div');
  caret.textContent = '▾';
  caret.setAttribute('aria-hidden', 'true');
  Object.assign(caret.style, {
    fontSize: CONTROL_FONT_SIZE,
    fontWeight: 'bold',
    color: 'blue',
    padding: '0 3px',
    userSelect: 'none',
  });
  const select = document.createElement('select');
  select.className = 'cell_attribute_select';
  select.setAttribute('aria-label', 'Show cells by');
  // Invisible over the caret: the caret shows, the native list opens on click.
  Object.assign(select.style, {
    position: 'absolute',
    inset: '0',
    width: '100%',
    height: '100%',
    opacity: '0',
    cursor: 'pointer',
    border: 'none',
    padding: '0',
    margin: '0',
    fontSize: CONTROL_FONT_SIZE,
    fontWeight: 'bold',
  });
  menu.append(caret, select);
  cell_button.after(menu);

  const update = () => {
    const options = cell_attribute_options(viz_state);
    const current = viz_state.cats.attribute || '';
    select.replaceChildren(
      ...options.map(({ value, label }) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label.toUpperCase();
        return option;
      })
    );
    select.value = options.some((o) => o.value === current) ? current : '';
    const shown = options.find((o) => o.value === select.value)?.label;
    select.title = `Show cells by: ${shown} (click for other attributes)`;
    menu.style.display = options.length > 1 ? 'inline-block' : 'none';
  };
  select.addEventListener('change', () => {
    const picked = select.value;
    update(); // shows the current choice until the switch lands
    on_pick(picked);
  });
  update();
  return { update, element: menu };
};
