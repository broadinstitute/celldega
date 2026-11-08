import { toggle_visibility_image_layers } from '../deck-gl/layers/image_layers';
import { get_aligned_he } from '../global_variables/image_info';
import { refresh_layer } from '../utils/refresh_layer';

// Both views retain the same spatial layers and only swap the image background.
// The selector is appended to `container`, the view-mode row (SPATIAL, IMG, XY).
export const make_image_source_control = (
  viz_state,
  layers_obj,
  container,
  channel_controls
) => {
  const select = document.createElement('select');
  select.setAttribute('aria-label', 'Image source');
  select.title = 'Image source: fluorescence (FLR) or H&E';
  // A text-only select styled like the view-mode buttons beside it.
  Object.assign(select.style, {
    appearance: 'none',
    webkitAppearance: 'none',
    MozAppearance: 'none',
    border: 'none',
    background: 'transparent',
    padding: '0',
    margin: '5px 0 0 5px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif',
    fontSize: '12px',
    fontWeight: 'bold',
    color: 'blue',
    cursor: 'pointer',
    userSelect: 'none',
  });
  for (const [value, text] of [
    ['primary', 'FLR'],
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
  container.appendChild(select);
  viz_state.containers.image_source = select;
  viz_state.update_image_source_control = update;
  update();
  return select;
};
