/**
 * PIC: save a screenshot from a widget's control panel, with a description.
 *
 * The front-end side of `widget.screenshot(description=...)`. Clicking PIC captures
 * the view right away (image + the widget's state), then opens a small dialog for a
 * title and a description. SAVE sends both to Python, which writes the PNG (with the
 * record embedded) and an optional .md explanation, and replies with the path.
 * Without a notebook transport, SAVE downloads the PNG with its saved-view record.
 */

import { snapshot_png } from '../viz/png';

const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

const text_button = (label, title, color = 'gray') => {
  const button = document.createElement('div');
  button.textContent = label;
  button.title = title;
  button.setAttribute('role', 'button');
  button.tabIndex = 0;
  Object.assign(button.style, {
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: 'bold',
    color,
    userSelect: 'none',
    fontFamily: FONT,
    flexShrink: '0',
  });
  return button;
};

/**
 * Add a PIC button next to the widget's logo (in its search row when there is one).
 *
 * @param {HTMLElement} ui_container - The widget's control panel.
 * @param {{model: object, capture: () => ({snapshot: object}|null|
 *   Promise<{snapshot: object}>)}} options - `capture` reads the view now, as a saved
 *   view (image, observed state, replay settings, identity); see viz/snapshot.js.
 * @returns {{button: HTMLElement, on_message: (msg: object) => boolean,
 *   dispose: () => void}} Route custom messages to `on_message` (it returns true
 *   for the ones it handled); call `dispose` on finalize.
 */
export const add_pic_button = (ui_container, { model, capture }) => {
  const button = text_button(
    'PIC',
    'Save a screenshot with a description: a PNG plus what it takes to recreate it'
  );
  const row = ui_container.querySelector('.search_logo_row');
  const logo = (row || ui_container).querySelector('.logo_button');
  if (logo?.parentNode) logo.parentNode.insertBefore(button, logo);
  else ui_container.appendChild(button);
  if (!row) button.style.margin = '5px 6px 0 auto';

  let dialog = null;
  let shot = null;
  let request_id = 0;
  const captured_status =
    typeof model?.send === 'function'
      ? 'The view is captured; saving writes a PNG with replay metadata.'
      : 'The view is captured; saving downloads a PNG with replay metadata.';

  const close = () => {
    dialog?.remove();
    dialog = null;
    shot = null;
  };

  const open = () => {
    close();
    let pending;
    let capture_error;
    try {
      pending = capture();
    } catch (error) {
      capture_error = error;
    }
    shot = pending?.then ? null : pending;
    dialog = document.createElement('div');
    const opened = dialog;
    dialog.className = 'celldega-pic-dialog';
    dialog.setAttribute('role', 'dialog');
    const rect = button.getBoundingClientRect();
    Object.assign(dialog.style, {
      position: 'fixed',
      top: `${Math.round(rect.bottom + 6)}px`,
      left: `${Math.round(Math.max(8, rect.right - 300))}px`,
      width: '300px',
      zIndex: '10000',
      background: 'white',
      border: '1px solid #d3d3d3',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
      padding: '8px',
      fontFamily: FONT,
      fontSize: '12px',
      boxSizing: 'border-box',
    });

    const field = (tag, placeholder) => {
      const input = document.createElement(tag);
      input.placeholder = placeholder;
      Object.assign(input.style, {
        width: '100%',
        boxSizing: 'border-box',
        fontFamily: FONT,
        fontSize: '12px',
        marginBottom: '6px',
        padding: '4px',
      });
      return input;
    };
    const title = field('input', 'Title (optional)');
    const description = field(
      'textarea',
      'What are you looking at, and why is it interesting?'
    );
    description.rows = 4;
    description.style.resize = 'vertical';

    const status = document.createElement('div');
    status.className = 'celldega-pic-status';
    status.style.color = '#8a929b';
    status.style.minHeight = '14px';
    status.textContent = shot
      ? captured_status
      : 'Nothing to capture: the view may not be ready yet.';
    if (capture_error)
      status.textContent = `Capture failed: ${capture_error.message}`;
    if (pending?.then) {
      status.textContent = 'Capturing…';
      pending
        .then((result) => {
          if (dialog !== opened) return;
          shot = result;
          status.textContent = captured_status;
        })
        .catch((error) => {
          if (dialog === opened)
            status.textContent = `Capture failed: ${error.message}`;
        });
    }

    const actions = document.createElement('div');
    Object.assign(actions.style, {
      display: 'flex',
      justifyContent: 'flex-end',
      gap: '14px',
      marginTop: '4px',
    });
    const save = text_button(
      'SAVE',
      'Save the screenshot (Ctrl/Cmd+Enter)',
      '#2c7fb8'
    );
    const cancel = text_button('CANCEL', 'Close without saving (Esc)');
    actions.append(cancel, save);
    dialog.append(title, description, status, actions);
    document.body.appendChild(dialog);
    description.focus();

    const submit = () => {
      if (!shot) return;
      if (typeof model?.send !== 'function') {
        if (!shot.snapshot) {
          status.textContent = 'This visualization cannot export a saved view';
          return;
        }
        const saved = {
          ...shot.snapshot,
          description: description.value.trim(),
          title: title.value.trim(),
          author: 'you',
        };
        let url;
        try {
          url = URL.createObjectURL(snapshot_png(saved, { title: title.value.trim() }));
        } catch (error) {
          status.textContent = `Not saved: ${error.message}`;
          return;
        }
        const link = document.createElement('a');
        link.href = url;
        link.download = 'celldega-view.png';
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        status.textContent =
          'Downloaded saved view PNG (including replay settings)';
        return;
      }
      request_id += 1;
      model.send({
        event: 'pic',
        id: request_id,
        title: title.value.trim(),
        description: description.value.trim(),
        ...shot,
      });
      status.style.color = '#8a929b';
      status.textContent = 'Saving…';
      save.style.pointerEvents = 'none';
    };
    save.addEventListener('click', submit);
    cancel.addEventListener('click', close);
    dialog.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') close();
      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) submit();
      // Keep typing out of the notebook's keyboard shortcuts.
      event.stopPropagation();
    });
  };

  button.addEventListener('click', open);
  button.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open();
    }
  });

  /** Python's reply: pic_saved {id, path} or pic_error {id, error}. */
  const on_message = (msg) => {
    if (msg?.event !== 'pic_saved' && msg?.event !== 'pic_error') return false;
    const status = dialog?.querySelector('.celldega-pic-status');
    if (!status || msg.id !== request_id) return true;
    if (msg.event === 'pic_saved') {
      status.style.color = '#2c7fb8';
      status.textContent = `Saved ${msg.path}`;
      setTimeout(close, 1500);
    } else {
      status.style.color = '#c0392b';
      status.textContent = `Not saved: ${msg.error}`;
      const save = [...dialog.querySelectorAll('[role="button"]')].find(
        (b) => b.textContent === 'SAVE'
      );
      if (save) save.style.pointerEvents = '';
    }
    return true;
  };

  return {
    button,
    on_message,
    dispose: () => {
      close();
      button.remove();
    },
  };
};
