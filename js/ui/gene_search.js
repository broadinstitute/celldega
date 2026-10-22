import { select_nbhd_cloud_gene } from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import {
  get_uniprot_info,
  request_uniprot_info,
} from '../external_apis/uniprot_api';
import { update_cat } from '../global_variables/cat';
import { select_genes } from '../global_variables/select_genes';
import { update_selected_genes } from '../global_variables/selected_genes';
import { sync_nbhd_cloud_opacity_sliders } from '../ui/bar_plot';
import { refresh_layer } from '../utils/refresh_layer';

import { contain_scroll, escape_html, is_gene_axis } from './gene_info';
import { set_gene_search_input } from './gene_search_input';
import { update_expression_note } from './trx_handle';

let gene_search_options = [];
let gene_datalist_counter = 0;

const is_gene_row_axis = (viz_state) => is_gene_axis(viz_state, 'row');

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

/** Gene names typed in the search box, split on commas. */
export const parse_gene_query = (value) =>
  String(value ?? '')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean);

/**
 * Map typed tokens to dataset gene names, case-insensitively.
 *
 * @returns {{genes: string[], complete: boolean}} `complete` is false while
 *   any token isn't (yet) a gene name.
 */
export const resolve_gene_tokens = (tokens, gene_lookup) => {
  const genes = tokens
    .map((token) => gene_lookup.get(token.toLowerCase()))
    .filter(Boolean);
  return { genes, complete: genes.length === tokens.length };
};

const MAX_GENE_SUGGESTIONS = 50;

/**
 * Datalist options that autocomplete the gene after the last comma: each is
 * the typed text up to that comma plus a matching gene, since a datalist
 * matches against the whole input value. Returns null without a comma (the
 * full gene list applies).
 */
export const gene_suggestions = (value, gene_names) => {
  const comma = value.lastIndexOf(',');
  if (comma < 0) return null;

  const tail = value.slice(comma + 1);
  const prefix = value.slice(0, comma + 1) + tail.match(/^\s*/)[0];
  const token = tail.trim().toLowerCase();
  const chosen = new Set(
    parse_gene_query(value.slice(0, comma)).map((gene) => gene.toLowerCase())
  );
  const candidates = gene_names.filter(
    (gene) => !chosen.has(gene.toLowerCase())
  );
  const starts = candidates.filter((gene) =>
    gene.toLowerCase().startsWith(token)
  );
  const contains = token
    ? candidates.filter(
        (gene) =>
          !gene.toLowerCase().startsWith(token) &&
          gene.toLowerCase().includes(token)
      )
    : [];
  return [...starts, ...contains]
    .slice(0, MAX_GENE_SUGGESTIONS)
    .map((gene) => `${prefix}${gene}`);
};

const same_genes = (a, b) =>
  a.length === b.length &&
  a.every((gene, index) => gene.toLowerCase() === b[index].toLowerCase());

/**
 * Show the current gene selection in the search box and the gene panel: the
 * genes as a comma-separated list, with UniProt name and description for one
 * gene or one name per line for several, plus a note when only the
 * highest-expressed subset of a larger selection is shown.
 */
const show_gene_selection = async (viz_state, selected_genes) => {
  const { gene_search_input: input, gene_text_box: box } = viz_state.genes;
  const revision = (box.revision = (box.revision ?? 0) + 1);

  // Leave the text alone while it already describes the selection (e.g.
  // mid-typing "NPHS1, "), so syncing never fights the user's edits.
  if (!same_genes(parse_gene_query(input.value), selected_genes)) {
    input.value = selected_genes.join(', ');
  }

  const genes = selected_genes.filter((gene) =>
    viz_state.genes.gene_names.includes(gene)
  );
  if (genes.length === 0) {
    box.textContent = '';
    return;
  }

  box.textContent = 'loading';
  await Promise.all(
    genes.map((gene) => request_uniprot_info(gene).catch(() => {}))
  );
  if (box.revision !== revision) return;

  const subset = viz_state.genes.gene_subset;
  const note =
    subset?.genes === selected_genes && subset.total > selected_genes.length
      ? `<i>Showing the ${selected_genes.length} highest-expressed of ${subset.total} selected genes.</i><br>`
      : '';

  if (genes.length === 1) {
    const info = get_uniprot_info(genes[0]);
    box.innerHTML =
      info?.name && info.description
        ? `${note}<span style="color: blue;">${info.name}</span><br>${info.description}`
        : note;
  } else {
    box.innerHTML =
      note +
      genes
        .map(
          (gene) =>
            `<span style="color: blue;">${escape_html(gene)}</span> ${escape_html(
              get_uniprot_info(gene)?.name ?? ''
            )}`
        )
        .join('<br>');
  }
  update_expression_note(viz_state);
  box.scrollTo({ top: 0, behavior: 'smooth' });
};

export const set_gene_search = async (
  _tech_type,
  _inst_deck,
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
  // This widget's list (gene_search_options is shared across widgets).
  const full_options = gene_search_options;

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
  viz_state.genes.gene_text_box.style.width = '120px';
  viz_state.genes.gene_text_box.style.paddingLeft = '2px';
  viz_state.genes.gene_text_box.style.paddingRight = '17px';

  // Keep wheel gestures inside the panel: previously the page still scrolled
  // once this box hit either end (or when its text didn't overflow at all).
  contain_scroll(viz_state.genes.gene_text_box);

  viz_state.genes.gene_search.appendChild(viz_state.genes.gene_text_box); // Append the new div with text

  // Set initial default value to "cluster"
  viz_state.genes.gene_search_input.value = '';
  update_cat(viz_state.cats, 'cluster');

  const input = viz_state.genes.gene_search_input;
  input.style.marginTop = '5px';

  viz_state.obs_store.selected_genes.subscribe((selected_genes) =>
    show_gene_selection(viz_state, selected_genes)
  );

  if (viz_state.nbhd_cloud?.is_nbhd_cloud) {
    input.addEventListener('input', () =>
      ist_gene_search_callback_nbhd_cloud(layers_obj, viz_state)
    );
    return;
  }

  // Comma-separated genes, e.g. "NPHS1, NPHS2": cells show their summed
  // expression and each gene's transcripts are shown.
  const gene_lookup = new Map(
    viz_state.genes.gene_names.map((gene) => [gene.toLowerCase(), gene])
  );
  const apply = (genes) => {
    if (same_genes(genes, viz_state.genes.selected_genes ?? [])) return;
    select_genes(viz_state, genes);
  };

  let showing_suggestions = false;
  const update_suggestions = () => {
    const suggestions = gene_suggestions(
      input.value,
      viz_state.genes.gene_names
    );
    if (!suggestions && !showing_suggestions) return;
    showing_suggestions = Boolean(suggestions);
    dataList.replaceChildren(
      ...(suggestions ?? full_options).map((value) => {
        const option = document.createElement('option');
        option.value = value;
        return option;
      })
    );
  };

  // True while the last gene typed is a strict prefix of another gene (e.g.
  // "ACE" on the way to "ACE2"), so typing doesn't select genes mid-word.
  const is_ambiguous_prefix = (token) => {
    const value = token.toLowerCase();
    return viz_state.genes.gene_names.some((gene) => {
      const candidate = gene.toLowerCase();
      return candidate !== value && candidate.startsWith(value);
    });
  };

  input.addEventListener('input', (event) => {
    update_suggestions();
    const tokens = parse_gene_query(input.value);
    if (
      tokens.length === 0 ||
      (tokens.length === 1 && tokens[0] === 'cluster')
    ) {
      apply([]);
      return;
    }
    const { genes, complete } = resolve_gene_tokens(tokens, gene_lookup);
    if (!complete) return;
    if (
      event.inputType !== 'insertReplacementText' &&
      is_ambiguous_prefix(tokens.at(-1))
    ) {
      return;
    }
    apply(genes);
  });

  // Enter applies whatever resolves, skipping unknown tokens.
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    apply(
      resolve_gene_tokens(parse_gene_query(input.value), gene_lookup).genes
    );
  });
};
