import { toggle_visibility_image_layers } from '../deck-gl/layers/image_layers';
import { get_aligned_he } from '../global_variables/image_info';
import { refresh_layer } from '../utils/refresh_layer';

import { CONTROL_FONT_SIZE } from './control_style';

const element_of = (button) => button?.node?.() ?? button ?? null;

/**
 * The image as one dropdown in the view-mode row: IMG / NONE, or FLR / H&E / NONE
 * when an aligned H&E is available. Styled like the view-mode dropdown beside it.
 *
 * The IMG button keeps its handler and state (hidden): NONE and showing an image
 * click it, so e.g. showing an image from the UMAP returns to SPATIAL as before.
 * The dropdown is blue while the image is on, gray while it's off or not drawn
 * (UMAP). Both sources keep the same spatial layers and only swap the image.
 *
 * Without an IMG button (e.g. Chromium) it's just the FLR / H&E choice, shown
 * only when there is an H&E.
 *
 * @param {HTMLElement} container - The view-mode row, holding the IMG button.
 * @param {HTMLElement} channel_controls - Fluorescence channel controls (hidden
 *   for H&E).
 */
export const make_image_source_control = (
  viz_state,
  layers_obj,
  container,
  channel_controls
) => {
  const img_button = element_of(viz_state.buttons?.buttons?.img);
  const combined = Boolean(img_button && img_button.parentNode === container);
  const select = document.createElement('select');
  select.className = 'image_source_select';
  select.setAttribute('aria-label', 'Image');
  select.title = combined
    ? 'Image: show it (or which one), or NONE'
    : 'Image source: fluorescence (FLR) or H&E';
  // A text-only select styled like the view-mode dropdown beside it.
  Object.assign(select.style, {
    appearance: 'none',
    webkitAppearance: 'none',
    MozAppearance: 'none',
    border: 'none',
    // No focus ring or shadow after a click, so it reads as plain text.
    outline: 'none',
    boxShadow: 'none',
    background: 'transparent',
    padding: '0',
    margin: '5px 0 0 5px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif',
    fontSize: CONTROL_FONT_SIZE,
    fontWeight: 'bold',
    color: 'blue',
    cursor: 'pointer',
    userSelect: 'none',
  });
  const option = (value, text) => {
    const element = document.createElement('option');
    element.value = value;
    element.textContent = text;
    select.appendChild(element);
    return element;
  };
  const primary = option('primary', 'FLR');
  const he = option('he', 'H&E');
  if (combined) option('none', 'NONE');

  const image_on = () => img_button.style.color === 'blue';
  const update = () => {
    const has_he = Boolean(get_aligned_he(viz_state.img));
    primary.textContent = has_he || !combined ? 'FLR' : 'IMG';
    he.hidden = !has_he;
    he.disabled = !has_he;
    const source = has_he ? viz_state.img.image_source || 'primary' : 'primary';
    layers_obj.image_source = source;
    channel_controls.style.display = source === 'he' ? 'none' : '';
    if (combined) {
      // NONE when switched off; the source (gray) while the UMAP hides it.
      const off = viz_state.img_layer_visible === false;
      select.value = off ? 'none' : source;
      select.style.color = !off && image_on() ? 'blue' : 'gray';
    } else {
      select.hidden = !has_he;
      select.value = source;
    }
  };
  const set_source = (source) => {
    if ((viz_state.img.image_source || 'primary') === source) return;
    viz_state.img.image_source = source;
    update();
    toggle_visibility_image_layers(
      layers_obj,
      viz_state.obs_store.viz_image_layers.get(),
      true
    );
    refresh_layer(viz_state, layers_obj, 'image_layers');
  };
  select.addEventListener('change', () => {
    const choice = select.value;
    if (!combined) {
      set_source(choice);
      return;
    }
    if (choice === 'none') {
      // Off; while the UMAP hides it, remember it for SPATIAL.
      if (image_on()) img_button.click();
      else viz_state.img_layer_visible = false;
    } else {
      if (get_aligned_he(viz_state.img)) set_source(choice);
      if (!image_on()) img_button.click();
    }
    update();
  });

  if (combined) {
    // The IMG button stays the source of truth (view switches, saved views and
    // dataset switches all set its color); the dropdown follows it.
    img_button.style.display = 'none';
    container.insertBefore(select, img_button);
    if (typeof MutationObserver === 'function') {
      new MutationObserver(() => update()).observe(img_button, {
        attributes: true,
        attributeFilter: ['style'],
      });
    }
  } else {
    container.appendChild(select);
  }
  viz_state.containers.image_source = select;
  viz_state.update_image_source_control = update;
  update();
  return select;
};
