"""DegaFile parquet writers for the `neighborhood-cloud` render technology.

Exports a caller-built `celldega.nbhd.NeighborhoodCollection` of alpha-shape
neighborhoods (see `celldega.nbhd.alpha_shape_cell_clusters_by_slice`) plus the
matching cell-level `AnnData` to the flat parquet layout the JS
`neighborhood-cloud` widget fetches directly.

Every file written here is a single, traditional parquet file (no row-group
chunking) — that mode isn't proven to work against AWS-hosted buckets yet.
`shapes/` holds all alpha-shape geometry, split by partition axis rather than
by directory-per-concept: `shapes/by_slice/` (one file per slice, every
cluster's polygon) and `shapes/by_gene/` (one file per gene, every slice's
polygon — mirrors `cells/by_cluster/`'s naming). `cells/by_cluster/` and
`meta_*` stay in the dozens of files (one per slice/cluster). `shapes/by_gene/`
is the exception: it's one file per *gene*, and `write_gene_shapes_streaming`
is meant to scale that to a whole gene panel (~40k files) — see its
docstring for why the streaming form exists alongside `write_gene_shapes`.

Not wired into `run_pre_processing.main()`: that pipeline only supports
Xenium/MERSCOPE and assumes an image-pyramid tree exists. Point-cloud-family
technologies (`point-cloud`, `neighborhood-cloud`) have no such tree and no
prior writer in `run_pre_processing.py` to extend.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
import json
from pathlib import Path

import anndata as ad
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import issparse
from shapely.geometry import mapping

from celldega.nbhd.alpha_shapes import iter_gene_alpha_shapes, iter_gene_alpha_shapes_by_slice
from celldega.nbhd.collection import NeighborhoodCollection


def _resolve_z(obs: pd.DataFrame, mask: np.ndarray, z_attr: str | None) -> np.ndarray:
    """Per-row Z values for the masked rows, or all zeros if `z_attr` is None."""
    if z_attr is None:
        return np.zeros(int(mask.sum()))
    return obs.loc[mask, z_attr].to_numpy(dtype=float)


def write_meta_slice(
    adata: ad.AnnData,
    path_dega_files: str | Path,
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
) -> pd.DataFrame:
    """Write `nbhd_cloud/meta_slice.parquet`, one row per slice.

    Columns: `slice_id`, `z`, `centroid_x`, `centroid_y`, `centroid_z`,
    `cell_count`. `z`/`centroid_z` are 0.0 when `z_attr` is not given.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData with spatial coordinates in `obsm["spatial"]` and a
        `slice_attr` (and, if given, `z_attr`) column in `obs`.
    path_dega_files : str | Path
        DegaFiles root directory; `nbhd_cloud/` is created if missing.
    slice_attr : str
        Column in `adata.obs` identifying each slice.
    z_attr : str | None
        Column in `adata.obs` with each cell's Z coordinate (expected constant
        per slice, e.g. from `celldega.align.serial_slices`).

    Returns
    -------
    pd.DataFrame
        The table written to `meta_slice.parquet`.
    """
    obs = adata.obs
    coords = np.asarray(adata.obsm["spatial"])

    rows = []
    for slice_id in obs[slice_attr].unique():
        mask = (obs[slice_attr] == slice_id).to_numpy()
        z_values = _resolve_z(obs, mask, z_attr)
        rows.append(
            {
                "slice_id": slice_id,
                "z": float(z_values[0]) if len(z_values) else 0.0,
                "centroid_x": float(coords[mask, 0].mean()),
                "centroid_y": float(coords[mask, 1].mean()),
                "centroid_z": float(z_values.mean()) if len(z_values) else 0.0,
                "cell_count": int(mask.sum()),
            }
        )

    df_meta_slice = pd.DataFrame(rows)

    out_dir = Path(path_dega_files) / "nbhd_cloud"
    out_dir.mkdir(parents=True, exist_ok=True)
    df_meta_slice.to_parquet(out_dir / "meta_slice.parquet", index=False)
    return df_meta_slice


def write_nbhd_cloud_cells(
    adata: ad.AnnData,
    path_dega_files: str | Path,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
) -> None:
    """Write `nbhd_cloud/cells/by_cluster/cluster_<id>.parquet`, one file per cluster.

    Each row: `cell_id`, `x`, `y`, `z`, `cluster_id`, `slice_id`. Cluster
    selection (not per-neighborhood) is the frontend's cell-display trigger —
    picking a cluster shows its cells across every slice, optionally narrowed
    to one slice client-side (the `slice_id` column is already there) when
    the slice bar has isolated one slice. A per-cluster file is the natural
    fit for that: one bounded fetch per selection, not one per slice.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData with spatial coordinates in `obsm["spatial"]` and
        `cluster_attr` / `slice_attr` (and, if given, `z_attr`) columns in `obs`.
    path_dega_files : str | Path
        DegaFiles root directory.
    cluster_attr, slice_attr, z_attr : str, str, str | None
        See `write_meta_slice`.
    """
    obs = adata.obs
    coords = np.asarray(adata.obsm["spatial"])
    z_all = _resolve_z(obs, np.ones(len(obs), dtype=bool), z_attr)

    df_cells = pd.DataFrame(
        {
            "cell_id": adata.obs_names.astype(str),
            "x": coords[:, 0].astype(float),
            "y": coords[:, 1].astype(float),
            "z": z_all,
            "cluster_id": obs[cluster_attr].astype(str).to_numpy(),
            "slice_id": obs[slice_attr].to_numpy(),
        }
    )

    by_cluster_dir = Path(path_dega_files) / "nbhd_cloud" / "cells" / "by_cluster"
    by_cluster_dir.mkdir(parents=True, exist_ok=True)

    for cluster_id, df_cluster in df_cells.groupby("cluster_id"):
        df_cluster.to_parquet(by_cluster_dir / f"cluster_{cluster_id}.parquet", index=False)


def write_cell_clusters_meta(nbhd: NeighborhoodCollection, path_dega_files: str | Path) -> None:
    """Write `cell_clusters/meta_cluster.parquet` (`cluster`, `color`, `count`).

    This is the same file/column convention every other technology already
    writes and that `set_cluster_metadata` (`js/global_variables/meta_cluster.js`)
    fetches unconditionally to populate `viz_state.cats.color_dict_cluster` and
    the cluster bar graph — neither of which is specific to neighborhood-cloud.
    Derived from `nbhd.gdf` (color per cluster is already consistent across
    slices; count is summed across a cluster's neighborhoods) rather than
    requiring the caller to supply it separately.
    """
    if nbhd.gdf is None:
        raise ValueError("nbhd must have geometry (gdf) set")
    gdf = nbhd.gdf
    if not {"cluster_id", "color", "cell_count"}.issubset(gdf.columns):
        raise ValueError("nbhd.gdf must have cluster_id/color/cell_count columns")

    df_meta_cluster = (
        gdf.groupby("cluster_id")
        .agg(color=("color", "first"), count=("cell_count", "sum"))
        .reset_index()
        .rename(columns={"cluster_id": "cluster"})
    )

    out_dir = Path(path_dega_files) / "cell_clusters"
    out_dir.mkdir(parents=True, exist_ok=True)
    df_meta_cluster.to_parquet(out_dir / "meta_cluster.parquet", index=False)


def write_nbhd_cloud_shapes_and_features(
    nbhd: NeighborhoodCollection,
    path_dega_files: str | Path,
) -> None:
    """Write shapes and neighborhood metadata:

    - `nbhd_cloud/shapes/by_slice/slice_<id>.parquet` — one file per slice,
      every cluster's polygon, with a `geometry_geojson` string column (a
      JSON geometry, e.g. `MultiPolygon` with XYZ coordinates) rather than
      GeoParquet/WKB, since it's fed straight into a deck.gl `GeoJsonLayer`
      the same way the legacy 2D `nbhd` feature's GeoJSON already is.
      Sibling to `shapes/by_gene/` (see `write_gene_shapes`) — both are
      alpha-shape geometry, partitioned along different axes (this one by
      slice, the other by gene), grouped under one `shapes/` parent rather
      than as unrelated-looking top-level directories.
    - `nbhd_cloud/meta_neighborhood.parquet` — `neighborhood_id`, `cluster_id`,
      `slice_id`, `color`, `area`, `cell_count`, `inv_alpha`.
    - `cell_clusters/meta_cluster.parquet` (via `write_cell_clusters_meta`).

    Per-neighborhood gene expression and population proportions are
    intentionally not computed/written here: gene coloring comes from the
    curated marker-gene alpha shapes instead (`alpha_shape_gene_expression_by_slice`
    / `write_gene_shapes`), and population proportions were never surfaced in
    the frontend. Both would need the same expensive per-slice spatial join
    this writer used to do just to produce data nothing read.

    Parameters
    ----------
    nbhd : NeighborhoodCollection
        Caller-built neighborhood collection spanning all slices, e.g. from
        `NeighborhoodCollection.from_gdf(alpha_shape_cell_clusters_by_slice(adata, ...))`.
    path_dega_files : str | Path
        DegaFiles root directory.
    """
    if nbhd.gdf is None:
        raise ValueError("nbhd must have geometry (gdf) set")
    if "slice_id" not in nbhd.gdf.columns:
        raise ValueError("nbhd.gdf must have a 'slice_id' column")

    gdf = nbhd.gdf
    nbhd_col = nbhd.nbhd_col

    out_dir = Path(path_dega_files) / "nbhd_cloud"
    shapes_dir = out_dir / "shapes" / "by_slice"
    shapes_dir.mkdir(parents=True, exist_ok=True)

    # Written as a plain JSON-geometry string column, not GeoParquet/WKB: the
    # JS frontend has no WKB decoder, but every other neighborhood shape it
    # already renders (the legacy 2D `nbhd` feature) arrives as GeoJSON via
    # the anywidget comm channel and is fed straight into a deck.gl
    # `GeoJsonLayer` — reusing that same wire format here (just sourced from
    # a parquet column instead of a synced trait) needs no new JS parsing.
    for slice_id, gdf_slice in gdf.groupby("slice_id"):
        df_shape_slice = pd.DataFrame(gdf_slice.drop(columns="geometry"))
        df_shape_slice.insert(0, "neighborhood_id", gdf_slice[nbhd_col].astype(str).to_numpy())
        df_shape_slice["geometry_geojson"] = [
            json.dumps(mapping(geom)) for geom in gdf_slice.geometry
        ]
        df_shape_slice.to_parquet(shapes_dir / f"slice_{slice_id}.parquet", index=False)

    meta_cols = [
        c
        for c in ("cluster_id", "slice_id", "color", "area", "cell_count", "inv_alpha")
        if c in gdf.columns
    ]
    df_meta_nbhd = pd.DataFrame(gdf[meta_cols])
    df_meta_nbhd.insert(0, "neighborhood_id", gdf[nbhd_col].astype(str).to_numpy())
    df_meta_nbhd.to_parquet(out_dir / "meta_neighborhood.parquet", index=False)

    write_cell_clusters_meta(nbhd, path_dega_files)


def write_gene_shapes(gdf_gene_alpha: gpd.GeoDataFrame, path_dega_files: str | Path) -> None:
    """Write `nbhd_cloud/shapes/by_gene/<gene>.parquet`, one file per gene (every slice).

    A curated-gene-list companion to `write_nbhd_cloud_shapes_and_features` —
    same `geometry_geojson` string-column convention (no GeoParquet/WKB), but
    keyed by gene instead of (slice, cluster), and one file per *gene*
    (covering every slice) rather than one file per *slice* (covering every
    cluster), since the frontend always wants "this gene's shapes across the
    whole tissue" as a unit, never a single-slice subset. Sibling to
    `shapes/by_slice/` (see `write_nbhd_cloud_shapes_and_features`) — both are
    alpha-shape geometry, grouped under one `shapes/` parent, partitioned
    along different axes. Takes an already fully-materialized
    `gdf_gene_alpha` (the output of `alpha_shape_gene_expression_by_slice`),
    so it's meant for a small, curated/bounded gene list where holding every
    gene's shapes for every slice in memory at once is fine. For a
    whole-transcriptome gene list (~40k genes), use
    `write_gene_shapes_streaming` instead, which writes each gene's parquet
    as soon as it's computed rather than requiring the whole result set up
    front.

    Each row: `gene`, `slice_id`, `mean_expression`, `max_expression`,
    `area`, `cell_count`, `inv_alpha`, `geometry_geojson`. Also writes
    `nbhd_cloud/shapes/by_gene/available_genes.json` — `{gene:
    max_expression}`, both the manifest the frontend checks before treating a
    selected gene as having its own alpha shapes, and the normalization
    reference for that gene's fill opacity (mirroring the per-cell
    gene-coloring convention).

    Parameters
    ----------
    gdf_gene_alpha : gpd.GeoDataFrame
        Output of `celldega.nbhd.alpha_shape_gene_expression_by_slice`.
    path_dega_files : str | Path
        DegaFiles root directory.
    """
    out_dir = Path(path_dega_files) / "nbhd_cloud" / "shapes" / "by_gene"
    out_dir.mkdir(parents=True, exist_ok=True)

    available_genes: dict[str, float] = {}
    for gene, gdf_gene in gdf_gene_alpha.groupby("gene"):
        df_shape = pd.DataFrame(gdf_gene.drop(columns="geometry"))
        df_shape["geometry_geojson"] = [json.dumps(mapping(geom)) for geom in gdf_gene.geometry]
        df_shape.to_parquet(out_dir / f"{gene}.parquet", index=False)
        available_genes[str(gene)] = float(gdf_gene["max_expression"].iloc[0])

    with (out_dir / "available_genes.json").open("w") as f:
        json.dump(available_genes, f, indent=2)


def _write_gene_shapes_from_iter(
    gene_shape_iter: Iterator[tuple[str, gpd.GeoDataFrame]],
    n_genes: int,
    out_dir: Path,
    progress_every: int,
) -> int:
    """Shared write loop behind both streaming gene-shapes writers below --
    the only difference between them is how each `(gene, gdf_gene)` pair is
    produced (from an in-memory `AnnData` column vs. a freshly-read
    `cbg/<gene>.parquet`), not what happens with it once produced."""
    out_dir.mkdir(parents=True, exist_ok=True)

    available_genes: dict[str, float] = {}
    n_written = 0
    for i, (gene, gdf_gene) in enumerate(gene_shape_iter, start=1):
        if not gdf_gene.empty:
            df_shape = pd.DataFrame(gdf_gene.drop(columns="geometry"))
            df_shape["geometry_geojson"] = [json.dumps(mapping(geom)) for geom in gdf_gene.geometry]
            df_shape.to_parquet(out_dir / f"{gene}.parquet", index=False)
            available_genes[str(gene)] = float(gdf_gene["max_expression"].iloc[0])
            n_written += 1

        if progress_every and i % progress_every == 0:
            print(f"gene shapes: {i}/{n_genes} genes processed, {n_written} written")

    with (out_dir / "available_genes.json").open("w") as f:
        json.dump(available_genes, f, indent=2)

    print(f"gene shapes: wrote {n_written}/{n_genes} genes to {out_dir}")
    return n_written


def write_gene_shapes_streaming(
    adata: ad.AnnData,
    gene_list: Sequence[str],
    path_dega_files: str | Path,
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    min_expression: float = 2.0,
    min_cells: int = 4,
    z_jitter: float = 0.1,
    progress_every: int = 500,
) -> int:
    """Whole-transcriptome variant of `write_gene_shapes` — writes as it computes.

    `alpha_shape_gene_expression_by_slice` + `write_gene_shapes` together
    require every gene's shapes for every slice to be held in memory before
    a single file is written — fine for a small curated marker-gene list,
    not for a whole gene panel (~40k genes). This streams
    `celldega.nbhd.iter_gene_alpha_shapes_by_slice` one gene at a time:
    as soon as a gene's shapes across every slice are ready, its parquet is
    written and that gene's in-memory result is dropped before moving to
    the next gene, so peak memory is bounded by one gene's shapes, not
    `len(gene_list)` genes' worth.

    Requires an `AnnData` with every gene in `gene_list` already loaded into
    `.X` — if your genes instead live in per-gene files (e.g.
    `cbg/<gene>.parquet`) and building a combined multi-gene `AnnData` just
    for this would itself be the expensive/wasteful step, use
    `write_gene_shapes_from_cbg` instead, which reads and processes one
    gene's file at a time and never assembles a combined matrix.

    Writes the same `nbhd_cloud/shapes/by_gene/<gene>.parquet` files (one per
    gene, same schema) and `available_genes.json` manifest as
    `write_gene_shapes`. Genes with no usable shape in any slice (below
    `min_cells` everywhere, or every candidate shape failed verification /
    GEOS choked — see `celldega.nbhd.alpha_shape`) are silently skipped, same
    as the non-streaming path.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData, same requirements as
        `celldega.nbhd.alpha_shape_gene_expression_by_slice`.
    gene_list : Sequence[str]
        Genes to compute shapes for — pass the full gene panel for a
        whole-transcriptome run.
    path_dega_files : str | Path
        DegaFiles root directory.
    slice_attr, z_attr, alphas, min_expression, min_cells, z_jitter :
        Forwarded to `iter_gene_alpha_shapes_by_slice` — see its docstring.
    progress_every : int
        Print a progress line every this many genes processed (0 disables).

    Returns
    -------
    int
        Number of genes that produced at least one shape and were written.
    """
    return _write_gene_shapes_from_iter(
        iter_gene_alpha_shapes_by_slice(
            adata,
            gene_list,
            slice_attr=slice_attr,
            z_attr=z_attr,
            alphas=alphas,
            min_expression=min_expression,
            min_cells=min_cells,
            z_jitter=z_jitter,
        ),
        len(gene_list),
        Path(path_dega_files) / "nbhd_cloud" / "shapes" / "by_gene",
        progress_every,
    )


def write_gene_shapes_from_cbg(
    cbg_dir: str | Path,
    gene_list: Sequence[str],
    obs: pd.DataFrame,
    coords: np.ndarray,
    path_dega_files: str | Path,
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    min_expression: float = 2.0,
    min_cells: int = 4,
    z_jitter: float = 0.1,
    progress_every: int = 500,
) -> int:
    """Gene-shapes writer that reads each gene's expression directly from
    `cbg_dir/<gene>.parquet`, one gene at a time — no combined multi-gene
    matrix or `AnnData` is ever assembled.

    `write_gene_shapes_streaming` still needs an `AnnData` with every gene
    already loaded into `.X` — building that from per-gene `cbg/` files (read
    each file, align to a shared cell index, stack into one combined sparse
    matrix, wrap in an `AnnData` that duplicates `obs`/`obsm`) is itself
    real, avoidable work when nothing downstream ever needs more than one
    gene's expression in memory at a time. This function does the per-gene
    `cbg/` read + cell-index alignment inline, one gene per iteration of
    `iter_gene_alpha_shapes`, so a gene's expression array exists in memory
    only for as long as it takes to compute (and write) that one gene's
    shapes — no per-gene reconstruction cache file needed either.

    Writes the same `nbhd_cloud/shapes/by_gene/<gene>.parquet` files and
    `available_genes.json` manifest as `write_gene_shapes`/
    `write_gene_shapes_streaming`.

    Parameters
    ----------
    cbg_dir : str | Path
        Directory of per-gene `<gene>.parquet` files (a single-column sparse
        series indexed by cell id), e.g. `<point_cloud_dir>/cbg`.
    gene_list : Sequence[str]
        Genes to compute shapes for — each must have a `cbg_dir/<gene>.parquet`.
    obs : pd.DataFrame
        Cell-level metadata, indexed by cell id (matching the index used in
        `cbg_dir`'s per-gene files), with `slice_attr` (and, if given,
        `z_attr`) columns.
    coords : np.ndarray
        Per-cell spatial coordinates, same row order as `obs`, shape
        `(n_cells, >=2)`.
    path_dega_files : str | Path
        DegaFiles root directory.
    slice_attr, z_attr, alphas, min_expression, min_cells, z_jitter :
        Forwarded to `celldega.nbhd.iter_gene_alpha_shapes` — see its
        docstring.
    progress_every : int
        Print a progress line every this many genes processed (0 disables).

    Returns
    -------
    int
        Number of genes that produced at least one shape and were written.
    """
    cbg_dir = Path(cbg_dir)
    cell_index = pd.Index(obs.index.astype(str))
    slice_ids = obs[slice_attr].to_numpy()
    z_values = obs[z_attr].to_numpy(dtype=float) if z_attr is not None else np.zeros(len(obs))
    n_cells = len(obs)

    def _gene_expression() -> Iterator[tuple[str, np.ndarray]]:
        for gene in gene_list:
            col = pd.read_parquet(cbg_dir / f"{gene}.parquet").iloc[:, 0]
            row_idx = cell_index.get_indexer(col.index.astype(str))
            valid = row_idx >= 0
            expr = np.zeros(n_cells, dtype=np.float32)
            expr[row_idx[valid]] = col.to_numpy()[valid]
            yield gene, expr

    return _write_gene_shapes_from_iter(
        iter_gene_alpha_shapes(
            coords,
            slice_ids,
            z_values,
            _gene_expression(),
            alphas=alphas,
            min_expression=min_expression,
            min_cells=min_cells,
            z_jitter=z_jitter,
        ),
        len(gene_list),
        Path(path_dega_files) / "nbhd_cloud" / "shapes" / "by_gene",
        progress_every,
    )


def _write_nbhd_cloud_landscape_parameters(path_dega_files: str | Path) -> None:
    """Write a minimal `landscape_parameters.json` for `technology="neighborhood-cloud"`.

    Deliberately not routed through `save_landscape_parameters` — that
    function assumes an image-pyramid tree (`pyramid_images/<image_name>/...`)
    exists to compute `max_pyramid_zoom`, which point-cloud-family
    technologies never write. Mirrors the minimal manifest shape already used
    for `point-cloud` datasets.
    """
    landscape_parameters = {
        "technology": "neighborhood-cloud",
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": None,
        "tile_size": None,
        "image_info": [],
        "image_format": ".webp",
        "use_int_index": True,
        "use_row_groups": False,
    }
    path_landscape_parameters = Path(path_dega_files) / "landscape_parameters.json"
    with path_landscape_parameters.open("w") as f:
        json.dump(landscape_parameters, f, indent=2)


def write_meta_gene_for_nbhd_cloud(adata: ad.AnnData, path_dega_files: str | Path) -> None:
    """Write a dataset-root `meta_gene.parquet` (`mean`, `std`, `max`, `non-zero`, `color`).

    Every technology's gene search box and gene bar graph fetch this file
    unconditionally (`set_meta_gene`/`set_color_dict_gene`, neither gated on
    technology) — neighborhood-cloud is no exception, even though its actual
    gene-expression *coloring* comes from the per-neighborhood
    `expression/<gene>.parquet` files (§`write_nbhd_cloud_shapes_and_features`),
    not this file. Reuses the existing `make_meta_gene` writer (same one every
    other technology uses) rather than duplicating its color-palette logic.
    """
    # Deferred import: `celldega.pre.make_meta_gene` lives in this package's
    # own `__init__.py`, which imports this module — importing it at module
    # load time would be circular.
    from celldega.pre import make_meta_gene

    if issparse(adata.X):
        # Keep it sparse end to end -- calc_meta_gene_data has a sparse-aware
        # path, and densifying here would otherwise materialize a
        # cells x genes dense array for the *entire* dataset (unlike the
        # per-slice nbhd-by-gene computation, which only ever densifies one
        # slice at a time).
        cbg = pd.DataFrame.sparse.from_spmatrix(
            adata.X.tocsr(), index=adata.obs_names, columns=adata.var_names
        )
    else:
        cbg = pd.DataFrame(np.asarray(adata.X), index=adata.obs_names, columns=adata.var_names)

    make_meta_gene(cbg, Path(path_dega_files) / "meta_gene.parquet")


def write_nbhd_cloud_dataset(
    adata: ad.AnnData,
    nbhd: NeighborhoodCollection,
    path_dega_files: str | Path,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
) -> None:
    """Write the full `neighborhood-cloud` DegaFile layout for one dataset.

    Orchestrates `write_meta_slice`, `write_nbhd_cloud_cells`, and
    `write_nbhd_cloud_shapes_and_features`, then writes
    `landscape_parameters.json`.

    Parameters
    ----------
    adata : AnnData
        Aligned 3D cell-level AnnData: `obsm["spatial"]` (x, y), `obs[cluster_attr]`,
        `obs[slice_attr]`, optionally `obs[z_attr]` (e.g. from
        `celldega.align.serial_slices.align_serial_slices`).
    nbhd : NeighborhoodCollection
        Caller-built neighborhood collection spanning all slices — e.g.
        `NeighborhoodCollection.from_gdf(alpha_shape_cell_clusters_by_slice(adata, ...))`.
        Must have a `slice_id` column in `nbhd.gdf`.
    path_dega_files : str | Path
        Output DegaFiles root directory.
    cluster_attr, slice_attr, z_attr
        See `write_meta_slice` / `write_nbhd_cloud_cells`.
    """
    write_meta_slice(adata, path_dega_files, slice_attr=slice_attr, z_attr=z_attr)
    write_nbhd_cloud_cells(
        adata,
        path_dega_files,
        cluster_attr=cluster_attr,
        slice_attr=slice_attr,
        z_attr=z_attr,
    )
    write_nbhd_cloud_shapes_and_features(nbhd, path_dega_files)
    write_meta_gene_for_nbhd_cloud(adata, path_dega_files)
    _write_nbhd_cloud_landscape_parameters(path_dega_files)
