import { IconLayer } from 'deck.gl';

/**
 * Pins: points of interest on the tissue, one per Snapshot (see ui/pins.js).
 *
 * Each pin sits at the center of its Snapshot's view, in the same coordinates as
 * the Landscape's camera target; hovering shows its name and memo, and clicking
 * opens its view.
 */

// A map pin in Celldega blue, its tip at the point.
const PIN_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="64" viewBox="0 0 24 32">' +
  '<path d="M12 1C6 1 1.5 5.4 1.5 11.2C1.5 19 12 31 12 31S22.5 19 22.5 11.2C22.5 5.4 18 1 12 1Z" ' +
  'fill="#2c7fb8" stroke="white" stroke-width="1.6"/>' +
  '<circle cx="12" cy="11" r="4" fill="white"/></svg>';

export const PIN_ICON = {
  url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(PIN_SVG)}`,
  width: 48,
  height: 64,
  anchorY: 64,
  mask: false,
};

const escape_text = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (char) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[char]
  );

/**
 * A pin's card, as HTML: its Snapshot's name, its memo (why the pin is there) and a
 * preview of its view. The pin's tooltip on the tissue and its row in the pins list
 * (ui/pins.js) both show it.
 *
 * @param {object} pin - `{name, description, thumb}`; `thumb` is a base64 JPEG.
 * @returns {string}
 */
export const pin_card_html = (pin) => {
  const memo = pin?.description
    ? `<div style="white-space: pre-wrap; margin-top: 2px;">${escape_text(pin.description)}</div>`
    : '';
  // Only plain base64 goes into the image's src.
  const preview =
    typeof pin?.thumb === 'string' && /^[A-Za-z0-9+/]+=*$/.test(pin.thumb)
      ? `<img src="data:image/jpeg;base64,${pin.thumb}" alt="" style="display: block; max-width: 200px; max-height: 200px; margin-top: 4px; border: 1px solid #d3d3d3;">`
      : '';
  return `<div><b>${escape_text(pin?.name || 'Snapshot')}</b></div>${memo}${preview}`;
};

/** Pins with a usable position (`target` is [x, y] in tissue coordinates). */
export const valid_pins = (pins) =>
  (Array.isArray(pins) ? pins : []).filter(
    (pin) =>
      Array.isArray(pin?.target) &&
      pin.target.length >= 2 &&
      Number.isFinite(Number(pin.target[0])) &&
      Number.isFinite(Number(pin.target[1]))
  );

/**
 * @param {object[]} pins - `{name, description, target: [x, y], snapshot}`.
 * @param {(pin: object) => void} on_click
 * @param {boolean} visible
 */
export const make_pin_layer = (pins, on_click, visible = false) =>
  new IconLayer({
    id: 'pin-layer',
    data: valid_pins(pins),
    visible,
    pickable: true,
    getIcon: () => PIN_ICON,
    getPosition: (pin) => [Number(pin.target[0]), Number(pin.target[1])],
    getSize: 30,
    sizeUnits: 'pixels',
    onClick: (info) => {
      if (info?.object) on_click(info.object);
      return true;
    },
  });
