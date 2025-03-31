import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import geopandas as gpd
import pandas as pd


def extract_roi_polygon(gdf_polygons: gpd.GeoDataFrame, roi_name: str) -> gpd.GeoDataFrame:
    """
    Extract the polygon corresponding to the specified region of interest (ROI).

    Args:
        gdf_polygons (gpd.GeoDataFrame): GeoDataFrame containing all polygons.
        roi_name (str): Name of the region of interest.

    Returns:
        gpd.GeoDataFrame: A single-row GeoDataFrame containing the ROI polygon.
    """
    return gdf_polygons[gdf_polygons["roi"] == roi_name].reset_index(drop=True)


def calculate_distances(gdf_points: gpd.GeoDataFrame, roi_polygon: gpd.GeoDataFrame, roi_name: str) -> gpd.GeoDataFrame:
    """
    Calculate the distance of each point to the given polygon.

    Args:
        gdf_points (gpd.GeoDataFrame): GeoDataFrame of points.
        roi_polygon (gpd.GeoDataFrame): Single-row GeoDataFrame of the ROI polygon.
        roi_name (str): Name of the ROI for naming the new distance column.

    Returns:
        gpd.GeoDataFrame: Points GeoDataFrame with a new column for distance to the polygon.
    """
    polygon_geom = roi_polygon.geometry.iloc[0]
    gdf_points = gdf_points.copy()
    gdf_points[f"distance_to_polygon_{roi_name}"] = gdf_points["geometry"].apply(lambda point: polygon_geom.distance(point))
    return gdf_points


def plot_distances(gdf_points: gpd.GeoDataFrame, roi_polygon: gpd.GeoDataFrame, roi_name: str, cmap=cm.plasma, markersize=0.5):
    """
    Plot the points colored by their distance to the polygon.

    Args:
        gdf_points (gpd.GeoDataFrame): GeoDataFrame with distance column.
        roi_polygon (gpd.GeoDataFrame): Single-row GeoDataFrame of the ROI polygon.
        roi_name (str): Name of the region of interest.
        cmap: Matplotlib colormap for coloring the distances.
        markersize (float): Size of points in the plot.
    """
    distances = gdf_points[f"distance_to_polygon_{roi_name}"]
    norm = mcolors.Normalize(vmin=distances.min(), vmax=distances.max())
    gdf_points = gdf_points.copy()
    gdf_points["color"] = distances.apply(lambda x: cmap(norm(x)))
    gdf_points["inside_polygon"] = gdf_points["geometry"].apply(lambda x: roi_polygon.geometry.iloc[0].contains(x))

    fig, ax = plt.subplots(figsize=(20, 8))
    gdf_points[~gdf_points["inside_polygon"]].plot(
        ax=ax,
        color=gdf_points[~gdf_points["inside_polygon"]]["color"],
        aspect=1,
        legend=True,
        markersize=markersize,
    )
    roi_polygon.plot(ax=ax, color="red", aspect=1, alpha=0.3, edgecolor="black", linewidth=2)
    centroid = roi_polygon.geometry.iloc[0].centroid
    ax.annotate(roi_name, (centroid.x, centroid.y), ha="center", va="center", fontsize=12)
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation="vertical", pad=0.01, aspect=40)
    cbar.set_label(f"Distance to Polygon {roi_name} (micron)")
    ax.invert_yaxis()
    plt.title(f"Cells Colored by Distance to Polygon {roi_name}")
    plt.xlabel("x (micron)")
    plt.ylabel("y (micron)")
    plt.tight_layout()
    plt.show()


def generate_gradient_bands(roi_polygon: gpd.GeoDataFrame, band_width: float, num_bands: int) -> gpd.GeoDataFrame:
    """
    Create concentric buffer bands around the ROI polygon.

    Args:
        roi_polygon (gpd.GeoDataFrame): Single-row GeoDataFrame of the ROI polygon.
        band_width (float): Width of each buffer band (in microns).
        num_bands (int): Number of buffer bands to generate.

    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing all generated bands.
    """
    bands = []
    for i in range(1, num_bands + 1):
        band = roi_polygon.copy()
        band["geometry"] = band["geometry"].buffer(i * band_width)
        band["band"] = i
        bands.append(band)
    return gpd.GeoDataFrame(pd.concat(bands, ignore_index=True)).set_crs('EPSG:4326')


def assign_bands_to_points(gdf_points: gpd.GeoDataFrame, gdf_bands: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Assign each point to a buffer band using a spatial join.

    Args:
        gdf_points (gpd.GeoDataFrame): GeoDataFrame of points.
        gdf_bands (gpd.GeoDataFrame): GeoDataFrame of buffer bands.

    Returns:
        gpd.GeoDataFrame: Points joined with the band info they fall within.
    """
    return gdf_points.sjoin(gdf_bands, how="left", predicate="within")


def compute_gene_gradients(gdf_joined: gpd.GeoDataFrame, roi_name: str, band_width: float, gene_list: list) -> gpd.GeoDataFrame:
    """
    Compute mean gene expression per band for the selected genes.

    Args:
        gdf_joined (gpd.GeoDataFrame): Points joined with bands.
        roi_name (str): Name of the ROI to identify the distance column.
        band_width (float): Width of the buffer bands (in microns).
        gene_list (list): List of gene names to compute gradients for.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with additional mean expression columns per band.
    """
    gdf = gdf_joined.copy()
    gdf["band"] = (gdf[f"distance_to_polygon_{roi_name}"] // band_width).astype(int)
    for gene in gene_list:
        band_means = gdf.groupby("band")[gene].mean().reset_index()
        band_means.columns = ["band", f"{gene}_mean"]
        gdf = gdf.merge(band_means, on="band")
    return gdf


def plot_gene_gradients(gdf: gpd.GeoDataFrame, roi_polygon: gpd.GeoDataFrame, roi_name: str, gene_list: list, markersize: float = 1):
    """
    Plot gene expression gradients relative to the polygon for each gene.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame with computed gene gradients.
        roi_polygon (gpd.GeoDataFrame): Single-row GeoDataFrame of the ROI polygon.
        roi_name (str): Name of the region of interest.
        gene_list (list): List of genes to plot.
        markersize (float): Size of points in the plot.
    """
    for gene in gene_list:
        fig, ax = plt.subplots(figsize=(20, 8))
        gdf.plot(
            ax=ax,
            column=f"{gene}_mean",
            aspect=1,
            cmap="coolwarm",
            legend=True,
            alpha=0.7,
            markersize=markersize,
        )
        centroid = roi_polygon.geometry.iloc[0].centroid
        ax.annotate(roi_name, (centroid.x, centroid.y), ha="center", va="center", fontsize=12)
        ax.invert_yaxis()
        plt.title(f"{gene} Expression Gradient Relative to {roi_name}")
        plt.xlabel("x (micron)")
        plt.ylabel("y (micron)")
        plt.tight_layout()
        plt.show()


def save_bands_to_parquet(gdf_bands: gpd.GeoDataFrame, file_path: str):
    """
    Save the buffer bands to a Parquet file.

    Args:
        gdf_bands (gpd.GeoDataFrame): GeoDataFrame containing the bands.
        file_path (str): Destination file path to save the Parquet file.
    """
    gdf_bands.to_parquet(file_path, engine="pyarrow")
    print(f"Gradient bands saved to {file_path}")
