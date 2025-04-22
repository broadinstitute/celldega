"""
Module for spatial operation and analysis
"""


import geopandas as gpd
import celldega as dega
from ..nbhd import *

def calc_distance_to_roi(
    gdf_polygons: gpd.GeoDataFrame,
    gdf_points: gpd.GeoDataFrame,
    roi_name: str
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Calculate the distance of points to the specified region of interest.
    
    Args:
        gdf_polygons: GeoDataFrame containing polygons with a 'roi' column.
        gdf_points: GeoDataFrame containing points to calculate distances for.
        roi_name: Name of the region of interest (ROI) to calculate distances to.
    
    Returns:
        A tuple containing:
            - gdf_points: The input gdf_points with added distance column.
            - gdf_polygon: The extracted polygon for the specified ROI.
    """

    print (f"Extract the polygon for the specified ROI: {roi_name}")
    # Extract the polygon for the specified ROI
    gdf_polygon = gdf_polygons.loc[gdf_polygons["roi"] == roi_name].reset_index()
    
    # Calculate distances from points to the polygon
    polygon_geom = gdf_polygon.geometry.iloc[0]

    gdf_points_with_dist = gdf_points.copy()
    gdf_points_with_dist[f"distance_to_polygon_{roi_name}"] = gdf_points_with_dist.distance(polygon_geom)
    print (f"Distances from points to polygon {roi_name} were calculated.")
    return gdf_points_with_dist, gdf_polygon


def calc_gene_expression_by_band(
    gdf_points: gpd.GeoDataFrame,
    gdf_bands: gpd.GeoDataFrame,
    roi_name: str,
    band_width: float,
    gene_list: list
) -> gpd.GeoDataFrame:
    """
    Calculate gene expression gradients relative to the roi.
    
    Args:
        gdf_points: GeoDataFrame containing points with distance column.
        gdf_bands: GeoDataFrame containing bands (concentric rings).
        roi_name: Name of the region of interest.
        gene_list: List of genes to calculate gradients for.
    
    Returns:
        A GeoDataFrame containing the bands and mean gene expression.
    """

    print (f"Complete calculating gene exp. gradient from points to {roi_name}.")
    
    # Spatial join: Assign each cell to the closest buffer
    gdf_join_all = gdf_points.sjoin(gdf_bands, how="left", predicate="within").drop(
        columns=['index_right'], errors='ignore')

    # Compute mean expression for each gene
    for gene in gene_list:
        band_avg_expression = gdf_join_all.groupby("band")[gene].mean().reset_index()
        band_avg_expression.columns = ["band", f"{gene}_mean"]
        gdf_join_all = gdf_join_all.merge(band_avg_expression, on="band")

    return gdf_join_all


def _create_band_pixel(gdf_micron, gdf_pixel, roi_name, n_rings, band_width, json_fname):
    """
    Creates concentric bands in pixel space and saves as GeoJSON.
    
    Parameters:
    - gdf_micron: GeoDataFrame in micron coordinates
    - gdf_pixel: GeoDataFrame in pixel coordinates
    - roi_name: name of the region of interest
    - n_rings: number of concentric rings to create
    - band_width: desired band width in microns
    - json_fname: output filename for GeoJSON
    """
    
    # 1. Calculate conversion factor
    micron_poly = gdf_micron[gdf_micron['roi'] == roi_name]['geometry'].iloc[0]
    pixel_poly = gdf_pixel[gdf_pixel['roi'] == roi_name]['geometry'].iloc[0]
    conversion_factor = (micron_poly.area / pixel_poly.area) ** 0.5

    # 2. Create bands in pixel space (scaled by conversion factor)
    gdf_pixel = gdf_pixel.loc[gdf_pixel["roi"] == roi_name].reset_index()
    gdf_bands_pixel = calc_grad_nbhd_from_roi(gdf_pixel, n_rings, band_width/conversion_factor)
    
    # 3. Save to GeoJSON
    gdf_bands_pixel.to_file(json_fname, driver='GeoJSON')
    return gdf_bands_pixel


