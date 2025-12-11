import { switch_dataset } from './switch_dataset';

/**
 * Creates a small dataset dropdown selector for switching between datasets.
 * @param {Object} viz_state - The visualization state object
 * @param {Object} deck_ist - The deck.gl instance
 * @param {Object} layers_obj - The layers object
 * @returns {HTMLElement} The dropdown container element
 */
export const make_dataset_dropdown = (viz_state, deck_ist, layers_obj) => {
  const base_urls = viz_state.base_urls || [];

  // Don't create dropdown if there's only one or no datasets
  if (base_urls.length <= 1) {
    return null;
  }

  const container = document.createElement('div');
  container.className = 'dataset-dropdown-container';
  container.style.display = 'inline-flex';
  container.style.alignItems = 'center';
  container.style.marginLeft = '5px';
  container.style.marginRight = '5px';
  container.style.position = 'relative';

  const select = document.createElement('select');
  select.className = 'dataset-dropdown';
  select.style.width = '55px';
  select.style.height = '18px';
  select.style.fontSize = '9px';
  select.style.padding = '1px 2px';
  select.style.border = '1px solid #d3d3d3';
  select.style.borderRadius = '3px';
  select.style.backgroundColor = 'white';
  select.style.cursor = 'pointer';
  select.style.outline = 'none';
  select.style.fontFamily =
    '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';
  select.style.transition = 'width 0.15s ease';
  select.title = 'Switch dataset';

  // Calculate max width needed for full labels
  const max_label_length = Math.max(
    ...base_urls.map((d) => (d.label || '').length)
  );
  const expanded_width = Math.min(Math.max(max_label_length * 7 + 20, 80), 150);

  // Add focus/hover styling - expand on focus/mousedown
  select.addEventListener('mousedown', () => {
    select.style.width = `${expanded_width}px`;
  });
  select.addEventListener('focus', () => {
    select.style.borderColor = '#8797ff';
    select.style.width = `${expanded_width}px`;
  });
  select.addEventListener('blur', () => {
    select.style.borderColor = '#d3d3d3';
    select.style.width = '55px';
  });
  select.addEventListener('change', () => {
    // Collapse after selection
    setTimeout(() => {
      select.style.width = '55px';
    }, 100);
  });

  // Add options for each dataset
  base_urls.forEach((dataset, index) => {
    const option = document.createElement('option');
    option.value = index;
    // Use short_label if available, otherwise use label, otherwise default
    const label = dataset.short_label || dataset.label || `DS-${index + 1}`;
    const full_label = dataset.label || `Dataset ${index + 1}`;
    option.textContent = label;
    option.title = full_label; // Full label on hover
    select.appendChild(option);
  });

  // Set initial value from obs_store
  select.value = viz_state.obs_store.current_dataset_index.get();

  // Handle change event
  select.addEventListener('change', async (event) => {
    const new_index = parseInt(event.target.value, 10);
    const current_index = viz_state.obs_store.current_dataset_index.get();

    if (
      new_index !== current_index &&
      !viz_state.obs_store.dataset_switching.get()
    ) {
      // Show loading state
      select.disabled = true;
      select.style.opacity = '0.5';

      try {
        await switch_dataset(new_index, viz_state, deck_ist, layers_obj);
      } catch (error) {
        // Revert selection on error
        select.value = current_index;
      } finally {
        select.disabled = false;
        select.style.opacity = '1';
      }
    }
  });

  // Subscribe to dataset index changes to keep dropdown in sync
  viz_state.obs_store.current_dataset_index.subscribe((index) => {
    select.value = index;
  });

  container.appendChild(select);

  return container;
};
