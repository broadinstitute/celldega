/**
 * Comparing a few genes: when two or more genes are selected, their transcripts
 * get distinct temporary colors (a gene's own color is arbitrary, and two genes
 * can share a near-identical one), and the gene bar chart becomes their key.
 *
 * A selection typed in the gene search, or made by a Clustergram, Clerk or
 * Python, also filters the gene bars to just these genes ("filter"): the
 * scientist is comparing genes they chose, not reading the local expression
 * ranking. Shift-clicking bars builds a selection from that ranking, so it keeps
 * every bar (only the colors change) unless the bars are already a filtered key.
 *
 * Stored on `viz_state.genes`: `comparison` ({genes, colors, filter} or null) and
 * `comparison_colors` (rgb by gene id, for the transcript layer). select_genes
 * sets it; any other change of the selected genes clears it (selected_genes.js).
 */

/**
 * Distinct colors for up to 20 genes (the selection cap), most distinct first.
 * The first few avoid the fluorescence channels' red, green and blue, so the
 * transcripts stand out on the image.
 */
export const COMPARISON_COLORS = [
  [255, 225, 25],
  [240, 50, 230],
  [66, 212, 244],
  [245, 130, 49],
  [191, 239, 69],
  [250, 190, 212],
  [255, 250, 200],
  [220, 190, 255],
  [170, 255, 195],
  [230, 25, 75],
  [60, 180, 75],
  [67, 99, 216],
  [145, 30, 180],
  [70, 153, 144],
  [255, 216, 177],
  [154, 99, 36],
  [128, 128, 0],
  [128, 0, 0],
  [0, 0, 117],
  [169, 169, 169],
];

/**
 * Set (or clear, under two genes) the comparison for a gene selection.
 * @param {object} genes - `viz_state.genes`.
 * @param {string[]} selected - The selected genes, in order (colors follow it).
 * @param {{filter?: boolean}} [options] - Filter the gene bars to these genes.
 */
export const set_gene_comparison = (
  genes,
  selected,
  { filter = true } = {}
) => {
  if (!genes) return;
  const list = (selected ?? []).map(String);
  if (list.length < 2) {
    genes.comparison = null;
    genes.comparison_colors = null;
    return;
  }
  const colors = {};
  const by_id = [];
  list.forEach((gene, i) => {
    const rgb = COMPARISON_COLORS[i % COMPARISON_COLORS.length];
    colors[gene] = rgb;
    const id = genes.g_nameMapping?.[gene];
    if (id !== undefined) by_id[id] = rgb;
  });
  genes.comparison = { genes: list, colors, filter: Boolean(filter) };
  genes.comparison_colors = by_id;
};

/** A gene's color: its comparison color while comparing, else its own. */
export const gene_color = (genes, name) =>
  genes?.comparison?.colors?.[name] ?? genes?.color_dict_gene?.[name];

/**
 * The gene bars to draw: while a filtered comparison is on, just its genes, in
 * selection order, with their counts (0 when none are in view), as its key.
 * @param {object} genes - `viz_state.genes`.
 * @param {{name: string, value: number}[]} bar_data
 */
export const comparison_bar_data = (genes, bar_data) => {
  const comparison = genes?.comparison;
  if (!comparison?.filter) return bar_data ?? [];
  const values = new Map((bar_data ?? []).map((d) => [d.name, d.value]));
  return comparison.genes.map((name) => ({
    name,
    value: values.get(name) ?? 0,
  }));
};

/** What a gene bar chart shows for the comparison; redraw when it changes. */
export const comparison_key = (genes) => {
  const comparison = genes?.comparison;
  return comparison
    ? `${comparison.filter ? 'filter' : 'colors'}:${comparison.genes.join(',')}`
    : '';
};
