import { create_color_input } from './editor_common';

// Outline-free text buttons (matching the CELL/LNDMRK toggle look) — the
// color carries the meaning, no border/background box, to keep the toolbar
// compact. Blue = clickable/ready; while a mode is engaged its button reads
// "CANCEL" in red (click it to leave the mode, discarding anything unsaved).
const CANCEL_COLOR = 'red';

const make_button = (label) => {
  const button = document.createElement('button');
  button.textContent = label;
  button.className = 'landmark-button';
  button.type = 'button';
  button.style.fontSize = '11px';
  button.style.fontWeight = '700';
  button.style.padding = '1px 2px';
  button.style.border = 'none';
  button.style.background = 'none';
  button.style.color = 'blue';
  button.style.cursor = 'pointer';
  button.style.userSelect = 'none';
  button.style.textAlign = 'left';
  return button;
};

/**
 * MARK/MODIFY/SAVE/DEL adapt to celldega's three landmark states — browse,
 * mark, modify (see `set_toolbar_mode`). The buttons stack vertically and
 * appear/disappear in place (below one another) so showing/hiding them never
 * shifts the rest of the control panel sideways. Browse shows just MARK;
 * MODIFY surfaces only once a specific landmark is selected. MARK/MODIFY are
 * toggles — blue when available, green while their mode is engaged, clicked
 * again to leave (so no CANCEL button is needed). DEL is always red.
 */
export const make_landmark_toolbar = ({
  on_mark_toggle,
  on_modify_toggle,
  on_save,
  on_delete,
}) => {
  const container = document.createElement('div');
  container.className = 'landmark-toolbar';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'flex-start';
  container.style.gap = '2px';
  container.style.padding = '2px 4px';
  // Fixed width (sized for the label textbox, the widest child) so buttons
  // and the textbox/color swatch appearing/disappearing changes only this
  // column's height, never its width — the sections to the right stay put.
  container.style.width = '78px';

  const mark_button = make_button('MARK');
  const modify_button = make_button('MODIFY');
  const save_button = make_button('SAVE');
  const del_button = make_button('DEL');
  save_button.style.display = 'none';
  del_button.style.display = 'none';
  del_button.style.color = 'red';

  mark_button.addEventListener('click', () => on_mark_toggle());
  modify_button.addEventListener('click', () => on_modify_toggle());
  save_button.addEventListener('click', () => on_save());
  del_button.addEventListener('click', () => on_delete());

  container.append(mark_button, modify_button, save_button, del_button);

  return {
    container,
    buttons: {
      mark: mark_button,
      modify: modify_button,
      save: save_button,
      del: del_button,
    },
  };
};

const show = (button, visible) => {
  button.style.display = visible ? 'block' : 'none';
};

/** `mode` is 'browse' | 'mark' | 'modify' — see `landmark.js`'s state
 * machine. MARK is the primary browse button; MODIFY only appears once a
 * specific landmark is selected (while marking a targeted existing landmark,
 * `mark_has_target`, or in modify). Whichever of MARK/MODIFY is engaged
 * swaps its label to "CANCEL" (red) — click it to leave the mode; blue
 * "MARK"/"MODIFY" the rest of the time. */
export const set_toolbar_mode = (
  buttons,
  mode,
  { mark_has_target = false } = {}
) => {
  const browse = mode === 'browse';
  const mark = mode === 'mark';
  const modify = mode === 'modify';

  show(buttons.mark, browse || mark);
  buttons.mark.textContent = mark ? 'CANCEL' : 'MARK';
  buttons.mark.style.color = mark ? CANCEL_COLOR : 'blue';

  show(buttons.modify, modify || (mark && mark_has_target));
  buttons.modify.textContent = modify ? 'CANCEL' : 'MODIFY';
  buttons.modify.style.color = modify ? CANCEL_COLOR : 'blue';

  show(buttons.save, mark || modify);
};

/** Blue + clickable once there's something for SAVE to actually commit (e.g.
 * a drawn-but-unsaved point in 'mark', or a tentatively-typed rename); gray
 * and inert otherwise, so an inactive SAVE reads as — and behaves as —
 * non-clickable (blue = clickable). */
export const set_save_button_active = (buttons, active) => {
  buttons.save.style.color = active ? 'blue' : 'gray';
  buttons.save.style.cursor = active ? 'pointer' : 'default';
  buttons.save.style.pointerEvents = active ? 'auto' : 'none';
};

export const set_del_button_visible = (buttons, visible) => {
  show(buttons.del, visible);
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
export const register_landmark_keyboard_shortcuts = (
  { on_mark_toggle, on_save, on_cancel, on_delete },
  target = document
) => {
  const handler = (event) => {
    if (ignores_landmark_shortcut(event)) return;
    const key = event.key?.toLowerCase();

    // 'l' (not 'm') starts a landmark: Jupyter reserves 'm' for "make cell
    // markdown". Enter (and 's') saves.
    if (key === 'l') {
      event.preventDefault();
      on_mark_toggle();
    } else if (key === 's' || key === 'enter') {
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

  target.addEventListener('keydown', handler);
  return () => target.removeEventListener('keydown', handler);
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

/** A CELL/LNDMRK/TRX-style layer-visibility toggle — copied directly from
 * Landscape's own button pattern (`js/ui/text_buttons.js`'s `make_button`/
 * `toggle_visible_button`): a plain clickable text label, blue when active
 * and gray when not, with no separate checkbox/checkmark — the text color
 * *is* the state, read directly off the element by whatever else needs to
 * sync with it (see `set_toggle_active`). `on_toggle(active)` fires on click
 * with the new state. */
export const make_toggle_button = (
  label_text,
  { active = true, disabled = false, on_toggle } = {}
) => {
  const button = document.createElement('div');
  button.textContent = label_text;
  button.style.fontSize = '11px';
  button.style.fontWeight = '700';
  button.style.userSelect = 'none';
  button.style.cursor = disabled ? 'default' : 'pointer';
  button.style.color = disabled ? '#d3d3d3' : active ? 'blue' : 'gray';

  if (!disabled) {
    button.addEventListener('click', () => {
      const next_active = button.style.color !== 'blue';
      set_toggle_active(button, next_active);
      on_toggle?.(next_active);
    });
  }

  return button;
};

export function set_toggle_active(button, active) {
  button.style.color = active ? 'blue' : 'gray';
}

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
 * existing landmark marker is clicked to target a landmark.
 *
 * - `on_input(value)` fires on every keystroke — for live UI feedback (e.g.
 *   lighting up SAVE) without committing anything.
 * - `on_commit(value, committed)` fires on Enter (`committed = true`) and on
 *   blur (`committed = false`). A rename should only actually apply on an
 *   explicit commit (Enter, or the SAVE button) — never on blur — so the
 *   caller uses `committed` to decide whether to stage or write through.
 *
 * An empty value means "back to auto-numbering", only meaningful in 'mark'. */
export const make_label_input = ({ on_input, on_commit }) => {
  const input = document.createElement('input');
  input.type = 'text';
  input.style.width = '60px';
  input.style.height = '18px';
  input.style.fontSize = '10px';
  input.style.padding = '1px 4px';
  input.style.marginTop = '3px';
  input.style.boxSizing = 'border-box';
  input.style.border = '1px solid #d3d3d3';
  input.style.borderRadius = '3px';
  input.style.display = 'none';
  input.title =
    'Landmark name — click a LNDMRK bar or an existing marker to target one';

  input.addEventListener('input', () => on_input?.(input.value.trim()));
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    on_commit(input.value.trim(), true);
    input.blur();
  });
  input.addEventListener('blur', () => on_commit(input.value.trim(), false));

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
