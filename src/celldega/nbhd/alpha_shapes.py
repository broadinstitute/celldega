"""Module for alpha shapes computation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import anndata as ad
import geopandas as gpd
from libpysal.cg import alpha_shape as libpysal_alpha_shape
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Point, base

from .utils import (
    _category_colors,
    _cell_coords,
    _classify_polygons_contains_check,
    _fallback_category_colors,
    _obs_column_at,
    _round_coordinates,
    stamp_z,
)


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
    """
    Compute the alpha shape (concave hull) of a 2D point set.

    Parameters
    ----------
    points : np.ndarray
        Point coordinates, shape `(n_points, 2)`.
    inv_alpha : float
        Inverse alpha; larger values trace the points more loosely.

    Returns
    -------
    MultiPolygon
        The verified alpha-shape polygons (empty when none could be computed).
    """
    try:
        poly = libpysal_alpha_shape(points, 1 / inv_alpha)
    except Exception:
        # Same libpysal/GEOS fragility handled in `_verify_polygons_with_alpha_bulk`
        # (e.g. GEOSException: "side location conflict" from a self-intersecting
        # triangulation) -- a small fraction of point configurations trip GEOS's
        # spatial-index query inside libpysal's alpha_shape itself, before
        # verification even runs. Treat this point set as producing no shape
        # rather than aborting the whole batch over one unrepresentable configuration.
        return MultiPolygon()
    gdf_curated = _classify_polygons_contains_check(poly.values, points)
    validated_poly = _verify_polygons_with_alpha_bulk(
        gdf_curated.geometry.values,
        points,
        1 / inv_alpha,
    )
    return MultiPolygon(validated_poly.values)


def alpha_shape_cell_clusters(
    adata: Any,
    cat: str = "cluster",
    alphas: Sequence[float] = (100, 150, 200, 250, 300, 350),
    meta_cluster: pd.DataFrame | None = None,
    *,
    modality: str | None = None,
    spatial_key: str = "spatial",
) -> gpd.GeoDataFrame:
    """
    Compute alpha shapes for each cluster of cells.

    Parameters
    ----------
    adata : AnnData or MuData
        Cell-level data with spatial coordinates in `obsm[spatial_key]` and
        cluster labels in `obs[cat]`. For a MuData, `cat` is looked up in the
        global `obs` and then in the modalities' own `obs`.
    cat : str
        Column with cluster/category labels.
    alphas : Sequence[float]
        Inverse alpha values to compute shapes for.
    meta_cluster : pd.DataFrame | None
        Optional cluster metadata with a 'color' column, indexed by cluster.
        If not provided, colors come from `uns[f'{cat}_colors']` when
        available, otherwise default to black.
    modality : str, optional
        For a MuData input, the modality to take coordinates and labels from.
    spatial_key : str, default "spatial"
        Key of the cell coordinates in `obsm`.

    Returns
    -------
    gpd.GeoDataFrame
        Alpha shapes for each cluster at each alpha value, indexed (and named)
        `f"{cluster}_{inv_alpha}"`, with columns `name`, `cat`, `geometry`,
        `inv_alpha`, `color`, and `area`, sorted by area.
    """
    coords = _cell_coords(adata, spatial_key=spatial_key, modality=modality)
    labels = _obs_column_at(adata, cat, coords, modality=modality)
    xy = coords.to_numpy()

    if meta_cluster is not None:
        color_lookup = {str(k): v for k, v in meta_cluster["color"].items()}
    else:
        color_lookup = _category_colors(adata, cat, modality=modality)

    gdf_alpha = gpd.GeoDataFrame()

    for inv_alpha in alphas:
        for inst_cluster in labels.dropna().unique():
            mask = (labels == inst_cluster).to_numpy()
            if mask.sum() > 3:
                inst_shape = alpha_shape(xy[mask], inv_alpha)

                inst_name = f"{inst_cluster}_{inv_alpha}"

                gdf_alpha.loc[inst_name, "name"] = inst_name
                gdf_alpha.loc[inst_name, "cat"] = inst_cluster
                gdf_alpha.loc[inst_name, "geometry"] = inst_shape
                gdf_alpha.loc[inst_name, "inv_alpha"] = int(inv_alpha)
                gdf_alpha.loc[inst_name, "color"] = color_lookup.get(str(inst_cluster), "#000000")

    gdf_alpha["geometry"] = gdf_alpha["geometry"].apply(
        lambda geom: _round_coordinates(geom, precision=2)
    )
    gdf_alpha["area"] = gdf_alpha.area

    return gdf_alpha.loc[gdf_alpha.area.sort_values(ascending=False).index.tolist()]


def alpha_shape_cell_clusters_by_slice(
    adata: Any,
    cluster_attr: str = "cluster",
    slice_attr: str = "slice_id",
    z_attr: str | None = None,
    alphas: Sequence[float] = (150,),
    meta_cluster: pd.DataFrame | None = None,
    z_jitter: float = 0.1,
    progress_every: int = 0,
    *,
    modality: str | None = None,
    spatial_key: str = "spatial",
) -> gpd.GeoDataFrame:
    """
    Compute one alpha shape per (slice, cluster) pair, each stamped with its slice's Z.

    For each slice, computes `alpha_shape_cell_clusters` / `filter_alpha_shapes`
    at a single alpha resolution, then stamps every resulting polygon with that
    slice's Z (from `z_attr`, or 0.0 if not given) plus a small per-cluster
    jitter (via `stamp_z`) so overlapping, coplanar cluster polygons within a
    slice don't z-fight.

    Parameters
    ----------
    adata : AnnData or MuData
        Cell-level data with spatial coordinates in `obsm[spatial_key]` and
        `cluster_attr` / `slice_attr` (and, if given, `z_attr`) columns in `obs`.
    cluster_attr : str
        Column with cluster/category labels.
    slice_attr : str
        Column identifying each slice.
    z_attr : str | None
        Column with each cell's Z coordinate (expected to be one constant value
        per slice). If None, every slice is stamped at Z=0.
    alphas : Sequence[float]
        Must contain exactly one inverse-alpha resolution (see `alpha_shape`) —
        this function computes a single resolution per (slice, cluster), unlike
        `alpha_shape_cell_clusters` which can sweep several.
    meta_cluster : pd.DataFrame | None
        Optional cluster metadata with a 'color' column. Defaults to the colors
        in `uns[f"{cluster_attr}_colors"]`, or a distinct fallback palette when
        none are stored, so every slice shares one palette.
    z_jitter : float
        Per-cluster Z offset within a slice, to avoid z-fighting between
        coplanar cluster polygons that would otherwise sit at the exact same Z.
    progress_every : int
        Print a progress line every this many slices processed (0, the
        default, disables it). Each alpha shape involves a Delaunay
        triangulation plus verification, so this is the slow part of a
        neighborhood-cloud pre-processing run on a dataset with many slices.
    modality : str, optional
        For a MuData input, the modality to take coordinates and labels from.
    spatial_key : str, default "spatial"
        Key of the cell coordinates in `obsm`.

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

    coords = _cell_coords(adata, spatial_key=spatial_key, modality=modality)
    clusters = _obs_column_at(adata, cluster_attr, coords, modality=modality)
    slices = _obs_column_at(adata, slice_attr, coords, modality=modality)
    z_values = (
        _obs_column_at(adata, z_attr, coords, modality=modality) if z_attr is not None else None
    )

    # The per-slice inputs below carry no `uns`, so resolve one shared palette
    # up front: stored colors, else a distinct fallback per cluster (otherwise
    # every shape would be black).
    if meta_cluster is None:
        color_dict = _category_colors(adata, cluster_attr, modality=modality)
        if not color_dict:
            categories = (
                list(clusters.cat.categories)
                if isinstance(clusters.dtype, pd.CategoricalDtype)
                else sorted(clusters.dropna().unique(), key=str)
            )
            color_dict = _fallback_category_colors(categories)
        meta_cluster = pd.DataFrame({"color": pd.Series(color_dict)})

    slice_ids = slices.unique()
    n_slices = len(slice_ids)

    gdfs: list[gpd.GeoDataFrame] = []
    for i, slice_id in enumerate(slice_ids, start=1):
        if progress_every and i % progress_every == 0:
            print(f"alpha shapes: slice {i}/{n_slices} ({slice_id})")
        mask = (slices == slice_id).to_numpy()
        cluster_values = clusters.to_numpy()[mask]

        adata_slice = ad.AnnData(
            obs=pd.DataFrame(
                {cluster_attr: cluster_values},
                index=pd.Index(coords.index[mask].astype(str)),
            ),
            obsm={"spatial": coords.to_numpy()[mask]},
        )

        gdf_alpha = alpha_shape_cell_clusters(
            adata_slice, cat=cluster_attr, alphas=[alpha], meta_cluster=meta_cluster
        )
        if gdf_alpha.empty:
            continue
        gdf_alpha = filter_alpha_shapes(gdf_alpha, alpha=alpha).reset_index(drop=True)
        if gdf_alpha.empty:
            continue

        z_val = float(z_values.to_numpy()[mask][0]) if z_values is not None else 0.0
        z_per_cluster = z_val + gdf_alpha.index.to_numpy(dtype=float) * z_jitter
        gdf_alpha["geometry"] = [
            stamp_z(geom, z) for geom, z in zip(gdf_alpha["geometry"], z_per_cluster, strict=True)
        ]

        cell_counts = pd.Series(cluster_values).astype(str).value_counts()
        gdf_alpha["cluster_id"] = gdf_alpha["name"].astype(str)
        gdf_alpha["slice_id"] = slice_id
        gdf_alpha["cell_count"] = gdf_alpha["cluster_id"].map(cell_counts).fillna(0).astype(int)
        gdf_alpha["name"] = gdf_alpha["slice_id"].astype(str) + "__" + gdf_alpha["cluster_id"]

        gdfs.append(gdf_alpha)

    if not gdfs:
        raise ValueError("no alpha shapes could be computed for any slice")

    gdf_all = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), geometry="geometry")
    if progress_every:
        print(f"alpha shapes: done, {len(gdf_all)} neighborhoods across {n_slices} slices")
    return gdf_all


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
        # Names are "{cat}_{alpha}"; strip the suffix whether alpha was written
        # as an int (150) or a float (150.0)
        suffixes = {f"_{alpha}"}
        if float(alpha).is_integer():
            suffixes |= {f"_{int(alpha)}", f"_{float(alpha)}"}

        def _strip_alpha(name: str) -> str:
            for suffix in suffixes:
                if name.endswith(suffix):
                    return name[: -len(suffix)]
            return name

        gdf_filtered["name"] = gdf_filtered["name"].apply(_strip_alpha)

    # Reset index for clean output
    return gdf_filtered.reset_index(drop=True)
