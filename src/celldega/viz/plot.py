import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import geopandas as gpd
from shapely.geometry import Point


def plot_distance_to_roi(
    adata: gpd.GeoDataFrame,
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


    # Create a GeoDataFrame for the points
    gdf_points = gpd.GeoDataFrame(
    data={
        f"distance_to_roi_{roi_name}": adata.obs[f"distance_to_roi_{roi_name}"],
    },
    geometry=[Point(xy) for xy in adata.obsm['spatial'][:, :2]],
    crs="EPSG:4326"
)

    # Normalize distances for color mapping
    norm = mcolors.Normalize(
        vmin=gdf_points[f"distance_to_roi_{roi_name}"].min(),
        vmax=gdf_points[f"distance_to_roi_{roi_name}"].max(),
    )
    
    # Map distances to colors
    gdf_points["color"] = gdf_points[f"distance_to_roi_{roi_name}"].apply(
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

    