/* eslint-disable import/no-cycle */

import * as d3 from 'd3';
import { ScatterplotLayer } from 'deck.gl';

import { update_cat, update_selected_cats } from '../../global_variables/cat';
import { update_cell_exp_array } from '../../global_variables/cell_exp_array';
import { update_selected_genes } from '../../global_variables/selected_genes';
import { update_gene_text_box } from '../../ui/gene_search';
import { toggle_image_layers_and_ctrls } from '../../ui/ui_containers';
import { grab_trx_tiles_in_view } from '../../vector_tile/transcripts/grab_trx_tiles_in_view';
import { get_layers_list } from '../utils/layers_ist';

import { update_cell_layer_id } from './cell_layer';
import { update_path_layer_id } from './path_layer';

export const update_trx_layer_id = (genes, layers_obj) => {
  layers_obj.trx_layer = layers_obj.trx_layer.clone({
    id: `trx-layer-${genes.selected_genes.join('-')}`,
  });
};

const trx_layer_callback = async (
  info,
  _d,
  deck_ist,
  layers_obj,
  viz_state
) => {
  const inst_gene = viz_state.genes.trx_names_array[info.index];

  if (!inst_gene) {
    // console.error("Invalid gene name at index:", info.index)
    return;
  }

  const reset_gene = inst_gene === viz_state.cats.cat;

  const new_cat = reset_gene ? 'cluster' : inst_gene;

  toggle_image_layers_and_ctrls(
    layers_obj,
    viz_state,
    viz_state.cats.cat === inst_gene
  );

  update_cat(viz_state.cats, new_cat);

  update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
  update_selected_cats(viz_state.cats, [], viz_state.obs_store);

  await update_cell_exp_array(
    viz_state.cats,
    viz_state.genes,
    viz_state.global_base_url,
    inst_gene,
    viz_state.seg.version,
    viz_state.vector_name_integer,
    viz_state.aws
  );

  update_cell_layer_id(layers_obj, new_cat);

  update_path_layer_id(layers_obj, new_cat);

  update_trx_layer_id(viz_state.genes, layers_obj);

  const layers_list = get_layers_list(layers_obj, viz_state.close_up);
  deck_ist.setProps({ layers: layers_list });

  // //////////////////////////////////////////////////////////
  // viz_state.genes.svg_bar_gene
  //   .selectAll('g')
  //   .attr('font-weight', 'normal')
  //   .attr('opacity', reset_gene ? 1.0 : 0.25);

  // if (!reset_gene) {
  //   const selectedBar = viz_state.genes.svg_bar_gene
  //     .selectAll('g')
  //     .filter(function () {
  //       const textElement = d3.select(this).select('text').node();
  //       return textElement && textElement.textContent === inst_gene;
  //     })
  //     .attr('opacity', 1.0);

  //   if (!selectedBar.empty()) {
  //     const barPosition = selectedBar.node().getBoundingClientRect().top;

  //     const containerPosition =
  //       viz_state.containers.bar_gene.getBoundingClientRect().top;
  //     const scrollPosition =
  //       barPosition -
  //       containerPosition +
  //       viz_state.containers.bar_gene.scrollTop;

  //     viz_state.genes.svg_bar_gene.attr('opacity', 1.0);

  //     viz_state.containers.bar_gene.scrollTo({
  //       top: scrollPosition,
  //       behavior: 'smooth',
  //     });
  //   }
  // } else {
  //   viz_state.containers.bar_gene.scrollTo({
  //     top: 0,
  //     behavior: 'smooth',
  //   });
  // }
  // //////////////////////////////////////////////////////////

  viz_state.genes.gene_search_input.value =
    viz_state.genes.gene_search_input.value !== inst_gene ? inst_gene : '';

  update_gene_text_box(viz_state.genes, reset_gene ? '' : inst_gene);
};

export const ini_trx_layer = (genes) => {
  const trx_layer = new ScatterplotLayer({
    id: 'trx-layer',
    data: genes.trx_data,
    pickable: true,
    getFillColor: (i, d) => {
      const inst_gene = genes.trx_names_array[d.index];
      const inst_color = genes.color_dict_gene[inst_gene];
      const inst_opacity =
        genes.selected_genes.length === 0 ||
        genes.selected_genes.includes(inst_gene)
          ? 255
          : 5;

      return [...inst_color, inst_opacity];
    },
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
