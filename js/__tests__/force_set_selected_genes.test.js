/* global require */

describe('force_set_selected_genes', () => {
  let force_set_selected_genes;
  let update_selected_genes;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../global_variables/selected_genes.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');

    const code = `${source}\nmodule.exports = { force_set_selected_genes, update_selected_genes };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ force_set_selected_genes, update_selected_genes } = module.exports);
  });

  const makeGenes = () => ({
    selected_genes: [],
    selected_gene_ids: new Set(),
    g_nameMapping: { GAPDH: 5, INS: 2 },
  });

  const makeStore = () => {
    let value = null;
    return {
      selected_genes: {
        set: (v) => {
          value = v;
        },
        get: () => value,
      },
    };
  };

  it('updates selected_gene_ids so the trx layer can focus the gene', () => {
    const genes = makeGenes();
    const store = makeStore();

    force_set_selected_genes(genes, ['GAPDH'], store);

    expect(genes.selected_genes).toEqual(['GAPDH']);
    // The Set the transcript layer reads to dim non-selected transcripts.
    expect([...genes.selected_gene_ids]).toEqual([5]);
    expect(store.selected_genes.get()).toEqual(['GAPDH']);
  });

  it('does not toggle off when re-setting the same gene (unlike update_selected_genes)', () => {
    const genes = makeGenes();
    genes.selected_genes = ['GAPDH'];
    genes.selected_gene_ids = new Set([5]);

    force_set_selected_genes(genes, ['GAPDH'], makeStore());
    expect(genes.selected_genes).toEqual(['GAPDH']);
    expect([...genes.selected_gene_ids]).toEqual([5]);

    // Contrast: the toggling variant clears an already-selected gene.
    const genes2 = makeGenes();
    genes2.selected_genes = ['GAPDH'];
    genes2.selected_gene_ids = new Set([5]);
    update_selected_genes(genes2, ['GAPDH'], makeStore());
    expect(genes2.selected_genes).toEqual([]);
  });

  it('clears selected_gene_ids when cleared', () => {
    const genes = makeGenes();
    genes.selected_genes = ['GAPDH'];
    genes.selected_gene_ids = new Set([5]);

    force_set_selected_genes(genes, [], makeStore());
    expect(genes.selected_genes).toEqual([]);
    expect(genes.selected_gene_ids.size).toBe(0);
  });
});
