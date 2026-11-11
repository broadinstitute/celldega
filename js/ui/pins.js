/**
 * PINS: points of interest on the Landscape, from Snapshots (Python: `landscape.pins`).
 *
 * The button shows or hides the pins (`show_pins`); it appears only when there are
 * pins. Pins are drawn on the tissue (not in UMAP or XY). Hovering one shows its
 * Snapshot's name and memo; clicking opens the Snapshot's view.
 *
 * While the pins are shown, a scrolling list of them takes the place of the image
 * channel controls (as the XY axes do): the same pins by name, so the view is led
 * by the Snapshots rather than by image settings.
 */

import { make_pin_layer, valid_pins } from '../deck-gl/layers/pin_layer';
import { refresh_layer } from '../utils/refresh_layer';

import { CONTROL_FONT_SIZE } from './control_style';

const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

const ACTIVE_BACKGROUND = '#e3eef7';

/**
 * @param {{viz_state: object, layers_obj: object, container: HTMLElement|null,
 *   restore: (snapshot: object) => Promise<unknown>}} options - `container` holds
 *   the button (the view-mode row); `restore` opens a saved view (the Landscape's
 *   `restore_snapshot`).
 * @returns {{button: HTMLElement, list: HTMLElement, dispose: () => void}}
 */
export const add_pins_control = ({
  viz_state,
  layers_obj,
  container,
  restore,
}) => {
  const { model } = viz_state;
  const button = document.createElement('div');
  button.className = 'pins_button';
  button.textContent = 'PINS';
  button.setAttribute('role', 'button');
  button.tabIndex = 0;
  Object.assign(button.style, {
    cursor: 'pointer',
    fontSize: CONTROL_FONT_SIZE,
    fontWeight: 'bold',
    userSelect: 'none',
    fontFamily: FONT,
    margin: '5px 0 0 5px',
    flexShrink: '0',
  });
  container?.appendChild(button);

  // The list, in the image controls' place (the same box as the channel list).
  const list = document.createElement('div');
  list.className = 'pins_list';
  Object.assign(list.style, {
    display: 'none',
    width: '135px',
    height: '72px',
    overflowY: 'auto',
    border: '1px solid #d3d3d3',
    marginTop: '3px',
    marginLeft: '2px',
    boxSizing: 'border-box',
    fontFamily: FONT,
  });
  viz_state.containers?.image?.appendChild(list);
  list.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } = list;
    const at_top = scrollTop === 0 && event.deltaY < 0;
    const at_bottom =
      scrollTop + clientHeight >= scrollHeight && event.deltaY > 0;
    if (at_top || at_bottom) event.preventDefault();
  });

  let active = '';
  let open = async () => {};
  const pins = () => valid_pins(model?.get?.('pin_data'));
  const shown = () => Boolean(model?.get?.('show_pins'));
  const in_space = () =>
    (viz_state.obs_store.landscape_view?.get?.() ?? 'spatial') === 'spatial';

  const draw_list = () => {
    list.replaceChildren();
    pins().forEach((pin) => {
      const row = document.createElement('div');
      row.className = 'pins_list_item';
      row.textContent = pin.name || 'Snapshot';
      row.title = pin.description
        ? `${pin.name}\n${pin.description}`
        : pin.name || '';
      row.setAttribute('role', 'button');
      row.tabIndex = 0;
      const is_active = pin.name === active;
      Object.assign(row.style, {
        cursor: 'pointer',
        fontSize: '12px',
        lineHeight: '17px',
        padding: '0 4px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        userSelect: 'none',
        color: is_active ? 'blue' : '#222',
        fontWeight: is_active ? 'bold' : 'normal',
        background: is_active ? ACTIVE_BACKGROUND : '',
      });
      row.addEventListener('click', () => open(pin));
      row.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          open(pin);
        }
      });
      list.appendChild(row);
    });
  };

  open = async (pin) => {
    if (!pin?.snapshot) return;
    active = pin.name;
    button.title = `Opening ${pin.name}…`;
    draw_list();
    try {
      await restore(pin.snapshot);
      button.title = `Opened ${pin.name}`;
    } catch (error) {
      button.title = `Couldn't open ${pin.name}: ${error?.message || error}`;
    }
  };

  const sync = () => {
    const count = pins().length;
    const on = shown() && in_space() && count > 0;
    button.style.display = count ? '' : 'none';
    button.style.color = shown() ? 'blue' : 'gray';
    if (!button.title.startsWith('Open') && !button.title.startsWith("Couldn't"))
      button.title = `${shown() ? 'Hide' : 'Show'} ${count} pinned Snapshot${
        count === 1 ? '' : 's'
      } (hover a pin for its memo; click to open its view)`;
    // The list stands in for the image controls while the pins are shown.
    const { image_controls, image_source } = viz_state.containers || {};
    if (on) {
      [image_controls, image_source].forEach((element) => {
        if (element) element.style.display = 'none';
      });
      viz_state.pins_list_shown = true;
    } else if (viz_state.pins_list_shown) {
      // Give the image controls back (XY hides them again in its own view).
      [image_controls, image_source].forEach((element) => {
        if (element && in_space()) element.style.display = '';
      });
      viz_state.pins_list_shown = false;
    }
    list.style.display = on ? '' : 'none';
    draw_list();
    layers_obj.pin_layer = make_pin_layer(pins(), open, on);
    refresh_layer(viz_state, layers_obj, 'pin_layer');
  };

  const toggle = () => {
    if (typeof model?.set !== 'function') return;
    model.set('show_pins', !shown());
    model.save_changes?.();
    button.title = '';
    sync();
  };
  button.addEventListener('click', toggle);
  button.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggle();
    }
  });

  const events = ['change:pin_data', 'change:show_pins'];
  events.forEach((event) => model?.on?.(event, sync));
  // After the view's own handlers (XY swaps the image controls too).
  const on_view = () => setTimeout(sync, 0);
  const unsubscribe = viz_state.obs_store.landscape_view?.subscribe?.(
    on_view,
    { immediate: false }
  );
  sync();

  return {
    button,
    list,
    dispose: () => {
      events.forEach((event) => model?.off?.(event, sync));
      unsubscribe?.();
      button.remove();
      list.remove();
    },
  };
};
