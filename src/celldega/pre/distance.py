import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import geopandas as gpd
import pandas as pd
from .boundary_tile import batch_transform_geometries
from .__init__ import _to_geometry

def calc_distance_to_polygon(
    gdf_polygons: gpd.GeoDataFrame,
    gdf_points: gpd.GeoDataFrame,
    roi_name: str
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """
    Calculate the distance of points to the specified polygon.
    
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
    gdf_points[f"distance_to_polygon_{roi_name}"] = gdf_points["geometry"].apply(
        lambda point: gdf_polygon.geometry.iloc[0].distance(point)
    )
    print (f"Distances from points to polygon {roi_name} were calculated.")
    return gdf_points, gdf_polygon

def plot_distance_to_polygon(
    gdf_points: gpd.GeoDataFrame,
    gdf_polygon: gpd.GeoDataFrame,
    roi_name: str,
    cmap=cm.plasma,
    markersize: float = 0.5
):
    """
    Plot the points colored by their distance to the polygon.
    
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
    
    # Identify points inside the polygon
    polygon = gdf_polygon.geometry.iloc[0]  # Assuming one polygon
    gdf_points["inside_polygon"] = gdf_points["geometry"].apply(
        lambda x: polygon.contains(x))
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(20, 8))
    
    # Plot points outside the polygon with gradient color
    gdf_points[~gdf_points["inside_polygon"]].plot(
        ax=ax,
        color=gdf_points[~gdf_points["inside_polygon"]]["color"],
        aspect=1,
        legend=True,
        markersize=markersize,
    )
    
    # Plot the polygon as a filled area with label
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
    cbar.set_label(f"Distance to Polygon {roi_name} (micron)")
    
    # Adjust the plot
    ax.invert_yaxis()
    plt.title(
        f"Region Selected Cells Colored Based on Distance to the Polygon {roi_name} (micron)"
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
    # Create buffers at multiple distances
    band_list = []
    for i in range(1, num_bands + 1):
        outer = polygon.buffer(i * band_width)
        inner = polygon.buffer((i - 1) * band_width)
        ring = outer.difference(inner)

        band = {'geometry': ring, 'band': i}
        band_list.append(band)

    return gpd.GeoDataFrame(pd.DataFrame(band_list), crs='EPSG:4326')


def calc_gene_gradient_to_polygon(
    gdf_points: gpd.GeoDataFrame,
    gdf_polygon: gpd.GeoDataFrame,
    roi_name: str,
    band_width: float,
    num_bands: int,
    gene_list: list
) -> gpd.GeoDataFrame:
    """
    Calculate gene expression gradients relative to the polygon.
    
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

def plot_gene_gradient_to_polygon(
    gdf_join_all: gpd.GeoDataFrame,
    gdf_polygon: gpd.GeoDataFrame,
    roi_name: str,
    gene_list: list,
    markersize: float = 1
):
    """
    Plot gene expression gradients relative to the polygon.
    
    Args:
        gdf_join_all: GeoDataFrame containing bands and gene expression data.
        gdf_polygon: GeoDataFrame containing the target polygon.
        roi_name: Name of the region of interest.
        gene_list: List of genes to plot gradients for.
        markersize: Size of the points in the plot.
    """

    print (f"Plotting gene expression gradient from points to polygon {roi_name}...")

    for gene in gene_list:
        # Plot results
        fig, ax = plt.subplots(figsize=(20, 8))
        
        # Plot points outside the polygon with gradient color
        gdf_join_all.plot(
            ax=ax,
            column=f"{gene}_mean",
            aspect=1,
            cmap="coolwarm",
            legend=True,
            alpha=0.7,
            markersize=markersize,
        )

        # Plot the polygon as a filled area with label
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
        plt.title(f"Gradient of {gene} Expression per Cell Along Distance to Polygon")
        plt.xlabel("x (micron)")
        plt.ylabel("y (micron)")
        plt.tight_layout()
        plt.show()

def save_bands_to_parquet(gdf_bands: gpd.GeoDataFrame, file_path: str):
    """
    Save the generated bands to a Parquet file.
    
    Args:
        gdf_bands: GeoDataFrame containing the bands.
        file_path: Path to save the Parquet file.
    """
    # Save to Parquet
    gdf_bands.to_parquet(file_path, engine="pyarrow")
    print(f"Gradient bands saved to {file_path}")