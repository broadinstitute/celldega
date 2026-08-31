import { select_nbhd_cloud_gene } from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { update_cell_exp_array } from '../global_variables/cell_exp_array';
import { update_selected_genes } from '../global_variables/selected_genes';
import { sync_nbhd_cloud_opacity_sliders } from '../ui/bar_plot';
import { refresh_layer } from '../utils/refresh_layer';

import { set_gene_search_input } from './gene_search_input';

let gene_search_options = [];
let gene_datalist_counter = 0;

const is_gene_row_axis = (viz_state) =>
  String(
    viz_state.row_entity?.entity ?? viz_state.row_entity ?? ''
  ).toLowerCase() === 'gene';

const get_matrix_row_search_entries = (viz_state) => {
  const entries = [];
  const labels = viz_state.labels?.row_label_data || [];

  (viz_state.row_nodes || []).forEach((node, index) => {
    const name = node?.name;
    if (name !== null && name !== undefined && String(name) !== '') {
      entries.push({ index, value: String(name) });
    }

    const label = labels[index];
    const display_name = label?.display_name;
    if (
      display_name !== null &&
      display_name !== undefined &&
      String(display_name) !== ''
    ) {
      entries.push({ index, value: String(display_name) });
    }
  });

  return entries;
};

export const find_matrix_row_index = (viz_state, query) => {
  const value = String(query ?? '').trim();
  if (!value) return null;

  const entries = get_matrix_row_search_entries(viz_state);
  const exact = entries.find((entry) => entry.value === value);
  if (exact) return exact.index;

  const normalized = value.toLocaleLowerCase();
  return (
    entries.find((entry) => entry.value.toLocaleLowerCase() === normalized)
      ?.index ?? null
  );
};

/**
 * Build the compact Clustergram row search. It intentionally reuses the
 * Landscape search input's styling and datalist behavior, while selection only
 * centers a matrix row rather than changing the spatial color encoding.
 */
export const set_matrix_row_search = (viz_state, on_select) => {
  const search_container = document.createElement('div');
  search_container.className = 'matrix_row_search';
  search_container.style.flexShrink = '0';
  search_container.style.marginTop = '4px';
  search_container.style.marginLeft = '10px';

  const search_state = {};
  const placeholder = is_gene_row_axis(viz_state)
    ? 'Gene search'
    : 'Row search';
  set_gene_search_input(search_state, placeholder);
  const input = search_state.gene_search_input;

  gene_datalist_counter += 1;
  const datalist = document.createElement('datalist');
  datalist.id = `matrix_rows_datalist_${gene_datalist_counter}_${Date.now()}`;
  input.setAttribute('list', datalist.id);

  const row_values = Array.from(
    new Set(
      get_matrix_row_search_entries(viz_state).map((entry) => entry.value)
    )
  );
  row_values.forEach((value) => {
    const option = document.createElement('option');
    option.value = value;
    datalist.appendChild(option);
  });

  input.style.width = '156px';
  input.style.maxWidth = '250px';
  input.style.height = '12px';
  input.style.fontSize = '12px';
  input.style.border = '1px solid #d3d3d3';
  input.style.borderRadius = '0';
  input.style.display = 'inline-block';
  input.style.padding = '1pt 2pt';
  input.style.marginTop = '0px';

  const focus_query = (query = input.value) => {
    const row_index = find_matrix_row_index(viz_state, query);
    if (row_index === null) return false;
    on_select?.(row_index);
    return true;
  };

  // True while the typed text is a strict prefix of some other row name
  // (e.g. "ACE" on the way to "ACE2"): focusing now would lurch the view to
  // the shorter match mid-keystroke. Datalist picks (insertReplacementText)
  // and Enter always focus.
  const is_ambiguous_prefix = (query) => {
    const value = String(query ?? '')
      .trim()
      .toLocaleLowerCase();
    if (!value) return false;
    return get_matrix_row_search_entries(viz_state).some((entry) => {
      const candidate = entry.value.toLocaleLowerCase();
      return candidate !== value && candidate.startsWith(value);
    });
  };

  input.addEventListener('input', (event) => {
    if (
      event.inputType !== 'insertReplacementText' &&
      is_ambiguous_prefix(input.value)
    ) {
      return;
    }
    focus_query();
  });
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    focus_query();
  });

  search_container.appendChild(input);
  search_container.appendChild(datalist);
  viz_state.row_search = {
    container: search_container,
    input,
    focus: (query) => {
      input.value = String(query ?? '');
      return focus_query(input.value);
    },
  };

  return search_container;
};

// neighborhood-cloud's gene search is entirely separate from the legacy
// per-cell path below: there's no cell_exp_array to update, and typing a
// gene selects/clears its gene-shapes the same way clicking its bar does
// (bar_callback_gene, bar_plot.js) -- this just drives the same underlying
// function from the text input instead.
const ist_gene_search_callback_nbhd_cloud = async (layers_obj, viz_state) => {
  const inst_gene = viz_state.genes.gene_search_input.value;
  // '' (cleared) and the literal 'cluster' option both mean "go back to
  // cluster color" -- re-selecting the already-selected gene is exactly
  // select_nbhd_cloud_gene's own reset case.
  const isReset =
    inst_gene === '' ||
    inst_gene === 'cluster' ||
    inst_gene === viz_state.nbhd_cloud.selected_gene;
  const gene = isReset ? viz_state.nbhd_cloud.selected_gene : inst_gene;

  if (gene == null) {
    return;
  }

  const previousSelectedGene = viz_state.nbhd_cloud.selected_gene;
  await select_nbhd_cloud_gene(gene, viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_cell_layer');
  sync_nbhd_cloud_opacity_sliders(viz_state);

  // Drives the Uniprot gene-info panel (ui_containers.js's
  // obs_store.selected_genes subscriber) -- only when the gene actually
  // changed (an unavailable gene is a no-op in select_nbhd_cloud_gene, so
  // `selected_gene` is unchanged; re-pushing the same value would trip
  // update_selected_genes' own same-array-means-toggle-off heuristic and
  // incorrectly clear the panel).
  if (viz_state.nbhd_cloud.selected_gene !== previousSelectedGene) {
    update_selected_genes(
      viz_state.genes,
      viz_state.nbhd_cloud.selected_gene != null
        ? [viz_state.nbhd_cloud.selected_gene]
        : [],
      viz_state.obs_store
    );
  }

  const hasSelection = viz_state.nbhd_cloud.selected_gene != null;
  viz_state.genes.svg_bar_gene
    ?.selectAll('rect')
    .style('opacity', (bar) =>
      !hasSelection || bar.name === viz_state.nbhd_cloud.selected_gene
        ? 1.0
        : 0.2
    );
  viz_state.nbhd_cloud.svg_bar_cluster?.selectAll('rect').style('opacity', 1.0);
};

const ist_gene_search_callback = async (deck_ist, layers_obj, viz_state) => {
  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    await ist_gene_search_callback_nbhd_cloud(layers_obj, viz_state);
    return;
  }

  const inst_gene = viz_state.genes.gene_search_input.value;

  const new_cat = inst_gene === '' ? 'cluster' : inst_gene;

  if (inst_gene === '' || viz_state.genes.gene_names.includes(inst_gene)) {
    update_cat(viz_state.cats, new_cat);

    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: false,
      trx_layer: false,
    });

    update_selected_genes(
      viz_state.genes,
      inst_gene === '' ? [] : [inst_gene],
      viz_state.obs_store
    );

    const inst_gene_in_gene_names =
      viz_state.genes.gene_names.includes(inst_gene);

    if (inst_gene_in_gene_names) {
      await update_cell_exp_array(
        viz_state.cats,
        viz_state.genes,
        viz_state.global_base_url,
        inst_gene,
        viz_state.seg.version,
        viz_state.vector_name_integer,
        viz_state.aws,
        viz_state.row_group_readers?.cbg
      );
    }

    // make selected_cats an empty array if new_cat is cluster or
    // make it an array with the selected gene if inst_gene is not an empty string
    // update_selected_cats(viz_state.cats, [new_cat], viz_state.obs_store);
    //
    // update selected_cats after update_cell_exp_array has been run
    // can clean up and move more logic to observability
    update_selected_cats(
      viz_state.cats,
      new_cat === 'cluster' ? [] : [inst_gene],
      viz_state.obs_store
    );
  }
};

export const set_gene_search = async (
  _tech_type,
  inst_deck,
  layers_obj,
  viz_state
) => {
  // neighborhood-cloud only ever responds to genes with a shape or a cell
  // scatter (see select_nbhd_cloud_gene) -- listing the full gene panel
  // here would mean most entries silently do nothing when picked.
  gene_search_options = viz_state.nbhd_cloud?.is_nbhd_cloud
    ? [
        'cluster',
        ...new Set([
          ...(viz_state.nbhd_cloud.available_gene_shapes?.keys() ?? []),
          ...(viz_state.nbhd_cloud.available_gene_scatter?.keys() ?? []),
        ]),
      ]
    : ['cluster', ...viz_state.genes.gene_names];

  viz_state.genes.gene_search.style.width = '115px';

  set_gene_search_input(viz_state.genes);

  const dataList = document.createElement('datalist');
  // Use unique ID to prevent contamination between multiple Landscape instances
  gene_datalist_counter += 1;
  dataList.id = `genes_datalist_${gene_datalist_counter}_${Date.now()}`;
  viz_state.genes.gene_search_input.setAttribute('list', dataList.id);

  // Populate the datalist with gene names
  gene_search_options.forEach((optionText) => {
    const option = document.createElement('option');
    option.value = optionText;
    dataList.appendChild(option);
  });

  // Apply styles to the input element
  viz_state.genes.gene_search_input.style.width = '156px'; // '109px'
  viz_state.genes.gene_search_input.style.maxWidth = '250px';
  viz_state.genes.gene_search_input.style.height = '12px';
  viz_state.genes.gene_search_input.style.fontSize = '12px';
  viz_state.genes.gene_search_input.style.border = '1px solid #d3d3d3';
  viz_state.genes.gene_search_input.style.borderRadius = '0';

  viz_state.genes.gene_search_input.style.display = 'inline-block';
  viz_state.genes.gene_search_input.style.padding = '1pt 2pt';

  // Append elements
  viz_state.genes.gene_search.appendChild(viz_state.genes.gene_search_input);
  viz_state.genes.gene_search.appendChild(dataList);

  // Create a div element with some text
  viz_state.genes.gene_text_box = document.createElement('div');
  viz_state.genes.gene_text_box.textContent = '';
  viz_state.genes.gene_text_box.style.marginTop = '3px';
  viz_state.genes.gene_text_box.style.color = '#222222';
  viz_state.genes.gene_text_box.style.border = '1px solid #d3d3d3';
  viz_state.genes.gene_text_box.style.height = '69px'; //'71px'
  viz_state.genes.gene_text_box.style.overflow = 'scroll';
  viz_state.genes.gene_text_box.style.fontSize = '12px';
  viz_state.genes.gene_text_box.style.cursor = 'default';
  viz_state.genes.gene_text_box.style.width = '142px';
  viz_state.genes.gene_text_box.style.paddingLeft = '2px';
  viz_state.genes.gene_text_box.style.paddingRight = '17px';

  viz_state.genes.gene_text_box.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } =
      viz_state.genes.gene_text_box;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  viz_state.genes.gene_search.appendChild(viz_state.genes.gene_text_box); // Append the new div with text

  // Set initial default value to "cluster"
  viz_state.genes.gene_search_input.value = '';
  update_cat(viz_state.cats, 'cluster');

  // Event listener when an option is selected or the input is cleared
  const callback = () =>
    ist_gene_search_callback(inst_deck, layers_obj, viz_state);
  viz_state.genes.gene_search_input.style.marginTop = '5px';

  viz_state.genes.gene_search_input.addEventListener('input', callback);
};
