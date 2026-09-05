import { update_cell_layer_radius } from '../deck-gl/layers/cell_layer';
import { update_opacity_single_image_layer } from '../deck-gl/layers/image_layers';
import {
  update_nbhd_cloud_gene_fill_opacity,
  update_nbhd_cloud_manual_fill_opacity,
} from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { update_nbhd_layer_opacity } from '../deck-gl/layers/nbhd_layer';
import { update_trx_layer_radius } from '../deck-gl/layers/trx_layer';
import { refresh_layer } from '../utils/refresh_layer';

const clamp_to_byte = (value) => {
  return Math.max(0, Math.min(255, Math.round(value)));
};

const clamp_percent = (value) => {
  return Math.max(0, Math.min(100, value));
};

let slider_styles_injected = false;

const slider_style_block = `
.slider {
  --c: #1e90ff;
  --track: #e5e5e5;
  --thumb-border: #9aa0a6;
  --val: 50%;

  -webkit-appearance: none;
  appearance: none;
  width: 75px;
  height: 20px;
  background: transparent;
  margin: 0;
}

.slider:disabled {
  --c: #c5c5c5;
  --thumb-border: #d0d0d0;
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.slider::-webkit-slider-runnable-track {
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(
    to right,
    var(--c) 0 var(--val),
    var(--track) var(--val) 100%
  );
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--c);
  border: 2px solid var(--thumb-border);
  margin-top: -4px;
  cursor: pointer;
}

.slider:disabled::-webkit-slider-thumb {
  cursor: not-allowed;
}

.slider::-moz-range-track {
  height: 8px;
  border-radius: 999px;
  background: var(--track);
}

.slider::-moz-range-progress {
  height: 8px;
  border-radius: 999px;
  background: var(--c);
}

.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--c);
  border: 2px solid var(--thumb-border);
  cursor: pointer;
}

.slider:disabled::-moz-range-thumb {
  cursor: not-allowed;
}
`;

const ensure_slider_styles = () => {
  if (slider_styles_injected) {
    return;
  }

  if (typeof document === 'undefined') {
    return;
  }

  const style_element = document.createElement('style');
  style_element.textContent = slider_style_block;
  document.head.appendChild(style_element);
  slider_styles_injected = true;
};

const set_slider_custom_property_defaults = (slider) => {
  if (!slider.style.getPropertyValue('--track')) {
    slider.style.setProperty('--track', '#e5e5e5');
  }

  if (!slider.style.getPropertyValue('--thumb-border')) {
    slider.style.setProperty('--thumb-border', '#9aa0a6');
  }

  if (!slider.style.getPropertyValue('--c')) {
    slider.style.setProperty('--c', '#1e90ff');
  }
};

const update_slider_fill_percent = (slider) => {
  const min_value = Number(slider.min ?? 0);
  const max_value = Number(slider.max ?? 100);
  const slider_value = Number(slider.value ?? min_value);

  const safe_min = Number.isFinite(min_value) ? min_value : 0;
  const safe_max = Number.isFinite(max_value) ? max_value : 100;
  const safe_value = Number.isFinite(slider_value) ? slider_value : safe_min;
  const range = safe_max - safe_min;
  const percent = range === 0 ? 0 : ((safe_value - safe_min) * 100) / range;

  slider.style.setProperty('--val', `${clamp_percent(percent)}%`);
};

const array_to_hex = (components) => {
  if (!components || components.length < 3) {
    return undefined;
  }

  const [r, g, b] = components.slice(0, 3).map((component) => {
    const numeric_value = Number(component);

    if (Number.isNaN(numeric_value)) {
      return '00';
    }

    return clamp_to_byte(numeric_value).toString(16).padStart(2, '0');
  });

  return `#${r}${g}${b}`;
};

const rgb_color_to_hex = (color) => {
  if (!color) {
    return undefined;
  }

  if (Array.isArray(color)) {
    return array_to_hex(color);
  }

  if (typeof ArrayBuffer !== 'undefined' && ArrayBuffer.isView(color)) {
    return array_to_hex(Array.from(color));
  }

  const trimmed_color = String(color).trim();

  if (trimmed_color.startsWith('#')) {
    return trimmed_color;
  }

  const components = trimmed_color.match(/\d+(?:\.\d+)?/g);

  return array_to_hex(components);
};

const set_slider_accent_color = (slider, color) => {
  const hex_color = rgb_color_to_hex(color);

  set_slider_custom_property_defaults(slider);

  if (!hex_color) {
    return;
  }

  slider.style.setProperty('--c', hex_color);
  slider.style.setProperty('accent-color', hex_color);
};

export const make_slider = () => {
  return document.createElement('input');
};

export const set_image_layer_sliders = (img) => {
  img.image_layer_sliders = img.image_info.map((info) => {
    const input = document.createElement('input');
    input.name = info.button_name;
    set_slider_accent_color(input, info.color);
    return input;
  });
};

const cell_slider_callback = async (deck_ist, layers_obj, viz_state) => {
  const scale_down_cell_radius = 5;

  update_cell_layer_radius(
    layers_obj,
    viz_state.sliders.cell.value / scale_down_cell_radius,
    viz_state
  );

  refresh_layer(viz_state, layers_obj, 'cell_layer');
};

const trx_slider_callback = async (deck_ist, layers_obj, viz_state) => {
  // Repurposed for neighborhood-cloud only: an independent opacity control
  // for gene-shapes mode (disabled/enabled opposite the NBHD slider, see
  // sync_nbhd_cloud_opacity_sliders in bar_plot.js), not the legacy
  // per-transcript radius this slot controls for every other technology.
  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    update_nbhd_cloud_gene_fill_opacity(
      viz_state,
      layers_obj,
      viz_state.sliders.trx.value / 100
    );
    refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
    return;
  }

  const scale_down_trx_radius = 100;

  update_trx_layer_radius(
    layers_obj,
    viz_state.sliders.trx.value / scale_down_trx_radius
  );

  refresh_layer(viz_state, layers_obj, 'trx_layer');
};

const nbhd_slider_callback = async (_deck_ist, layers_obj, viz_state) => {
  const opacity = viz_state.sliders.nbhd.value / 100;

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    update_nbhd_cloud_manual_fill_opacity(viz_state, layers_obj, opacity);
    refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
    return;
  }

  update_nbhd_layer_opacity(layers_obj, opacity);

  refresh_layer(viz_state, layers_obj, 'nbhd_layer');
};

export const make_img_layer_slider_callback = (
  name,
  deck_ist,
  layers_obj,
  viz_state
) => {
  return async () => {
    const inst_slider = viz_state.img.image_layer_sliders.filter(
      (slider) => slider.name === name
    )[0];

    // Get the slider value from the event
    const opacity = inst_slider.value / 10;

    // Use the slider value to update the opacity
    update_opacity_single_image_layer(
      viz_state,
      layers_obj,
      name,
      opacity,
      viz_state.img.image_layer_colors
    );

    refresh_layer(viz_state, layers_obj, 'image_layers');
  };
};

export const ini_slider_params = (slider, ini_value, callback) => {
  ensure_slider_styles();

  slider.type = 'range';
  slider.min = '0';
  slider.max = '100';
  slider.value = ini_value;
  slider.classList.add('slider');
  slider.style.width = '75px';

  set_slider_custom_property_defaults(slider);
  update_slider_fill_percent(slider);

  const handle_input = (event) => {
    update_slider_fill_percent(slider);

    if (typeof callback === 'function') {
      callback(event);
    }
  };

  slider.addEventListener('input', handle_input);
};

export const ini_slider = (slider_type, inst_deck, layers_obj, viz_state) => {
  let ini_value;
  let callback;

  const slider = make_slider();

  switch (slider_type) {
    case 'cell':
      ini_value = viz_state.genes.trx_ini_raidus * 100;
      callback = () => cell_slider_callback(inst_deck, layers_obj, viz_state);
      break;
    case 'trx':
      // Repurposed as neighborhood-cloud's gene-shapes opacity control --
      // matches gene_fill_opacity's default (0.75 = 75%, see landscape_ist.js)
      // rather than the unrelated legacy per-transcript radius default.
      ini_value = viz_state.nbhd_cloud?.is_nbhd_cloud
        ? 75
        : viz_state.genes.trx_ini_raidus * 100;
      callback = () => trx_slider_callback(inst_deck, layers_obj, viz_state);
      break;
    case 'nbhd':
      // neighborhood-cloud's manual multiplier defaults to 75% (see
      // landscape_ist.js -- less than fully opaque so cell centroids and
      // overlapping slices stay visible underneath) -- match that here
      // rather than reading the unrelated legacy nbhd_layer's opacity, so
      // the slider's initial position doesn't lie about the actual
      // starting opacity.
      ini_value = viz_state.nbhd_cloud?.is_nbhd_cloud
        ? 75
        : layers_obj.nbhd_layer.props.opacity * 100;
      callback = () => nbhd_slider_callback(inst_deck, layers_obj, viz_state);
      break;

    default:
    // console.log('no match', slider_type)
  }

  ini_slider_params(slider, ini_value, callback);

  // save the slider to viz_state with a property name of slider_type
  viz_state.sliders[slider_type] = slider;
};

/**
 * Initialize a slider that steps through a fixed set of stops rather than the
 * default continuous 0-100 range (e.g. the RANK view slider, whose positions
 * index into precomputed filter levels).
 *
 * @param {HTMLInputElement} slider - Slider element to configure.
 * @param {object} [options] - Range configuration.
 * @param {number} [options.min] - Lowest index.
 * @param {number} [options.max] - Highest index.
 * @param {number} [options.step] - Step between stops.
 * @param {number} [options.value] - Initial index.
 * @param {Function} [options.callback] - Called on input, after the fill repaints.
 * @returns {HTMLInputElement} The configured slider.
 */
export const ini_discrete_slider_params = (slider, options = {}) => {
  const { min = 0, max = 100, step = 1, value = 0, callback } = options;

  ensure_slider_styles();

  slider.type = 'range';
  slider.min = String(min);
  slider.max = String(max);
  slider.step = String(step);
  slider.value = String(value);
  slider.classList.add('slider');
  slider.style.width = '75px';

  set_slider_custom_property_defaults(slider);
  update_slider_fill_percent(slider);

  slider.addEventListener('input', (event) => {
    update_slider_fill_percent(slider);

    if (typeof callback === 'function') {
      callback(event);
    }
  });

  return slider;
};

/**
 * Move a slider programmatically (e.g. a Python-driven trait change), keeping
 * its filled-track styling in sync. Assigning `.value` alone would leave the
 * track painted at the old position.
 *
 * @param {HTMLInputElement} slider - Slider element.
 * @param {number|string} value - New value.
 */
export const set_slider_value = (slider, value) => {
  if (!slider) return;

  slider.value = String(value);
  update_slider_fill_percent(slider);
};

export const toggle_slider = (slider, state) => {
  if (!slider) {
    return;
  }

  slider.disabled = !state;
};
