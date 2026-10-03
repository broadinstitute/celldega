import { toggle_visibility_image_layers } from '../deck-gl/layers/image_layers';
import { get_aligned_he } from '../global_variables/image_info';
import { refresh_layer } from '../utils/refresh_layer';

// Both views retain the same spatial layers and only swap the image background.
export const make_image_source_control = (
  viz_state,
  layers_obj,
  container,
  channel_controls
) => {
  const select = document.createElement('select');
  select.setAttribute('aria-label', 'Image source');
  select.style.cssText = 'font-size:11px;max-width:115px;margin-left:4px';
  for (const [value, text] of [
    ['primary', 'Fluorescence'],
    ['he', 'H&E'],
  ]) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = text;
    select.appendChild(option);
  }
  const update = () => {
    const has_he = Boolean(get_aligned_he(viz_state.img));
    select.hidden = !has_he;
    select.value = has_he ? viz_state.img.image_source || 'primary' : 'primary';
    layers_obj.image_source = select.value;
    channel_controls.style.display = select.value === 'he' ? 'none' : '';
  };
  select.addEventListener('change', () => {
    viz_state.img.image_source = select.value;
    update();
    toggle_visibility_image_layers(
      layers_obj,
      viz_state.obs_store.viz_image_layers.get(),
      true
    );
    refresh_layer(viz_state, layers_obj, 'image_layers');
  });
  container.insertBefore(select, channel_controls);
  viz_state.update_image_source_control = update;
  update();
  return select;
};
