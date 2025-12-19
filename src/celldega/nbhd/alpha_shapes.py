"""Module for alpha shapes computation."""

from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Any

import anndata as ad
import geopandas as gpd
from libpysal.cg import alpha_shape as libpysal_alpha_shape
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Point, base, shape

from .utils import _classify_polygons_contains_check, _round_coordinates


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
        recalculated_alpha = libpysal_alpha_shape(coords, alpha)

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
    poly = libpysal_alpha_shape(points, 1 / inv_alpha)
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

    meta_cell = adata.obs

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
