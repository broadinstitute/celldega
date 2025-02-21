import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import geopandas as gpd
import pandas as pd

class DistanceToPolygon:
    """
    A class to calculate and visualize distances and gradients relative to a polygon.

    Attributes:
        gdf_polygons (gpd.GeoDataFrame): GeoDataFrame containing polygons with a 'roi' column.
        gdf_points (gpd.GeoDataFrame): GeoDataFrame containing points to calculate distances for.
        roi_name (str): Name of the region of interest (ROI) to calculate distances to.
        cmap: Colormap for distance visualization (default: matplotlib.cm.plasma).
        markersize (float): Size of the points in the plot (default: 0.5).
    """

    def __init__(
        self,
        gdf_polygons: gpd.GeoDataFrame,
        gdf_points: gpd.GeoDataFrame,
        roi_name: str,
        cmap=cm.plasma,
        markersize: float = 0.5,
    ):
        self.gdf_polygons = gdf_polygons
        self.gdf_points = gdf_points
        self.roi_name = roi_name
        self.cmap = cmap
        self.markersize = markersize

    def calc_distance_to_polygon(self) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Calculate the distance of points to the specified polygon.

        Returns:
            tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: A tuple containing:
                - `gdf_points`: The input `gdf_points` with added columns for distance and color.
                - `gdf_polygon`: The extracted polygon for the specified ROI.
        """
        # Extract the polygon for the specified ROI
        self.gdf_polygon = self.gdf_polygons.loc[
            self.gdf_polygons["roi"] == self.roi_name
        ].reset_index()

        # Calculate distances from points to the polygon
        self.gdf_points[f"distance_to_polygon_{self.roi_name}"] = self.gdf_points[
            "geometry"
        ].apply(lambda point: self.gdf_polygon.geometry.iloc[0].distance(point))

        return self.gdf_points, self.gdf_polygon

    def plot_distance_to_polygon(self):
        """
        Plot the points colored by their distance to the polygon.
        """
        if not hasattr(self, "gdf_polygon"):
            self.calc_distance_to_polygon()

        # Normalize distances for color mapping
        norm = mcolors.Normalize(
            vmin=self.gdf_points[f"distance_to_polygon_{self.roi_name}"].min(),
            vmax=self.gdf_points[f"distance_to_polygon_{self.roi_name}"].max(),
        )

        # Map distances to colors
        self.gdf_points["color"] = self.gdf_points[
            f"distance_to_polygon_{self.roi_name}"
        ].apply(lambda x: self.cmap(norm(x)))

        # Identify points inside the polygon
        polygon = self.gdf_polygon.geometry.iloc[0]  # Assuming one polygon
        self.gdf_points["inside_polygon"] = self.gdf_points["geometry"].apply(
            lambda x: polygon.contains(x)
        )

        # Create the plot
        fig, ax = plt.subplots(figsize=(20, 8))

        # Plot points outside the polygon with gradient color
        self.gdf_points[~self.gdf_points["inside_polygon"]].plot(
            ax=ax,
            color=self.gdf_points[~self.gdf_points["inside_polygon"]]["color"],
            aspect=1,
            legend=True,
            markersize=self.markersize,
        )

        # Plot the polygon as a filled area with label
        self.gdf_polygon.plot(
            ax=ax, color="red", aspect=1, alpha=0.3, edgecolor="black", linewidth=2
        )

        # Annotate the polygon with the ROI name at its centroid
        centroid = self.gdf_polygon.geometry.iloc[0].centroid
        ax.annotate(
            text=self.roi_name,
            xy=(centroid.x, centroid.y),
            ha="center",
            va="center",
            fontsize=12,
            color="black",
        )

        # Add colorbar for the gradient
        sm = cm.ScalarMappable(cmap=self.cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, orientation="vertical", pad=0.01, aspect=40)
        cbar.set_label(f"Distance to Polygon {self.roi_name} (micron)")

        # Adjust the plot
        ax.invert_yaxis()
        plt.title(
            f"Region Selected Cells Colored Based on Distance to the Polygon {self.roi_name} (micron)"
        )
        plt.tight_layout()
        plt.xlabel("x (micron)")
        plt.ylabel("y (micron)")
        plt.show()

    def calc_gene_gradient_to_polygon(
        self, band_width: float, num_bands: int, gene_list: list
    ) -> gpd.GeoDataFrame:
        """
        Calculate gene expression gradients relative to the polygon.

        Args:
            band_width (float): Width of each band (in microns).
            num_bands (int): Number of bands to create.
            gene_list (list): List of genes to calculate gradients for.

        Returns:
            gpd.GeoDataFrame: A GeoDataFrame containing the bands and mean gene expression.
        """
        if not hasattr(self, "gdf_polygon"):
            self.calc_distance_to_polygon()

        # Create buffers at multiple distances
        band_list = []
        for i in range(1, num_bands + 1):
            band = self.gdf_polygon.copy()
            band["geometry"] = band["geometry"].buffer(i * band_width)
            band["band"] = i
            band_list.append(band)

        # Merge all bands into a single GeoDataFrame
        self.gdf_bands = gpd.GeoDataFrame(
            pd.concat(band_list, ignore_index=True)
        ).set_crs('EPSG:4326')

        # Spatial join: Assign each cell to the closest buffer
        self.gdf_join_all = self.gdf_points.sjoin(self.gdf_bands, how="left", predicate="within")

        # Compute mean expression per band
        self.gdf_join_all["band"] = (
            self.gdf_join_all[f"distance_to_polygon_{self.roi_name}"] // band_width
        ).astype(int)

        # Compute mean expression for each gene
        for gene in gene_list:
            band_avg_expression = self.gdf_join_all.groupby("band")[gene].mean().reset_index()
            band_avg_expression.columns = ["band", f"{gene}_mean"]
            self.gdf_join_all = self.gdf_join_all.merge(band_avg_expression, on="band")

        return self.gdf_join_all

    def plot_gene_gradient_to_polygon(self, gene_list: list, markersize: float = 1):
        """
        Plot gene expression gradients relative to the polygon.

        Args:
            gene_list (list): List of genes to plot gradients for.
            markersize (float): Size of the points in the plot (default: 1).
        """
        if not hasattr(self, "gdf_join_all"):
            raise ValueError(
                "Gene gradients have not been calculated. Call `calc_gene_gradient_to_polygon` first."
            )

        for gene in gene_list:
            # Plot results
            fig, ax = plt.subplots(figsize=(20, 8))
            self.gdf_polygons.plot(ax=ax, column="roi", aspect=1, legend=True, cmap="tab10", alpha=0.2)

            self.gdf_join_all.plot(
                ax=ax,
                column=f"{gene}_mean",
                aspect=1,
                cmap="coolwarm",
                legend=True,
                alpha=0.7,
                markersize=markersize,
            )

            ax.invert_yaxis()
            plt.title(f"Gradient of {gene} Expression per Cell Along Distance to Polygon")
            plt.xlabel("x (micron)")
            plt.ylabel("y (micron)")
            plt.tight_layout()
            plt.show()

    def save_bands_to_parquet(self, file_path: str):
        """
        Save the generated bands (`gdf_bands`) to a Parquet file.

        Args:
            file_path (str): Path to save the Parquet file.
        """
        if not hasattr(self, "gdf_bands"):
            raise ValueError("Gradient bands have not been generated. Call `calc_gene_gradient_to_polygon` first.")

        # Save to Parquet
        self.gdf_bands.to_parquet(file_path, engine="pyarrow")
        print(f"Gradient bands saved to {file_path}")