import { toggle_slider } from './sliders';

/**
 * Refresh the nbhd layer by cloning it with a new ID.
 * This is necessary for deck.gl to recognize the layer has changed and re-render.
 *
 * @param {object} viz_state - The visualization state
 * @param {object} layers_obj - The deck.gl layers object
 * @param {string} attr_name - The attribute name for the new layer ID
 */
const refresh_nbhd_layer = (viz_state, layers_obj, attr_name) => {
  // Clone the layer with a new ID to trigger deck.gl re-render
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    id: `nbhd-layer-attr-${attr_name}-${Date.now()}`,
  });

  // Toggle deck_check to trigger the layer list update
  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    nbhd_layer: false,
  });
  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    nbhd_layer: true,
  });
};

/**
 * Create a compact dropdown for selecting neighborhood GDF attributes to color by.
 * This allows coloring neighborhoods by numerical attributes like 'area' from the GDF.
 *
 * @param {object} viz_state - The visualization state
 * @param {object} layers_obj - The deck.gl layers object
 * @returns {HTMLElement} The dropdown container element
 */
export const make_nbhd_attr_dropdown = (viz_state, layers_obj) => {
  const container = document.createElement('div');
  container.style.display = 'flex';
  container.style.alignItems = 'center';
  container.style.marginTop = '2px';
  container.style.marginBottom = '4px';
  container.style.marginLeft = '5px';

  const label = document.createElement('span');
  label.textContent = 'color:';
  label.style.fontSize = '9px';
  label.style.color = '#888';
  label.style.marginRight = '4px';

  const select = document.createElement('select');
  select.id = 'nbhd-attr-select';

  // Compact styling to match the discrete look
  select.style.width = '70px';
  select.style.height = '18px';
  select.style.fontSize = '10px';
  select.style.padding = '0 2px';
  select.style.border = '1px solid #ccc';
  select.style.borderRadius = '3px';
  select.style.backgroundColor = '#fafafa';
  select.style.cursor = 'pointer';
  select.style.outline = 'none';

  // Default option (categorical coloring)
  const defaultOption = document.createElement('option');
  defaultOption.value = 'cluster';
  defaultOption.textContent = 'cluster';
  select.appendChild(defaultOption);

  // Add GDF attributes from viz_state (populated from Python traitlet)
  const gdf_attrs = viz_state.nbhd?.gdf_attrs || [];
  for (const attr of gdf_attrs) {
    const option = document.createElement('option');
    option.value = attr;
    option.textContent = attr;
    select.appendChild(option);
  }

  // Handle attribute selection
  select.addEventListener('change', (e) => {
    const selectedAttr = e.target.value;

    // Get bar graph container to show/hide
    const barContainer = viz_state.containers?.bar_nbhd;

    if (selectedAttr === 'cluster') {
      // Reset to categorical coloring
      viz_state.nbhd.color_mode = 'cluster';
      viz_state.nbhd.gene_expression = null;
      viz_state.nbhd.current_gene = null;

      // Show bar graph and slider for categorical mode
      if (barContainer) {
        barContainer.style.display = 'block';
      }
      if (viz_state.sliders?.nbhd) {
        toggle_slider(viz_state.sliders.nbhd, true);
      }
    } else {
      // Color by GDF attribute - extract values from GeoJSON properties
      const featureCollection = viz_state.nbhd.feature_collection;
      if (featureCollection && featureCollection.features) {
        const values = {};
        let maxVal = -Infinity;
        let minVal = Infinity;

        for (const feature of featureCollection.features) {
          // Store by both cat and cat as string to handle numeric keys
          const cat = feature.properties.cat;
          const val = feature.properties[selectedAttr];
          if (typeof val === 'number' && !isNaN(val)) {
            // Store with multiple key formats for robust lookup
            values[cat] = val;
            values[String(cat)] = val;
            if (feature.properties.name) {
              values[feature.properties.name] = val;
            }
            if (val > maxVal) maxVal = val;
            if (val < minVal) minVal = val;
          }
        }

        console.log('NBHD attr dropdown - selected:', selectedAttr);
        console.log('NBHD attr dropdown - values:', values);
        console.log('NBHD attr dropdown - max:', maxVal, 'min:', minVal);

        // Store attribute data using existing gene expression infrastructure
        viz_state.nbhd.gene_expression = values;
        viz_state.nbhd.gene_max_exp = maxVal;
        viz_state.nbhd.gene_min_exp = minVal;
        viz_state.nbhd.current_gene = selectedAttr;
        viz_state.nbhd.color_mode = 'gene';

        // Hide bar graph and slider for numerical attribute mode
        // (opacity is used to encode the attribute value)
        if (barContainer) {
          barContainer.style.display = 'none';
        }
        if (viz_state.sliders?.nbhd) {
          toggle_slider(viz_state.sliders.nbhd, false);
        }

        // Set layer opacity to 1 so the value encoding opacity shows correctly
        layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
          opacity: 1.0,
        });
      }
    }

    // Refresh the nbhd layer by cloning it
    refresh_nbhd_layer(viz_state, layers_obj, selectedAttr);
  });

  container.appendChild(label);
  container.appendChild(select);

  return container;
};

/**
 * Update the dropdown options when gdf_attrs changes
 *
 * @param {object} viz_state - The visualization state
 */
export const update_nbhd_attr_dropdown = (viz_state) => {
  const select = document.getElementById('nbhd-attr-select');
  if (!select) return;

  // Clear existing options except the first (cluster)
  while (select.options.length > 1) {
    select.remove(1);
  }

  // Add new options from gdf_attrs
  const gdf_attrs = viz_state.nbhd?.gdf_attrs || [];
  for (const attr of gdf_attrs) {
    const option = document.createElement('option');
    option.value = attr;
    option.textContent = attr;
    select.appendChild(option);
  }
};

