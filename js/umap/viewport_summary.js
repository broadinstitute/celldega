import { load_gene_expression } from '../global_variables/cell_exp_array';
import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import {
  gene_signatures_from_parquet,
  gene_signatures_from_table,
  gene_signatures_source,
} from '../read_zarr/gene_signatures';
import { areBarDataEqual } from '../utils/compact_data';

/** Genes whose exact expression a TRX click computes for the cells in view. */
export const EXACT_GENES = 50;
const EXACT_CONCURRENCY = 4;

// The TRX button marks what the gene bars show in UMAP/XY: blue for actual
// expression (the whole dataset with every cell in view, or exact for the
// cells in view after a click), purple for an estimate from cell-type
// signatures, gray for whole-dataset genes while zoomed in. Zoomed in, a click
// computes exact expression for the cells in view.
const TRX_MODES = {
  whole: {
    color: 'blue',
    title: 'Whole-dataset expression: every cell is in view.',
  },
  estimate: {
    color: 'purple',
    title:
      'Estimated from cell-type signatures. Click for the exact expression of the top genes in view.',
  },
  dataset: {
    color: 'gray',
    title:
      'Whole-dataset genes. Click for the exact expression of the top genes in view.',
  },
  exact: {
    color: 'blue',
    title:
      'Exact mean expression per cell of the top genes for the cells in view.',
  },
};

export const viewport_cells = (positions, cats, bounds) => {
  const indices = [];
  const counts = new Map();
  let positioned = 0;
  for (let i = 0; i < cats.cell_names_array.length; i++) {
    const x = positions[2 * i];
    const y = positions[2 * i + 1];
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    positioned += 1;
    if (
      x < bounds.min_x ||
      x > bounds.max_x ||
      y < bounds.min_y ||
      y > bounds.max_y
    )
      continue;
    indices.push(i);
    const name = cats.cell_cats[i];
    if (name != null)
      counts.set(String(name), (counts.get(String(name)) || 0) + 1);
  }
  return {
    indices,
    // Every cell with a position is in view.
    all: indices.length === positioned,
    bars: Array.from(counts, ([name, value]) => ({ name, value })).sort(
      (a, b) => b.value - a.value
    ),
  };
};

export const estimate_viewport_genes = (
  signatures,
  bars,
  known_genes = null
) => {
  const sums = new Float64Array(signatures.genes.length);
  let covered = 0;
  for (const { name, value: count } of bars) {
    const means = signatures.means.get(String(name));
    if (!means) continue;
    covered += count;
    for (let g = 0; g < sums.length; g++) sums[g] += count * means[g];
  }
  return {
    covered,
    bars: covered
      ? signatures.genes
          .map((name, i) => ({
            name,
            value: sums[i] / covered,
          }))
          .filter(
            ({ name, value }) =>
              value > 0 && (!known_genes || known_genes.has(name))
          )
          .sort((a, b) => b.value - a.value)
          .slice(0, 200)
      : [],
  };
};

/**
 * Mean expression per cell of each gene over the cells flagged in `in_view`,
 * reading one gene at a time with `read_gene` ({cell_names, cell_exp}).
 * `cell_index` maps a returned cell name to its row; -1 skips the value.
 */
export const exact_viewport_genes = async (
  genes,
  in_view,
  n_cells,
  read_gene,
  cell_index,
  concurrency = EXACT_CONCURRENCY
) => {
  const sums = new Float64Array(genes.length);
  let next = 0;
  const worker = async () => {
    while (next < genes.length) {
      const g = next++;
      // Each worker reads its genes one at a time; the workers run in parallel.
      // eslint-disable-next-line no-await-in-loop
      const { cell_names, cell_exp } = await read_gene(genes[g]);
      let sum = 0;
      for (let i = 0; i < cell_names.length; i++) {
        const index = cell_index(cell_names[i]);
        if (index >= 0 && in_view[index]) sum += Number(cell_exp[i]) || 0;
      }
      sums[g] = sum;
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(concurrency, genes.length) }, worker)
  );
  return genes
    .map((name, g) => ({ name, value: n_cells ? sums[g] / n_cells : 0 }))
    .filter(({ value }) => value > 0)
    .sort((a, b) => b.value - a.value);
};

// Signatures for the viewport estimate: Landscape(adata_sig=...) bytes, a
// gene_signature_url store, or else a spatial DegaFiles' own df_sig.parquet
// (each default cluster's mean counts per cell), which only applies while the
// Landscape shows the DegaFiles' clusters.
const signature_loader = (viz_state) => {
  const { model } = viz_state;
  const bytes = model?.get?.('gene_signature_parquet');
  if (bytes?.byteLength) {
    return {
      required: true,
      load: () =>
        gene_signatures_from_parquet(bytes, {
          groupby: model.get('cluster_attr') || viz_state.cats.inst_cell_attr,
          units: 'mean expression per cell',
        }),
    };
  }
  const url = model?.get?.('gene_signature_url');
  if (url) return { required: true, load: () => gene_signatures_source(url) };
  const own_clusters =
    viz_state.img?.landscape_parameters?.technology !== 'Chromium' &&
    !model?.get?.('zarr_url') &&
    !model?.get?.('meta_cell_parquet')?.byteLength;
  if (!own_clusters || !viz_state.global_base_url) return null;
  const version = viz_state.seg?.version;
  const suffix = !version || version === 'default' ? '' : `_${version}`;
  return {
    required: false,
    load: async () =>
      gene_signatures_from_table(
        await get_arrow_table(
          `${viz_state.global_base_url}/df_sig${suffix}.parquet`,
          options.fetch,
          viz_state.aws ?? null
        ),
        {
          groupby: viz_state.cats.inst_cell_attr,
          units: 'mean counts per cell',
        }
      ),
  };
};

export const initialize_viewport_summary = (viz_state) => {
  const { cats, obs_store: obs } = viz_state;
  let signatures;
  let signature_error = false;
  let disposed = false;
  let was_active = false;
  let visible_indices = [];
  let last_bounds = null;
  let all_in_view = false;
  let candidate_genes = [];
  let exact = null;
  let exact_request = 0;
  let exact_loading = false;
  let trx_saved = null;
  // No captions: the bars speak for themselves, and TRX's color shows what the
  // gene bars hold (its tooltip has the details).
  const publish = (observable, bars) => {
    if (observable && !areBarDataEqual(observable.get(), bars))
      observable.set(bars);
  };

  // `mode` is a TRX_MODES key, `status` details for its tooltip; null hands the
  // button back to the spatial view.
  const paint_trx = (mode, status = '') => {
    const { trx: button } = viz_state.buttons?.buttons ?? {};
    if (!button?.style) return;
    if (!mode) {
      if (trx_saved) {
        button
          .style('color', trx_saved.color)
          .style('opacity', trx_saved.opacity)
          .attr('title', trx_saved.title);
      }
      trx_saved = null;
      return;
    }
    trx_saved ??= {
      color: button.style('color'),
      opacity: button.style('opacity'),
      title: button.attr('title'),
    };
    button
      .style('color', TRX_MODES[mode].color)
      .style('opacity', exact_loading ? 0.5 : 1)
      .style('cursor', 'pointer')
      .attr(
        'title',
        status ? `${TRX_MODES[mode].title}\n${status}` : TRX_MODES[mode].title
      );
  };

  const source = signature_loader(viz_state);
  const signature_dataset = viz_state.global_base_url;
  let gene_names;
  let known_genes;
  const update = (bounds) => {
    if (disposed) return;
    const view = obs.landscape_view.get();
    const active = view === 'umap' || view === 'xy';
    if (!active) {
      if (was_active) {
        publish(obs.new_cell_bar_data, cats.cluster_counts);
        publish(obs.new_gene_bar_data, viz_state.genes.top_gene_counts);
        paint_trx(null);
      }
      was_active = false;
      exact = null;
      exact_request += 1;
      exact_loading = false;
      return;
    }
    was_active = true;
    const positions =
      view === 'xy'
        ? viz_state.spatial.cell_xy_scatter_positions
        : viz_state.spatial.cell_umap_scatter_positions;
    if (!positions || !bounds) return;
    const key = [view, bounds.min_x, bounds.max_x, bounds.min_y, bounds.max_y]
      .map(String)
      .join('|');
    if (exact && exact.key !== key) exact = null;
    if (exact_loading && last_bounds?.key !== key) {
      // A pan or zoom cancels the exact calculation for the previous view.
      exact_request += 1;
      exact_loading = false;
    }
    last_bounds = { ...bounds, key };
    const { indices, all, bars } = viewport_cells(positions, cats, bounds);
    visible_indices = indices;
    all_in_view = all;
    publish(obs.new_cell_bar_data, bars);
    // Whole-dataset genes unless every visible cell has a signature.
    let gene_bars = viz_state.genes.top_gene_counts || [];
    let mode = 'dataset';
    let status = '';
    const { gene_names: next_gene_names } = viz_state.genes;
    if (gene_names !== next_gene_names) {
      gene_names = next_gene_names;
      known_genes = gene_names ? new Set(gene_names) : null;
    }
    if (all) {
      // Every cell is in view: the whole-dataset genes are actual, not estimated.
      mode = 'whole';
    } else if (source && signature_dataset !== viz_state.global_base_url) {
      status = source.required
        ? 'Gene signatures belong to the original dataset.'
        : '';
    } else if (signatures && signatures.groupby === cats.inst_cell_attr) {
      const estimate = estimate_viewport_genes(signatures, bars, known_genes);
      if (estimate.covered === indices.length) {
        gene_bars = estimate.bars;
        mode = 'estimate';
        status = `Cell-type means (${signatures.units}) weighted by the cells in view; variation within a cell type is not estimated.`;
      } else {
        status = `Signatures cover ${estimate.covered.toLocaleString()} of ${indices.length.toLocaleString()} cells.`;
      }
    } else if (signatures) {
      status = `Gene estimates require ${signatures.groupby}.`;
    } else if (source?.required) {
      status = signature_error
        ? 'Gene signatures unavailable.'
        : 'Loading gene signatures…';
    }
    candidate_genes = gene_bars;
    if (exact) {
      gene_bars = exact.bars;
      mode = 'exact';
      ({ status } = exact);
    } else if (exact_loading) {
      status = `Reading the exact expression of ${EXACT_GENES} genes…`;
    }
    paint_trx(mode, status);
    publish(obs.new_gene_bar_data, gene_bars);
  };

  const cell_index = (name) => {
    if (viz_state.vector_name_integer) {
      const index = Number(name);
      return Number.isInteger(index) && index < cats.cell_names_array.length
        ? index
        : -1;
    }
    return cats.cell_name_to_index_map?.get(String(name)) ?? -1;
  };

  // TRX in UMAP/XY: exact expression of the top candidate genes, read one gene
  // at a time for the cells in view. Its own cache keeps the gene selection's.
  const compute_exact = async () => {
    // With every cell in view the gene bars already show actual expression.
    if (disposed || !last_bounds || !visible_indices.length || all_in_view)
      return;
    const bounds = last_bounds;
    const genes = candidate_genes
      .slice(0, EXACT_GENES)
      .map(({ name }) => String(name));
    if (!genes.length) return;
    const request = ++exact_request;
    const in_view = new Uint8Array(cats.cell_names_array.length);
    for (const i of visible_indices) in_view[i] = 1;
    exact_loading = true;
    update(bounds);
    const cache = new Map();
    try {
      const exact_bars = await exact_viewport_genes(
        genes,
        in_view,
        visible_indices.length,
        (gene) =>
          load_gene_expression(
            cache,
            viz_state.global_base_url,
            viz_state.seg?.version,
            gene,
            viz_state.aws ?? null,
            viz_state.row_group_readers?.cbg
          ),
        cell_index
      );
      if (disposed || request !== exact_request) return;
      exact = {
        key: bounds.key,
        bars: exact_bars,
        status: `Top ${genes.length} genes, mean per cell of the values that color the cells.`,
      };
    } catch (error) {
      if (disposed || request !== exact_request) return;
      // eslint-disable-next-line no-console
      console.warn('[celldega] exact viewport expression failed', error);
    }
    exact_loading = false;
    update(bounds);
  };

  viz_state.update_embedding_viewport = update;
  viz_state.compute_embedding_viewport_exact = compute_exact;
  if (source) {
    source
      .load()
      .then((loaded) => {
        if (disposed) return;
        signatures = loaded;
        viz_state.refresh_viewport?.();
      })
      .catch(() => {
        if (disposed) return;
        signature_error = true;
        viz_state.refresh_viewport?.();
      });
  }
  return () => {
    disposed = true;
    if (viz_state.update_embedding_viewport === update)
      delete viz_state.update_embedding_viewport;
    if (viz_state.compute_embedding_viewport_exact === compute_exact)
      delete viz_state.compute_embedding_viewport_exact;
    paint_trx(null);
  };
};
