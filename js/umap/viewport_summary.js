import { gene_signatures_source } from '../read_zarr/gene_signatures';
import { areBarDataEqual } from '../utils/compact_data';

import { publish_selected_cells } from './embedding_gates';

export const viewport_cells = (positions, cats, bounds) => {
  const indices = [];
  const counts = new Map();
  for (let i = 0; i < cats.cell_names_array.length; i++) {
    const x = positions[2 * i];
    const y = positions[2 * i + 1];
    if (
      !Number.isFinite(x) ||
      !Number.isFinite(y) ||
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

export const initialize_viewport_summary = (viz_state) => {
  const { cats, obs_store: obs, containers } = viz_state;
  let signatures;
  let signature_error = false;
  let disposed = false;
  let was_active = false;
  let visible_indices = [];
  const panel = containers.bar_cluster?.closest('.ui_container');
  const panel_height = panel?.style.height;
  const captions = ['bar_cluster', 'bar_gene'].map((key) => {
    const caption = document.createElement('div');
    caption.style.cssText =
      'font:11px system-ui;color:#555;margin:4px 0;max-width:145px';
    caption.hidden = true;
    containers[key]?.before(caption);
    return caption;
  });
  const select = document.createElement('button');
  select.textContent = 'Select cells';
  select.setAttribute('aria-label', 'Select cells in view');
  select.title = 'Send all cells in the current viewport to Python';
  select.style.cssText = 'font:11px system-ui;margin-bottom:4px';
  select.hidden = true;
  select.onclick = () =>
    publish_selected_cells(
      viz_state,
      visible_indices.map((i) => cats.cell_names_array[i])
    );
  containers.bar_cluster?.before(select);
  const publish = (observable, bars) => {
    if (observable && !areBarDataEqual(observable.get(), bars))
      observable.set(bars);
  };
  const signature_url = viz_state.model?.get?.('gene_signature_url');
  const signature_dataset = viz_state.global_base_url;
  let gene_names;
  let known_genes;
  const update = (bounds) => {
    if (disposed) return;
    const view = obs.landscape_view.get();
    const active = view === 'umap' || view === 'xy';
    // Leave room for the summary labels while retaining the scrollable bars.
    if (panel) panel.style.height = active ? '150px' : panel_height;
    captions.forEach((caption) => {
      caption.hidden = !active;
    });
    select.hidden = !active || !viz_state.model?.set;
    if (!active) {
      if (was_active) {
        publish(obs.new_cell_bar_data, cats.cluster_counts);
        publish(obs.new_gene_bar_data, viz_state.genes.top_gene_counts);
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
    const { indices, bars } = viewport_cells(positions, cats, bounds);
    visible_indices = indices;
    select.disabled = !indices.length;
    captions[0].textContent = `${indices.length.toLocaleString()} cells in view`;
    publish(obs.new_cell_bar_data, bars);
    let gene_bars = !signature_url ? viz_state.genes.top_gene_counts || [] : [];
    const { gene_names: next_gene_names } = viz_state.genes;
    if (gene_names !== next_gene_names) {
      gene_names = next_gene_names;
      known_genes = gene_names ? new Set(gene_names) : null;
    }
    if (signature_url && signature_dataset !== viz_state.global_base_url) {
      gene_bars = [];
      captions[1].textContent =
        'Gene signatures belong to the original dataset';
    } else if (signatures && signatures.groupby === cats.inst_cell_attr) {
      const estimate = estimate_viewport_genes(signatures, bars, known_genes);
      if (estimate.covered === indices.length) gene_bars = estimate.bars;
      captions[1].textContent =
        estimate.covered === indices.length
          ? `Estimated genes · ${signatures.units}`
          : `Signatures cover ${estimate.covered.toLocaleString()} of ${indices.length.toLocaleString()} cells`;
      captions[1].title = `Cell-type means weighted by cells in view; ${signatures.genes.length.toLocaleString()} genes. Variation within a cell type is not estimated.`;
    } else {
      captions[1].textContent = signatures
        ? `Gene estimates require ${signatures.groupby}`
        : signature_error
          ? 'Gene signatures unavailable'
          : signature_url
            ? 'Loading gene signatures…'
            : 'Genes · whole dataset';
    }
    publish(obs.new_gene_bar_data, gene_bars);
  };
  viz_state.update_embedding_viewport = update;
  if (signature_url) {
    gene_signatures_source(signature_url)
      .then((source) => {
        if (disposed) return;
        signatures = source;
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
    captions.forEach((caption) => caption.remove());
    select.remove();
    if (panel) panel.style.height = panel_height;
  };
};
