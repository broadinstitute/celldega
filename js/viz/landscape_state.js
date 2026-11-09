/**
 * Landscape getters and setters: the Viz API half for a spatial Landscape.
 *
 * `get_landscape_state` reports what the Landscape shows (space, camera, how cells
 * are colored, the selection, and the cluster / gene counts in the current field of
 * view). `apply_landscape_state` changes it through the same code paths as the
 * controls: selecting clusters like the bar chart, coloring by genes like the
 * comma-separated search box, and moving the camera.
 */
import { force_set_selected_cats, update_cat } from '../global_variables/cat';
import { select_genes } from '../global_variables/select_genes';
import { force_set_selected_genes } from '../global_variables/selected_genes';
import { refresh_layer } from '../utils/refresh_layer';

import {
  get_landscape_layers,
  validate_landscape_layers,
  apply_landscape_layers,
} from './landscape_layers';

const MAX_BARS = 25;

/** Settings `apply_landscape_state` understands (the Python apply_state keys). */
export const LANDSCAPE_APPLY_KEYS = [
  'clusters',
  'genes',
  'view',
  'zoom_to',
  'reset_view',
  'space',
  'layers',
  'channels',
  'sliders',
  'image_source',
];
// Margin around a zoom_to target, and the share of cells kept per axis (drops
// stray outliers so one far-off cell doesn't zoom the view all the way out).
const ZOOM_PADDING = 1.15;
const ZOOM_QUANTILE = 0.02;

const round = (value, digits = 3) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  const factor = 10 ** digits;
  return Math.round(number * factor) / factor;
};

const bar_values = (observable, max) =>
  (observable?.get?.() || []).slice(0, max).map((item) => ({
    name: String(item?.name),
    value: round(item?.value),
  }));

const current_space = (viz_state) =>
  viz_state.obs_store?.landscape_view?.get?.() ||
  (viz_state.umap_state ? 'umap' : 'spatial');

/**
 * What the Landscape shows, as plain JSON.
 * @param {object} viz_state
 * @param {{max_bars?: number}} [options]
 */
export const get_landscape_state = (
  viz_state,
  { max_bars = MAX_BARS } = {}
) => {
  const color_by = viz_state.cats?.cat ?? null;
  const view =
    viz_state.current_view_state || viz_state.initial_view_state || {};
  return {
    kind: 'landscape',
    ...get_landscape_layers(viz_state),
    space: current_space(viz_state),
    view_state: {
      target: Array.isArray(view.target)
        ? view.target.map((v) => (Number.isFinite(v) ? v : null))
        : null,
      zoom: Number.isFinite(view.zoom) ? view.zoom : null,
    },
    // 'cluster', a gene name, or 'g1 + g2' when colored by several genes.
    color_by,
    selected_clusters:
      color_by === 'cluster'
        ? (viz_state.cats?.selected_cats || []).map(String)
        : [],
    selected_genes: (viz_state.genes?.selected_genes || []).map(String),
    selected_cells: viz_state.obs_store?.selected_cells?.get?.()?.length || 0,
    // Counts in the current field of view, as in the bar charts: cells per
    // cluster, and transcripts (or mean expression) per gene.
    viewport: {
      clusters: bar_values(viz_state.obs_store?.new_cell_bar_data, max_bars),
      genes: bar_values(viz_state.obs_store?.new_gene_bar_data, max_bars),
      ...(viz_state.viewport_gene_summary
        ? { gene_summary: { ...viz_state.viewport_gene_summary } }
        : {}),
    },
  };
};

const quantile = (sorted, q) =>
  sorted[
    Math.min(sorted.length - 1, Math.max(0, Math.floor(q * sorted.length)))
  ];

/**
 * A view state framing the given cells: by cluster(s) or by cell names.
 * @returns {{target: number[], zoom: number}|null}
 */
export const view_for_cells = (viz_state, { clusters, cells }, size) => {
  const positions =
    viz_state.spatial?.cell_scatter_data?.attributes?.getPosition;
  if (!positions?.value) return null;
  const stride = positions.size || 2;

  let indices = [];
  if (Array.isArray(cells) && cells.length) {
    const index_map = viz_state.cats?.cell_name_to_index_map;
    indices = cells
      .map((name) => index_map?.get?.(String(name)))
      .filter((index) => index !== undefined);
  } else if (Array.isArray(clusters) && clusters.length) {
    const wanted = new Set(clusters.map(String));
    (viz_state.cats?.cell_cats || []).forEach((cat, index) => {
      if (wanted.has(String(cat))) indices.push(index);
    });
  }
  if (!indices.length) return null;

  const xs = indices
    .map((i) => positions.value[i * stride])
    .sort((a, b) => a - b);
  const ys = indices
    .map((i) => positions.value[i * stride + 1])
    .sort((a, b) => a - b);
  const q = indices.length > 50 ? ZOOM_QUANTILE : 0;
  const [x0, x1] = [quantile(xs, q), quantile(xs, 1 - q)];
  const [y0, y1] = [quantile(ys, q), quantile(ys, 1 - q)];

  const width = Math.max(x1 - x0, 1);
  const height = Math.max(y1 - y0, 1);
  // Orthographic views draw 2^zoom pixels per world unit.
  const zoom = Math.log2(
    Math.min(
      size.width / (width * ZOOM_PADDING),
      size.height / (height * ZOOM_PADDING)
    )
  );
  return { target: [(x0 + x1) / 2, (y0 + y1) / 2, 0], zoom };
};

/**
 * Change what the Landscape shows.
 *
 * @param {object} viz_state
 * @param {{layers_obj: object, update_view_state: Function, size: {width: number,
 *   height: number}}} context
 * @param {object} changes - Any of:
 *   space: 'spatial', 'umap' or 'xy';
 *   clusters: cluster names to select (exactly; [] clears the selection);
 *   genes: genes to color cells by (up to 20; [] returns to cluster colors);
 *   view: {target: [x, y], zoom}; zoom_to: {clusters: [...]} or {cells: [...]};
 *   reset_view: true.
 * @returns {Promise<string[]>} What changed.
 */
export const apply_landscape_state = async (
  viz_state,
  context,
  changes = {}
) => {
  const { layers_obj, update_view_state, size } = context;
  const done = [];

  if (!changes || typeof changes !== 'object' || Array.isArray(changes)) {
    throw new Error('changes must be an object');
  }
  const unknown = Object.keys(changes || {}).filter(
    (key) => !LANDSCAPE_APPLY_KEYS.includes(key)
  );
  if (unknown.length) {
    throw new Error(
      `unknown Landscape setting(s): ${unknown.join(', ')}; supported: ${LANDSCAPE_APPLY_KEYS.join(', ')}`
    );
  }

  validate_landscape_layers(viz_state, changes);
  // Resolve invalid requests before selections, gene loads or the camera change.
  for (const key of ['clusters', 'genes']) {
    if (key in changes && !Array.isArray(changes[key])) {
      throw new Error(`${key} must be a list of names`);
    }
  }
  if (changes.genes) {
    if (changes.genes.length > 20)
      throw new Error('genes supports at most 20 names');
    const known = viz_state.genes?.gene_names;
    if (Array.isArray(known)) {
      const available = new Set(known.map(String));
      const missing = changes.genes.filter(
        (gene) => !available.has(String(gene))
      );
      if (missing.length)
        throw new Error(`unknown Landscape genes: ${missing.join(', ')}`);
    }
  }
  if ('reset_view' in changes && typeof changes.reset_view !== 'boolean') {
    throw new Error('reset_view must be a boolean');
  }
  const camera_keys = ['view', 'zoom_to', 'reset_view'].filter(
    (key) => key in changes && (key !== 'reset_view' || changes[key])
  );
  if (camera_keys.length > 1) {
    throw new Error('pass only one of view, zoom_to or reset_view');
  }
  if ('view' in changes) {
    const { view } = changes;
    if (
      !view ||
      typeof view !== 'object' ||
      Array.isArray(view) ||
      !Object.keys(view).length ||
      Object.keys(view).some((key) => !['target', 'zoom'].includes(key))
    ) {
      throw new Error('view must contain target and/or zoom');
    }
    if (
      'target' in view &&
      (!Array.isArray(view.target) ||
        ![2, 3].includes(view.target.length) ||
        !view.target.every(
          (value) => typeof value === 'number' && Number.isFinite(value)
        ))
    ) {
      throw new Error('view.target must contain two or three finite numbers');
    }
    if (
      'zoom' in view &&
      (typeof view.zoom !== 'number' || !Number.isFinite(view.zoom))
    ) {
      throw new Error('view.zoom must be a finite number');
    }
  }
  let framed = null;
  if ('zoom_to' in changes) {
    const target = changes.zoom_to;
    if (
      !target ||
      typeof target !== 'object' ||
      Array.isArray(target) ||
      Object.keys(target).length !== 1 ||
      !['clusters', 'cells'].includes(Object.keys(target)[0]) ||
      !Array.isArray(Object.values(target)[0]) ||
      !Object.values(target)[0].length
    ) {
      throw new Error('zoom_to must contain a nonempty clusters or cells list');
    }
    if ((changes.space ?? current_space(viz_state)) !== 'spatial') {
      throw new Error('zoom_to works in the spatial view; switch space first');
    }
    framed = view_for_cells(viz_state, target, size);
    if (!framed) throw new Error('no matching cells to zoom to');
  }

  // Space first, so a zoom_to in the same change sees the new space. Python sets
  // this as the landscape_state trait; web pages pass it here.
  if (changes.space !== undefined) {
    const space = String(changes.space);
    if (!['spatial', 'umap', 'xy'].includes(space)) {
      throw new Error("space must be 'spatial', 'umap' or 'xy'");
    }
    if (current_space(viz_state) !== space) {
      viz_state.model?.set?.('landscape_state', space);
      viz_state.model?.save_changes?.();
      if (current_space(viz_state) !== space) {
        throw new Error(`this Landscape has no ${space} view`);
      }
      done.push(`switched to the ${space} view`);
    }
  }

  if (Array.isArray(changes.clusters)) {
    const clusters = changes.clusters.map(String);
    // Like clicking cluster bars: cluster colors, this exact selection.
    viz_state.highlighted_cells = new Set();
    viz_state.obs_store.selected_cells?.set?.([]);
    update_cat(viz_state.cats, 'cluster');
    force_set_selected_genes(viz_state.genes, [], viz_state.obs_store);
    force_set_selected_cats(viz_state.cats, clusters, viz_state.obs_store);
    viz_state.obs_store.deck_check.set({
      ...viz_state.obs_store.deck_check.get(),
      cell_layer: false,
      path_layer: false,
      trx_layer: false,
    });
    refresh_layer(viz_state, layers_obj, 'cell_layer');
    done.push(
      clusters.length
        ? `highlighted cluster${clusters.length > 1 ? 's' : ''} ${clusters.join(', ')}`
        : 'cleared the cluster selection'
    );
  }

  if (Array.isArray(changes.genes)) {
    const genes = changes.genes.map(String);
    // Like the comma-separated gene search.
    await select_genes(viz_state, genes);
    refresh_layer(viz_state, layers_obj, 'cell_layer');
    refresh_layer(viz_state, layers_obj, 'trx_layer');
    done.push(
      genes.length
        ? `colored cells by ${genes.join(', ')}`
        : 'returned to cluster colors'
    );
  }

  let new_view = null;
  if (changes.reset_view) {
    new_view = viz_state.initial_view_state;
    done.push('reset the view');
  } else if (changes.zoom_to) {
    new_view = { ...(viz_state.current_view_state || {}), ...framed };
    const what = changes.zoom_to.cells
      ? `${changes.zoom_to.cells.length} cells`
      : `cluster${changes.zoom_to.clusters.length > 1 ? 's' : ''} ${changes.zoom_to.clusters.join(', ')}`;
    done.push(`zoomed to ${what}`);
  } else if (changes.view) {
    const { target, zoom } = changes.view;
    const base =
      viz_state.current_view_state || viz_state.initial_view_state || {};
    new_view = {
      ...base,
      ...(Array.isArray(target)
        ? {
            target: [
              Number(target[0]),
              Number(target[1]),
              Number(target[2] || 0),
            ],
          }
        : {}),
      ...(Number.isFinite(Number(zoom)) ? { zoom: Number(zoom) } : {}),
    };
    done.push('moved the view');
  }
  if (new_view) {
    await update_view_state(new_view, viz_state.close_up);
    viz_state.current_view_state = new_view;
  }

  done.push(...(await apply_landscape_layers(viz_state, context, changes)));
  return done;
};
