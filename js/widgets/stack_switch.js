/**
 * The switch of a stack (Python's `dega.viz.stack`, or a web page's `stack()`):
 * one text button per widget, the shown one in blue. Several visualizations share
 * one place and one is shown at a time; the others stay rendered, hidden, so
 * switching back is instant.
 *
 * In a notebook, each `display_<i>` trait is linked (in the browser) to a widget's
 * `layout.display`, and each `request_<i>` follows a widget's `view_request`: a
 * saved view opened in a widget (a Snapshot card, a pin, a Clerk link) shows it.
 */

import { CONTROL_FONT_SIZE } from '../ui/control_style';

// The Clustergram's text-button colors.
const ACTIVE = '#3355ff';
const INACTIVE = '#9aa0a6';
const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

/**
 * Draw the switch's buttons into `el`.
 * @param {HTMLElement} el
 * @param {string[]} labels
 * @param {(index: number) => void} on_select
 * @returns {{set_active: (index: number) => void, element: HTMLElement}}
 */
export const make_stack_buttons = (el, labels, on_select) => {
  const bar = document.createElement('div');
  bar.className = 'celldega-stack-switch';
  Object.assign(bar.style, {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '2px 4px',
    fontFamily: FONT,
    fontSize: CONTROL_FONT_SIZE,
    fontWeight: 'bold',
    userSelect: 'none',
  });
  const buttons = labels.map((label, index) => {
    if (index > 0) {
      const separator = document.createElement('span');
      separator.textContent = '|';
      separator.style.color = INACTIVE;
      bar.appendChild(separator);
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = String(label).toUpperCase();
    button.title = `Show ${label}`;
    Object.assign(button.style, {
      border: 'none',
      background: 'transparent',
      padding: '0',
      margin: '0',
      font: 'inherit',
      cursor: 'pointer',
      color: INACTIVE,
    });
    button.addEventListener('click', () => on_select(index));
    bar.appendChild(button);
    return button;
  });
  el.appendChild(bar);
  return {
    element: bar,
    set_active: (active) =>
      buttons.forEach((button, index) => {
        button.style.color = index === active ? ACTIVE : INACTIVE;
        button.setAttribute('aria-pressed', String(index === active));
      }),
  };
};

/**
 * Render a notebook stack switch (the `StackSwitch` widget).
 * @returns {() => void} Cleanup.
 */
export const render_stack_switch = ({ model, el }) => {
  const labels = model.get('labels') || [];
  // Requests saved before this view rendered (e.g. when a notebook reopens) are
  // old news: only newer ones bring a widget forward.
  const since = Date.now();
  let controls = null;
  const select = (index) => {
    if (!Number.isInteger(index) || index < 0 || index >= labels.length) return;
    labels.forEach((_, i) => {
      model.set(`display_${i}`, i === index ? '' : 'none');
    });
    if (model.get('selected') !== index) model.set('selected', index);
    model.save_changes?.();
    controls?.set_active(index);
  };
  controls = make_stack_buttons(el, labels, select);
  controls.set_active(model.get('selected') ?? 0);

  const listeners = [];
  const on = (event, listener) => {
    model.on(event, listener);
    listeners.push([event, listener]);
  };
  on('change:selected', () => select(model.get('selected')));
  labels.forEach((_, index) => {
    on(`change:request_${index}`, () => {
      const request = model.get(`request_${index}`) || {};
      if (!request.id) return;
      if (Number.isFinite(request.at) && request.at < since) return;
      select(index);
    });
  });
  return () => {
    listeners.forEach(([event, listener]) => model.off?.(event, listener));
    controls.element.remove();
  };
};

/**
 * A stack in a web page: a switch above one panel per label, one shown at a time.
 * Render a visualization into each panel, then `watch(index, viz.model)` so a
 * saved view opened in it (e.g. a Clerk link) shows it.
 *
 * @param {HTMLElement} el - Container
 * @param {string[]} labels - One per panel, in switch order
 * @param {{selected?: number}} [options]
 * @returns {{panels: HTMLElement[], select: (index: number) => void,
 *   watch: (index: number, model: object) => void, selected: () => number}}
 */
export const stack = (el, labels, { selected = 0 } = {}) => {
  let current = selected;
  let controls = null;
  const panels = labels.map(() => {
    const panel = document.createElement('div');
    panel.className = 'celldega-stack-panel';
    return panel;
  });
  const select = (index) => {
    if (!Number.isInteger(index) || index < 0 || index >= panels.length) return;
    current = index;
    panels.forEach((panel, i) => {
      panel.style.display = i === index ? '' : 'none';
    });
    controls?.set_active(index);
  };
  controls = make_stack_buttons(el, labels, select);
  panels.forEach((panel) => el.appendChild(panel));
  select(selected);
  return {
    panels,
    select,
    selected: () => current,
    watch: (index, model) => {
      const since = Date.now();
      model?.on?.('change:view_request', () => {
        const request = model.get('view_request') || {};
        if (request.id && !(Number.isFinite(request.at) && request.at < since))
          select(index);
      });
    },
  };
};
