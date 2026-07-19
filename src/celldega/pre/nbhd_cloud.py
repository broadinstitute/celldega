"""DegaFile parquet writers for the `neighborhood-cloud` render technology.

Exports a caller-built `celldega.nbhd.NeighborhoodCollection` of alpha-shape
neighborhoods (see `celldega.nbhd.alpha_shape_cell_clusters_by_slice`) plus the
matching cell-level `AnnData` to the flat parquet layout the JS
`neighborhood-cloud` widget fetches directly.

Every file written here is a single, traditional parquet file (no row-group
chunking) — that mode isn't proven to work against AWS-hosted buckets yet, and
neighborhood/slice counts are small enough that per-slice/per-cluster/per-gene
files stay in the dozens, not the many-tiny-files territory row-group chunking
exists to avoid.

Not wired into `run_pre_processing.main()`: that pipeline only supports
Xenium/MERSCOPE and assumes an image-pyramid tree exists. Point-cloud-family
technologies (`point-cloud`, `neighborhood-cloud`) have no such tree and no
prior writer in `run_pre_processing.py` to extend.
"""

from __future__ import annotations

import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy.sparse import issparse
from shapely.geometry import mapping

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
    """Write the dual redundant cell-centroid layout.

    `nbhd_cloud/cells/by_cluster/cluster_<id>.parquet` (one file per cluster,
    every slice) and `nbhd_cloud/cells/by_slice/slice_<id>.parquet` (one file
    per slice, every cluster) — each row: `cell_id`, `x`, `y`, `z`,
    `cluster_id`, `slice_id`, so either layout can filter on the other axis.

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
    by_slice_dir = Path(path_dega_files) / "nbhd_cloud" / "cells" / "by_slice"
    by_cluster_dir.mkdir(parents=True, exist_ok=True)
    by_slice_dir.mkdir(parents=True, exist_ok=True)

    for cluster_id, df_cluster in df_cells.groupby("cluster_id"):
        df_cluster.to_parquet(by_cluster_dir / f"cluster_{cluster_id}.parquet", index=False)

    for slice_id, df_slice in df_cells.groupby("slice_id"):
        df_slice.to_parquet(by_slice_dir / f"slice_{slice_id}.parquet", index=False)


def _slice_scoped_features(
    adata: ad.AnnData,
    nbhd: NeighborhoodCollection,
    cluster_attr: str,
    slice_attr: str,
) -> tuple[ad.AnnData, ad.AnnData]:
    """Per-slice `calc_signature`/`calc_population`, concatenated to the full neighborhood axis.

    `calc_signature`/`calc_population` do a plain 2D spatial join with no
    slice-awareness — joining cells against every slice's neighborhoods at once
    would let a cell in one slice fall inside an overlapping neighborhood from
    a *different* slice (serial tissue sections routinely share similar XY
    layout). Looping per slice keeps each spatial join scoped to that slice's
    own cells and neighborhoods only.
    """
    if nbhd.gdf is None:
        raise ValueError("nbhd must have geometry (gdf) set")
    if "slice_id" not in nbhd.gdf.columns:
        raise ValueError("nbhd.gdf must have a 'slice_id' column")

    obs = adata.obs
    gene_mods = []
    pop_mods = []

    for slice_id in nbhd.gdf["slice_id"].unique():
        gdf_slice = nbhd.gdf[nbhd.gdf["slice_id"] == slice_id]
        mask = (obs[slice_attr] == slice_id).to_numpy()
        adata_slice = adata[mask].copy()

        slice_collection = NeighborhoodCollection(
            gdf=gdf_slice, nbhd_type=nbhd.nbhd_type, nbhd_col=nbhd.nbhd_col
        )
        slice_collection.calc_signature(
            adata_slice,
            by="cell",
            modality_name="gene",
            min_cells=1,
            drop_missing=False,
            include_variance=True,
        )
        slice_collection.calc_population(
            adata_slice,
            category=cluster_attr,
            modality_name="population",
            min_cells=1,
            output="proportion",
            drop_missing=False,
        )
        gene_mods.append(slice_collection.mod["gene"])
        pop_mods.append(slice_collection.mod["population"])

    gene_full = ad.concat(gene_mods, join="outer", fill_value=0)
    pop_full = ad.concat(pop_mods, join="outer", fill_value=0)
    return gene_full, pop_full


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
    adata: ad.AnnData,
    nbhd: NeighborhoodCollection,
    path_dega_files: str | Path,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
) -> None:
    """Write shapes, neighborhood metadata, and gene/population feature tables.

    Computes nbhd-by-gene (mean + variance, via
    `NeighborhoodCollection.calc_signature`) and nbhd-by-population (via
    `.calc_population`) with a slice-scoped spatial join (`_slice_scoped_features`),
    attaches them to `nbhd`, then writes:

    - `nbhd_cloud/shapes/slice_<id>.parquet` — one file per slice, every
      cluster's polygon, with a `geometry_geojson` string column (a JSON
      geometry, e.g. `MultiPolygon` with XYZ coordinates) rather than
      GeoParquet/WKB, since it's fed straight into a deck.gl `GeoJsonLayer`
      the same way the legacy 2D `nbhd` feature's GeoJSON already is.
    - `nbhd_cloud/meta_neighborhood.parquet` — `neighborhood_id`, `cluster_id`,
      `slice_id`, `color`, `area`, `cell_count`, `inv_alpha`.
    - `nbhd_cloud/expression/<gene>.parquet` — `neighborhood_id`, `mean`,
      `variance` (one file per gene, fetched lazily by the frontend only when
      that gene is selected).
    - `nbhd_cloud/population.parquet` — `neighborhood_id`, `category`,
      `proportion` (long format).

    Parameters
    ----------
    adata : AnnData
        Aligned 3D cell-level AnnData (spatial coords, cluster/slice columns,
        gene expression matrix).
    nbhd : NeighborhoodCollection
        Caller-built neighborhood collection spanning all slices, e.g. from
        `NeighborhoodCollection.from_gdf(alpha_shape_cell_clusters_by_slice(adata, ...))`.
    path_dega_files : str | Path
        DegaFiles root directory.
    cluster_attr, slice_attr : str
        Columns in `adata.obs` used for the population modality and the
        per-slice spatial-join scoping, respectively.
    """
    if nbhd.gdf is None:
        raise ValueError("nbhd must have geometry (gdf) set")
    if "slice_id" not in nbhd.gdf.columns:
        raise ValueError("nbhd.gdf must have a 'slice_id' column")

    gdf = nbhd.gdf
    nbhd_col = nbhd.nbhd_col

    out_dir = Path(path_dega_files) / "nbhd_cloud"
    shapes_dir = out_dir / "shapes"
    expression_dir = out_dir / "expression"
    shapes_dir.mkdir(parents=True, exist_ok=True)
    expression_dir.mkdir(parents=True, exist_ok=True)

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

    gene_mod, pop_mod = _slice_scoped_features(adata, nbhd, cluster_attr, slice_attr)
    nbhd.add_mod("gene", gene_mod, var_entity_type="gene")
    nbhd.add_mod("population", pop_mod, var_entity_type="cell_population")

    def _dense(matrix: object) -> np.ndarray:
        return matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)

    gene_mean = pd.DataFrame(
        _dense(gene_mod.X), index=gene_mod.obs_names, columns=gene_mod.var_names
    )
    gene_variance = None
    if "variance" in gene_mod.layers:
        gene_variance = pd.DataFrame(
            _dense(gene_mod.layers["variance"]),
            index=gene_mod.obs_names,
            columns=gene_mod.var_names,
        )

    for gene in gene_mean.columns:
        df_gene = pd.DataFrame(
            {
                "neighborhood_id": gene_mean.index.astype(str),
                "mean": gene_mean[gene].to_numpy(),
                "variance": (
                    gene_variance[gene].to_numpy()
                    if gene_variance is not None
                    else np.zeros(len(gene_mean))
                ),
            }
        )
        df_gene.to_parquet(expression_dir / f"{gene}.parquet", index=False)

    pop_matrix = pd.DataFrame(_dense(pop_mod.X), index=pop_mod.obs_names, columns=pop_mod.var_names)
    pop_matrix.index.name = "neighborhood_id"
    df_population = pop_matrix.reset_index().melt(
        id_vars="neighborhood_id", var_name="category", value_name="proportion"
    )
    df_population.to_parquet(out_dir / "population.parquet", index=False)


def _write_nbhd_cloud_landscape_parameters(
    path_dega_files: str | Path,
    nearest_n_slices_default: int,
) -> None:
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
        "nbhd_cloud": {
            "directory": "nbhd_cloud",
            "nearest_n_slices_default": {"cells": nearest_n_slices_default},
        },
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
    nearest_n_slices_default: int = 3,
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
        `celldega.align.serial_slices.align_serial_slices`), and `X` = gene
        expression (used for nbhd-by-gene mean/variance).
    nbhd : NeighborhoodCollection
        Caller-built neighborhood collection spanning all slices — e.g.
        `NeighborhoodCollection.from_gdf(alpha_shape_cell_clusters_by_slice(adata, ...))`.
        Must have a `slice_id` column in `nbhd.gdf`.
    path_dega_files : str | Path
        Output DegaFiles root directory.
    cluster_attr, slice_attr, z_attr
        See `write_meta_slice` / `write_nbhd_cloud_cells`.
    nearest_n_slices_default : int
        Default nearest-slice count recorded in `landscape_parameters.json`'s
        `nbhd_cloud.nearest_n_slices_default.cells` (the frontend can still
        override per-widget via the `nbhd_cloud_nearest_n_slices` constructor
        kwarg).
    """
    write_meta_slice(adata, path_dega_files, slice_attr=slice_attr, z_attr=z_attr)
    write_nbhd_cloud_cells(
        adata,
        path_dega_files,
        cluster_attr=cluster_attr,
        slice_attr=slice_attr,
        z_attr=z_attr,
    )
    write_nbhd_cloud_shapes_and_features(
        adata, nbhd, path_dega_files, cluster_attr=cluster_attr, slice_attr=slice_attr
    )
    write_meta_gene_for_nbhd_cloud(adata, path_dega_files)
    _write_nbhd_cloud_landscape_parameters(path_dega_files, nearest_n_slices_default)
