/**
 * A slice-swap dropdown for one Landmark viewport — adapted from
 * `dataset_dropdown.js`'s styling, but generic over a shared slice-id pool
 * (Landscape's dropdown only ever switches one dataset for one viewport).
 */
export const make_landmark_dropdown = (
  slice_ids,
  slice_labels,
  current_value,
  on_change
) => {
  const select = document.createElement('select');
  select.className = 'landmark-slice-dropdown';
  select.style.width = '90px';
  select.style.height = '20px';
  select.style.fontSize = '10px';
  select.style.padding = '1px 4px';
  select.style.border = '1px solid #d3d3d3';
  select.style.borderRadius = '3px';
  select.style.backgroundColor = 'white';
  select.style.cursor = 'pointer';
  select.style.outline = 'none';
  select.title = 'Switch slice';

  slice_ids.forEach((id) => {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = slice_labels[id] || id;
    select.appendChild(option);
  });
  select.value = current_value;

  select.addEventListener('change', (event) => on_change(event.target.value));

  return select;
};

export const set_landmark_dropdown_value = (select, value) => {
  select.value = value;
};
