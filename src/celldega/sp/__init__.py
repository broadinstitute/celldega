"""
Module for spatial operation and analysis
"""

import pandas as pd
import geopandas as gpd
from ..nbhd import *
from shapely.geometry import Point


def calc_distance_to_roi(adata, gdf_polygon):
    """
    Calculate distance from each cell in adata to the specified ROI polygon
    and store the result in adata.obs.
    
    Parameters:
    - adata: AnnData object with .obsm['spatial'] for coordinates
    - gdf_polygon: GeoDataFrame with 'roi' and 'geometry' columns
    - roi_name: Name of the ROI polygon to measure distance to
    """

    polygon_geom = gdf_polygon.geometry.iloc[0]
    roi_name = gdf_polygon.roi.iloc[0]
    print(f"Extracting polygon for ROI: {roi_name}")

    if gdf_polygon.empty:
        raise ValueError(f"ROI '{roi_name}' not found in gdf_polygons.")

    # Get spatial coordinates
    spatial_coords = adata.obsm['spatial'][:, :2]
    points = [Point(xy) for xy in spatial_coords]

    # Compute distances
    distances = [pt.distance(polygon_geom) for pt in points]

    # Add to adata.obs
    dist_col = f"distance_to_roi_{roi_name}"
    adata.obs[dist_col] = distances

    print(f"Distance column '{dist_col}' added to adata.obs.")
    return adata


def calc_gene_expression_by_band(
    adata,
    gdf_bands: gpd.GeoDataFrame,
    nbhd_col: str = "band"
) -> gpd.GeoDataFrame:
    """
    Calculate mean gene expression per band from adata and band GeoDataFrame.

    Args:
        adata: AnnData object with spatial info in .obsm['spatial'] and gene data in .X.
        gdf_bands: GeoDataFrame with band polygons, must contain a 'band' column.
        nbhd_col: Neighborhood column in gdf_bands that labels each nbhd.

    Returns:
        GeoDataFrame with band geometries and mean gene expression values
        as columns named like 'GENE_mean'.
    """

    # Get gene list
    gene_list = adata.var.index

    gene_exp = pd.DataFrame(
        data=adata[:, gene_list].X.toarray() if hasattr(adata.X, 'toarray') else adata[:, gene_list].X,
        columns=gene_list,
        index=adata.obs_names
    )

    # Create combined DataFrame with geometry
    gdf_cell = gpd.GeoDataFrame(
        data={
            'cluster': adata.obs['leiden'],
            **gene_exp  # Unpacks all gene columns
        },
        geometry=[Point(xy) for xy in adata.obsm['spatial'][:, :2]],
        crs="EPSG:4326"  # Set your coordinate system here
    )

    # Spatial join: Assign each cell to the closest buffer
    gdf_join_all = gdf_cell.sjoin(gdf_bands, how="left", predicate="within").drop(
        columns=['index_right'], errors='ignore')

    # Compute mean expression for each gene
    for gene in gene_list:
        band_avg_expression = gdf_join_all.groupby(nbhd_col)[gene].mean().reset_index()
        band_avg_expression.columns = [nbhd_col, f"{gene}_mean"]
        gdf_join_all = gdf_join_all.merge(band_avg_expression, on=nbhd_col)

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


