import { options } from '../global_variables/fetch_options';
import { get_arrow_table } from '../read_parquet/get_arrow_table';
import {
  gene_signatures_from_parquet,
  gene_signatures_from_table,
  gene_signatures_source,
} from '../read_zarr/gene_signatures';
import { areBarDataEqual } from '../utils/compact_data';

// UMAP/XY gene bars use whole-dataset values or cell-type signature estimates.
const TRX_MODES = {
  whole: {
    color: 'blue',
    title: 'Whole-dataset expression: every cell is in view.',
  },
  estimate: {
    color: 'purple',
    title: 'Estimated from cell-type signatures.',
  },
  dataset: {
    color: 'gray',
    title: 'Whole-dataset genes; viewport signatures are unavailable.',
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
          .attr('title', trx_saved.title)
          .style('cursor', trx_saved.cursor);
      }
      trx_saved = null;
      return;
    }
    trx_saved ??= {
      color: button.style('color'),
      opacity: button.style('opacity'),
      title: button.attr('title'),
      cursor: button.style('cursor'),
    };
    button
      .style('color', TRX_MODES[mode].color)
      .style('opacity', 1)
      .style('cursor', 'default')
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
      return;
    }
    was_active = true;
    const positions =
      view === 'xy'
        ? viz_state.spatial.cell_xy_scatter_positions
        : viz_state.spatial.cell_umap_scatter_positions;
    if (!positions || !bounds) return;
    const { indices, all, bars } = viewport_cells(positions, cats, bounds);
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
    paint_trx(mode, status);
    publish(obs.new_gene_bar_data, gene_bars);
  };

  viz_state.update_embedding_viewport = update;
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
    paint_trx(null);
  };
};
