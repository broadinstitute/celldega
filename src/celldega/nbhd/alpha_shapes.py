"""Module for alpha shapes computation."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
import json
from typing import Any

import anndata as ad
import geopandas as gpd
from libpysal.cg import alpha_shape as libpysal_alpha_shape
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Point, base, shape

from .utils import _classify_polygons_contains_check, _round_coordinates, _stamp_z


def _verify_polygons_with_alpha_bulk(
    polygons: gpd.GeoSeries | Sequence[base.BaseGeometry],
    points: Sequence[Any],
    alpha: float,
    area_tolerance: float = 0.05,
) -> gpd.GeoSeries:
    """
    Verifies polygons by recalculating alpha shapes and ensuring agreement, using bulk spatial queries.

    Parameters
    ----------
    polygons : GeoSeries of polygons (GeoPandas)
    points : Array-like of point coordinates (e.g., numpy array or list of tuples)
    alpha : float
        Alpha value for recalculating alpha shapes

    Returns
    -------
    GeoSeries of curated polygons
    """
    curated_polygons: list[base.BaseGeometry] = []
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])
    points_sindex = points_gdf.sindex

    for poly in polygons:
        possible_matches_index = list(points_sindex.query(poly, predicate="intersects"))
        contained_points = points_gdf.iloc[possible_matches_index]

        if len(contained_points) < 4:
            continue

        coords = np.array([p.coords[0] for p in contained_points.geometry])
        try:
            recalculated_alpha = libpysal_alpha_shape(coords, alpha)
        except Exception:
            # A small fraction of point configurations produce a
            # self-intersecting triangulation that trips GEOS's spatial-index
            # query inside libpysal's alpha_shape (e.g. GEOSException:
            # "side location conflict" / "TopologyException") — a libpysal/GEOS
            # fragility, not specific to any one dataset. Treat this candidate
            # as failing verification (same as the area-tolerance/min-points
            # checks below) rather than aborting the whole batch over one
            # unverifiable polygon.
            continue

        if recalculated_alpha.shape[0] > 0:
            recalculated_area = recalculated_alpha.area.values[0]
            original_area = poly.area
            area_difference = abs(recalculated_area - original_area) / original_area

            if area_difference <= area_tolerance:
                curated_polygons.append(poly)

    return gpd.GeoSeries(curated_polygons, crs=getattr(polygons, "crs", None))


def alpha_shape(
    points: np.ndarray,
    inv_alpha: float,
) -> MultiPolygon:
    try:
        poly = libpysal_alpha_shape(points, 1 / inv_alpha)
    except Exception:
        # Same libpysal/GEOS fragility handled below in
        # `_verify_polygons_with_alpha_bulk` (e.g. GEOSException: "side
        # location conflict" from a self-intersecting triangulation) -- a
        # small fraction of point configurations trip GEOS's spatial-index
        # query inside libpysal's alpha_shape itself, before verification
        # even runs. Treat this point set as producing no shape rather than
        # aborting the whole batch over one unrepresentable configuration.
        return MultiPolygon()
    gdf_curated = _classify_polygons_contains_check(poly.values, points)
    validated_poly = _verify_polygons_with_alpha_bulk(
        gdf_curated.geometry.values,
        points,
        1 / inv_alpha,
    )
    return MultiPolygon(validated_poly.values)


def alpha_shape_cell_clusters(
    adata: ad.AnnData,
    cat: str = "cluster",
    alphas: Sequence[float] = (100, 150, 200, 250, 300, 350),
    meta_cluster: pd.DataFrame | None = None,
) -> gpd.GeoDataFrame:
    """
    Compute alpha shapes for each cluster in the cell metadata.

    Parameters
    ----------
    adata : AnnData
        AnnData object with cell metadata in obs and spatial coordinates in obsm["spatial"].
    cat : str
        Column name in adata.obs containing cluster/category labels.
    alphas : Sequence[float]
        List of inverse alpha values to compute shapes for.
    meta_cluster : pd.DataFrame | None
        Optional DataFrame with cluster metadata including 'color' column.
        If not provided, colors will be extracted from adata.uns[f'{cat}_colors']
        if available, otherwise defaults to black.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with alpha shapes for each cluster at each alpha value.
    """

    # Copy so we don't add a 'geometry' column to the caller's adata.obs (which
    # would otherwise leak into downstream serialization, e.g. Landscape parquet).
    meta_cell = adata.obs.copy()

    coords = adata.obsm["spatial"]
    meta_cell["geometry"] = list(coords)

    # Build color lookup from adata.uns if meta_cluster not provided
    adata_color_dict: dict[str, str] = {}
    if meta_cluster is None:
        color_key = f"{cat}_colors"
        if color_key in adata.uns:
            # Get categories and their corresponding colors
            categories = (
                adata.obs[cat].cat.categories
                if hasattr(adata.obs[cat], "cat")
                else adata.obs[cat].unique()
            )
            colors = adata.uns[color_key]
            # Map categories to colors (colors are in same order as categories)
            for i, category in enumerate(categories):
                if i < len(colors):
                    adata_color_dict[str(category)] = colors[i]

    gdf_alpha = gpd.GeoDataFrame()

    for inv_alpha in alphas:
        for inst_cluster in meta_cell[cat].unique():
            inst_clust = meta_cell[meta_cell[cat] == inst_cluster]
            if inst_clust.shape[0] > 3:
                nested_array = inst_clust["geometry"].values
                flat_array = np.vstack(nested_array)
                inst_shape = alpha_shape(flat_array, inv_alpha)

                inst_name = f"{inst_cluster}_{inv_alpha}"

                gdf_alpha.loc[inst_name, "name"] = inst_name
                gdf_alpha.loc[inst_name, "cat"] = inst_cluster
                gdf_alpha.loc[inst_name, "geometry"] = inst_shape
                gdf_alpha.loc[inst_name, "inv_alpha"] = int(inv_alpha)

                # Look up color: meta_cluster > adata.uns colors > default black
                inst_cluster_str = str(inst_cluster)
                if meta_cluster is not None and inst_cluster in meta_cluster.index:
                    gdf_alpha.loc[inst_name, "color"] = meta_cluster.loc[inst_cluster, "color"]
                elif inst_cluster_str in adata_color_dict:
                    gdf_alpha.loc[inst_name, "color"] = adata_color_dict[inst_cluster_str]
                else:
                    gdf_alpha.loc[inst_name, "color"] = "#000000"

    gdf_alpha["geometry"] = gdf_alpha["geometry"].apply(
        lambda geom: _round_coordinates(geom, precision=2)
    )
    gdf_alpha["area"] = gdf_alpha.area

    return gdf_alpha.loc[gdf_alpha.area.sort_values(ascending=False).index.tolist()]


def alpha_shape_cell_clusters_by_slice(
    adata: ad.AnnData,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    meta_cluster: pd.DataFrame | None = None,
    z_jitter: float = 0.1,
) -> gpd.GeoDataFrame:
    """
    Compute one alpha shape per (slice, cluster) pair, each stamped with its slice's Z.

    Mirrors the approach validated in
    `notebooks/Serial_Slice_Alpha_Shapes_3D_Demo.ipynb`: for each slice, builds a
    throwaway per-slice `AnnData` and reuses `alpha_shape_cell_clusters` /
    `filter_alpha_shapes` at a single alpha resolution, then stamps every
    resulting polygon with that slice's Z (from `z_attr`, or 0.0 if not given)
    plus a small per-cluster jitter (via `_stamp_z`) so overlapping, coplanar
    cluster polygons within a slice don't z-fight.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData with spatial coordinates in `obsm["spatial"]` and
        `cluster_attr` / `slice_attr` (and, if given, `z_attr`) columns in `obs`.
    cluster_attr : str
        Column in `adata.obs` with cluster/category labels.
    slice_attr : str
        Column in `adata.obs` identifying each slice.
    z_attr : str | None
        Column in `adata.obs` with each cell's Z coordinate (expected to be one
        constant value per slice, e.g. from `celldega.align.serial_slices`). If
        None, every slice is stamped at Z=0 (e.g. for a future 2D
        "neighborhood-scape" use where "slice" means "dataset").
    alphas : Sequence[float]
        Must contain exactly one inverse-alpha resolution (see `alpha_shape`) —
        this function computes a single resolution per (slice, cluster), unlike
        `alpha_shape_cell_clusters` which can sweep several.
    meta_cluster : pd.DataFrame | None
        Optional cluster color/metadata lookup, forwarded to
        `alpha_shape_cell_clusters`.
    z_jitter : float
        Per-cluster Z offset within a slice, to avoid z-fighting between
        coplanar cluster polygons that would otherwise sit at the exact same Z.

    Returns
    -------
    gpd.GeoDataFrame
        One row per (slice, cluster) neighborhood, with columns `name`
        (`f"{slice_id}__{cluster_id}"`), `cluster_id`, `slice_id`, `geometry`
        (3D), `color`, `area`, `inv_alpha`, `cell_count`.
    """
    if len(alphas) != 1:
        raise ValueError(
            "alpha_shape_cell_clusters_by_slice computes a single alpha-shape "
            "resolution per (slice, cluster); pass exactly one value in `alphas`"
        )
    alpha = alphas[0]

    obs = adata.obs
    coords = np.asarray(adata.obsm["spatial"])

    gdfs: list[gpd.GeoDataFrame] = []
    for slice_id in obs[slice_attr].unique():
        mask = (obs[slice_attr] == slice_id).to_numpy()
        cluster_values = obs.loc[mask, cluster_attr].to_numpy()

        adata_slice = ad.AnnData(
            obs=pd.DataFrame({cluster_attr: cluster_values}),
            obsm={"spatial": coords[mask, :2].astype(float)},
        )

        gdf_alpha = alpha_shape_cell_clusters(
            adata_slice, cat=cluster_attr, alphas=[alpha], meta_cluster=meta_cluster
        )
        if gdf_alpha.empty:
            continue
        gdf_alpha = filter_alpha_shapes(gdf_alpha, alpha=alpha).reset_index(drop=True)
        if gdf_alpha.empty:
            continue

        z_val = float(obs.loc[mask, z_attr].iloc[0]) if z_attr is not None else 0.0
        z_per_cluster = z_val + gdf_alpha.index.to_numpy(dtype=float) * z_jitter
        gdf_alpha["geometry"] = [
            _stamp_z(geom, z) for geom, z in zip(gdf_alpha["geometry"], z_per_cluster, strict=True)
        ]

        cell_counts = pd.Series(cluster_values).astype(str).value_counts()
        gdf_alpha["cluster_id"] = gdf_alpha["name"].astype(str)
        gdf_alpha["slice_id"] = slice_id
        gdf_alpha["cell_count"] = gdf_alpha["cluster_id"].map(cell_counts).fillna(0).astype(int)
        gdf_alpha["name"] = gdf_alpha["slice_id"].astype(str) + "__" + gdf_alpha["cluster_id"]

        gdfs.append(gdf_alpha)

    if not gdfs:
        raise ValueError("no alpha shapes could be computed for any slice")

    return gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), geometry="geometry")


# A gene's index-within-`gene_list` is reduced modulo this many buckets, each
# a full `z_jitter` step apart -- bounds total Z spread to
# `_Z_JITTER_BUCKETS * z_jitter` (~20 at the default 0.1, still small next to
# a typical few-hundred-unit inter-slice Z spacing) no matter how many genes
# are in play, while keeping each step's *size* exactly `z_jitter` so it
# survives the 2-decimal-place rounding `_round_coordinates` applies
# downstream (a step scaled down by dividing z_jitter across many buckets
# would round back to 0 and defeat the whole point). Prime, so bucket
# assignment doesn't alias on a common factor in gene_list ordering.
_Z_JITTER_BUCKETS = 199


def _gene_z_offset(gene_index: int, z_jitter: float) -> float:
    """A small, deterministic per-gene Z offset -- avoids exact z-fighting
    between different genes' shapes landing in the same slice, without
    needing every gene's shapes for that slice computed up front to hand out
    sequential offsets (which the streaming, one-gene-at-a-time writer in
    `celldega.pre.nbhd_cloud.write_gene_shapes_streaming` can't do). Always 0
    for `gene_index == 0`, so a single-gene call is unaffected. Depth testing
    is disabled on the JS side for this layer already (see
    `nbhd_cloud_shapes_layer.js`), so an occasional bucket collision between
    two genes in the same slice is a minor cosmetic risk, not a rendering
    bug.
    """
    return (gene_index % _Z_JITTER_BUCKETS) * z_jitter


_GENE_SHAPE_COLUMNS = [
    "name",
    "gene",
    "slice_id",
    "geometry",
    "area",
    "inv_alpha",
    "cell_count",
    "mean_expression",
    "max_expression",
]

# `cells/by_gene/<gene>.parquet` schema -- mirrors `cells/by_cluster/<id>
# .parquet`'s cell_id/x/y/z/slice_id columns, with `expression` standing in
# for `cluster_id` since these cells are selected/colored by expression, not
# category.
_GENE_CELL_COLUMNS = ["cell_id", "gene", "slice_id", "x", "y", "z", "expression"]


def _select_top_expressing_cells(
    expr: np.ndarray,
    min_expression: float,
    max_cells: int,
) -> np.ndarray:
    """Indices of up to `max_cells` highest-`expr` cells among those with
    `expr >= min_expression` (the same "expressing" population the alpha
    shape itself is built from) -- an O(n) top-K selection (argpartition),
    not a full sort, since `max_cells` is meant to bound a per-gene cell
    file to a small fraction of a whole-tissue cell count regardless of how
    broadly the gene is actually expressed."""
    candidate_idx = np.flatnonzero(expr >= min_expression)
    if max_cells <= 0 or candidate_idx.size == 0:
        return candidate_idx[:0]
    if candidate_idx.size <= max_cells:
        return candidate_idx
    top_within = np.argpartition(expr[candidate_idx], -max_cells)[-max_cells:]
    return candidate_idx[top_within]


def iter_gene_alpha_shapes(
    coords: np.ndarray,
    slice_ids: np.ndarray,
    z_values: np.ndarray,
    gene_expression: Iterable[tuple[str, np.ndarray]],
    cell_ids: np.ndarray | None = None,
    alphas: Sequence[float] = (150,),
    min_expression: float = 2.0,
    min_cells: int = 4,
    z_jitter: float = 0.1,
    max_cells: int = 50_000,
) -> Iterator[tuple[str, gpd.GeoDataFrame, pd.DataFrame]]:
    """
    Yield `(gene, gdf_gene, df_cells)` one gene at a time, from a
    caller-supplied stream of `(gene, expression_array)` pairs — no
    `AnnData` involved.

    This is the AnnData-free core `iter_gene_alpha_shapes_by_slice` wraps:
    that function exists for the interactive-analysis case where you
    already have (or are willing to build) an `AnnData` with every gene in
    `gene_list` loaded into `.X`. This function instead takes a plain
    per-cell coordinate/slice/Z array plus an *iterable* of
    `(gene, expression_array)` — the caller decides how each gene's
    expression array is produced, which matters when the source is
    per-gene files (e.g. `cbg/<gene>.parquet`, see
    `celldega.pre.nbhd_cloud.write_gene_shapes_from_cbg`): a plain
    generator can read one gene's file, hand back its array, and let the
    caller's reference to it drop before the next gene is read, without
    ever assembling a combined multi-gene matrix (dense or sparse) or an
    `AnnData` wrapper around it — pure overhead when nothing downstream
    ever needs more than one gene's expression at a time.

    Alongside each gene's shape, also selects up to `max_cells` of that
    gene's own highest-expressing cells (same `min_expression` threshold as
    the shape) — real cell centroids to "pepper" the alpha shape with in
    the frontend, grounding the coarse polygon in actual single-cell
    positions. Capped rather than exhaustive because an unbounded per-gene
    cell file would scale with how many cells express the gene, not with
    dataset size in general — a broadly-expressed gene could otherwise mean
    a cell file sized like the whole dataset.

    Parameters
    ----------
    coords : np.ndarray
        Per-cell spatial coordinates, shape `(n_cells, >=2)` — only the
        first two columns are used for the alpha shape itself.
    slice_ids : np.ndarray
        Per-cell slice identifier, shape `(n_cells,)`.
    z_values : np.ndarray
        Per-cell Z coordinate, shape `(n_cells,)` (all zeros for a 2D run).
        Expected constant within a slice, like elsewhere in this module.
    gene_expression : Iterable[tuple[str, np.ndarray]]
        Yields `(gene, expr)` pairs, `expr` a per-cell array aligned to
        `coords`/`slice_ids`/`z_values` (same order, same length). Genes are
        processed in the order this iterable yields them (and that order is
        what `_gene_z_offset` derives each gene's Z bucket from).
    cell_ids : np.ndarray | None
        Per-cell identifier, shape `(n_cells,)`, aligned like `coords`. If
        None, `df_cells` is always empty (no cell selection performed) --
        e.g. when a caller only wants shapes and doesn't have cell ids handy.
    alphas, min_expression, min_cells, z_jitter :
        Same meaning as `alpha_shape_gene_expression_by_slice`.
    max_cells : int
        Cap on the number of top-expressing cells selected per gene (across
        all slices combined). 0 (or `cell_ids=None`) skips cell selection
        entirely, yielding an always-empty `df_cells`.

    Yields
    ------
    tuple[str, gpd.GeoDataFrame, pd.DataFrame]
        `(gene, gdf_gene, df_cells)` — `gdf_gene` as documented on
        `iter_gene_alpha_shapes_by_slice`. `df_cells` has columns
        `cell_id`, `gene`, `slice_id`, `x`, `y`, `z`, `expression` — one row
        per selected cell, empty (zero rows, same columns) if no cells were
        selected (no `cell_ids`, `max_cells <= 0`, or no expressing cells).
    """
    if len(alphas) != 1:
        raise ValueError(
            "iter_gene_alpha_shapes computes a single alpha-shape resolution "
            "per (slice, gene); pass exactly one value in `alphas`"
        )
    alpha = alphas[0]

    coords = np.asarray(coords)
    slice_ids = np.asarray(slice_ids)
    z_values = np.asarray(z_values, dtype=float)
    cell_ids_arr = np.asarray(cell_ids) if cell_ids is not None else None
    unique_slice_ids = pd.unique(slice_ids)

    # Each slice's Z stamped once, up front -- cheap (one value per slice),
    # and avoids recomputing it for every gene.
    slice_masks = {slice_id: slice_ids == slice_id for slice_id in unique_slice_ids}
    slice_z = {
        slice_id: float(z_values[mask][0]) if mask.any() else 0.0
        for slice_id, mask in slice_masks.items()
    }

    for gene_index, (gene, expr) in enumerate(gene_expression):
        expr = np.asarray(expr)
        max_expression = float(expr.max()) if expr.size else 0.0

        rows: list[dict[str, Any]] = []
        for slice_id, slice_mask in slice_masks.items():
            gene_mask = slice_mask & (expr >= min_expression)
            if gene_mask.sum() < min_cells:
                continue

            points = coords[gene_mask, :2].astype(float)
            geometry = alpha_shape(points, alpha)
            if geometry.is_empty:
                # Either GEOS choked on this point configuration (see
                # `alpha_shape`) or every candidate triangle failed
                # verification -- either way, no representable shape for
                # this (slice, gene) pair, so skip it like a below-`min_cells`
                # pair rather than writing a degenerate empty geometry.
                continue

            z = slice_z[slice_id] + _gene_z_offset(gene_index, z_jitter)
            geometry = _round_coordinates(_stamp_z(geometry, z), precision=2)

            rows.append(
                {
                    "gene": gene,
                    "slice_id": slice_id,
                    "geometry": geometry,
                    "mean_expression": float(expr[gene_mask].mean()),
                    "cell_count": int(gene_mask.sum()),
                }
            )

        if cell_ids_arr is not None:
            top_idx = _select_top_expressing_cells(expr, min_expression, max_cells)
        else:
            top_idx = np.empty(0, dtype=int)

        if top_idx.size:
            # Real cell Z (not jittered) -- cell centroids render in a
            # separate depth-test-disabled PointCloudLayer, so they don't
            # need the shapes' anti-z-fighting jitter (see nbhd_cloud_cell_layer.js).
            df_cells = pd.DataFrame(
                {
                    "cell_id": cell_ids_arr[top_idx],
                    "gene": gene,
                    "slice_id": slice_ids[top_idx],
                    "x": coords[top_idx, 0].astype(float),
                    "y": coords[top_idx, 1].astype(float),
                    "z": z_values[top_idx],
                    "expression": expr[top_idx].astype(float),
                }
            )[_GENE_CELL_COLUMNS]
        else:
            df_cells = pd.DataFrame(columns=_GENE_CELL_COLUMNS)

        if not rows:
            yield gene, gpd.GeoDataFrame(columns=_GENE_SHAPE_COLUMNS, geometry="geometry"), df_cells
            continue

        df_gene = pd.DataFrame(rows)
        df_gene["inv_alpha"] = int(alpha)
        df_gene["name"] = df_gene["slice_id"].astype(str) + "__" + df_gene["gene"].astype(str)
        gdf_gene = gpd.GeoDataFrame(df_gene, geometry="geometry")
        gdf_gene["area"] = gdf_gene.area
        gdf_gene["max_expression"] = max_expression

        yield gene, gdf_gene[_GENE_SHAPE_COLUMNS], df_cells


def iter_gene_alpha_shapes_by_slice(
    adata: ad.AnnData,
    gene_list: Sequence[str],
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    min_expression: float = 2.0,
    min_cells: int = 4,
    z_jitter: float = 0.1,
    max_cells: int = 50_000,
) -> Iterator[tuple[str, gpd.GeoDataFrame, pd.DataFrame]]:
    """
    Yield `(gene, gdf_gene, df_cells)` one gene at a time, instead of
    building the whole (slice, gene) result set in memory before returning
    anything.

    An `AnnData`-sourcing wrapper around `iter_gene_alpha_shapes`: for each
    gene in `gene_list`, densifies that one column from `adata.X` and hands
    it to `iter_gene_alpha_shapes` (along with `adata.obs_names` as cell
    ids). Convenient when you already have (or are willing to build) an
    `AnnData` with every gene in `gene_list` loaded —
    `alpha_shape_gene_expression_by_slice` (a thin eager wrapper around this
    generator) is the interactive/analysis entry point for that case. If
    your genes instead come from per-gene files (e.g. `cbg/<gene>.parquet`)
    and you don't want to assemble a combined multi-gene `AnnData` just to
    call this, use `iter_gene_alpha_shapes` directly with a generator that
    reads one file per gene — see
    `celldega.pre.nbhd_cloud.write_gene_shapes_from_cbg`.

    Parameters
    ----------
    adata, slice_attr, z_attr, alphas, min_expression, min_cells, z_jitter :
        Same meaning as `alpha_shape_gene_expression_by_slice`.
    gene_list : Sequence[str]
        Genes to compute shapes for, in the order they'll be processed (and
        the order `_gene_z_offset` derives each gene's Z bucket from).
    max_cells : int
        Forwarded to `iter_gene_alpha_shapes` — cap on top-expressing cells
        selected per gene (0 skips cell selection).

    Yields
    ------
    tuple[str, gpd.GeoDataFrame, pd.DataFrame]
        `(gene, gdf_gene, df_cells)` — `gdf_gene` has columns `name`
        (`f"{slice_id}__{gene}"`), `gene`, `slice_id`, `geometry` (3D),
        `area`, `inv_alpha`, `cell_count`, `mean_expression`,
        `max_expression` (whole-tissue single-cell max for that gene). Empty
        (zero rows, same columns) if the gene produced no usable shape in
        any slice -- below `min_cells` everywhere, or every candidate shape
        failed verification / GEOS choked (see `alpha_shape`). `df_cells`
        has columns `cell_id`, `gene`, `slice_id`, `x`, `y`, `z`,
        `expression` — see `iter_gene_alpha_shapes`.
    """
    missing = [gene for gene in gene_list if gene not in adata.var_names]
    if missing:
        raise ValueError(f"genes not found in adata.var_names: {missing}")

    obs = adata.obs
    coords = np.asarray(adata.obsm["spatial"])
    slice_ids = obs[slice_attr].to_numpy()
    z_values = obs[z_attr].to_numpy(dtype=float) if z_attr is not None else np.zeros(len(obs))
    cell_ids = adata.obs_names.astype(str).to_numpy()
    gene_positions = {gene: adata.var_names.get_loc(gene) for gene in gene_list}

    def _gene_column(gene: str) -> np.ndarray:
        col = adata.X[:, gene_positions[gene]]
        col = col.toarray() if hasattr(col, "toarray") else np.asarray(col)
        return col.ravel()

    def _gene_expression() -> Iterator[tuple[str, np.ndarray]]:
        for gene in gene_list:
            # Densified once per gene, reused across every slice inside
            # `iter_gene_alpha_shapes` -- a CSR column slice is an O(nnz)
            # scan, so re-fetching it per slice would mean re-scanning the
            # whole matrix once per slice per gene.
            yield gene, _gene_column(gene)

    yield from iter_gene_alpha_shapes(
        coords,
        slice_ids,
        z_values,
        _gene_expression(),
        cell_ids=cell_ids,
        alphas=alphas,
        min_expression=min_expression,
        min_cells=min_cells,
        z_jitter=z_jitter,
        max_cells=max_cells,
    )


def alpha_shape_gene_expression_by_slice(
    adata: ad.AnnData,
    gene_list: Sequence[str],
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    min_expression: float = 2.0,
    min_cells: int = 4,
    z_jitter: float = 0.1,
) -> gpd.GeoDataFrame:
    """
    Compute one alpha shape per (slice, gene) pair, built from expressing cells.

    Generalizes `alpha_shape_cell_clusters_by_slice` — instead of grouping
    cells by a cluster label, each shape is built from whichever cells have
    `adata[:, gene].X >= min_expression` within that slice. A thin eager
    wrapper around `iter_gene_alpha_shapes_by_slice` that collects every
    gene's shapes into one GeoDataFrame before returning — convenient for
    interactive/analysis use on a bounded gene list (a curated marker
    panel), but holds every gene's shapes for every slice in memory at once.
    For a whole-transcriptome gene list (~40k genes), use
    `iter_gene_alpha_shapes_by_slice` directly, or
    `celldega.pre.nbhd_cloud.write_gene_shapes_streaming` to write results to
    DegaFiles as they're produced instead of materializing all of them.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData with spatial coordinates in `obsm["spatial"]`,
        `slice_attr` (and, if given, `z_attr`) columns in `obs`, and `gene_list`
        present in `adata.var_names`.
    gene_list : Sequence[str]
        Genes to compute shapes for. Must all be present in `adata.var_names`.
    slice_attr : str
        Column in `adata.obs` identifying each slice.
    z_attr : str | None
        Column in `adata.obs` with each cell's Z coordinate. If None, every
        slice is stamped at Z=0.
    alphas : Sequence[float]
        Must contain exactly one inverse-alpha resolution — one resolution
        per (slice, gene), same restriction as `alpha_shape_cell_clusters_by_slice`.
    min_expression : float
        A cell counts as "expressing" a gene when its value is at least this
        (default: 2 counts).
    min_cells : int
        Minimum number of expressing cells required to compute a shape for a
        (slice, gene) pair; pairs with fewer are silently skipped.
    z_jitter : float
        Small per-gene Z offset, to avoid z-fighting between coplanar gene
        shapes that would otherwise sit at the exact same Z (see
        `_gene_z_offset`).

    Returns
    -------
    gpd.GeoDataFrame
        One row per (slice, gene) shape, with columns `name`
        (`f"{slice_id}__{gene}"`), `gene`, `slice_id`, `geometry` (3D),
        `area`, `inv_alpha`, `cell_count`, `mean_expression`, and
        `max_expression` (whole-tissue single-cell max for that gene,
        repeated across every row of that gene — see `write_gene_shapes`).
    """
    dfs = [
        gdf_gene
        # max_cells=0: this function only ever returns shapes, so skip the
        # (otherwise wasted) top-expressing-cell selection entirely.
        for _, gdf_gene, _ in iter_gene_alpha_shapes_by_slice(
            adata,
            gene_list,
            slice_attr=slice_attr,
            z_attr=z_attr,
            alphas=alphas,
            min_expression=min_expression,
            min_cells=min_cells,
            z_jitter=z_jitter,
            max_cells=0,
        )
        if not gdf_gene.empty
    ]

    if not dfs:
        raise ValueError("no gene alpha shapes could be computed for any slice")

    return gpd.GeoDataFrame(pd.concat(dfs, ignore_index=True), geometry="geometry")


def filter_alpha_shapes(
    gdf_alpha: gpd.GeoDataFrame,
    alpha: float,
    min_area: float = 0,
    clean_names: bool = True,
) -> gpd.GeoDataFrame:
    """
    Filter alpha shapes by a specific alpha value and optionally clean up names.

    Alpha shapes computed by `alpha_shape_cell_clusters` have names in the format
    `{category}_{alpha}` (e.g., "cluster_0_150"). This function filters to a specific
    alpha value and removes the trailing `_{alpha}` suffix from names.

    Parameters
    ----------
    gdf_alpha : gpd.GeoDataFrame
        GeoDataFrame of alpha shapes with 'inv_alpha', 'area', 'name', and 'cat' columns.
        Typically the output of `alpha_shape_cell_clusters`.
    alpha : float
        The inverse alpha value to filter for (must match values in 'inv_alpha' column).
    min_area : float, default 0
        Minimum area threshold. Shapes with area <= min_area are excluded.
    clean_names : bool, default True
        If True, removes the trailing `_{alpha}` suffix from the 'name' column,
        leaving just the category name (e.g., "cluster_0" instead of "cluster_0_150").

    Returns
    -------
    gpd.GeoDataFrame
        Filtered GeoDataFrame with optionally cleaned names.

    Examples
    --------
    >>> gdf_alpha = dega.nbhd.alpha_shape_cell_clusters(adata, cat="leiden")
    >>> gdf_filtered = dega.nbhd.filter_alpha_shapes(gdf_alpha, alpha=150)
    >>> # Names are now just category names without the alpha suffix
    >>> print(gdf_filtered["name"].tolist()[:3])
    ['0', '1', '2']
    """
    # Filter by alpha value
    gdf_filtered = gdf_alpha[gdf_alpha["inv_alpha"] == alpha].copy()

    # Filter by minimum area
    gdf_filtered = gdf_filtered[gdf_filtered["area"] > min_area]

    if clean_names:
        # Remove the trailing _{alpha} suffix from names
        # Names are in format "{cat}_{alpha}", we want just "{cat}"
        alpha_suffix = f"_{int(alpha)}"
        gdf_filtered["name"] = gdf_filtered["name"].apply(
            lambda x: x[: -len(alpha_suffix)] if x.endswith(alpha_suffix) else x
        )

    # Reset index for clean output
    return gdf_filtered.reset_index(drop=True)


def alpha_shape_geojson(
    gdf_alpha: gpd.GeoDataFrame,
    meta_cluster: gpd.GeoDataFrame,
    inst_alpha: float,
) -> dict:
    geojson_alpha = json.loads(gdf_alpha.to_json())
    for feature in geojson_alpha["features"]:
        if feature["geometry"] is not None:
            geometry = shape(feature["geometry"])
            feature["properties"]["area"] = geometry.area
            _id = feature["id"]
            color = meta_cluster.loc[_id.split("_")[0], "color"]
            feature["properties"]["color"] = color
    geojson_alpha["inst_alpha"] = inst_alpha
    return geojson_alpha
