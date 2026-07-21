import * as d3 from 'd3';

import { create_color_input } from './editor_common';

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

/**
 * MARK/SAVE/DEL adapt to celldega's three landmark states — browse, mark,
 * modify (see `set_mark_button_mode`/`set_save_button_visible`/
 * `set_del_button_visible`) — mirroring NBHD's SKTCH/EDIT/SAVE/DELETE
 * pattern of showing only the buttons relevant to the current state.
 * SAVE starts hidden (browse has nothing to save yet); DEL is always red,
 * since deleting a landmark here is a whole-landmark, unconfirmable action.
 */
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
  save_button.style.display = 'none';
  del_button.style.display = 'none';
  del_button.style.color = 'red';
  del_button.style.borderColor = '#f0b8b8';

  mark_button.addEventListener('click', () => on_mark_toggle());
  save_button.addEventListener('click', () => on_save());
  del_button.addEventListener('click', () => on_delete());

  container.append(mark_button, save_button, del_button);

  return {
    container,
    buttons: { mark: mark_button, save: save_button, del: del_button },
  };
};

/** `mode` is one of 'browse' | 'mark' | 'modify' — see `landmark.js`'s state
 * machine. Rather than leaving MARK on-screen (disabled/relabeled) once
 * you're already mid-action, the same button slot swaps to CANCEL — a
 * single, always-clickable way back to 'browse' from either 'mark' or
 * 'modify', discarding anything not yet saved. */
export const set_mark_button_mode = (buttons, mode) => {
  const is_browse = mode === 'browse';
  d3.select(buttons.mark)
    .text(is_browse ? 'MARK' : 'CANCEL')
    .style('color', is_browse ? 'blue' : '#8a6d3b')
    .style('border-color', is_browse ? '#d3d3d3' : '#e0c28a')
    .property('disabled', false)
    .style('cursor', 'pointer');
};

export const set_save_button_visible = (buttons, visible) => {
  d3.select(buttons.save).style('display', visible ? 'inline-flex' : 'none');
};

/** Blue once there's something for SAVE to actually commit (e.g. a drawn-but-
 * unsaved landmark instance in 'mark'); the default gray otherwise, so the
 * button visually confirms "yes, this click will do something." */
export const set_save_button_active = (buttons, active) => {
  d3.select(buttons.save)
    .style('color', active ? 'blue' : 'gray')
    .style('border-color', active ? '#a9c6ff' : '#d3d3d3');
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

/** A CELL/TRX-style label + pill toggle switch, mirroring Landscape's
 * layer-visibility toggles. `on_change(checked)` fires on click. */
export const make_toggle_button = (
  label_text,
  { checked = true, disabled = false } = {}
) => {
  const container = document.createElement('label');
  container.style.display = 'inline-flex';
  container.style.alignItems = 'center';
  container.style.gap = '4px';
  container.style.fontSize = '11px';
  container.style.fontWeight = '700';
  container.style.color = disabled ? '#b0b0b0' : 'blue';
  container.style.cursor = disabled ? 'default' : 'pointer';
  container.style.userSelect = 'none';

  const label = document.createElement('span');
  label.textContent = label_text;

  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  input.disabled = disabled;
  input.style.accentColor = 'blue';
  input.style.cursor = disabled ? 'default' : 'pointer';

  container.append(label, input);
  return { container, input };
};

/** A small labeled range slider, matching `make_rotation_slider`'s shape —
 * used for cell-point-radius control. */
export const make_range_slider = (
  { min, max, step, value, format, title },
  on_change
) => {
  const container = document.createElement('div');
  container.style.display = 'flex';
  container.style.alignItems = 'center';
  container.style.gap = '4px';
  container.style.fontSize = '9px';

  const label = document.createElement('span');
  label.textContent = format(value);
  label.style.width = '20px';
  label.style.textAlign = 'right';

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.min = String(min);
  slider.max = String(max);
  slider.step = String(step);
  slider.value = String(value);
  slider.style.width = '60px';
  slider.title = title || '';

  slider.addEventListener('input', () => {
    const numeric = Number(slider.value);
    label.textContent = format(numeric);
    on_change(numeric);
  });

  container.append(slider, label);
  return { container, slider, label };
};

/** The label of whatever's currently being placed (MARK) or edited (MODIFY)
 * — the LNDMRK equivalent of a gene-search box: hidden in 'browse', shown
 * and editable in 'mark'/'modify', and updated when a LNDMRK bar or an
 * existing pin is clicked to target a landmark. `on_commit(value)`
 * fires on Enter/blur (an empty value means "back to auto-numbering", only
 * meaningful in 'mark'). */
export const make_label_input = (on_commit) => {
  const input = document.createElement('input');
  input.type = 'text';
  input.style.width = '70px';
  input.style.height = '18px';
  input.style.fontSize = '10px';
  input.style.padding = '1px 4px';
  input.style.border = '1px solid #d3d3d3';
  input.style.borderRadius = '3px';
  input.style.display = 'none';
  input.title =
    'Landmark name — click a LNDMRK bar or an existing pin to target one';

  const commit = () => on_commit(input.value.trim());
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    commit();
    input.blur();
  });
  input.addEventListener('blur', commit);

  return { container: input, input };
};

export const set_label_input_value = (label_input, value) => {
  label_input.input.value = value;
};

export const set_label_input_visible = (label_input, visible) => {
  label_input.input.style.display = visible ? 'inline-block' : 'none';
};

/** A color swatch next to the label textbox — same NBHD sketch/modify
 * pattern (`create_color_input`, a native color picker) for overriding a
 * landmark's default (computed) color. Hidden in 'browse'; shown for
 * whichever landmark is targeted in 'mark'/'modify'. `on_change(hex)` fires
 * as the user picks, same as the native input's own live-preview behavior. */
export const make_landmark_color_input = (on_change) => {
  const input = create_color_input('#4f80ff');
  input.style.width = '20px';
  input.style.height = '18px';
  input.style.display = 'none';
  input.title = 'Landmark color';

  input.addEventListener('input', () => on_change(input.value));

  return { container: input, input };
};

export const set_color_input_value = (color_input, hex) => {
  color_input.input.value = hex;
};

export const set_color_input_visible = (color_input, visible) => {
  color_input.input.style.display = visible ? 'inline-block' : 'none';
};
