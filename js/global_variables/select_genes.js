import { force_set_selected_cats, update_cat } from './cat';
import { update_cell_exp_array } from './cell_exp_array';
import { force_set_selected_genes } from './selected_genes';

/**
 * Most genes shown at once. Each gene's expression is fetched separately, so
 * a large selection (e.g. a 200-gene Clustergram dendrogram cut) shows only
 * its MAX_SELECTED_GENES highest-expressed genes rather than stalling the
 * widget.
 */
export const MAX_SELECTED_GENES = 20;

/**
 * Known, de-duplicated genes from `genes`. Over MAX_SELECTED_GENES, keeps the
 * genes with the highest mean expression (meta_gene), in their given order.
 *
 * @param {string[]} genes
 * @param {object} gene_state - `viz_state.genes` (gene_names, meta_gene).
 * @returns {{selected: string[], total: number}} `total` counts the known
 *   genes requested, so `total > selected.length` means a subset is shown.
 */
export const limit_gene_selection = (genes, gene_state) => {
  const known = new Set(gene_state.gene_names);
  const unique = [...new Set((genes ?? []).map(String))].filter((gene) =>
    known.has(gene)
  );
  if (unique.length <= MAX_SELECTED_GENES) {
    return { selected: unique, total: unique.length };
  }

  const mean = (gene) => Number(gene_state.meta_gene?.[gene]?.mean) || 0;
  const top = new Set(
    [...unique].sort((a, b) => mean(b) - mean(a)).slice(0, MAX_SELECTED_GENES)
  );
  return {
    selected: unique.filter((gene) => top.has(gene)),
    total: unique.length,
  };
};

/**
 * `cats.cat` for a gene selection: the gene itself for one gene (single-gene
 * toggles compare against it), a combined label for several.
 */
export const gene_selection_cat = (genes) =>
  genes.length === 0 ? 'cluster' : genes.join(' + ');

/**
 * Whether a gene selection that set `cats.cat` to `cat` is still the current
 * selection once its expression has loaded: no newer load replaced it
 * (`applied`, from update_cell_exp_array), and no cluster click or cleared
 * selection, which load nothing, changed `cats.cat`. Every path that loads
 * expression before setting the selection checks this first.
 */
export const is_current_gene_load = (cats, applied, cat) =>
  Boolean(applied) && cats.cat === cat;

/**
 * Show `genes` in a Landscape or Yearbook: the transcripts of every listed
 * gene, and cells colored by their summed expression. An empty list returns
 * to cluster coloring.
 *
 * @param {object} viz_state
 * @param {string[]} genes
 */
export const select_genes = async (viz_state, genes) => {
  const { cats, obs_store } = viz_state;
  const { selected, total } = limit_gene_selection(genes, viz_state.genes);

  // Read by the gene panel (gene_search.js) to note when only a subset is
  // shown. Tied to this exact list, so selections made elsewhere never show
  // a stale note; set before selected_genes notifies the panel.
  viz_state.genes.gene_subset = { genes: selected, total };
  update_cat(cats, gene_selection_cat(selected));
  obs_store.deck_check.set({
    ...obs_store.deck_check.get(),
    cell_layer: false,
    trx_layer: false,
  });
  force_set_selected_genes(viz_state.genes, selected, obs_store);

  if (selected.length > 0) {
    const applied = await update_cell_exp_array(
      cats,
      viz_state.genes,
      viz_state.global_base_url,
      selected,
      viz_state.seg.version,
      viz_state.vector_name_integer,
      viz_state.aws,
      viz_state.row_group_readers?.cbg
    );
    // A newer selection replaced this one while its expression loaded.
    if (!is_current_gene_load(cats, applied, gene_selection_cat(selected))) {
      return;
    }
  }

  // Set after the expression loads: this is what refreshes the cell colors.
  force_set_selected_cats(cats, selected, obs_store);
};
