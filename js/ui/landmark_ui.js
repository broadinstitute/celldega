import * as d3 from 'd3';

const make_button = (label) => {
  const button = document.createElement('button');
  button.textContent = label;
  button.className = 'landmark-button';
  button.type = 'button';
  button.style.fontSize = '10px';
  button.style.fontWeight = '600';
  button.style.padding = '3px 10px';
  button.style.marginRight = '4px';
  button.style.border = '1px solid #d3d3d3';
  button.style.borderRadius = '3px';
  button.style.backgroundColor = 'white';
  button.style.color = 'gray';
  button.style.cursor = 'pointer';
  return button;
};

export const make_landmark_toolbar = ({
  on_mark_toggle,
  on_save,
  on_delete,
}) => {
  const container = document.createElement('div');
  container.className = 'landmark-toolbar';
  container.style.display = 'flex';
  container.style.alignItems = 'center';
  container.style.padding = '4px';

  const mark_button = make_button('MARK');
  const save_button = make_button('SAVE');
  const del_button = make_button('DEL');
  del_button.style.display = 'none';

  mark_button.addEventListener('click', () => on_mark_toggle());
  save_button.addEventListener('click', () => on_save());
  del_button.addEventListener('click', () => on_delete());

  container.append(mark_button, save_button, del_button);

  return {
    container,
    buttons: { mark: mark_button, save: save_button, del: del_button },
  };
};

export const set_mark_button_active = (buttons, active) => {
  d3.select(buttons.mark)
    .classed('active', active)
    .style('color', active ? 'blue' : 'gray')
    .style('border-color', active ? '#8797ff' : '#d3d3d3');
};

export const set_del_button_visible = (buttons, visible) => {
  d3.select(buttons.del).style('display', visible ? 'inline-flex' : 'none');
};

const ignores_landmark_shortcut = (event) => {
  if (
    event.defaultPrevented ||
    event.metaKey ||
    event.ctrlKey ||
    event.altKey
  ) {
    return true;
  }

  const tag_name = event.target?.tagName?.toLowerCase();
  return (
    event.target?.isContentEditable ||
    tag_name === 'input' ||
    tag_name === 'textarea' ||
    tag_name === 'select' ||
    tag_name === 'button'
  );
};

/**
 * "m" toggles MARK, "s" SAVEs the current draft pair, Escape cancels the
 * draft (or exits MARK if there's no draft), Delete/Backspace removes the
 * selected committed pair — mirrors the guard + cleanup-callback pattern
 * `672602e0` established for Landscape's SKTCH shortcut.
 */
export const register_landmark_keyboard_shortcuts = ({
  on_mark_toggle,
  on_save,
  on_cancel,
  on_delete,
}) => {
  const handler = (event) => {
    if (ignores_landmark_shortcut(event)) return;
    const key = event.key?.toLowerCase();

    if (key === 'm') {
      event.preventDefault();
      on_mark_toggle();
    } else if (key === 's') {
      event.preventDefault();
      on_save();
    } else if (key === 'escape') {
      event.preventDefault();
      on_cancel();
    } else if (key === 'delete' || key === 'backspace') {
      event.preventDefault();
      on_delete();
    }
  };

  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
};

/** A coarse manual-rotation slider for one side, to assist visually lining
 * up features before precisely placing landmarks. Purely a display aid —
 * see `rotation_state`/`getModelMatrixProps` in the landmark layers. */
export const make_rotation_slider = (on_change) => {
  const container = document.createElement('div');
  container.className = 'landmark-rotation-slider';
  container.style.display = 'flex';
  container.style.alignItems = 'center';
  container.style.gap = '4px';
  container.style.fontSize = '9px';

  const label = document.createElement('span');
  label.textContent = '0°';
  label.style.width = '28px';
  label.style.textAlign = 'right';

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.min = '-180';
  slider.max = '180';
  slider.step = '1';
  slider.value = '0';
  slider.style.width = '90px';
  slider.title = 'Rotate this slice (display only)';

  slider.addEventListener('input', () => {
    const degrees = Number(slider.value);
    label.textContent = `${degrees}°`;
    on_change(degrees);
  });

  container.append(slider, label);
  return { container, slider, label };
};

export const set_rotation_slider_value = ({ slider, label }, degrees) => {
  slider.value = String(degrees);
  label.textContent = `${degrees}°`;
};

export const make_cluster_legend = (categories, on_select) => {
  const container = document.createElement('div');
  container.className = 'landmark-cluster-legend';
  container.style.display = 'flex';
  container.style.flexWrap = 'wrap';
  container.style.gap = '3px';
  container.style.padding = '2px 4px';
  container.style.fontSize = '9px';

  let selected = null;
  const items = [];

  categories.forEach(({ cluster, color }) => {
    const item = document.createElement('span');
    item.style.display = 'inline-flex';
    item.style.alignItems = 'center';
    item.style.cursor = 'pointer';
    item.style.padding = '1px 4px';
    item.style.borderRadius = '3px';
    item.style.border = '1px solid transparent';

    const swatch = document.createElement('span');
    swatch.style.width = '8px';
    swatch.style.height = '8px';
    swatch.style.borderRadius = '50%';
    swatch.style.backgroundColor = color;
    swatch.style.marginRight = '3px';

    const label = document.createElement('span');
    label.textContent = cluster;

    item.append(swatch, label);
    item.addEventListener('click', () => {
      selected = selected === cluster ? null : cluster;
      items.forEach((entry) => {
        entry.el.style.borderColor =
          entry.cluster === selected ? '#8797ff' : 'transparent';
      });
      on_select(selected);
    });

    container.appendChild(item);
    items.push({ cluster, el: item });
  });

  return container;
};
