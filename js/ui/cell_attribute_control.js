/** Compact obs-column selector and a continuous legend for numerical attributes. */
export const make_cell_attribute_control = (viz_state, onChange) => {
  const attributes = viz_state.cats.meta_cell_attr.filter((name) => name !== 'color');
  if (!attributes.length || viz_state.nbhd_cloud?.is_nbhd_cloud) return null;
  const root = document.createElement('div');
  root.style.cssText = 'padding:2px 3px 5px;font:11px Arial,sans-serif;';
  const select = document.createElement('select');
  select.setAttribute('aria-label', 'Cell color attribute');
  select.style.cssText = 'width:100%;max-width:110px;font:11px Arial,sans-serif;border:1px solid #ccc;background:white;';
  attributes.forEach((name) => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
  const legend = document.createElement('div');
  legend.style.paddingTop = '5px';
  const ramp = document.createElement('div');
  ramp.style.cssText = 'height:8px;background:linear-gradient(to right,rgb(239,243,255),rgb(8,48,107));';
  const labels = document.createElement('div');
  labels.style.cssText = 'display:flex;justify-content:space-between;';
  const minimum = document.createElement('span');
  const maximum = document.createElement('span');
  labels.append(minimum, maximum);
  const missing = document.createElement('div');
  missing.style.color = '#667085';
  legend.append(ramp, labels, missing);
  root.append(select, legend);
  const update = () => {
    const cats = viz_state.cats;
    select.value = cats.inst_cell_attr;
    const numeric = cats.attribute_numeric && (!cats.cat || cats.cat === 'cluster');
    legend.style.display = numeric ? '' : 'none';
    viz_state.containers.bar_cluster.style.display = cats.attribute_numeric ? 'none' : '';
    const format = (value) => Number(value.toPrecision(4)).toLocaleString();
    minimum.textContent = format(cats.numeric_domain?.[0] ?? 0);
    maximum.textContent = format(cats.numeric_domain?.[1] ?? 1);
    missing.textContent = cats.numeric_missing ? `${cats.numeric_missing.toLocaleString()} missing · gray` : '';
  };
  const change = () => onChange(select.value);
  select.addEventListener('change', change);
  const unsubscribe = viz_state.obs_store.selected_genes.subscribe(update);
  return {
    root,
    update,
    dispose() {
      unsubscribe();
      select.removeEventListener('change', change);
      root.remove();
    },
  };
};
