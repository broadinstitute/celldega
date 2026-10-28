import {
  get_point_cloud_cell_radius,
  refresh_cell_layer_data,
  update_cell_layer_radius,
} from '../deck-gl/layers/cell_layer';
import { update_opacity_single_image_layer } from '../deck-gl/layers/image_layers';
import {
  update_nbhd_cloud_gene_fill_opacity,
  update_nbhd_cloud_manual_fill_opacity,
} from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { update_nbhd_layer_opacity } from '../deck-gl/layers/nbhd_layer';
import { update_trx_layer_radius } from '../deck-gl/layers/trx_layer';
import { rescale_cell_exp_array } from '../global_variables/cell_exp_array';
import { is_orbit_technology } from '../global_variables/image_info';
import { refresh_layer } from '../utils/refresh_layer';
import { register_ui_cleanup } from '../utils/ui_cleanup';

import {
  has_gene_selection,
  is_trx_force_shown,
  sync_trx_slider,
  trx_forced_size_scale,
  update_expression_note,
} from './trx_handle';

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
  const is_point_cloud = is_orbit_technology(
    viz_state.img?.landscape_parameters?.technology
  );

  update_cell_layer_radius(
    layers_obj,
    is_point_cloud
      ? get_point_cloud_cell_radius(viz_state)
      : viz_state.sliders.cell.value / 5,
    viz_state
  );

  refresh_layer(viz_state, layers_obj, 'cell_layer');
};

// Zoomed out, the TRX slider sets the expression drawn at full cell opacity,
// as a percent of the max (100 = the max, the default scaling). Past 100 it
// dims the cells, for genes that many cells express highly.
export const CELL_OPACITY_SLIDER_MAX = 150;
const opacity_slider_scale = (value) => Math.max(1, Number(value)) / 100;

/** Set `cats.cell_exp_scale` and recolor the cells to match. */
const set_cell_exp_scale = (layers_obj, viz_state, scale) => {
  const { cats } = viz_state;
  cats.cell_exp_scale = scale;
  update_expression_note(viz_state);
  if (cats.cat === 'cluster' || viz_state.cell_opacity_frame) return;

  // At most one rescale per frame while dragging.
  viz_state.cell_opacity_frame = requestAnimationFrame(() => {
    viz_state.cell_opacity_frame = null;
    rescale_cell_exp_array(cats);
    refresh_cell_layer_data(layers_obj, viz_state, {
      updateTriggers: {
        getFillColor: [viz_state.selection_token, cats.cell_exp_scale],
      },
    });
    refresh_layer(viz_state, layers_obj, 'cell_layer');
  });
};

const cell_opacity_slider_callback = (layers_obj, viz_state) =>
  set_cell_exp_scale(
    layers_obj,
    viz_state,
    opacity_slider_scale(viz_state.sliders.trx.value)
  );

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

  if (viz_state.trx_slider_mode === 'opacity') {
    cell_opacity_slider_callback(layers_obj, viz_state);
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
      ini_value = is_orbit_technology(
        viz_state.img?.landscape_parameters?.technology
      )
        ? 50
        : layers_obj.cell_layer.props.getRadius * 5;
      callback = () => cell_slider_callback(inst_deck, layers_obj, viz_state);
      break;
    case 'trx':
      // Repurposed as neighborhood-cloud's gene-shapes opacity control --
      // matches gene_fill_opacity's default (0.75 = 75%, see landscape_ist.js)
      // rather than the unrelated legacy per-transcript radius default.
      ini_value = viz_state.nbhd_cloud?.is_nbhd_cloud
        ? 75
        : viz_state.genes.trx_ini_radius * 100;
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

/**
 * TRX slider position for full transcript size in close-up, the top of its
 * range. Gene selections slide to it (see ini_selected_gene_trx_focus).
 */
export const TRX_FOCUS_SLIDER_VALUE = 100;
const TRX_FOCUS_DURATION_MS = 300;

/**
 * Top of the TRX size slider (full transcript size): larger while transcripts
 * are forced at intermediate zoom (see trx_handle.js).
 */
const trx_size_slider_max = (viz_state) =>
  Math.round(
    TRX_FOCUS_SLIDER_VALUE *
      (is_trx_force_shown(viz_state) ? trx_forced_size_scale(viz_state) : 1)
  );

/**
 * Transcript size once the size slider's top changes from `old_max` to
 * `max`: with genes selected, full size stays full size; otherwise the size
 * is kept, within range.
 */
const resize_trx_size = (viz_state, value, old_max, max) =>
  has_gene_selection(viz_state) && value >= old_max
    ? max
    : Math.min(value, max);

/** Ease-in-out cubic on t in [0, 1]. */
const ease_in_out = (t) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/**
 * Enlarge transcripts while a gene is selected, then restore the previous
 * size when the selection clears. Selecting a gene (bar, search, transcript
 * click, or a linked Clustergram) animates the TRX slider to full size, the
 * top of its range, which is larger at intermediate zoom with transcripts
 * forced; full size then stays full size as the view enters or leaves that
 * zoom (see resize_trx_size). Clearing the selection jumps straight back to
 * wherever the slider was before, since every gene's transcripts reappear at
 * that moment and shrinking them all in an animation reads as a glitch.
 * Dragging the slider during the animation stops it, and the user's value
 * wins.
 *
 * Neighborhood-cloud repurposes the TRX slider as an opacity control, so it is
 * left alone there.
 */
export const ini_selected_gene_trx_focus = (
  inst_deck,
  layers_obj,
  viz_state
) => {
  const slider = viz_state.sliders?.trx;
  if (!slider || viz_state.nbhd_cloud?.is_nbhd_cloud) return;

  // Slider value from before the gene was selected; null when not focused.
  let restore_value = null;
  let frame_id = null;

  const cancel_animation = () => {
    if (frame_id !== null) cancelAnimationFrame(frame_id);
    frame_id = null;
  };

  // Zoomed out the slider shows cell opacity, so the transcript size lives in
  // trx_slider_values (see ini_trx_slider_modes) and is applied directly.
  const sliding_size = () => viz_state.trx_slider_mode !== 'opacity';
  const current_size = () =>
    sliding_size() ? Number(slider.value) : viz_state.trx_slider_values.size;

  const apply_value = (value) => {
    if (!layers_obj.trx_layer) return;
    if (sliding_size()) {
      set_slider_value(slider, value);
      trx_slider_callback(inst_deck, layers_obj, viz_state);
    } else {
      viz_state.trx_slider_values.size = value;
      update_trx_layer_radius(layers_obj, value / 100);
    }
  };

  const animate_to = (target) => {
    cancel_animation();
    const start = current_size();
    if (!Number.isFinite(start) || start === target || !sliding_size()) {
      apply_value(target);
      return;
    }
    const start_time = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start_time) / TRX_FOCUS_DURATION_MS);
      apply_value(start + (target - start) * ease_in_out(t));
      frame_id = t < 1 ? requestAnimationFrame(step) : null;
    };
    frame_id = requestAnimationFrame(step);
  };

  // Programmatic value changes don't fire 'input', so this is the user dragging.
  const on_user_input = () => cancel_animation();
  slider.addEventListener('input', on_user_input);

  const unsubscribe = viz_state.obs_store.selected_genes.subscribe(
    (selected_genes) => {
      const focused =
        Array.isArray(selected_genes) && selected_genes.length > 0;
      if (focused && restore_value === null) {
        restore_value = current_size();
        animate_to(trx_size_slider_max(viz_state));
      } else if (!focused && restore_value !== null) {
        // Within range: it may be from intermediate zoom's wider one.
        const target = Math.min(restore_value, trx_size_slider_max(viz_state));
        restore_value = null;
        cancel_animation();
        apply_value(target);
      }
    },
    { immediate: false }
  );

  register_ui_cleanup(viz_state, () => {
    cancel_animation();
    slider.removeEventListener('input', on_user_input);
    unsubscribe?.();
  });
};

/**
 * Widen the TRX size slider while transcripts are forced at intermediate zoom
 * (see trx_handle.js), and narrow it back after, shrinking transcripts that
 * were made larger than the close-up max. Full size with genes selected
 * stays full size (see resize_trx_size).
 */
export const sync_trx_slider_range = (layers_obj, viz_state) => {
  const slider = viz_state.sliders?.trx;
  if (!slider || viz_state.trx_slider_mode !== 'size') return;

  const value = Number(slider.value);
  const old_max = Number(slider.max);
  const max = trx_size_slider_max(viz_state);
  slider.max = String(max);
  const size = resize_trx_size(viz_state, value, old_max, max);
  set_slider_value(slider, size);
  if (size !== value) {
    update_trx_layer_radius(layers_obj, size / 100);
    refresh_layer(viz_state, layers_obj, 'trx_layer');
  }
};

/**
 * Switch the Landscape's TRX slider between its two jobs as the view enters
 * and leaves close-up: transcript size in close-up, cell expression opacity
 * zoomed out (see trx_handle.js). Each job keeps its own slider position, and
 * the opacity applies only zoomed out.
 */
export const ini_trx_slider_modes = (layers_obj, viz_state) => {
  const slider = viz_state.sliders?.trx;
  if (!slider || viz_state.nbhd_cloud?.is_nbhd_cloud) return;

  viz_state.trx_slider_values = { size: Number(slider.value), opacity: 100 };

  const apply_mode = (close_up) => {
    const mode = close_up ? 'size' : 'opacity';
    if (mode !== viz_state.trx_slider_mode) {
      if (viz_state.trx_slider_mode) {
        viz_state.trx_slider_values[viz_state.trx_slider_mode] = Number(
          slider.value
        );
      }
      viz_state.trx_slider_mode = mode;
      const max =
        mode === 'size'
          ? trx_size_slider_max(viz_state)
          : CELL_OPACITY_SLIDER_MAX;
      slider.max = String(max);
      let value = viz_state.trx_slider_values[mode];
      if (mode === 'size') {
        // Saved in close-up's range: the wider one ends before close_up does.
        const size = resize_trx_size(
          viz_state,
          value,
          TRX_FOCUS_SLIDER_VALUE,
          max
        );
        if (size !== value) update_trx_layer_radius(layers_obj, size / 100);
        value = size;
      }
      set_slider_value(slider, value);
      // The opacity scale applies only while the slider shows it, so close-up
      // cells use the full range.
      const scale = mode === 'opacity' ? opacity_slider_scale(value) : 1;
      if ((viz_state.cats.cell_exp_scale ?? 1) !== scale) {
        set_cell_exp_scale(layers_obj, viz_state, scale);
      }
      slider.title =
        mode === 'size' ? 'Transcript size' : 'Cell expression opacity';
      if (mode === 'size') {
        toggle_slider(slider, layers_obj.trx_layer?.props?.visible !== false);
      }
    }
    sync_trx_slider(viz_state);
    update_expression_note(viz_state);
  };
  apply_mode(Boolean(viz_state.close_up));

  // The note's count changes once a new selection's expression has loaded,
  // which is when selected_cats is set.
  const refresh = () => {
    sync_trx_slider(viz_state);
    update_expression_note(viz_state);
  };
  const unsubscribes = [
    viz_state.obs_store.close_up.subscribe(apply_mode, { immediate: false }),
    viz_state.obs_store.selected_genes.subscribe(refresh, { immediate: false }),
    viz_state.obs_store.selected_cats.subscribe(refresh, { immediate: false }),
  ];
  register_ui_cleanup(viz_state, () => {
    cancelAnimationFrame(viz_state.cell_opacity_frame);
    unsubscribes.forEach((unsubscribe) => unsubscribe?.());
  });
};
