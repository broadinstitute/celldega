"""
Module for spatial operation and analysis
"""


import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import geopandas as gpd
import pandas as pd
import colorsys
import numpy as np

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

def plot_distance_to_roi(
    gdf_points: gpd.GeoDataFrame,
    gdf_polygon: gpd.GeoDataFrame,
    roi_name: str,
    cmap=cm.plasma,
    markersize: float = 0.5
):
    """
    Plot the points colored by their distance to the region of interest.
    
    Args:
        gdf_points: GeoDataFrame containing points with distance column.
        gdf_polygon: GeoDataFrame containing the target polygon.
        roi_name: Name of the region of interest.
        cmap: Colormap for distance visualization.
        markersize: Size of the points in the plot.
    """

    print (f"Plotting distances from points to polygon {roi_name}...")

    # Normalize distances for color mapping
    norm = mcolors.Normalize(
        vmin=gdf_points[f"distance_to_polygon_{roi_name}"].min(),
        vmax=gdf_points[f"distance_to_polygon_{roi_name}"].max(),
    )
    
    # Map distances to colors
    gdf_points["color"] = gdf_points[f"distance_to_polygon_{roi_name}"].apply(
        lambda x: cmap(norm(x))
    )
    
    # Identify points inside the roi
    polygon = gdf_polygon.geometry.iloc[0]  # Assuming one roi
    gdf_points["inside_polygon"] = gdf_points["geometry"].apply(
        lambda x: polygon.contains(x))
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(20, 8))
    
    # Plot points outside the roi with gradient color
    gdf_points[~gdf_points["inside_polygon"]].plot(
        ax=ax,
        color=gdf_points[~gdf_points["inside_polygon"]]["color"],
        aspect=1,
        legend=True,
        markersize=markersize,
    )
    
    # Plot the roi as a filled area with label
    gdf_polygon.plot(
        ax=ax, color="gray", aspect=1, alpha=0.5, edgecolor="black", linewidth=2
    )
    
    # Annotate the polygon with the ROI name at its centroid
    centroid = gdf_polygon.geometry.iloc[0].centroid
    ax.annotate(
        text=roi_name,
        xy=(centroid.x, centroid.y),
        ha="center",
        va="center",
        fontsize=12,
        color="black",
    )
    
    # Add colorbar for the gradient
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation="vertical", pad=0.01, aspect=40)
    cbar.set_label(f"Distance to ROI {roi_name} (micron)")
    
    # Adjust the plot
    ax.invert_yaxis()
    plt.title(
        f"Region Selected Cells Colored Based on Distance to the ROI {roi_name} (micron)"
    )
    plt.tight_layout()
    plt.xlabel("x (micron)")
    plt.ylabel("y (micron)")
    plt.show()


def create_concentric_rings(polygon, num_bands, band_width):
    """
    Create concentric rings (buffers) around a given polygon.

    This function generates multiple concentric rings around a polygon by creating buffers
    at increasing distances from the original polygon. Each ring is defined by the area
    between two consecutive buffers.

    Parameters:
    polygon (shapely.geometry.Polygon): The polygon around which to create concentric rings.
    num_bands (int): The number of concentric rings to create.
    band_width (float): The width of each ring in the same units as the polygon.

    Returns:
    geopandas.GeoDataFrame: A GeoDataFrame containing the concentric rings as individual
                            geometries with a 'band' identifier for each ring. The GeoDataFrame
                            is set to the EPSG:4326 coordinate reference system.
    """
    band_list = []
    for i in range(1, num_bands + 1):
        outer = polygon.buffer(i * band_width)
        inner = polygon.buffer((i - 1) * band_width)
        ring = outer.difference(inner)

        band = polygon.copy()
        band["geometry"] = ring
        band["band"] = i
        band_list.append(band)

    return gpd.GeoDataFrame(pd.concat(band_list, ignore_index=True)).set_crs('EPSG:4326')

def calc_gene_expression_by_band(
    gdf_points: gpd.GeoDataFrame,
    gdf_polygon: gpd.GeoDataFrame,
    roi_name: str,
    band_width: float,
    num_bands: int,
    gene_list: list
) -> gpd.GeoDataFrame:
    """
    Calculate gene expression gradients relative to the roi.
    
    Args:
        gdf_points: GeoDataFrame containing points with distance column.
        gdf_polygon: GeoDataFrame containing the target polygon.
        path_landscape_files: path to landscaope files
        roi_name: Name of the region of interest.
        band_width: Width of each band (in microns).
        num_bands: Number of bands to create.
        gene_list: List of genes to calculate gradients for.
    
    Returns:
        A GeoDataFrame containing the bands and mean gene expression.
    """

    print (f"Complete calculating gene exp. gradient from points to {roi_name} using {band_width} micron rings.")


    # Merge all bands into a single GeoDataFrame
    gdf_bands = create_concentric_rings(gdf_polygon, num_bands, band_width)
    
    # Spatial join: Assign each cell to the closest buffer
    gdf_join_all = gdf_points.sjoin(gdf_bands, how="left", predicate="within").drop(
        columns=['index_right'], errors='ignore')
    
    # Compute mean expression per band
    gdf_join_all["band"] = (
        gdf_join_all[f"distance_to_polygon_{roi_name}"] // band_width
    ).astype(int)
    
    # Compute mean expression for each gene
    for gene in gene_list:
        band_avg_expression = gdf_join_all.groupby("band")[gene].mean().reset_index()
        band_avg_expression.columns = ["band", f"{gene}_mean"]
        gdf_join_all = gdf_join_all.merge(band_avg_expression, on="band")

    return gdf_join_all, gdf_bands

def plot_gene_gradient_to_roi(
    gdf_join_all: gpd.GeoDataFrame,
    gdf_polygon: gpd.GeoDataFrame,
    roi_name: str,
    gene_list: list,
    markersize: float = 1
):
    """
    Plot gene expression gradients relative to the region of interest.
    
    Args:
        gdf_join_all: GeoDataFrame containing bands and gene expression data.
        gdf_polygon: GeoDataFrame containing the target roi.
        roi_name: Name of the region of interest.
        gene_list: List of genes to plot gradients for.
        markersize: Size of the points in the plot.
    """

    print (f"Plotting gene expression gradient from points to ROI {roi_name}...")

    for gene in gene_list:
        # Plot results
        fig, ax = plt.subplots(figsize=(20, 8))
        
        # Plot points outside the roi with gradient color
        gdf_join_all.plot(
            ax=ax,
            column=f"{gene}_mean",
            aspect=1,
            cmap="coolwarm",
            legend=True,
            alpha=0.7,
            markersize=markersize,
        )

        # Plot the roi as a filled area with label
        gdf_polygon.plot(
            ax=ax, color="gray", aspect=1, alpha=0.5, edgecolor="black", linewidth=2
        )

        # Annotate the polygon with the ROI name at its centroid
        centroid = gdf_polygon.geometry.iloc[0].centroid
        ax.annotate(
            text=roi_name,
            xy=(centroid.x, centroid.y),
            ha="center",
            va="center",
            fontsize=12,
            color="black",
        )         

        ax.invert_yaxis()
        plt.title(f"Gradient of {gene} Expression per Cell Along Distance to ROI")
        plt.xlabel("x (micron)")
        plt.ylabel("y (micron)")
        plt.tight_layout()
        plt.show()


def create_band_pixel(gdf_micron, gdf_pixel, roi_name, n_rings, band_width, json_fname):
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
    gdf_bands_pixel = create_concentric_rings(gdf_pixel, n_rings, band_width/conversion_factor)
    
    # 3. Save to GeoJSON
    gdf_bands_pixel.to_file(json_fname, driver='GeoJSON')
    return gdf_bands_pixel


def assign_distinct_colors(spatial_region, color_metric='cat', alpha=100):
    """
    Assign perceptually distinct colors to features based on band values
    Supports >12 distinguishable colors using HSV color space cycling
    """
    bands = [f['properties'][color_metric] for f in spatial_region['features']]
    min_band, max_band = min(bands), max(bands)
    
    for feature in spatial_region['features']:
        band = feature['properties'][color_metric]
        
        # Normalize band value (handle NaN/None)
        try:
            norm = (float(band) - min_band) / (max_band - min_band) if max_band > min_band else 0.5
        except (TypeError, ValueError):
            norm = 0.5  # Fallback for invalid values
        
        # Generate distinct color using HSV space
        hue = norm * 0.9  # 0.9 avoids red-purple wrap which looks similar
        saturation = 0.8 + (norm * 0.2)  # Vary saturation slightly
        value = 0.7 + (norm * 0.3)  # Vary brightness
        
        # Convert to RGB
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        
        # Apply to feature (scale 0-255)
        feature['properties']['color'] = [
            int(r * 255),
            int(g * 255),
            int(b * 255),
            alpha
        ]