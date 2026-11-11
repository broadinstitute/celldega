/* global require */

// PINS: Snapshots pinned on the Landscape; a pin opens its Snapshot's view.
const fs = require('fs');
const path = require('path');

const strip = (file) =>
  fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

class IconLayer {
  constructor(props) {
    this.props = props;
    this.id = props.id;
  }
}

const load = () =>
  new Function(
    'IconLayer',
    'refresh_layer',
    `${strip('../ui/control_style.js')}
     ${strip('../deck-gl/layers/pin_layer.js')}
     ${strip('../ui/pins.js')}
     return { add_pins_control, valid_pins, PIN_ICON };`
  );

const observable = (value) => {
  const subscribers = new Set();
  return {
    get: () => value,
    set: (next) => {
      value = next;
      subscribers.forEach((fn) => fn(value));
    },
    subscribe: (fn) => {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
  };
};

const PIN = {
  name: 'Glomerulus',
  description: 'Podocytes around the tuft.',
  target: [10, 20],
  snapshot: { schema: 'celldega.view', kind: 'landscape', state: {} },
};

const setup = (pins = [PIN], show = false) => {
  const refresh_layer = jest.fn();
  const api = load()(IconLayer, refresh_layer);
  const state = { pin_data: pins, show_pins: show };
  const listeners = {};
  const model = {
    get: (key) => state[key],
    set: (key, value) => {
      state[key] = value;
      (listeners[`change:${key}`] || []).forEach((fn) => fn());
    },
    save_changes: jest.fn(),
    on: (event, fn) => {
      (listeners[event] ||= []).push(fn);
    },
    off: jest.fn(),
  };
  const viz_state = {
    model,
    obs_store: { landscape_view: observable('spatial') },
  };
  const layers_obj = {};
  const container = document.createElement('div');
  const restore = jest.fn(async () => ['restored']);
  const control = api.add_pins_control({
    viz_state,
    layers_obj,
    container,
    restore,
  });
  return { api, model, viz_state, layers_obj, control, restore, refresh_layer };
};

describe('PINS', () => {
  test('the button appears only with pins and toggles them', () => {
    const empty = setup([]);
    expect(empty.control.button.style.display).toBe('none');

    const { control, model, layers_obj, refresh_layer } = setup();
    expect(control.button.style.display).toBe('');
    expect(control.button.textContent).toBe('PINS');
    expect(layers_obj.pin_layer.props.visible).toBe(false);
    control.button.click();
    expect(model.get('show_pins')).toBe(true);
    expect(control.button.style.color).toBe('blue');
    expect(layers_obj.pin_layer.props.visible).toBe(true);
    expect(refresh_layer).toHaveBeenLastCalledWith(
      expect.anything(),
      layers_obj,
      'pin_layer'
    );
  });

  test('pins sit at their view center and open their view on click', async () => {
    const { layers_obj, restore } = setup([PIN], true);
    const layer = layers_obj.pin_layer;
    expect(layer.id).toBe('pin-layer');
    expect(layer.props.getPosition(PIN)).toEqual([10, 20]);
    expect(layer.props.pickable).toBe(true);
    layer.props.onClick({ object: PIN });
    await Promise.resolve();
    expect(restore).toHaveBeenCalledWith(PIN.snapshot);
  });

  test('pins show on the tissue only, not in UMAP or XY', async () => {
    const { viz_state, layers_obj } = setup([PIN], true);
    const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
    viz_state.obs_store.landscape_view.set('umap');
    await tick();
    expect(layers_obj.pin_layer.props.visible).toBe(false);
    viz_state.obs_store.landscape_view.set('spatial');
    await tick();
    expect(layers_obj.pin_layer.props.visible).toBe(true);
  });

  test('while shown, a list of the pins replaces the image controls', async () => {
    const image = document.createElement('div');
    const image_controls = document.createElement('div');
    image.appendChild(image_controls);
    const refresh_layer = jest.fn();
    const api = load()(IconLayer, refresh_layer);
    const state = {
      pin_data: [PIN, { ...PIN, name: 'Medulla', target: [3, 4] }],
      show_pins: false,
    };
    const model = {
      get: (key) => state[key],
      set: (key, value) => {
        state[key] = value;
      },
      save_changes: jest.fn(),
      on: jest.fn(),
      off: jest.fn(),
    };
    const restore = jest.fn(async () => []);
    const control = api.add_pins_control({
      viz_state: {
        model,
        obs_store: { landscape_view: observable('spatial') },
        containers: { image, image_controls },
      },
      layers_obj: {},
      container: document.createElement('div'),
      restore,
    });
    expect(control.list.parentNode).toBe(image);
    expect(control.list.style.display).toBe('none');
    control.button.click();
    expect(control.list.style.display).toBe('');
    expect(image_controls.style.display).toBe('none');
    const rows = [...control.list.querySelectorAll('.pins_list_item')];
    expect(rows.map((row) => row.textContent)).toEqual([
      'Glomerulus',
      'Medulla',
    ]);
    expect(rows[0].title).toBe('Glomerulus\nPodocytes around the tuft.');
    rows[1].click();
    await Promise.resolve();
    expect(restore).toHaveBeenCalledWith(PIN.snapshot);
    // The opened pin is marked; hiding the pins gives the image controls back.
    expect(
      control.list.querySelectorAll('.pins_list_item')[1].style.color
    ).toBe('blue');
    control.button.click();
    expect(control.list.style.display).toBe('none');
    expect(image_controls.style.display).toBe('');
  });

  test('pins without a position are left out', () => {
    const { api } = setup();
    expect(
      api.valid_pins([PIN, { name: 'x' }, { target: ['a', 1] }, null])
    ).toEqual([PIN]);
  });
});

describe('view-mode menu', () => {
  const { collapse_view_modes } = new Function(
    `${strip('../ui/view_mode_menu.js')}\nreturn { collapse_view_modes };`
  )();

  const make = () => {
    const row = document.createElement('div');
    const button = (text) => {
      const el = document.createElement('div');
      el.textContent = text;
      row.appendChild(el);
      return el;
    };
    const umap = button('UMAP');
    const spatial = button('SPATIAL');
    const img = button('IMG');
    const xy = button('XY');
    const view = observable('spatial');
    const viz_state = {
      buttons: { buttons: { spatial: { node: () => spatial }, umap, xy } },
      obs_store: { landscape_view: view },
    };
    collapse_view_modes(viz_state, row);
    return { row, spatial, umap, xy, img, view };
  };

  test('only the current mode shows; the caret lists the others', () => {
    const { row, spatial, umap, xy, img } = make();
    const menu = row.firstChild;
    expect(menu.className).toBe('view_mode_menu');
    expect([...menu.children].map((c) => c.textContent)).toEqual([
      'SPATIAL',
      'UMAP',
      'XY',
      '▾',
    ]);
    expect(row.children[1]).toBe(img); // IMG and the rest stay after the menu
    expect([spatial, umap, xy].map((b) => b.style.display)).toEqual([
      '',
      'none',
      'none',
    ]);
    menu.lastChild.click();
    expect([spatial, umap, xy].map((b) => b.style.display)).toEqual([
      '',
      '',
      '',
    ]);
  });

  test('switching modes shows the new one and closes the menu', async () => {
    const { row, spatial, umap, view } = make();
    row.firstChild.lastChild.click();
    umap.click();
    view.set('umap');
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(umap.style.display).toBe('');
    expect(spatial.style.display).toBe('none');
  });
});
