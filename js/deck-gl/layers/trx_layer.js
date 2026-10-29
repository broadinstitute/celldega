import { ScatterplotLayer } from 'deck.gl';

import { select_genes } from '../../global_variables/select_genes';
import { getModelMatrixProps } from '../../utils/rotation';
import { grab_trx_tiles_in_view } from '../../vector_tile/transcripts/grab_trx_tiles_in_view';

const getTranscriptGeneName = (genes, index) => {
  const geneId = genes.trx_gene_ids?.[index];
  if (geneId === undefined || geneId < 0) {
    return null;
  }

  return genes.g_nameMapping_inv?.[geneId] ?? null;
};

const trx_layer_callback = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_gene = getTranscriptGeneName(viz_state.genes, info.index);

  if (!inst_gene) {
    return;
  }

  // Select just this gene, or clear it if it's the only one selected.
  const current = viz_state.genes.selected_genes ?? [];
  const only_this_gene = current.length === 1 && current[0] === inst_gene;
  await select_genes(viz_state, only_this_gene ? [] : [inst_gene]);
};

export const ini_trx_layer = (viz_state) => {
  const { genes } = viz_state;

  const trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: genes.trx_data,
    pickable: true,
    getFillColor: (i, d) => {
      const geneId = genes.trx_gene_ids?.[d.index];
      const inst_color = genes.g_colorMapping_inv?.[geneId] || [0, 0, 0];
      const inst_opacity =
        !genes.selected_gene_ids ||
        genes.selected_gene_ids.size === 0 ||
        genes.selected_gene_ids.has(geneId)
          ? 255
          : 0;

      return [...inst_color, inst_opacity];
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
  viz_state
) => {
  viz_state.genes.trx_data = await grab_trx_tiles_in_view(
    base_url,
    tiles_in_view,
    viz_state
  );

  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    data: viz_state.genes.trx_data,
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
