import { new_toggle_cell_layer_visibility } from '../deck-gl/layers/cell_layer';
import { update_nbhd_layer_data, toggle_nbhd_layer_visibility } from '../deck-gl/layers/nbhd_layer';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { make_bar_graph, bar_callback_nbhd } from '../ui/bar_plot';
import { toggle_slider } from '../ui/sliders';
import { refresh_layer } from '../utils/refresh_layer';

export const update_ist_landscape_from_cgm = async (
  deck_ist,
  layers_obj,
  viz_state
) => {
  const raw_click = viz_state.model.get('update_trigger');
  if (!raw_click || typeof raw_click !== 'object') {
    return;
  }

  const click_info = {
    type: raw_click.type || raw_click.click_type,
    value: raw_click.value || raw_click.click_value,
  };

  const click_type = click_info.type?.replace('-', '_');
  const entity =
    raw_click.entity ||
    raw_click.click_entity ||
    viz_state.model.get('entity') ||
    'CELL';

  if (!click_type) {
    return;
  }

  let inst_gene;
  let new_cat;

  // add try catch block
  try {
    if (click_type === 'row_label') {
      inst_gene = click_info.value.name;

      new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

      if (entity === 'CELL') {
        console.log("in cell block");
        update_cat(viz_state.cats, new_cat);
        update_selected_genes(viz_state.genes, [inst_gene], viz_state.obs_store);
        // update_selected_cats(viz_state.cats, [], viz_state.obs_store);
        update_selected_cats(
          viz_state.cats,
          new_cat === 'cluster' ? [] : [inst_gene],
          viz_state.obs_store
        );

        await update_cell_exp_array(
          viz_state.cats,
          viz_state.genes,
          viz_state.global_base_url,
          inst_gene,
          viz_state.seg.version,
          viz_state.vector_name_integer,
          viz_state.aws
        );

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        // set_cell_layer_onclick(deck_ist, layers_obj, viz_state);
        // new_toggle_cell_layer_visibility(layers_obj, true);
        // toggle_slider(viz_state.sliders.cell, true);

      } else {
        console.log("in nbhd block");

        toggle_nbhd_layer_visibility(layers_obj, false);
        new_toggle_cell_layer_visibility(layers_obj, true);
        toggle_slider(viz_state.sliders.cell, true);

        viz_state.buttons.buttons.nbhd.style('color', 'gray');
        viz_state.buttons.buttons.cell.style('color', 'blue');

        new_cat = click_info.value.name;
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      }
    } else if (click_type === 'col_label') {
      inst_gene = 'cluster';
      new_cat = click_info.value.name;
      if (entity === 'CELL') {
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else {

        toggle_nbhd_layer_visibility(layers_obj, true);
        new_toggle_cell_layer_visibility(layers_obj, false);
        toggle_slider(viz_state.sliders.cell, false);

        viz_state.buttons.buttons.nbhd.style('color', 'blue');
        viz_state.buttons.buttons.cell.style('color', 'gray');

        viz_state.obs_store.selected_nbhds.set([new_cat]);
        await update_nbhd_layer_data(viz_state, layers_obj);

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');

        make_bar_graph(
          viz_state.containers.bar_nbhd,
          bar_callback_nbhd,
          viz_state.nbhd.svg_bar_nbhd,
          viz_state.nbhd.bar_data,
          viz_state.nbhd.color_dict,
          deck_ist,
          layers_obj,
          viz_state
        );

        viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1);
        viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 0.2);
      }
    } else if (click_type === 'col_dendro') {
      const new_cats = click_info.value.selected_names;

      update_cat(viz_state.cats, 'cluster');
      update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
      update_selected_genes(viz_state.genes, [], viz_state.obs_store);

      const layer = entity === 'NBHD' ? 'nbhd_layer' : 'cell_layer';
      refresh_layer(viz_state, layers_obj, layer);
    }
  } catch (error) {
    handleAsyncError(error, {
      context: 'updating IST landscape from CGM',
      logUnexpected: true,
      throwOnAuth: false,
    });
  }
};
