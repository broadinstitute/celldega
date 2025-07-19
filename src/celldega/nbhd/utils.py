"""Helper and utility functions."""

# Standard library imports
from collections.abc import Sequence
from typing import Any

# Third-party imports
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, base
from shapely.ops import transform

from celldega.pre.boundary_tile import (
    _round_nested_coord_list,
    batch_transform_geometries,
)


def _add_centroids_to_obsm(
    adata: Any,
    gdf: gpd.GeoDataFrame,
    key: str = "spatial",
) -> None:
    """
    Computes centroid x, y coordinates from a GeoDataFrame and stores them in adata.obsm.
    """
    if len(adata) != len(gdf):
        raise ValueError("Number of rows in adata and gdf must match.")

    centroids = gdf.geometry.centroid
    spatial_coords = np.vstack([centroids.x.values, centroids.y.values]).T
    adata.obsm[key] = spatial_coords


def _classify_polygons_contains_check(
    polygons: gpd.GeoSeries | Sequence[base.BaseGeometry],
    points: Sequence[Any],
) -> gpd.GeoSeries:
    """
    Classifies polygons as "real" or "fake" based on whether they contain any points inside.

    Parameters
    ----------
    polygons : GeoSeries of polygons (GeoPandas)
    points : Array-like of point coordinates (e.g., numpy array or list of tuples)

    Returns
    -------
    GeoSeries of curated polygons.
    """
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])
    gdf_poly = gpd.GeoDataFrame(geometry=polygons)
    joined = gpd.sjoin(points_gdf, gdf_poly, predicate="within")
    real_polygons_indices = joined["index_right"].unique()
    curated_polygons = gdf_poly.iloc[real_polygons_indices]
    # Use .get() for a more concise and idiomatic way to handle the conditional return
    return curated_polygons.get("geometry", curated_polygons)


def _get_df_cell(adata: Any) -> pd.DataFrame:
    """
    Load cell-level cluster and spatial coordinates from an h5ad file as a DataFrame.
    """
    df_cell = pd.DataFrame(
        {
            "cluster": adata.obs["leiden"],
            "x": adata.obsm["spatial"][:, 0],
            "y": adata.obsm["spatial"][:, 1],
        }
    )
    df_cell["geometry"] = df_cell.apply(
        lambda row: [round(row["x"], 3), round(row["y"], 3)], axis=1
    )
    return df_cell


def _get_gdf_cell(adata: Any) -> gpd.GeoDataFrame:
    """
    Load cell-level cluster and spatial coordinates from an h5ad file as a GeoDataFrame.
    """
    return gpd.GeoDataFrame(
        {"cluster": adata.obs["leiden"]},
        geometry=gpd.points_from_xy(*adata.obsm["spatial"].T[:2]),
        crs="EPSG:4326",
    )


def _get_gdf_trx(data_dir: str) -> gpd.GeoDataFrame:
    """
    Load transcript data as a GeoDataFrame with spatial coordinates.
    """
    df_trx = pd.read_parquet(
        f"{data_dir}/transcripts.parquet",
        columns=["feature_name", "x_location", "y_location", "cell_id"],
        engine="pyarrow",
    )
    geometry = gpd.points_from_xy(df_trx["x_location"], df_trx["y_location"])
    return gpd.GeoDataFrame(df_trx[["feature_name", "cell_id"]], geometry=geometry, crs="EPSG:4326")


def _round_coordinates(
    geometry: base.BaseGeometry | None, precision: int = 2
) -> base.BaseGeometry | None:
    """
    Round the coordinates of a Shapely geometry to the specified precision.

    Parameters
    ----------
    geometry : Shapely geometry object (e.g., Polygon, MultiPolygon).
    precision : int
        Number of decimal places to round to.

    Returns
    -------
    Rounded Shapely geometry or None.
    """
    if geometry is None:
        return None

    def round_coords(
        x: float, y: float, z: float | None = None
    ) -> tuple[float, float] | tuple[float, float, float]:
        if z is not None:
            return (round(x, precision), round(y, precision), round(z, precision))
        return (round(x, precision), round(y, precision))

    return transform(round_coords, geometry)


def get_gdf_cell_from_adata(
    adata: Any,
    key: str = "spatial",
    cluster_key: str = "leiden",
) -> gpd.GeoDataFrame:
    """Return cell coordinates from an :class:`~anndata.AnnData` object as a
    :class:`geopandas.GeoDataFrame`.

    Parameters
    ----------
    adata:
        AnnData object with spatial coordinates stored in ``adata.obsm[key]``.
    key:
        Key in ``adata.obsm`` where the spatial coordinates are stored.
    cluster_key:
        Column in ``adata.obs`` containing cluster labels. Defaults to
        ``"leiden"``.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with cell clusters (if present) and point geometries.
    """

    clusters = adata.obs.get(cluster_key)
    return gpd.GeoDataFrame(
        {"cluster": clusters} if clusters is not None else {},
        geometry=gpd.points_from_xy(*adata.obsm[key].T[:2]),
        crs="EPSG:4326",
    )


def save_nbhd_to_parquet(
    gdf_nbhd: gpd.GeoDataFrame,
    path_output: str,
    transformation_matrix: np.ndarray | str,
    image_scale: float = 1,
) -> None:
    """Save neighborhoods to a Parquet file after converting from micron to
    image (Parquet) space.

    Parameters
    ----------
    gdf_nbhd:
        Neighborhood polygons in micron coordinates.
    path_output:
        Destination Parquet file.
    transformation_matrix:
        3x3 affine matrix or path to ``micron_to_image_transform.csv``.
    image_scale:
        Scale factor applied after the affine transformation.
    """

    if isinstance(transformation_matrix, str):
        transformation_matrix = pd.read_csv(transformation_matrix, header=None, sep=" ").values

    transformed = batch_transform_geometries(
        gdf_nbhd["geometry"], transformation_matrix, image_scale
    )
    df = gdf_nbhd.copy()
    df["GEOMETRY"] = [coords for coords in transformed]
    df["GEOMETRY"] = df["GEOMETRY"].apply(lambda x: _round_nested_coord_list(x))
    df.drop(columns=["geometry"], inplace=True)
    df.to_parquet(path_output, index=False)


def save_alpha_shape_clusters_to_parquet(
    meta_cell: gpd.GeoDataFrame,
    path_output: str,
    transformation_matrix: np.ndarray | str,
    alphas: Sequence[float] | None = None,
    cat: str = "cluster",
    image_scale: float = 1,
) -> None:
    """Compute alpha shapes for cell clusters and save as Parquet.

    Parameters
    ----------
    meta_cell:
        GeoDataFrame with cell coordinates in micron space.
    path_output:
        Destination Parquet file.
    transformation_matrix:
        3x3 affine matrix or path to ``micron_to_image_transform.csv``.
    alphas:
        Iterable of alpha values to compute shapes for. Defaults to
        ``(100, 150, 200, 250, 300, 350)``.
    cat:
        Column in ``meta_cell`` containing cluster labels. Defaults to
        ``"cluster"``.
    image_scale:
        Scale factor applied after the affine transformation.
    """

    if alphas is None:
        alphas = (100, 150, 200, 250, 300, 350)

    gdf_alpha = alpha_shape_cell_clusters(meta_cell, cat=cat, alphas=alphas)
    save_nbhd_to_parquet(
        gdf_alpha,
        path_output,
        transformation_matrix,
        image_scale=image_scale,
    )
