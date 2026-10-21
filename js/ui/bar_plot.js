import * as d3 from 'd3';

import { new_toggle_cell_layer_visibility } from '../deck-gl/layers/cell_layer';
import {
  refresh_nbhd_cloud_cluster_cells,
  refresh_nbhd_cloud_gene_cells,
} from '../deck-gl/layers/nbhd_cloud_cell_layer';
import {
  apply_nbhd_cloud_slice_filter,
  select_nbhd_cloud_gene,
  toggle_nbhd_cloud_cluster_selection,
} from '../deck-gl/layers/nbhd_cloud_shapes_layer';
import { toggle_trx_layer_visibility } from '../deck-gl/layers/trx_layer';
import { update_cat, update_selected_cats } from '../global_variables/cat';
import { select_genes } from '../global_variables/select_genes';
import { update_selected_genes } from '../global_variables/selected_genes';
import { escape_html, make_gene_hover_tooltip } from '../ui/gene_info';
import { toggle_slider } from '../ui/sliders';
import { refresh_layer } from '../utils/refresh_layer';
import { register_ui_cleanup } from '../utils/ui_cleanup';

export const make_bar_container = () => {
  return document.createElement('div');
};

/** Height of one bar's rect; bars are laid out every BAR_HEIGHT + 1 px. */
export const BAR_HEIGHT = 15;

/**
 * SVG height that fits `num_bars` bars: each bar is offset 2px and spaced
 * BAR_HEIGHT + 1 apart, so the last bar ends at (BAR_HEIGHT + 1) * n + 1.
 * Sizing to BAR_HEIGHT * (n + 1) instead clipped the last bars (the rarest
 * clusters) once a list had more than ~14 entries.
 *
 * @param {number} num_bars
 * @returns {number}
 */
export const bar_svg_height = (num_bars) => (BAR_HEIGHT + 1) * num_bars + 2;

/**
 * Add `name` to `selected_names`, or remove it if already present (shift-click
 * multi-select). Compares as strings, like the bar highlight.
 *
 * @param {Array<string|number>} selected_names
 * @param {string|number} name
 * @returns {Array<string|number>} A new array.
 */
export const toggle_bar_name = (selected_names, name) => {
  const names = Array.isArray(selected_names) ? selected_names : [];
  const key = String(name);
  return names.some((value) => String(value) === key)
    ? names.filter((value) => String(value) !== key)
    : [...names, name];
};

/**
 * Tooltip HTML for a cluster bar: the cluster name and its cell count, plus a
 * shift-click hint where multi-select is available.
 *
 * @param {{name: string|number, value: number}} d
 * @param {{multi_select?: boolean}} [options]
 * @returns {string}
 */
export const cluster_bar_tooltip_html = (d, { multi_select = false } = {}) => {
  const count = Number(d?.value);
  const count_line = Number.isFinite(count)
    ? `<br>cells: ${count.toLocaleString()}`
    : '';
  const hint = multi_select
    ? '<br><i>Shift-click to select multiple clusters</i>'
    : '';
  return `<span style="color: #7fb0ff;">cluster: ${escape_html(d?.name)}</span>${count_line}${hint}`;
};

// Multi-select is a Landscape feature; Yearbook queries one cluster at a time.
const supports_cluster_multi_select = (viz_state) => !viz_state.yearbook;

/**
 * Show a hover tooltip on bar groups: UniProt name/description for gene bars,
 * name and cell count for cluster bars. One tooltip element per widget, removed
 * when the widget is finalized.
 *
 * @param {d3.Selection} bars - Bar `g` groups (data-bound).
 * @param {'gene'|'cluster'|null} kind
 * @param {object} viz_state
 */
export const attach_bar_tooltip = (bars, kind, viz_state) => {
  if (kind !== 'gene' && kind !== 'cluster') return;

  if (!viz_state.bar_tooltip) {
    viz_state.bar_tooltip = make_gene_hover_tooltip();
    register_ui_cleanup(viz_state, () => {
      viz_state.bar_tooltip?.destroy();
      viz_state.bar_tooltip = null;
    });
  }

  // Read the tooltip off viz_state at event time (it is recreated per widget).
  bars
    .on('mouseenter.tooltip', (event, d) => {
      const tooltip = viz_state.bar_tooltip;
      if (!tooltip || !d) return;
      if (kind === 'gene') {
        tooltip.show(
          String(d.name),
          event,
          viz_state.nbhd_cloud?.is_nbhd_cloud
            ? ''
            : '<br><i>Shift-click to select multiple genes</i>'
        );
      } else {
        tooltip.show_html(
          cluster_bar_tooltip_html(d, {
            multi_select: supports_cluster_multi_select(viz_state),
          }),
          event
        );
      }
    })
    .on('mousemove.tooltip', (event) => viz_state.bar_tooltip?.move(event))
    .on('mouseleave.tooltip', () => viz_state.bar_tooltip?.hide());
};

/**
 * Opacity for a bar given the current selection: full for the selected bar(s)
 * (and for every bar when nothing is selected), dimmed otherwise. The highlight
 * is applied via each bar group's opacity rather than the rect fill's own alpha
 * so a selection change (bar click) and a data re-render can't fight over the
 * same attribute and leave the bar coloring stale.
 *
 * @param {Array<string|number>} selected_names - currently selected bar names
 * @param {string|number} bar_name - the bar being styled
 * @returns {number} 1.0 (highlighted) or 0.2 (dimmed)
 */
export const get_bar_highlight_opacity = (selected_names, bar_name) => {
  const names = (Array.isArray(selected_names) ? selected_names : []).map(
    (name) => String(name)
  );
  if (names.length === 0) {
    return 1.0;
  }
  return names.includes(String(bar_name)) ? 1.0 : 0.2;
};

// The NBHD slider controls cluster-color opacity; the repurposed TRX slider
// controls gene opacity, for either gene mode (sliders.js) -- only one mode
// is ever active at a time, so only one slider should ever be enabled.
// Called after any action that can change `nbhd_cloud.gene_shapes_mode`/
// `gene_scatter_mode` (cluster select, gene select, shape click).
export const sync_nbhd_cloud_opacity_sliders = (viz_state) => {
  const geneMode = Boolean(
    viz_state.nbhd_cloud.gene_shapes_mode ||
      viz_state.nbhd_cloud.gene_scatter_mode
  );
  toggle_slider(viz_state.sliders.nbhd, !geneMode);
  toggle_slider(viz_state.sliders.trx, geneMode);
};

export const bar_callback_cat = (
  _event,
  d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  // ensure that cell button, slider and bars are active
  _viz_state.buttons?.buttons?.cell?.style?.('color', 'blue');

  toggle_slider(_viz_state.sliders.cell, true);
  _viz_state.cats.svg_bar_cluster.selectAll('rect').style('opacity', 1.0);
  new_toggle_cell_layer_visibility(_layers_obj, true);

  if (_viz_state.nbhd.is_nbhd) {
    _viz_state.obs_store.viz_nbhd_layer.set(false);
    _viz_state.obs_store.viz_edit_layer.set(false);
    // wrap in try
    try {
      _viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');
      toggle_slider(_viz_state.sliders.nbhd, false);
    } catch {
      // intentionally ignore missing neighborhood button
    }
  }

  // add cell_layer, path_layer, and trx_layer to the deck_check observable
  _viz_state.obs_store.deck_check.set({
    ..._viz_state.obs_store.deck_check.get(),
    cell_layer: false,
    path_layer: false,
    trx_layer: false,
  });

  // Shift-click adds/removes a cluster from the current cluster selection; a
  // selected gene (cat !== 'cluster') is replaced by a fresh selection.
  const multi_select =
    Boolean(_event?.shiftKey) && supports_cluster_multi_select(_viz_state);
  const current_clusters =
    _viz_state.cats.cat === 'cluster' ? _viz_state.cats.selected_cats : [];
  const new_selected_cats = multi_select
    ? toggle_bar_name(current_clusters, d.name)
    : [d.name];

  update_cat(_viz_state.cats, 'cluster');
  update_selected_cats(
    _viz_state.cats,
    new_selected_cats,
    _viz_state.obs_store
  );
  update_selected_genes(_viz_state.genes, [], _viz_state.obs_store);

  // toggle gene bars based on whether any cluster is still selected
  if (_viz_state.cats.selected_cats.length === 0) {
    _viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);
  } else {
    _viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 0.2);
  }
};

export const bar_callback_gene = async (
  _event,
  d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  if (_viz_state.nbhd_cloud?.is_nbhd_cloud) {
    const isReset = d.name === _viz_state.nbhd_cloud.selected_gene;
    await select_nbhd_cloud_gene(d.name, _viz_state, _layers_obj);
    refresh_layer(_viz_state, _layers_obj, 'nbhd_cloud_shapes_layer');
    refresh_layer(_viz_state, _layers_obj, 'nbhd_cloud_cell_layer');
    sync_nbhd_cloud_opacity_sliders(_viz_state);

    // A gene with neither a shape nor a cell scatter is a no-op
    // (select_nbhd_cloud_gene leaves state untouched) -- don't relabel this
    // bar as "selected" for a click that didn't actually do anything.
    const isAvailable =
      _viz_state.nbhd_cloud.available_gene_shapes?.has(d.name) ||
      _viz_state.nbhd_cloud.available_gene_scatter?.has(d.name);
    if (!isReset && !isAvailable) {
      return;
    }

    // Drives the Uniprot gene-info panel (ui_containers.js's
    // obs_store.selected_genes subscriber) -- nbhd-cloud's gene selection
    // is otherwise entirely separate from this shared store, so without
    // this the panel never updated for a gene picked via the gene bar.
    update_selected_genes(
      _viz_state.genes,
      isReset ? [] : [d.name],
      _viz_state.obs_store
    );

    _viz_state.genes.svg_bar_gene
      .selectAll('rect')
      .style('opacity', (bar) => (isReset || bar.name === d.name ? 1.0 : 0.2));
    // Gene mode just cleared any cluster selection (select_nbhd_cloud_gene)
    // -- the cluster bar's own highlight is this handler's responsibility,
    // same as the gene bar's above.
    _viz_state.nbhd_cloud.svg_bar_cluster
      ?.selectAll('rect')
      .style('opacity', 1.0);
    return;
  }

  // ensure that trx button, slider, and bars are active
  _viz_state.buttons?.buttons?.trx?.style?.('color', 'blue');

  toggle_slider(_viz_state.sliders.trx, true);
  _viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);

  toggle_trx_layer_visibility(_layers_obj, true);

  if (_viz_state.nbhd.is_nbhd) {
    _viz_state.obs_store.viz_nbhd_layer.set(false);
    _viz_state.obs_store.viz_edit_layer.set(false);
    // wrap in try
    try {
      _viz_state.buttons?.buttons?.nbhd?.style?.('color', 'gray');
      toggle_slider(_viz_state.sliders.nbhd, false);
    } catch {
      // intentionally ignore missing neighborhood button
    }
  }

  // Shift-click adds/removes a gene (cells show the summed expression); a
  // plain click selects just this gene, or clears it if it's the only one.
  const current_genes = _viz_state.genes.selected_genes ?? [];
  const new_genes = _event?.shiftKey
    ? toggle_bar_name(current_genes, d.name)
    : current_genes.length === 1 && current_genes[0] === d.name
      ? []
      : [d.name];

  _viz_state.cats.svg_bar_cluster
    .selectAll('rect')
    .style('opacity', new_genes.length === 0 ? 1.0 : 0.2);

  await select_genes(_viz_state, new_genes);
};

export const bar_callback_nbhd = (
  _event,
  _d,
  _deck_ist,
  _layers_obj,
  _viz_state
) => {
  if (_viz_state.nbhd.edit) {
    _viz_state.obs_store.viz_edit_layer.set(true);

    // Safely style the NBHD button if it exists
    // Note: edit buttons are DOM nodes, regular buttons are d3 selections
    if (_viz_state.buttons?.buttons?.nbhd) {
      const btn = _viz_state.buttons.buttons.nbhd;
      if (typeof btn.style === 'function') {
        btn.style('color', 'blue');
      } else {
        d3.select(btn).style('color', 'blue');
      }
    }
    toggle_slider(_viz_state.sliders.nbhd, true);

    const prev_selected_nbhds = _viz_state.obs_store.selected_nbhds.get();
    if (
      prev_selected_nbhds[0] === _d.name &&
      prev_selected_nbhds.length === 1
    ) {
      _viz_state.obs_store.selected_nbhds.set([]);
      _layers_obj.edit_layer = _layers_obj.edit_layer.clone({
        selectedFeatureIndexes: [],
      });
    } else {
      _viz_state.obs_store.selected_nbhds.set([_d.name]);
      // Use edit.feature_collection for edit mode
      const features = _viz_state.edit?.feature_collection?.features || [];
      const featureIndex = features.findIndex(
        (f) => f.properties.name === _d.name || f.properties.cat === _d.name
      );
      if (featureIndex >= 0) {
        _layers_obj.edit_layer = _layers_obj.edit_layer.clone({
          selectedFeatureIndexes: [featureIndex],
        });
      }
    }

    refresh_layer(_viz_state, _layers_obj, 'edit_layer');

    if (_viz_state.obs_store.selected_nbhds.get().length > 0) {
      _viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', (d) => {
        if (d.name === _d.name) {
          return 1.0;
        } else {
          return 0.2;
        }
      });
    } else {
      _viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
    }
  } else {
    _viz_state.obs_store.viz_nbhd_layer.set(true);
    _viz_state.obs_store.viz_edit_layer.set(false);

    // Safely style the NBHD button if it exists
    // Note: edit buttons are DOM nodes, regular buttons are d3 selections
    if (_viz_state.buttons?.buttons?.nbhd) {
      const btn = _viz_state.buttons.buttons.nbhd;
      if (typeof btn.style === 'function') {
        btn.style('color', 'blue');
      } else {
        d3.select(btn).style('color', 'blue');
      }
    }

    const prev_selected_nbhds = _viz_state.obs_store.selected_nbhds.get();
    if (
      prev_selected_nbhds[0] === _d.name &&
      prev_selected_nbhds.length === 1
    ) {
      _viz_state.obs_store.selected_nbhds.set([]);
    } else {
      _viz_state.obs_store.selected_nbhds.set([_d.name]);
    }

    refresh_layer(_viz_state, _layers_obj, 'nbhd_layer');

    if (_viz_state.obs_store.selected_nbhds.get().length > 0) {
      _viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', (d) => {
        if (d.name === _d.name) {
          return 1.0;
        } else {
          return 0.2;
        }
      });
    } else {
      _viz_state.nbhd.svg_bar_nbhd.selectAll('rect').style('opacity', 1.0);
    }
  }
};

// Per-slice bar graph: clicking a slice isolates the 3D view to that
// slice's shapes (every other slice's neighborhoods disappear entirely,
// not just dimmed) -- click again to show every slice. A cluster selection
// (NBHD bar / shape click) stays active across slices, so re-run the cell
// display against whichever cluster is currently selected, narrowed to the
// new slice filter.
export const bar_callback_nbhd_cloud_slice = async (
  _event,
  d,
  _deck_ist,
  layers_obj,
  viz_state
) => {
  const { nbhd_cloud } = viz_state;
  nbhd_cloud.selected_slice_ids ??= new Set();

  if (
    nbhd_cloud.selected_slice_ids.size === 1 &&
    nbhd_cloud.selected_slice_ids.has(d.name)
  ) {
    nbhd_cloud.selected_slice_ids.clear();
  } else {
    nbhd_cloud.selected_slice_ids.clear();
    nbhd_cloud.selected_slice_ids.add(d.name);
  }

  const hasSelection = nbhd_cloud.selected_slice_ids.size > 0;
  nbhd_cloud.svg_bar_slice
    .selectAll('rect')
    .style('opacity', (bar) =>
      !hasSelection || nbhd_cloud.selected_slice_ids.has(bar.name) ? 1.0 : 0.2
    );

  // Filters whichever feature set is currently relevant -- cluster shapes,
  // or the selected gene's own shapes if gene-shapes mode is active -- so
  // isolating a slice while viewing a gene doesn't silently swap back to
  // (filtered) cluster shapes while leaving gene-shapes mode's state stuck on.
  apply_nbhd_cloud_slice_filter(viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');

  // Same "whichever is currently relevant" split for cells -- gene mode's
  // cells (peppered, shape-backed, or scatter-only) live in a different
  // per-gene cache than cluster cells, so re-filtering cluster cells here
  // would silently do nothing while a gene mode is active (the bug: slice
  // isolation had no visible effect on gene cells).
  if (nbhd_cloud.gene_shapes_mode || nbhd_cloud.gene_scatter_mode) {
    await refresh_nbhd_cloud_gene_cells(viz_state, layers_obj);
  } else {
    await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);
  }
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_cell_layer');
};

// Per-cluster bar graph (one bar per cluster, area summed across every
// slice's instance of it): click highlights that cluster's shapes across
// every slice (others dim) and loads its cell centroids on demand -- click
// again to clear both. Same effect as clicking one of that cluster's shapes
// directly (nbhd_cloud_shapes_layer.js's onClick).
export const bar_callback_nbhd_cloud_cluster = async (
  _event,
  d,
  _deck_ist,
  layers_obj,
  viz_state
) => {
  const clusterId = String(d.name);
  toggle_nbhd_cloud_cluster_selection(clusterId, viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_shapes_layer');
  sync_nbhd_cloud_opacity_sliders(viz_state);

  const hasSelection =
    (viz_state.nbhd_cloud.selected_cluster_ids?.size ?? 0) > 0;
  viz_state.nbhd_cloud.svg_bar_cluster
    .selectAll('rect')
    .style('opacity', (bar) =>
      !hasSelection ||
      viz_state.nbhd_cloud.selected_cluster_ids.has(String(bar.name))
        ? 1.0
        : 0.2
    );
  // Cluster selection just cleared gene mode (toggle_nbhd_cloud_cluster_selection)
  // -- the gene bar's own highlight is this handler's responsibility, same
  // as the cluster bar's above.
  viz_state.genes.svg_bar_gene.selectAll('rect').style('opacity', 1.0);

  await refresh_nbhd_cloud_cluster_cells(viz_state, layers_obj);
  refresh_layer(viz_state, layers_obj, 'nbhd_cloud_cell_layer');
};

export const make_bar_graph = (
  bar_container,
  click_callback,
  svg_bar,
  bar_data,
  color_dict,
  deck_ist,
  layers_obj,
  viz_state,
  { tooltip = null } = {}
) => {
  bar_container.className = 'bar_container';
  bar_container.style.width = '107px';
  bar_container.style.height = '72px';
  bar_container.style.marginLeft = '5px';
  bar_container.style.overflowY = 'auto';
  bar_container.style.border = '1px solid #d3d3d3';

  bar_container.addEventListener('wheel', (event) => {
    const { scrollTop, scrollHeight, clientHeight } = bar_container;
    const atTop = scrollTop === 0;
    const atBottom = scrollTop + clientHeight === scrollHeight;

    if ((atTop && event.deltaY < 0) || (atBottom && event.deltaY > 0)) {
      event.preventDefault();
    }
  });

  const bar_height = BAR_HEIGHT;
  const svg_height = bar_svg_height(bar_data.length);

  svg_bar
    .attr('width', 100)
    .attr('height', svg_height)
    .attr('font-family', 'sans-serif')
    .attr('font-size', '13')
    .attr('text-anchor', 'end')
    .style('user-select', 'none');

  bar_container.appendChild(svg_bar.node());

  const max_bar_width = 90;
  const bar_data_values = bar_data.map((x) => x.value);

  const y_new = d3
    .scaleBand()
    .domain(d3.range(bar_data_values.length))
    .range([0, (bar_height + 1) * bar_data_values.length]);

  const x_new = d3
    .scaleLinear()
    // `|| 1` guards an all-zero domain (e.g. no landmarks marked yet) --
    // otherwise a zero-width domain divides by zero and every bar gets a
    // NaN width instead of rendering at 0.
    .domain([0, d3.max(bar_data_values) || 1])
    .range([0, max_bar_width]);

  const bar = svg_bar
    .selectAll('g')
    .data(bar_data)
    .join('g')
    .attr('transform', (d, i) => `translate(2,${y_new(i) + 2})`)
    .on('click', (event, d) =>
      click_callback(event, d, deck_ist, layers_obj, viz_state)
    );

  attach_bar_tooltip(bar, tooltip, viz_state);

  bar
    .append('rect')
    .attr('fill', (d) => {
      // Fall back to a neutral gray instead of throwing when a bar's name has
      // no entry in color_dict (e.g. a data-source mismatch between what
      // populates the bar list and what populates its color lookup) --
      // a missing color shouldn't crash the whole bar graph.
      const inst_rgb = color_dict[d.name] || [128, 128, 128];
      return `rgb(${inst_rgb[0]}, ${inst_rgb[1]}, ${inst_rgb[2]})`;
    })
    .attr('width', (d) => x_new(d.value))
    .attr('height', y_new.bandwidth() - 1);

  bar
    .append('text')
    .attr('fill', 'black')
    .attr('x', '5px')
    .attr('y', y_new.bandwidth() / 2 - 1)
    .attr('dy', '0.35em')
    .attr('text-anchor', 'start')
    .text((d) => d.name);
};
