import { GeoJsonLayer } from 'deck.gl';

import { hexToRgb } from '../../utils/hexToRgb';
import { refresh_layer } from '../../utils/refresh_layer';
import { getModelMatrixProps } from '../../utils/rotation';

/**
 * Get color for a neighborhood feature based on current color mode
 *
 * Supports two color modes:
 * - 'cluster' (default): Color by categorical attribute (cat/leiden) using the feature's color property
 * - 'gene': Color by gene expression using red intensity (similar to cell gene coloring)
 *
 * @param {object} d - The GeoJSON feature
 * @param {object} viz_state - The visualization state
 * @returns {Array<number>} RGBA color array
 */
const get_nbhd_color = (d, viz_state) => {
  const colorMode = viz_state.nbhd.color_mode || 'cluster';
  const selectedNbhds = viz_state.obs_store.selected_nbhds.get();
  const hasSelection = selectedNbhds.length > 0;
  const isSelected = hasSelection && selectedNbhds.includes(d.properties.cat);

  // Handle selection visibility
  if (hasSelection && !isSelected) {
    return [0, 0, 0, 0]; // Fully transparent for non-selected
  }

  let inst_color;
  let inst_opacity = 255;

  if (colorMode === 'gene' && viz_state.nbhd.gene_expression) {
    // Gene/attribute expression mode: use red intensity like cell layer
    // Try multiple keys for lookup: cat (primary), name (fallback)
    const gene_expression = viz_state.nbhd.gene_expression;
    const cat_key = d.properties.cat;
    const name_key = d.properties.name;

    // Look up expression value - try cat first (matches bar graph), then name
    let expression = 0;
    if (cat_key !== undefined && gene_expression[cat_key] !== undefined) {
      expression = gene_expression[cat_key];
    } else if (name_key !== undefined && gene_expression[name_key] !== undefined) {
      expression = gene_expression[name_key];
    } else if (cat_key !== undefined && gene_expression[String(cat_key)] !== undefined) {
      expression = gene_expression[String(cat_key)];
    }

    const max_exp = viz_state.nbhd.gene_max_exp || 1;

    // Normalize expression to 0-255 range using log scale (similar to cell layer)
    let normalized_exp;
    if (expression > 0 && max_exp > 0) {
      const log_exp = Math.log1p(expression);
      const log_max = Math.log1p(max_exp);
      normalized_exp = Math.round((log_exp / log_max) * 255);
    } else {
      normalized_exp = 0;
    }

    // Red color with expression-based intensity
    inst_color = [255, 0, 0];
    inst_opacity = Math.max(30, normalized_exp); // Minimum opacity of 30 for visibility
  } else {
    // Default cluster/categorical mode
    inst_color = hexToRgb(d.properties.color);
  }

  inst_color.push(inst_opacity);
  return inst_color;
};

export const ini_nbhd_layer = (viz_state, visible) => {
  const nbhd_layer = new GeoJsonLayer({
    id: 'nbhd-layer',
    data: viz_state.nbhd.feature_collection,
    pickable: true,
    stroked: false,
    filled: true,
    getLineWidth: 1,
    getFillColor: (d) => get_nbhd_color(d, viz_state),
    opacity: 0.5,
    visible,
    ...getModelMatrixProps(viz_state.rotation),
  });

  return nbhd_layer;
};

export const filter_cat_nbhd_feature_collection = (viz_state) => {
  let filt_features;

  if (viz_state.cats.selected_cats.length === 0) {
    filt_features = viz_state.nbhd.ini_feature_collection.features;
  } else {
    filt_features = viz_state.nbhd.ini_feature_collection.features.filter((d) =>
      viz_state.cats.selected_cats.includes(d.properties.cat)
    );
  }
  viz_state.nbhd.feature_collection = {
    type: 'FeatureCollection',
    features: filt_features,
  };
};

export const update_nbhd_layer_data = (viz_state, layers_obj) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    data: viz_state.nbhd.feature_collection,
  });
};

export const update_nbhd_layer_opacity = (layers_obj, opacity) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    opacity,
  });
};

const nbhd_layer_onclick = async (
  info,
  _event,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_nbhd = info.object.properties.cat;

  // update selected_nbhds observable with the clicked nbhd unless
  // the clicked nbhd is already equal to selected_nbhds
  const prev_selected_nbhds = viz_state.obs_store.selected_nbhds.get();
  if (
    prev_selected_nbhds[0] === inst_nbhd &&
    prev_selected_nbhds.length === 1
  ) {
    viz_state.obs_store.selected_nbhds.set([]);
  } else {
    viz_state.obs_store.selected_nbhds.set([inst_nbhd]);
  }

  // refresh the nbhd layer
  refresh_layer(viz_state, layers_obj, 'nbhd_layer');

  // highlight the nbhd in the bar plot
  if (viz_state.obs_store.selected_nbhds.get().length > 0) {
    viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', (d) => {
      if (d.name === inst_nbhd) {
        return 1.0;
      } else {
        return 0.2;
      }
    });
  } else {
    viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
  }

  //   // scroll to the nbhd in the bar plot
  // viz_state.nbhd.svg_bar_nbhd.selectAll('rect')
  //   .filter((d) => d.name === inst_nbhd)
  //   .node().scrollIntoView({
  //     behavior: 'smooth',
  //     block: 'center',
  //     inline: 'nearest',
  //   });
};

export const set_nbhd_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    onClick: (info, event) =>
      nbhd_layer_onclick(info, event, deck_ist, layers_obj, viz_state),
  });
};

export const toggle_nbhd_layer_visibility = (layers_obj, visible) => {
  layers_obj.nbhd_layer = layers_obj.nbhd_layer.clone({
    visible,
  });
};
