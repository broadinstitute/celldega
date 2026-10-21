/* global require */

// Multi-gene selection: the 20-gene cap (keeping the highest-expressed genes),
// summed expression for cell opacity, comma-separated search with
// autocomplete after the last comma, and shift-click on gene bars.

const fs = require('fs');
const path = require('path');

const read_stripped = (rel_path) =>
  fs
    .readFileSync(path.join(__dirname, rel_path), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export (const |function )/gm, '$1');

const load = (rel_path, shims, names, extra_args = {}) => {
  const code = `${shims}\n${read_stripped(rel_path)}\nmodule.exports = { ${names.join(', ')} };`;
  const module = { exports: {} };
  new Function('module', 'exports', ...Object.keys(extra_args), code)(
    module,
    module.exports,
    ...Object.values(extra_args)
  );
  return module.exports;
};

const make_observable = (initial) => {
  let value = initial;
  const subscribers = new Set();
  return {
    get: () => value,
    set: (next) => {
      if (value !== next) {
        value = next;
        subscribers.forEach((fn) => fn(value));
      }
    },
    subscribe: (fn) => {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
  };
};

describe('select_genes', () => {
  let mod;
  const expression_calls = [];
  const control = { applied: true, pending: null };

  beforeAll(() => {
    const shims = `
      const update_cat = (cats, cat) => { cats.cat = cat; };
      const force_set_selected_cats = (cats, selected) => { cats.selected_cats = selected; };
      const force_set_selected_genes = (genes, selected, obs_store) => {
        genes.selected_genes = selected;
        obs_store.selected_genes.set(selected);
      };
      const update_cell_exp_array = async (cats, genes, base_url, gene_list) => {
        expression_calls.push(gene_list);
        if (control.pending) await control.pending;
        return control.applied;
      };
    `;
    mod = load(
      '../global_variables/select_genes.js',
      shims,
      ['MAX_SELECTED_GENES', 'limit_gene_selection', 'select_genes'],
      { expression_calls, control }
    );
  });

  beforeEach(() => {
    expression_calls.length = 0;
    control.applied = true;
    control.pending = null;
  });

  const gene_names = Array.from({ length: 30 }, (_, i) => `G${i}`);
  // G29 has the highest mean, G0 the lowest.
  const meta_gene = Object.fromEntries(
    gene_names.map((gene, i) => [gene, { mean: i, max: 10 }])
  );

  it('drops unknown and duplicate genes', () => {
    expect(
      mod.limit_gene_selection(['G1', 'nope', 'G1', 'G2'], {
        gene_names,
        meta_gene,
      })
    ).toEqual({ selected: ['G1', 'G2'], total: 2 });
  });

  it('keeps the highest-expressed genes over the cap, in their order', () => {
    const { selected, total } = mod.limit_gene_selection(gene_names, {
      gene_names,
      meta_gene,
    });
    expect(total).toBe(30);
    expect(selected).toHaveLength(mod.MAX_SELECTED_GENES);
    expect(selected[0]).toBe('G10');
    expect(selected.at(-1)).toBe('G29');
  });

  const make_viz_state = () => ({
    cats: { selected_cats: [] },
    genes: { gene_names, meta_gene, selected_genes: [] },
    obs_store: {
      deck_check: make_observable({}),
      selected_genes: make_observable([]),
    },
    seg: { version: 'default' },
  });

  it('loads the summed expression before setting the cell categories', async () => {
    const viz_state = make_viz_state();
    await mod.select_genes(viz_state, ['G3', 'G4']);
    expect(expression_calls).toEqual([['G3', 'G4']]);
    expect(viz_state.genes.selected_genes).toEqual(['G3', 'G4']);
    expect(viz_state.cats.selected_cats).toEqual(['G3', 'G4']);
    expect(viz_state.cats.cat).toBe('G3 + G4');
  });

  it('records the requested count only for a capped selection', async () => {
    const viz_state = make_viz_state();
    await mod.select_genes(viz_state, gene_names);
    const subset = viz_state.genes.gene_subset;
    expect(subset.total).toBe(30);
    expect(subset.genes).toBe(viz_state.genes.selected_genes);
  });

  it('returns to cluster coloring without loading expression', async () => {
    const viz_state = make_viz_state();
    await mod.select_genes(viz_state, []);
    expect(expression_calls).toHaveLength(0);
    expect(viz_state.cats.cat).toBe('cluster');
    expect(viz_state.cats.selected_cats).toEqual([]);
  });

  it('leaves the categories to a newer selection that replaced it', async () => {
    const viz_state = make_viz_state();
    control.applied = false;
    viz_state.cats.selected_cats = ['previous'];
    await mod.select_genes(viz_state, ['G1']);
    expect(viz_state.cats.selected_cats).toEqual(['previous']);
  });
});

describe('update_cell_exp_array with several genes', () => {
  const expression = {
    A: { cell_names: ['a', 'b'], cell_exp: [4, 1] },
    B: { cell_names: ['b', 'c'], cell_exp: [1, 2] },
  };
  const gate = { pending: null };
  let update_cell_exp_array;

  beforeAll(() => {
    const shims = `
      const options = { fetch: {} };
      const get_arrow_table = async (url) => {
        if (gate.pending) await gate.pending;
        return url;
      };
      const getGeneExpressionColumns = (table, gene) => expression[gene];
    `;
    ({ update_cell_exp_array } = load(
      '../global_variables/cell_exp_array.js',
      shims,
      ['update_cell_exp_array'],
      { expression, gate }
    ));
  });

  const make_cats = () => ({
    cell_names_array: ['a', 'b', 'c'],
    cell_name_to_index_map: new Map([
      ['a', 0],
      ['b', 1],
      ['c', 2],
    ]),
    meta_cell_id_set: null,
  });
  const genes = { meta_gene: { A: { max: 4 }, B: { max: 2 } } };
  const byte = (value, max) =>
    Math.round((Math.log1p(value) / Math.log1p(max)) * 255);

  it('sums raw expression and scales by the largest sum', async () => {
    const cats = make_cats();
    const applied = await update_cell_exp_array(
      cats,
      genes,
      '/data',
      ['A', 'B'],
      'default',
      false
    );
    expect(applied).toBe(true);
    // Sums: a = 4, b = 1 + 1 = 2, c = 2; largest sum = 4.
    expect(Array.from(cats.cell_exp_array)).toEqual([
      255,
      byte(2, 4),
      byte(2, 4),
    ]);
  });

  it('keeps a single gene scaled by its meta_gene max', async () => {
    const cats = make_cats();
    await update_cell_exp_array(cats, genes, '/data', 'B', 'default', false);
    expect(Array.from(cats.cell_exp_array)).toEqual([0, byte(1, 2), 255]);
  });

  it('ignores a load that a newer request replaced', async () => {
    const cats = make_cats();
    let release;
    gate.pending = new Promise((resolve) => {
      release = resolve;
    });
    // Different base URL, so this load isn't served from the cache.
    const older = update_cell_exp_array(
      cats,
      genes,
      '/other',
      ['A'],
      'default',
      false
    );
    gate.pending = null;
    await update_cell_exp_array(cats, genes, '/data', ['B'], 'default', false);
    release();
    expect(await older).toBe(false);
    expect(Array.from(cats.cell_exp_array)).toEqual([0, byte(1, 2), 255]);
  });
});

describe('comma-separated gene search', () => {
  let search;

  beforeAll(() => {
    const shims = `
      const select_nbhd_cloud_gene = async () => {};
      const get_uniprot_info = () => undefined;
      const request_uniprot_info = async () => undefined;
      const update_cat = () => {};
      const select_genes = async () => {};
      const update_selected_genes = () => {};
      const sync_nbhd_cloud_opacity_sliders = () => {};
      const refresh_layer = () => {};
      const contain_scroll = () => {};
      const escape_html = (value) => String(value);
      const is_gene_axis = () => true;
      const set_gene_search_input = () => {};
    `;
    search = load('../ui/gene_search.js', shims, [
      'parse_gene_query',
      'resolve_gene_tokens',
      'gene_suggestions',
    ]);
  });

  const gene_names = ['NPHS1', 'NPHS2', 'PODXL', 'ACE', 'ACE2', 'CLU'];
  const lookup = new Map(gene_names.map((gene) => [gene.toLowerCase(), gene]));

  it('splits on commas and ignores blanks', () => {
    expect(search.parse_gene_query(' NPHS1 , nphs2,, ')).toEqual([
      'NPHS1',
      'nphs2',
    ]);
    expect(search.parse_gene_query('')).toEqual([]);
  });

  it('resolves tokens case-insensitively and flags incomplete ones', () => {
    expect(search.resolve_gene_tokens(['nphs1', 'PODXL'], lookup)).toEqual({
      genes: ['NPHS1', 'PODXL'],
      complete: true,
    });
    expect(search.resolve_gene_tokens(['NPHS1', 'POD'], lookup)).toEqual({
      genes: ['NPHS1'],
      complete: false,
    });
  });

  it('uses the full gene list until a comma is typed', () => {
    expect(search.gene_suggestions('NPH', gene_names)).toBeNull();
  });

  it('autocompletes the gene after the last comma', () => {
    expect(search.gene_suggestions('NPHS1, ac', gene_names)).toEqual([
      'NPHS1, ACE',
      'NPHS1, ACE2',
    ]);
    // Genes already listed aren't suggested again; prefix matches come
    // before substring matches.
    expect(search.gene_suggestions('NPHS1,nphs', gene_names)).toEqual([
      'NPHS1,NPHS2',
    ]);
    expect(search.gene_suggestions('CLU, s', gene_names)).toEqual([
      'CLU, NPHS1',
      'CLU, NPHS2',
    ]);
  });
});

describe('shift-click on gene bars', () => {
  let bar_callback_gene;
  const selections = [];

  beforeAll(() => {
    const shims = `
      const select_genes = async (viz_state, genes) => {
        selections.push(genes);
        viz_state.genes.selected_genes = genes;
      };
      const toggle_slider = () => {};
      const toggle_trx_layer_visibility = () => {};
      const new_toggle_cell_layer_visibility = () => {};
      const refresh_layer = () => {};
      const register_ui_cleanup = () => {};
      const make_gene_hover_tooltip = () => ({});
      const escape_html = (value) => String(value);
    `;
    ({ bar_callback_gene } = load(
      '../ui/bar_plot.js',
      shims,
      ['bar_callback_gene'],
      { selections }
    ));
  });

  beforeEach(() => {
    selections.length = 0;
  });

  const bars = { selectAll: () => ({ style: () => {} }) };
  const make_viz_state = () => ({
    cats: { svg_bar_cluster: bars },
    genes: { svg_bar_gene: bars, selected_genes: [] },
    sliders: {},
    nbhd: {},
  });
  const click = (viz_state, name, shiftKey = false) =>
    bar_callback_gene({ shiftKey }, { name }, null, {}, viz_state);

  it('adds and removes genes with shift-click', async () => {
    const viz_state = make_viz_state();
    await click(viz_state, 'NPHS1');
    await click(viz_state, 'NPHS2', true);
    await click(viz_state, 'PODXL', true);
    expect(viz_state.genes.selected_genes).toEqual(['NPHS1', 'NPHS2', 'PODXL']);
    await click(viz_state, 'NPHS2', true);
    expect(viz_state.genes.selected_genes).toEqual(['NPHS1', 'PODXL']);
  });

  it('narrows to one gene on a plain click, then clears it', async () => {
    const viz_state = make_viz_state();
    viz_state.genes.selected_genes = ['NPHS1', 'PODXL'];
    await click(viz_state, 'PODXL');
    expect(viz_state.genes.selected_genes).toEqual(['PODXL']);
    await click(viz_state, 'PODXL');
    expect(viz_state.genes.selected_genes).toEqual([]);
  });
});
