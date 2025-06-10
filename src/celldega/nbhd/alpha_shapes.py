"""Module for alpha shapes computation."""

from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Any

import geopandas as gpd
from libpysal.cg import alpha_shape as libpysal_alpha_shape
import numpy as np
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
    meta_cell: gpd.GeoDataFrame,
    cat: str = "cluster",
    alphas: Sequence[float] = (100, 150, 200, 250, 300, 350),
) -> gpd.GeoDataFrame:
    """
    Compute alpha shapes for each cluster in the cell metadata.
    """
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

    gdf_alpha["geometry"] = gdf_alpha["geometry"].apply(
        lambda geom: _round_coordinates(geom, precision=2)
    )
    gdf_alpha["area"] = gdf_alpha.area
    return gdf_alpha.loc[gdf_alpha.area.sort_values(ascending=False).index.tolist()]


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
