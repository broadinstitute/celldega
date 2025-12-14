import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import {
  update_selected_genes,
  sync_selected_genes,
} from '../global_variables/selected_genes';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { refresh_layer } from '../utils/refresh_layer';

/**
 * Check if a click value represents a cell cluster selection.
 * Supports both legacy format (row_entity === 'cell_cluster') and
 * new format (entity === 'cell' && attr === 'leiden').
 */
export const isCellCluster = (clickValue) => {
  if (!clickValue) return false;

  // Legacy format check
  if (clickValue.row_entity === 'cell_cluster') return true;

  // New format check: entity is 'cell' and attr is a clustering attribute
  if (clickValue.entity === 'cell') {
    const clusteringAttrs = ['leiden', 'cluster', 'cell_type', 'cell_cluster'];
    return clusteringAttrs.includes(clickValue.attr);
  }

  return false;
};

/**
 * Check if a click value represents a neighborhood selection.
 */
export const isNeighborhood = (clickValue) => {
  if (!clickValue) return false;

  // Legacy format check
  if (clickValue.col_entity === 'nbhd') return true;

  // New format check
  return clickValue.entity === 'nbhd' || clickValue.entity === 'hextile';
};

/**
 * Check if a click value represents a gene selection.
 */
export const isGene = (clickValue) => {
  if (!clickValue) return false;

  // New format check
  return clickValue.entity === 'gene';
};

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

  if (!click_type) {
    return;
  }

  let inst_gene;
  let new_cat;

  // add try catch block
  try {
    if (click_type === 'row_label') {
      // Check if this is a cell cluster selection using entity/attr
      if (isCellCluster(click_info.value)) {
        inst_gene = 'cluster';
        new_cat = click_info.value.name;

        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      } else {
        // Treat as gene selection
        inst_gene = click_info.value.name;

        new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

        update_cat(viz_state.cats, new_cat);
        update_selected_genes(
          viz_state.genes,
          [inst_gene],
          viz_state.obs_store
        );

        // Load gene expression data BEFORE updating selected_cats
        // This ensures cell_exp_array is populated before the cell layer refreshes
        await update_cell_exp_array(
          viz_state.cats,
          viz_state.genes,
          viz_state.global_base_url,
          inst_gene,
          viz_state.seg.version,
          viz_state.vector_name_integer,
          viz_state.aws
        );

        // Update selected_cats after cell_exp_array has been populated
        // This triggers the subscription that refreshes the cell layer
        update_selected_cats(
          viz_state.cats,
          new_cat === 'cluster' ? [] : [inst_gene],
          viz_state.obs_store
        );

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      }
    } else if (click_type === 'col_label') {
      // Check if this is a neighborhood selection
      if (isNeighborhood(click_info.value)) {
        const new_nbhd = click_info.value.name;
        viz_state.obs_store.selected_nbhds.set([new_nbhd]);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');

        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) => (d.name === new_nbhd ? 1.0 : 0.2));

          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .filter((d) => d.name === new_nbhd)
            .node()
            ?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            });
        } else {
          viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
        }
      } else {
        inst_gene = 'cluster';
        new_cat = click_info.value.name;

        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      }
    } else if (click_type === 'col_dendro') {
      const new_cats = click_info.value.selected_names;
      // Check if columns represent neighborhoods
      const col_entity_full =
        click_info.value.col_entity_full || click_info.value;
      if (isNeighborhood(col_entity_full)) {
        viz_state.obs_store.selected_nbhds.set(new_cats);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          const selected_nbhds = viz_state.obs_store.selected_nbhds.get();
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) =>
              selected_nbhds.includes(d.name) ? 1.0 : 0.2
            );

          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .filter((d) => selected_nbhds.includes(d.name))
            .node()
            ?.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            });
        } else {
          viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
        }
      } else {
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
      }
    } else if (click_type === 'row_dendro') {
      const new_cats = click_info.value.selected_names;
      // Check if rows represent cell clusters
      const row_entity_full =
        click_info.value.row_entity_full || click_info.value;
      if (isCellCluster(row_entity_full)) {
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(viz_state.cats, new_cats, viz_state.obs_store);
        update_selected_genes(viz_state.genes, [], viz_state.obs_store);

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');
      } else {
        update_selected_genes(viz_state.genes, new_cats, viz_state.obs_store);

        sync_selected_genes(viz_state, viz_state.genes.selected_genes);

        if (new_cats.length === 1) {
          inst_gene = new_cats[0];
          new_cat = inst_gene === viz_state.cats.cat ? 'cluster' : inst_gene;

          update_cat(viz_state.cats, new_cat);

          // Load gene expression data BEFORE updating selected_cats
          await update_cell_exp_array(
            viz_state.cats,
            viz_state.genes,
            viz_state.global_base_url,
            inst_gene,
            viz_state.seg.version,
            viz_state.vector_name_integer,
            viz_state.aws
          );

          // Update selected_cats after cell_exp_array has been populated
          update_selected_cats(
            viz_state.cats,
            new_cat === 'cluster' ? [] : [inst_gene],
            viz_state.obs_store
          );
        } else {
          update_cat(viz_state.cats, 'cluster');
          update_selected_cats(viz_state.cats, [], viz_state.obs_store);
        }

        viz_state.obs_store.viz_nbhd_layer.set(false);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');

        refresh_layer(viz_state, layers_obj, 'cell_layer');
        refresh_layer(viz_state, layers_obj, 'trx_layer');
      }
    } else if (click_type === 'mat_value') {
      const { row, col, row_entity_full, col_entity_full } = click_info.value;

      // Use the full entity info if available
      const rowEntity = row_entity_full || row;
      const colEntity = col_entity_full || col;

      // Check if we have a cell cluster + neighborhood combination
      if (isCellCluster(rowEntity) && isNeighborhood(colEntity)) {
        const new_nbhds = [col.name];
        viz_state.obs_store.selected_nbhds.set(new_nbhds);
        viz_state.obs_store.viz_nbhd_layer.set(true);
        viz_state.buttons?.buttons?.nbhd?.style?.('color', 'blue');
        refresh_layer(viz_state, layers_obj, 'nbhd_layer');

        // Also highlight the selected cluster
        update_cat(viz_state.cats, 'cluster');
        update_selected_cats(
          viz_state.cats,
          [row.name],
          viz_state.obs_store
        );
        refresh_layer(viz_state, layers_obj, 'cell_layer');

        if (viz_state.obs_store.selected_nbhds.get().length > 0) {
          const selected_nbhds = viz_state.obs_store.selected_nbhds.get();
          viz_state.nbhd.svg_bar_nbhd
            .selectAll('rect')
            .style('opacity', (d) =>
              selected_nbhds.includes(d.name) ? 1.0 : 0.2
            );
        }
      }
    }
  } catch (error) {
    handleAsyncError(error, {
      context: 'updating IST landscape from CGM',
      logUnexpected: true,
      throwOnAuth: false,
    });
  }
};
