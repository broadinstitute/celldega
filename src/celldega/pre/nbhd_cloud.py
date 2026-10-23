"""DegaFile parquet writers for the `neighborhood-cloud` render technology.

Exports a GeoDataFrame of per-slice alpha-shape neighborhoods (see
`celldega.nbhd.alpha_shape_cell_clusters_by_slice`) plus the matching
cell-level `AnnData` to the flat parquet layout the JS `neighborhood-cloud`
widget fetches directly.

Every file written here is a single, traditional parquet file (no row-group
chunking) — that mode isn't proven to work against AWS-hosted buckets yet.
`shapes/by_slice/` holds the alpha-shape geometry (one file per slice, every
cluster's polygon). `cells/` holds per-cell data: `cells/by_cluster/` (every
cell in a cluster, all slices) and `cells/by_gene/` (up to `max_cells` of a
gene's highest-expressing cells, see `write_gene_cell_scatter`).

Every writer here reads gene expression from an already-loaded `AnnData`
(`adata.X`) — none of them read from per-gene `cbg/<gene>.parquet` files.

Not wired into `run_pre_processing.main()`: that pipeline only supports
Xenium/MERSCOPE and assumes an image-pyramid tree exists. Point-cloud-family
technologies (`point-cloud`, `neighborhood-cloud`) have no such tree and no
prior writer in `run_pre_processing.py` to extend.
"""

from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

import anndata as ad
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import issparse
from shapely.geometry import mapping

from celldega.nbhd.utils import _as_nbhd_gdf


# `cells/by_gene/<gene>.parquet` schema -- mirrors `cells/by_cluster/<id>
# .parquet`'s cell_id/x/y/z/slice_id columns, with `expression` standing in
# for `cluster_id` since these cells are selected/colored by expression, not
# category.
_GENE_CELL_COLUMNS = ["cell_id", "gene", "slice_id", "x", "y", "z", "expression"]

_NBHD_CLOUD_CLUSTER_COLUMNS = {"cluster_id", "color", "cell_count"}


def _select_top_expressing_cells(
    expr: np.ndarray,
    min_expression: float,
    max_cells: int,
) -> np.ndarray:
    """Indices of up to `max_cells` highest-`expr` cells among those with
    `expr >= min_expression` -- an O(n) top-K selection (argpartition), not a
    full sort, since `max_cells` is meant to bound a per-gene cell file to a
    small fraction of a whole-tissue cell count regardless of how broadly the
    gene is actually expressed."""
    candidate_idx = np.flatnonzero(expr >= min_expression)
    if max_cells <= 0 or candidate_idx.size == 0:
        return candidate_idx[:0]
    if candidate_idx.size <= max_cells:
        return candidate_idx
    top_within = np.argpartition(expr[candidate_idx], -max_cells)[-max_cells:]
    return candidate_idx[top_within]


def _nbhd_cloud_gdf(nbhd: Any) -> tuple[gpd.GeoDataFrame, str]:
    """Resolve and validate the per-slice neighborhood GeoDataFrame."""
    gdf, nbhd_col = _as_nbhd_gdf(nbhd)
    missing = (_NBHD_CLOUD_CLUSTER_COLUMNS | {"slice_id"}) - set(gdf.columns)
    if missing:
        raise ValueError(f"nbhd is missing required columns: {sorted(missing)}")
    return gdf, nbhd_col


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
        per slice, e.g. from a serial-slice alignment).

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
    max_cells: int | None = None,
    random_state: int = 0,
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
    max_cells : int | None
        Cap on the number of cells written per cluster (across all its
        slices combined). Above this many, a **uniform random** subsample is
        written instead of every cell -- unlike a gene's top-expressing cell
        cap (`max_cells` on `write_gene_cell_scatter`), there's no
        per-cell ranking signal within a cluster (every member is equally
        "in" the cluster), so random is the only choice that doesn't bias
        toward an arbitrary subset. `None` (default) writes every cell,
        matching this function's original, uncapped behavior.
    random_state : int
        Seed for the subsampling RNG, so results are reproducible run to run.
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
        if max_cells is not None and len(df_cluster) > max_cells:
            df_cluster = df_cluster.sample(n=max_cells, random_state=random_state)
        df_cluster.to_parquet(by_cluster_dir / f"cluster_{cluster_id}.parquet", index=False)


def write_cell_clusters_meta(nbhd: Any, path_dega_files: str | Path) -> None:
    """Write `cell_clusters/meta_cluster.parquet` (`cluster`, `color`, `count`).

    This is the same file/column convention every other technology already
    writes and that `set_cluster_metadata` (`js/global_variables/meta_cluster.js`)
    fetches unconditionally to populate `viz_state.cats.color_dict_cluster` and
    the cluster bar graph — neither of which is specific to neighborhood-cloud.
    Derived from the neighborhood geometry (color per cluster is already
    consistent across slices; count is summed across a cluster's
    neighborhoods) rather than requiring the caller to supply it separately.

    Parameters
    ----------
    nbhd : GeoDataFrame or neighborhood-like object
        Per-slice neighborhoods with `cluster_id`, `color`, and `cell_count`
        columns (e.g. from `alpha_shape_cell_clusters_by_slice`).
    path_dega_files : str | Path
        DegaFiles root directory.
    """
    gdf, _ = _as_nbhd_gdf(nbhd)
    missing = _NBHD_CLOUD_CLUSTER_COLUMNS - set(gdf.columns)
    if missing:
        raise ValueError(f"nbhd is missing required columns: {sorted(missing)}")

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
    nbhd: Any,
    path_dega_files: str | Path,
) -> None:
    """Write shapes and neighborhood metadata:

    - `nbhd_cloud/shapes/by_slice/slice_<id>.parquet` — one file per slice,
      every cluster's polygon, with a `geometry_geojson` string column (a
      JSON geometry, e.g. `MultiPolygon` with XYZ coordinates) rather than
      GeoParquet/WKB, since it's fed straight into a deck.gl `GeoJsonLayer`
      the same way the 2D `nbhd` feature's GeoJSON already is.
    - `nbhd_cloud/meta_neighborhood.parquet` — `neighborhood_id`, `cluster_id`,
      `slice_id`, `color`, `area`, `cell_count`, `inv_alpha`.
    - `cell_clusters/meta_cluster.parquet` (via `write_cell_clusters_meta`).

    Per-neighborhood gene expression and population proportions are
    intentionally not computed/written here: gene coloring comes from the
    per-gene cell scatter (`write_gene_cell_scatter`), and population
    proportions were never surfaced in the frontend.

    Parameters
    ----------
    nbhd : GeoDataFrame or neighborhood-like object
        Neighborhoods spanning all slices, e.g. from
        `alpha_shape_cell_clusters_by_slice(adata, ...)`, with unique ids
        (`name`), `slice_id`, `cluster_id`, `color`, and `cell_count` columns.
    path_dega_files : str | Path
        DegaFiles root directory.
    """
    gdf, nbhd_col = _nbhd_cloud_gdf(nbhd)

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
        df_shape_slice = pd.DataFrame(
            gdf_slice.drop(columns=["geometry", "neighborhood_id"], errors="ignore")
        )
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

    write_cell_clusters_meta(gdf, path_dega_files)


def write_gene_cell_scatter(
    adata: ad.AnnData,
    gene_list: Sequence[str],
    path_dega_files: str | Path,
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    min_expression: float = 2.0,
    min_cells: int = 4,
    max_cells: int = 50_000,
    progress_every: int = 500,
) -> int:
    """Gene-coloring writer: a capped, top-expressing cell scatter per gene.

    Selects each gene's top-expressing cells (`_select_top_expressing_cells`,
    an O(n) `argpartition`, no geometry at all), so "browse any gene" scales to
    a large gene list: a capped point scatter of real single-cell positions and
    expression values, colored by per-cell expression.

    Reads each gene's expression directly from an already-loaded `adata.X`
    column.

    Writes `nbhd_cloud/cells/by_gene/<gene>.parquet` (columns: `cell_id`,
    `gene`, `slice_id`, `x`, `y`, `z`, `expression`) plus
    `nbhd_cloud/cells/by_gene/available_gene_scatter.json` — `{gene:
    max_expression}`, the manifest the frontend checks before fetching a
    gene's cells.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData with spatial coordinates in `obsm["spatial"]`, a
        `slice_attr` (and, if given, `z_attr`) column in `obs`, and every
        gene in `gene_list` present in `adata.var_names`.
    gene_list : Sequence[str]
        Genes to write a cell scatter for.
    path_dega_files : str | Path
        DegaFiles root directory.
    slice_attr, z_attr : str, str | None
        See `write_meta_slice`.
    min_expression : float
        A cell counts as "expressing" a gene when its value is at least this.
    min_cells : int
        Minimum number of expressing cells (before capping) required to
        write a gene's scatter at all; genes with fewer are silently skipped.
    max_cells : int
        Cap on the number of top-expressing cells written per gene (across
        all slices combined).
    progress_every : int
        Print a progress line every this many genes processed (0 disables).

    Returns
    -------
    int
        Number of genes that had enough expressing cells and were written.
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

    cells_out_dir = Path(path_dega_files) / "nbhd_cloud" / "cells" / "by_gene"
    cells_out_dir.mkdir(parents=True, exist_ok=True)

    available_genes: dict[str, float] = {}
    n_written = 0
    for i, gene in enumerate(gene_list, start=1):
        expr = _gene_column(gene)

        if int((expr >= min_expression).sum()) >= min_cells:
            top_idx = _select_top_expressing_cells(expr, min_expression, max_cells)
            df_cells = pd.DataFrame(
                {
                    "cell_id": cell_ids[top_idx],
                    "gene": gene,
                    "slice_id": slice_ids[top_idx],
                    "x": coords[top_idx, 0].astype(float),
                    "y": coords[top_idx, 1].astype(float),
                    "z": z_values[top_idx],
                    "expression": expr[top_idx].astype(float),
                }
            )[_GENE_CELL_COLUMNS]
            df_cells.to_parquet(cells_out_dir / f"{gene}.parquet", index=False)
            available_genes[str(gene)] = float(expr.max())
            n_written += 1

        if progress_every and i % progress_every == 0:
            print(f"gene cell scatter: {i}/{len(gene_list)} genes processed, {n_written} written")

    with (cells_out_dir / "available_gene_scatter.json").open("w") as f:
        json.dump(available_genes, f, indent=2)

    print(
        f"gene cell scatter: wrote {n_written}/{len(gene_list)} genes to {cells_out_dir} "
        "(no alpha shape -- capped top-expressing cell scatter only)"
    )
    return n_written


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
    # Write under both the new (neighborhood_cloud.json, fetched by the
    # NeighborhoodCloud widget) and legacy (landscape_parameters.json) filenames
    # so pre-rename loaders keep resolving the manifest during the transition.
    root = Path(path_dega_files)
    for name in ("landscape_parameters.json", "neighborhood_cloud.json"):
        with (root / name).open("w") as f:
            json.dump(landscape_parameters, f, indent=2)


def write_meta_gene_for_nbhd_cloud(adata: ad.AnnData, path_dega_files: str | Path) -> None:
    """Write a dataset-root `meta_gene.parquet` (`mean`, `std`, `max`, `non-zero`, `color`).

    Every technology's gene search box and gene bar graph fetch this file
    unconditionally (`set_meta_gene`/`set_color_dict_gene`, neither gated on
    technology) — neighborhood-cloud is no exception, even though its actual
    gene-expression *coloring* comes from the per-gene cell scatter
    (`write_gene_cell_scatter`), not this file. Reuses the existing `make_meta_gene` writer (same one every
    other technology uses) rather than duplicating its color-palette logic.
    """
    # A label-only aligned AnnData (clusters/slices but no expression matrix,
    # e.g. `X` with zero var columns) is a legitimate neighborhood-cloud input:
    # the cluster shapes and cell scatter carry the view, and gene coloring
    # simply isn't available. Skip meta_gene rather than letting the empty CBG
    # blow up `make_meta_gene`'s per-gene stats.
    if adata.X is None or adata.n_vars == 0:
        return

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
    nbhd: Any,
    path_dega_files: str | Path,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    max_cells: int | None = None,
    random_state: int = 0,
    write_meta_gene: bool = True,
) -> None:
    """Write the full `neighborhood-cloud` DegaFile layout for one dataset.

    Orchestrates `write_meta_slice`, `write_nbhd_cloud_cells`, and
    `write_nbhd_cloud_shapes_and_features`, then writes
    `landscape_parameters.json`.

    Parameters
    ----------
    adata : AnnData
        Aligned 3D cell-level AnnData: `obsm["spatial"]` (x, y), `obs[cluster_attr]`,
        `obs[slice_attr]`, optionally `obs[z_attr]` (e.g. from a serial-slice
        alignment).
    nbhd : GeoDataFrame or neighborhood-like object
        Neighborhoods spanning all slices, e.g.
        `alpha_shape_cell_clusters_by_slice(adata, ...)`. Needs unique ids
        (`name`) and `slice_id`, `cluster_id`, `color`, `cell_count` columns.
    path_dega_files : str | Path
        Output DegaFiles root directory.
    cluster_attr, slice_attr, z_attr
        See `write_meta_slice` / `write_nbhd_cloud_cells`.
    max_cells, random_state
        Forwarded to `write_nbhd_cloud_cells` — cap (via uniform random
        subsample) on cells written per cluster. `max_cells=None` (default)
        writes every cell, unchanged from this function's original behavior.
    write_meta_gene : bool
        Whether to write `meta_gene.parquet` (the dataset-root per-gene stats).
        `True` (default) preserves the original behavior; `False` skips it for a
        clusters-only cloud with no gene-expression data.
    """
    write_meta_slice(adata, path_dega_files, slice_attr=slice_attr, z_attr=z_attr)
    write_nbhd_cloud_cells(
        adata,
        path_dega_files,
        cluster_attr=cluster_attr,
        slice_attr=slice_attr,
        z_attr=z_attr,
        max_cells=max_cells,
        random_state=random_state,
    )
    write_nbhd_cloud_shapes_and_features(nbhd, path_dega_files)
    if write_meta_gene:
        write_meta_gene_for_nbhd_cloud(adata, path_dega_files)
    _write_nbhd_cloud_landscape_parameters(path_dega_files)
