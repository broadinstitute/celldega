/* global require */

describe('neighborhood-cloud gene search drives the shared Uniprot gene-info panel', () => {
  let ist_gene_search_callback_nbhd_cloud;
  let obsSelectedGenes;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const readStripped = (relPath) =>
      fs
        .readFileSync(path.join(__dirname, relPath), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');

    // Real update_selected_genes (not shimmed) -- its own same-array-means-
    // toggle-off heuristic is exactly what this fix has to avoid tripping
    // on the "gene unavailable, no-op" case.
    const source = [
      readStripped('../global_variables/selected_genes.js'),
      readStripped('../ui/gene_search.js'),
    ].join('\n');

    // Fakes the real contract: a no-op (leaves nbhd_cloud.selected_gene
    // untouched) for a gene not in available_gene_shapes, otherwise resets
    // to null (same gene selected again) or sets the new gene.
    const shims = `
      const set_gene_search_input = () => {};
      const select_nbhd_cloud_gene = async (gene, viz_state) => {
        const { nbhd_cloud } = viz_state;
        if (gene === nbhd_cloud.selected_gene) {
          nbhd_cloud.selected_gene = null;
        } else if (nbhd_cloud.available_gene_shapes?.has(gene)) {
          nbhd_cloud.selected_gene = gene;
        }
      };
      const update_cat = () => {};
      const update_selected_cats = () => {};
      const update_cell_exp_array = () => {};
      const sync_nbhd_cloud_opacity_sliders = () => {};
      const refresh_layer = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { ist_gene_search_callback_nbhd_cloud };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ ist_gene_search_callback_nbhd_cloud } = module.exports);
  });

  beforeEach(() => {
    obsSelectedGenes = [];
  });

  const fakeRects = () => ({ selectAll: () => ({ style: () => {} }) });

  const makeViewState = (searchValue, nbhd_cloud_overrides = {}) => ({
    nbhd_cloud: {
      svg_bar_cluster: fakeRects(),
      ...nbhd_cloud_overrides,
    },
    genes: {
      gene_search_input: { value: searchValue },
      svg_bar_gene: fakeRects(),
      selected_genes: [],
    },
    obs_store: { selected_genes: { set: (v) => obsSelectedGenes.push(v) } },
  });

  test('typing an available gene pushes it to obs_store.selected_genes', async () => {
    const viz_state = makeViewState('Matn1', {
      available_gene_shapes: new Map([['Matn1', 10]]),
    });

    await ist_gene_search_callback_nbhd_cloud({}, viz_state);

    expect(obsSelectedGenes).toEqual([['Matn1']]);
    expect(viz_state.nbhd_cloud.selected_gene).toBe('Matn1');
  });

  test('clearing the search box (already selected) clears obs_store.selected_genes', async () => {
    const viz_state = makeViewState('Matn1', {
      available_gene_shapes: new Map([['Matn1', 10]]),
    });

    await ist_gene_search_callback_nbhd_cloud({}, viz_state);
    obsSelectedGenes = [];
    viz_state.genes.gene_search_input.value = '';
    await ist_gene_search_callback_nbhd_cloud({}, viz_state);

    expect(obsSelectedGenes).toEqual([[]]);
    expect(viz_state.nbhd_cloud.selected_gene).toBeNull();
  });

  test('typing an unavailable gene is a no-op: obs_store is left untouched', async () => {
    const viz_state = makeViewState('NotAGene', {
      available_gene_shapes: new Map([['Matn1', 10]]),
    });

    await ist_gene_search_callback_nbhd_cloud({}, viz_state);

    expect(obsSelectedGenes).toEqual([]);
    expect(viz_state.nbhd_cloud.selected_gene).toBeUndefined();
  });

  test('typing an unavailable gene while another gene is already selected leaves the panel alone', async () => {
    const viz_state = makeViewState('Matn1', {
      available_gene_shapes: new Map([['Matn1', 10]]),
    });
    await ist_gene_search_callback_nbhd_cloud({}, viz_state);
    obsSelectedGenes = [];

    viz_state.genes.gene_search_input.value = 'NotAGene';
    await ist_gene_search_callback_nbhd_cloud({}, viz_state);

    // select_nbhd_cloud_gene is a no-op for an unavailable gene, so
    // selected_gene stays 'Matn1' -- must NOT re-push (which would trip
    // update_selected_genes' same-array-means-toggle-off heuristic and
    // incorrectly clear the panel).
    expect(obsSelectedGenes).toEqual([]);
    expect(viz_state.nbhd_cloud.selected_gene).toBe('Matn1');
  });
});
