import { CONTROL_FONT_SIZE } from './control_style';

/**
 * The dropdown of a Clustergram with several matrices (`Clustergram(matrix={name:
 * Matrix})`): one option per matrix, its description on hover, like the
 * Landscape's dataset dropdown. Choosing one calls `menu.on_change(name)`; the
 * Clustergram then shows that matrix (see multi_matrix_viz.js).
 *
 * @param {{names: string[], active: string, descriptions?: object,
 *   on_change: (name: string) => void}} menu
 * @returns {HTMLSelectElement|null} The dropdown, or null for one matrix.
 */
export const make_matrix_dropdown = (menu) => {
  const names = menu?.names || [];
  if (names.length <= 1) return null;

  const select = document.createElement('select');
  select.className = 'matrix-dropdown';
  Object.assign(select.style, {
    width: '126px',
    height: '18px',
    fontSize: CONTROL_FONT_SIZE,
    padding: '1px 2px',
    border: '1px solid #d3d3d3',
    borderRadius: '3px',
    backgroundColor: 'white',
    cursor: 'pointer',
    outline: 'none',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif',
  });

  const descriptions = menu.descriptions || {};
  const describe = (name) =>
    descriptions[name] ? `${name}: ${descriptions[name]}` : name;

  names.forEach((name) => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    option.title = describe(name);
    select.appendChild(option);
  });
  select.value = menu.active;
  select.title = describe(menu.active);

  select.addEventListener('focus', () => {
    select.style.borderColor = '#8797ff';
  });
  select.addEventListener('blur', () => {
    select.style.borderColor = '#d3d3d3';
  });
  select.addEventListener('change', () => {
    select.title = describe(select.value);
    menu.on_change?.(select.value);
  });
  return select;
};
