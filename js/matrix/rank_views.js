// Reduced-dimensionality ("rank") views.
//
// `Matrix.clust(views=...)` precomputes a handful of filter levels -- top N rows
// by marker strength (rank_genes_groups), variance, sum, ... -- and independently
// re-biclusters each one. The slider does not compute anything; it swaps in a
// precomputed level, exactly like Clustergrammer's filter sliders.
//
// Each view arrives already expressed in the *full* matrix's index space:
//   - row_indices: which rows survive (ascending, so scipy leaf id j in this
//                  view's linkage is row_indices[j] -- see alt_slice_linkage)
//   - row_clust / col_clust: full-length order arrays, pre-offset by 1 to match
//                  the front end's order convention
//   - row_linkage / col_linkage: that level's own dendrograms
//
// So applying a view is: set the filter, swap two order arrays and two linkage
// matrices. The existing crop machinery does all the rendering work from there.

import { alt_slice_linkage } from './dendro';

const to_index_array = (values) =>
  Array.isArray(values)
    ? values.map(Number).filter((value) => Number.isFinite(value))
    : [];

/**
 * Parse `network.views` into front-end state. Must run after the label data has
 * populated `viz_state.mat.orders` and `viz_state.linkage`, since the
 * unfiltered ("all") stop is captured from them.
 *
 * @param {object} viz_state - Visualization state.
 * @param {object} network - Network object (views ride along in the metadata).
 */
export const ini_rank_views = (viz_state, network) => {
  const raw = Array.isArray(network?.views) ? network.views : [];

  const views = raw
    .map((view) => ({
      level: Number(view?.level),
      view_type: String(view?.view_type || 'rank'),
      row_indices: to_index_array(view?.row_indices),
      row_clust: to_index_array(view?.row_clust),
      col_clust: to_index_array(view?.col_clust),
      row_linkage: Array.isArray(view?.row_linkage) ? view.row_linkage : [],
      col_linkage: Array.isArray(view?.col_linkage) ? view.col_linkage : [],
    }))
    .map((view) => ({ ...view, n_rows: view.row_indices.length }))
    // Drop anything that doesn't line up with this matrix rather than risk
    // rendering a view against mismatched geometry.
    .filter(
      (view) =>
        Number.isFinite(view.level) &&
        view.row_indices.length > 0 &&
        view.row_clust.length === viz_state.mat.num_rows &&
        view.col_clust.length === viz_state.mat.num_cols &&
        view.row_linkage.length > 0 &&
        view.col_linkage.length > 0
    )
    .sort((a, b) => a.level - b.level);

  viz_state.rank_view = {
    views,
    view_type: views[0]?.view_type || null,
    // The "all" stop: the clustering the widget loaded with. Captured up front
    // because applying a view overwrites these in place.
    base: {
      row_clust: viz_state.mat.orders.row.clust,
      col_clust: viz_state.mat.orders.col.clust,
      row_linkage: viz_state.linkage.row,
      col_linkage: viz_state.linkage.col,
    },
    current: null,
    filter: { row: null, col: null },
    leaf_map: { row: null, col: null },
  };
};

export const has_rank_views = (viz_state) =>
  (viz_state.rank_view?.views?.length || 0) > 0;

/**
 * Slider stops, most-reduced first, with `null` ("all", the full matrix) last.
 *
 * @param {object} viz_state - Visualization state.
 * @returns {Array<number|null>} Ordered stop values.
 */
export const get_rank_view_stops = (viz_state) => [
  ...(viz_state.rank_view?.views || []).map((view) => view.level),
  null,
];

/**
 * Snap a requested row count onto an available stop. Anything falsy, negative,
 * or at/above the largest precomputed level resolves to `null` ("all"), so
 * `rank_dim=0` and an out-of-range request both open unfiltered.
 *
 * @param {object} viz_state - Visualization state.
 * @param {number|null} requested - Requested row count.
 * @returns {number|null} An available level, or null for the full matrix.
 */
export const resolve_rank_view_level = (viz_state, requested) => {
  const views = viz_state.rank_view?.views || [];
  const level = Number(requested);
  if (!views.length || !Number.isFinite(level) || level <= 0) return null;

  // A request past the coarsest precomputed level means "everything".
  const max_level = views[views.length - 1].level;
  if (level > max_level) return null;

  // Ties fall to the smaller level (views are sorted ascending), which keeps
  // the snap conservative rather than showing more rows than asked for.
  const closest = views.reduce((best, view) =>
    Math.abs(view.level - level) < Math.abs(best.level - level) ? view : best
  );

  return closest.level;
};

/**
 * Swap the matrix into a rank view's ordering/linkage, or back to the full
 * matrix when `level` is null. Pure state mutation -- no layer work -- so it can
 * run before layers exist and have the first render already come up reduced.
 *
 * @param {object} viz_state - Visualization state.
 * @param {number|null} level - Target level, or null for the full matrix.
 * @returns {boolean} Whether state actually changed.
 */
export const set_rank_view_state = (viz_state, level) => {
  const { rank_view } = viz_state;
  if (!rank_view) return false;

  const target = level == null ? null : Number(level);
  if (rank_view.current === target) return false;

  const view =
    target == null
      ? null
      : rank_view.views.find((candidate) => candidate.level === target);

  if (target != null && !view) return false;

  const source = view || rank_view.base;

  rank_view.current = view ? view.level : null;
  rank_view.filter = { row: view ? view.row_indices : null, col: null };
  // Only the row axis is filtered, so column leaf ids still line up with column
  // node indices and need no remap.
  rank_view.leaf_map = { row: view ? view.row_indices : null, col: null };

  viz_state.mat.orders.row.clust = source.row_clust;
  viz_state.mat.orders.col.clust = source.col_clust;
  viz_state.linkage.row = source.row_linkage;
  viz_state.linkage.col = source.col_linkage;

  return true;
};

/**
 * Recompute the dendrogram grouping for the linkage a view just swapped in.
 * Re-derives each axis's max linkage distance (view linkages have their own
 * scale) and re-slices at the Dendro slider's current position.
 *
 * @param {object} viz_state - Visualization state.
 */
export const refresh_rank_view_dendro = (viz_state) => {
  ['row', 'col'].forEach((axis) => {
    const link_mat = viz_state.linkage[axis];
    if (!Array.isArray(link_mat) || link_mat.length === 0) return;

    viz_state.dendro.max_linkage_dist[axis] =
      link_mat[link_mat.length - 1][2] + 0.01;

    const percent = Number(
      viz_state.dendro.sliders?.[`${axis}_percent`] ??
        viz_state.dendro.default_link_level * 100
    );
    const dist_thresh =
      (viz_state.dendro.max_linkage_dist[axis] * percent) / 100;

    if (viz_state.dendro.sliders) {
      viz_state.dendro.sliders[`${axis}_value`] = dist_thresh;
    }

    alt_slice_linkage(viz_state, axis, dist_thresh);
  });
};
