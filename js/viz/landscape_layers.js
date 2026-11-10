import { calc_viewport } from '../deck-gl/core/calc_viewport';
import { new_toggle_cell_layer_visibility } from '../deck-gl/layers/cell_layer';
import {
  toggle_visibility_image_layers,
  toggle_visibility_single_image_layer,
} from '../deck-gl/layers/image_layers';
import { toggle_nbhd_layer_visibility } from '../deck-gl/layers/nbhd_layer';
import { toggle_path_layer_visibility } from '../deck-gl/layers/path_layer';
import { toggle_trx_layer_visibility } from '../deck-gl/layers/trx_layer';
import { get_aligned_he } from '../global_variables/image_info';
import { toggle_slider } from '../ui/sliders';
import { sync_trx_button, trx_forced_size_scale } from '../ui/trx_handle';
import { refresh_layer } from '../utils/refresh_layer';

const LAYERS = {
  cells: 'cell_layer',
  transcripts: 'trx_layer',
  neighborhoods: 'nbhd_layer',
};
const object = (value) =>
  value && typeof value === 'object' && !Array.isArray(value);
const number = (value, max) =>
  typeof value === 'number' &&
  Number.isFinite(value) &&
  value >= 0 &&
  value <= max;

export const get_landscape_layers = (state) => {
  const layers = state.layers_obj;
  if (!layers) return {};
  const channels = Object.fromEntries(
    (state.img?.image_layer_sliders || []).map((slider) => {
      const layer = (layers.image_layers || []).find(
        (l) =>
          l.props.imageButtonName === slider.name ||
          l.id.startsWith(slider.name)
      );
      return [
        slider.name,
        {
          visible: layer?.props.channelVisible !== false,
          intensity: Number(slider.value),
        },
      ];
    })
  );
  const sliders = {};
  for (const key of ['cell', 'nbhd']) {
    if (state.sliders?.[key]) sliders[key] = Number(state.sliders[key].value);
  }
  if (state.sliders?.trx) {
    sliders.trx = state.trx_slider_values
      ? {
          ...state.trx_slider_values,
          [state.trx_slider_mode]: Number(state.sliders.trx.value),
        }
      : { value: Number(state.sliders.trx.value) };
  }
  // Neighborhoods report NBHD mode (what the setter sets): the neighborhood layer
  // is always created visible, so its own flag says nothing about the view.
  const nbhd_mode = state.obs_store.viz_nbhd_layer?.get?.();
  return {
    layers: {
      image: Boolean(state.obs_store.viz_image_layers?.get()),
      ...Object.fromEntries(
        Object.entries(LAYERS)
          .filter(([, key]) => layers[key])
          .map(([name, key]) => [
            name,
            name === 'neighborhoods' && typeof nbhd_mode === 'boolean'
              ? nbhd_mode
              : layers[key].props.visible !== false,
          ])
      ),
    },
    channels,
    sliders,
    image_source: state.img?.image_source || 'primary',
  };
};

export const validate_landscape_layers = (state, changes) => {
  if ('layers' in changes) {
    if (!object(changes.layers)) throw new Error('layers must be an object');
    for (const [key, value] of Object.entries(changes.layers)) {
      if (
        !['image', ...Object.keys(LAYERS)].includes(key) ||
        typeof value !== 'boolean'
      ) {
        throw new Error(`invalid layer setting: ${key}`);
      }
      if (key !== 'image' && !state.layers_obj?.[LAYERS[key]])
        throw new Error(`layer unavailable: ${key}`);
    }
  }
  if ('channels' in changes) {
    if (!object(changes.channels))
      throw new Error('channels must be an object');
    const names = new Set(
      (state.img?.image_layer_sliders || []).map((s) => s.name)
    );
    for (const [name, settings] of Object.entries(changes.channels)) {
      if (!names.has(name)) throw new Error(`unknown image channel: ${name}`);
      if (
        !object(settings) ||
        Object.keys(settings).some(
          (k) => !['visible', 'intensity'].includes(k)
        ) ||
        ('visible' in settings && typeof settings.visible !== 'boolean') ||
        ('intensity' in settings && !number(settings.intensity, 100))
      ) {
        throw new Error(`invalid channel settings: ${name}`);
      }
    }
  }
  if ('sliders' in changes) {
    if (!object(changes.sliders)) throw new Error('sliders must be an object');
    for (const [key, value] of Object.entries(changes.sliders)) {
      if (!['cell', 'trx', 'nbhd'].includes(key) || !state.sliders?.[key])
        throw new Error(`slider unavailable: ${key}`);
      if (key === 'trx') {
        const modes = state.trx_slider_values ? ['size', 'opacity'] : ['value'];
        if (
          !object(value) ||
          Object.keys(value).some(
            (mode) =>
              !modes.includes(mode) ||
              !number(
                value[mode],
                mode === 'size'
                  ? 100 * trx_forced_size_scale(state)
                  : mode === 'opacity'
                    ? 150
                    : 100
              )
          )
        ) {
          throw new Error('invalid transcript slider settings');
        }
      } else if (!number(value, 100))
        throw new Error(`${key} slider must be between 0 and 100`);
    }
  }
  if (
    'image_source' in changes &&
    (!['primary', 'he'].includes(changes.image_source) ||
      (changes.image_source === 'he' && !get_aligned_he(state.img)))
  ) {
    throw new Error(`image source unavailable: ${changes.image_source}`);
  }
};

/** Apply through the rendering helpers and slider callbacks used by the UI. */
export const apply_landscape_layers = async (state, context, changes) => {
  const keys = ['layers', 'channels', 'sliders', 'image_source'].filter(
    (key) => key in changes
  );
  if (!keys.length) return [];
  const { layers_obj: layers, deck } = context;
  const requested = changes.layers || {};
  if ('image_source' in changes) {
    state.img.image_source = changes.image_source;
    layers.image_source = changes.image_source;
    state.update_image_source_control?.();
  }
  if ('image' in requested) {
    state.img_layer_visible = requested.image;
    state.obs_store.viz_image_layers.set(requested.image);
    state.obs_store.viz_background_layer?.set(requested.image);
  }
  const setters = {
    cells: new_toggle_cell_layer_visibility,
    transcripts: toggle_trx_layer_visibility,
    neighborhoods: toggle_nbhd_layer_visibility,
  };
  const buttons = { cells: 'cell', transcripts: 'trx', neighborhoods: 'nbhd' };
  for (const [key, set] of Object.entries(setters)) {
    if (!(key in requested)) continue;
    const visible = requested[key];
    set(layers, visible);
    if (key === 'cells' && layers.path_layer)
      toggle_path_layer_visibility(layers, visible);
    if (key === 'neighborhoods') state.obs_store.viz_nbhd_layer?.set(visible);
    if (visible && key !== 'neighborhoods')
      state.obs_store.viz_edit_layer?.set(false);
    state.buttons?.buttons?.[buttons[key]]?.style(
      'color',
      visible ? 'blue' : 'gray'
    );
    toggle_slider(state.sliders?.[buttons[key]], visible);
    refresh_layer(state, layers, LAYERS[key]);
  }
  if ('transcripts' in requested) {
    state.trx_forced = requested.transcripts && state.trx_zone === 'forceable';
    if (state.trx_forced && state.last_viewport_params) {
      await calc_viewport(state.last_viewport_params, deck, layers, state);
    }
    sync_trx_button(state, layers);
  }
  if ('image' in requested || changes.image_source) {
    toggle_visibility_image_layers(
      layers,
      state.obs_store.viz_image_layers.get(),
      true
    );
  }
  for (const [name, settings] of Object.entries(changes.channels || {})) {
    const slider = state.img.image_layer_sliders.find((s) => s.name === name);
    // Each callback replaces shared image layers; finish it before the next channel.
    // eslint-disable-next-line no-await-in-loop
    if ('intensity' in settings) await slider.apply_value(settings.intensity);
    if ('visible' in settings) {
      toggle_visibility_single_image_layer(layers, name, settings.visible);
      state.buttons?.buttons?.[name.toLowerCase()]?.style(
        'color',
        settings.visible ? 'blue' : 'gray'
      );
      toggle_slider(
        slider,
        settings.visible && state.obs_store.viz_image_layers.get()
      );
    }
  }
  if (changes.channels || changes.image_source || 'image' in requested) {
    toggle_visibility_image_layers(
      layers,
      state.obs_store.viz_image_layers.get(),
      true
    );
    refresh_layer(state, layers, 'image_layers');
  }
  for (const [key, value] of Object.entries(changes.sliders || {})) {
    if (key === 'trx' && state.trx_slider_values) {
      Object.assign(state.trx_slider_values, value);
      if (state.trx_slider_mode in value)
        // eslint-disable-next-line no-await-in-loop -- callbacks update shared render state
        await state.sliders.trx.apply_value(value[state.trx_slider_mode]);
    } else
      // eslint-disable-next-line no-await-in-loop -- callbacks update shared render state
      await state.sliders[key].apply_value(key === 'trx' ? value.value : value);
  }
  return keys.map((key) => `updated ${key}`);
};
