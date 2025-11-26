import { ScatterplotLayer } from 'deck.gl';

import { update_cat, update_selected_cats } from '../../global_variables/cat';
import { update_cell_exp_array } from '../../global_variables/cell_exp_array';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { getModelMatrixProps } from '../../utils/rotation';
import { grab_trx_tiles_in_view } from '../../vector_tile/transcripts/grab_trx_tiles_in_view';

const trx_layer_callback = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_gene = viz_state.genes.trx_names_array[info.index];

  if (!inst_gene) {
    return;
  }

  const reset_gene = inst_gene === viz_state.cats.cat;

  const new_cat = reset_gene ? 'cluster' : inst_gene;

  update_cat(viz_state.cats, new_cat);

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    trx_layer: false,
  });

  update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
  // testing setting selected_cats to array with the selected gene for
  // observable updates
  update_selected_cats(viz_state.cats, [inst_gene], viz_state.obs_store);

  await update_cell_exp_array(
    viz_state.cats,
    viz_state.genes,
    viz_state.global_base_url,
    inst_gene,
    viz_state.seg.version,
    viz_state.vector_name_integer,
    viz_state.aws
  );
};

export const ini_trx_layer = (viz_state) => {
  const { genes } = viz_state;

  const trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: genes.trx_data,
    pickable: true,
    getFillColor: (i, d) => {
      const inst_gene = genes.trx_names_array[d.index];
      const inst_color = genes.color_dict_gene[inst_gene] || [0, 0, 0];
      const inst_opacity =
        genes.selected_genes.length === 0 || genes.selected_genes.includes(inst_gene)
          ? 255
          : 5;

      const safeColor =
        Array.isArray(inst_color) && inst_color.length === 3 ? inst_color : [0, 0, 0];

      return [...safeColor, inst_opacity];
    },
    ...getModelMatrixProps(viz_state.rotation),
  });

  return trx_layer;
};

export const set_trx_layer_onclick = (deck_ist, layers_obj, viz_state) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    onClick: (event, d) =>
      trx_layer_callback(event, d, deck_ist, layers_obj, viz_state),
  });
};

export const update_trx_layer_data = async (
  base_url,
  tiles_in_view,
  layers_obj,
  viz_state,
  filterFn = null
) => {
  const trx_scatter_data = await grab_trx_tiles_in_view(
    base_url,
    tiles_in_view,
    viz_state
  );

  const names = viz_state.genes.trx_names_array || [];
  const combo = viz_state.combo_data.trx || [];
  const positionAttribute = trx_scatter_data?.attributes?.getPosition;
  const positions = positionAttribute?.value || new Float32Array();
  const dim = positionAttribute?.size || 2;

  const keepIndices = names.map((_, idx) => idx).filter((idx) => {
    if (typeof filterFn !== 'function') return true;
    const x = positions[idx * dim];
    const y = positions[idx * dim + 1];
    return filterFn({
      name: names[idx],
      x,
      y,
      index: idx,
    });
  });

  const filteredPositions = new Float32Array(Math.max(keepIndices.length * dim, 0));
  const filteredCombo = [];
  const filteredNames = [];

  keepIndices.forEach((origIdx, i) => {
    filteredPositions[i * dim] = positions[origIdx * dim];
    filteredPositions[i * dim + 1] = positions[origIdx * dim + 1];
    if (dim === 3) {
      filteredPositions[i * dim + 2] = positions[origIdx * dim + 2];
    }

    const fallback = {
      name: names[origIdx] ?? 'unknown',
      x: positions[origIdx * dim],
      y: positions[origIdx * dim + 1],
    };

    filteredCombo.push(combo[origIdx] || fallback);
    filteredNames.push(names[origIdx] ?? fallback.name);
  });

  viz_state.genes.trx_names_array = filteredNames;
  viz_state.combo_data.trx = filteredCombo;
  const baseScatter = trx_scatter_data && typeof trx_scatter_data === 'object' ? trx_scatter_data : { attributes: {} };

  viz_state.genes.trx_data = {
    ...baseScatter,
    length: keepIndices.length,
    attributes: {
      ...(baseScatter.attributes || {}),
      getPosition: {
        ...(baseScatter.attributes?.getPosition || { size: dim }),
        value: filteredPositions,
      },
    },
  };

  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    data: viz_state.combo_data.trx,
  });

  // update viz_state layers before notifying deck_ready
  viz_state.layers_obj = layers_obj;

  viz_state.obs_store.deck_check.set({
    ...viz_state.obs_store.deck_check.get(),
    trx_layer: true,
    trx_data: true,
  });
};

export const toggle_trx_layer_visibility = (layers_obj, visible) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    visible,
  });
};

export const update_trx_layer_radius = (layers_obj, radius) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    getRadius: radius,
  });
};

export const update_trx_pickable_state = (layers_obj, pickable) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    pickable,
  });
};
