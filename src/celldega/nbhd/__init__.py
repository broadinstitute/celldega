"""
Module for performing neighborhood analysis.
"""

from libpysal.cg import alpha_shape as libpysal_alpha_shape
import geopandas as gpd
from shapely import Point, MultiPolygon
from shapely.ops import transform
import numpy as np
import json
from shapely.geometry import Point, Polygon, box, shape
from shapely.affinity import affine_transform
from shapely.affinity import translate
import os
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import shape
import pandas as pd
import matplotlib.cm as cm
import os
from shapely import wkt

def _classify_polygons_contains_check(polygons, points):
    """
    Classifies polygons as "real" or "fake" based on whether they contain any points inside.

    Parameters:
    - polygons: GeoSeries of polygons (GeoPandas)
    - points: Array-like of point coordinates (e.g., numpy array or list of tuples)

    Returns:
    - GeoSeries of curated polygons
    """
    # Convert points to GeoDataFrame
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])

    # Spatial join: Find points inside each polygon
    gdf_poly = gpd.GeoDataFrame(geometry=polygons)
    joined = gpd.sjoin(points_gdf, gdf_poly, predicate="within")

    # Get indices of polygons that contain at least one point
    real_polygons_indices = joined["index_right"].unique()

    # Filter polygons: Keep only those that contain points
    curated_polygons = gdf_poly.iloc[real_polygons_indices]

    return curated_polygons


def _verify_polygons_with_alpha_bulk(polygons, points, alpha, area_tolerance=0.05):
    """
    Verifies polygons by recalculating alpha shapes and ensuring agreement, using bulk spatial queries.

    Parameters:
    - polygons: GeoSeries of polygons (GeoPandas)
    - points: Array-like of point coordinates (e.g., numpy array or list of tuples)
    - alpha: Alpha value for recalculating alpha shapes

    Returns:
    - GeoSeries of curated polygons
    """
    curated_polygons = []
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])

    # Build spatial index for points
    points_sindex = points_gdf.sindex

    for poly in polygons:
        # Bulk query to get candidate points
        possible_matches_index = list(points_sindex.query(poly, predicate="intersects"))

        # Extract points that intersect (including points on the boundary)
        contained_points = points_gdf.iloc[possible_matches_index]

        if len(contained_points) < 4:
            # If too few points, skip recalculation (consider this polygon invalid)
            continue

        # Convert contained points to a NumPy array of coordinates
        coords = np.array([p.coords[0] for p in contained_points.geometry])

        # Recalculate alpha shape for the points
        recalculated_alpha = libpysal_alpha_shape(coords, alpha)

        # check that there is a geometry
        if recalculated_alpha.shape[0] > 0:
            recalculated_area = recalculated_alpha.area.values[0]
            original_area = poly.area

            # Compute fractional difference in area
            area_difference = abs(recalculated_area - original_area) / original_area

            if area_difference <= area_tolerance:
                curated_polygons.append(poly)

    return gpd.GeoSeries(curated_polygons, crs=polygons.crs)



def alpha_shape(points, inv_alpha):

    poly = libpysal_alpha_shape(points, 1/inv_alpha)

    gdf_curated = _classify_polygons_contains_check(poly.values, points)

    validated_poly = _verify_polygons_with_alpha_bulk(
        gdf_curated.geometry.values,
        points,
        1/inv_alpha
    )

    multi_poly = MultiPolygon(validated_poly.values)

    return multi_poly



def _round_coordinates(geometry, precision=2):
    """
    Round the coordinates of a Shapely geometry to the specified precision.

    Parameters:
    - geometry: Shapely geometry object (e.g., Polygon, MultiPolygon).
    - precision: Number of decimal places to round to.

    Returns:
    - Rounded Shapely geometry.
    """
    if geometry is None:
        return None

    def round_coords(x, y, z=None):
        if z is not None:
            return (round(x, precision), round(y, precision), round(z, precision))
        return (round(x, precision), round(y, precision))

    return transform(round_coords, geometry)


def alpha_shape_cell_clusters(meta_cell, cat='cluster', alphas=[100, 150, 200, 250, 300, 350]):

    """
    Compute alpha shapes for each cluster in the cell metadata.

    Parameters:
    - meta_cell: GeoDataFrame of cell metadata.
    - cat: Column name in meta_cell containing the cluster labels.
    - alphas: List of alpha values to compute shapes for.

    Returns:
    - GeoDataFrame of alpha shapes.

    """

    gdf_alpha = gpd.GeoDataFrame()

    for inv_alpha in alphas:

        for inst_cluster in meta_cell[cat].unique():

            inst_clust = meta_cell[meta_cell[cat] == inst_cluster]

            if inst_clust.shape[0]> 3:

                nested_array = inst_clust['geometry'].values

                # Convert to a 2D NumPy array
                flat_array = np.vstack(nested_array)

                inst_shape = alpha_shape(flat_array, inv_alpha)

                inst_name = inst_cluster + '_' + str(inv_alpha)

                gdf_alpha.loc[inst_name, 'name'] = inst_name

                gdf_alpha.loc[inst_name, 'cat'] = inst_cluster

                gdf_alpha.loc[inst_name, 'geometry'] = inst_shape

                gdf_alpha.loc[inst_name, 'inv_alpha'] = int(inv_alpha)

    gdf_alpha["geometry"] = gdf_alpha["geometry"].apply(lambda geom: _round_coordinates(geom, precision=2))

    gdf_alpha['area'] = gdf_alpha.area

    gdf_alpha = gdf_alpha.loc[gdf_alpha.area.sort_values(ascending=False).index.tolist()]

    return gdf_alpha

def alpha_shape_geojson(gdf_alpha, meta_cluster, inst_alpha):

    geojson_alpha = json.loads(gdf_alpha.to_json())

    # Step 2: Edit the properties of each feature
    for feature in geojson_alpha["features"]:

        if feature['geometry'] is not None:

            # Parse the geometry with Shapely for additional calculations
            geometry = shape(feature["geometry"])

            # Add area property
            feature["properties"]["area"] = geometry.area

            id = feature['id']

            color = meta_cluster.loc[id.split('_')[0], 'color']

            # Add a custom color property (example: based on the area)
            feature["properties"]["color"] = color # [255, 0, 0, 100]  # RGBA values
        else:
            # print('is None')
            pass

    geojson_alpha['inst_alpha'] = inst_alpha

    return geojson_alpha

def create_hextile(radius, path_landscape_files=None, img_height=100, img_width=100, pixel_size=0.2125):

    if isinstance(path_landscape_files, str):
        tree = ET.parse(os.path.join(path_landscape_files, "pyramid_images/bound.dzi"))
        root = tree.getroot()
        img_width = int(root[0].attrib["Width"])
        img_height = int(root[0].attrib["Height"])

        transformation_matrix = pd.read_csv(
            f"{path_landscape_files}/micron_to_image_transform.csv", sep=" ", header=None
        ).values[:3, :3]

    else:
        transformation_matrix = np.eye(3)

    hex_height = 2 * radius
    hex_width = np.sqrt(3) * radius
    vert_spacing = 3 / 4 * hex_height  # = 1.5 * r for pointy-topped hexagons
    horiz_spacing = hex_width

    # Calculate number of hexes
    n_cols = int(np.ceil(img_width / horiz_spacing)) + 2
    n_rows = int(np.ceil(img_height / vert_spacing)) + 2

    # Precompute unit hexagon
    angles = np.radians(np.arange(0, 360, 60))
    unit_hex = Polygon([(radius * np.sin(a), radius * np.cos(a)) for a in angles])

    # Generate hexagons by translating the unit hex
    hexagons = []
    for row in range(n_rows):
        for col in range(n_cols):
            x = col * horiz_spacing
            y = row * vert_spacing
            if row % 2 == 1:
                x += horiz_spacing / 2
            hexagons.append(translate(unit_hex, xoff=x, yoff=y))

    # Define image boundary as a shapely box (left, bottom, right, top)
    image_bounds = box(0, 0, img_width, img_height)

    # Clip each hexagon to this box
    clipped_hexes = [
        hex.intersection(image_bounds)
        for hex in hexagons
        if hex.intersects(image_bounds)
    ]

    # Replace original GeoDataFrame
    gdf_hextile = gpd.GeoDataFrame(geometry=clipped_hexes)

    gdf_hextile.rename(columns={"geometry": "geometry_image_space"}, inplace=True)
    gdf_hextile.set_geometry("geometry_image_space", inplace=True)

    transformation_matrix_inv = np.linalg.inv(transformation_matrix)

    a = transformation_matrix_inv[0, 0]
    b = transformation_matrix_inv[0, 1]
    d = transformation_matrix_inv[1, 0]
    e = transformation_matrix_inv[1, 1]
    xoff = transformation_matrix_inv[0, 2]
    yoff = transformation_matrix_inv[1, 2]

    inverse_affine_params = [a, b, d, e, xoff, yoff]

    gdf_hextile['geometry'] = gdf_hextile['geometry_image_space'].apply(
    lambda geom: affine_transform(geom, inverse_affine_params)
    )

    gdf_hextile.set_geometry("geometry", inplace=True)

    radius_in_microns = pixel_size * radius

    if isinstance(path_landscape_files, str):
        gdf_hextile.to_parquet(os.path.join(path_landscape_files, "hextiles.parquet"))
        print(f"Hextiles saved at '{path_landscape_files}' as 'hextiles.parquet'\n")

        fig, ax = plt.subplots(1, 1, figsize=(60, 80))
        gdf_hextile.plot(ax=ax, alpha=1, linewidth=1, facecolor='none', edgecolor='black')
        ax.set_title(f"Hextiles (hexagon radius: {radius_in_microns} microns)", fontsize=50)
        ax.set_xlabel("x (pixels)", fontsize=25)
        ax.set_ylabel("y (pixels)", fontsize=25)
        plt.xticks(fontsize=20)
        plt.yticks(fontsize=20)
        plt.gca().invert_yaxis()
        plt.show()
        plt.close()

    return gdf_hextile

def read_parquet_error_check(path):
    try:
        return gpd.read_parquet(path)
    except ValueError as e:
        if "Missing geo metadata" in str(e):
            return pd.read_parquet(path)
        else:
            raise

def hexatile_specific_unassigned_transcripts(
    gdf_hextile,
    gdf_transcripts=None,
    path_data=None,
    path_landscape_files=None,
    percentage_unassigned_threshold=75
):
    """
    Visualizes the proportion of unassigned transcripts in each hexagonal tile of a spatial transcriptomics dataset.

    This function reads transcript data and transformation parameters from the given directories,
    applies coordinate transformations if necessary, allots transcripts to hexagonal spatial tiles,
    and calculates the percentage of unassigned transcripts per tile.

    Tiles with a percentage of unassigned transcripts lower than the specified threshold are visualized.

    Parameters:
    -----------
    gdf_hextile : geopandas.GeoDataFrame
        A GeoDataFrame containing the hexagonal tiling of the spatial region with associated geometry.

    path_data : str
        Path to the directory containing transcriptomic data, including `transcripts.parquet`.

    percentage_unassigned_threshold : float, optional (default=75)
        The threshold (in percent) for including tiles in the visualization. Tiles with a higher
        percentage of unassigned transcripts are excluded from the plot.

    Returns:
    --------
    None
        This function displays a matplotlib plot showing the percentage of unassigned transcripts
        in each hexagonal tile and saves the intermediate transcript assignment result as a Parquet file.

    """

    from ..pre.boundary_tile import batch_transform_geometries
    from ..pre.__init__ import _to_geometry

    print("Reading transcripts file...")

    ## only Xenium and Custom Tech supported for now

    if gdf_transcripts is None:

        if path_data is None:
            raise ValueError("Either gdf_transcripts or path_data must be provided.")

        trx = read_parquet_error_check(os.path.join(path_data, "transcripts.parquet"))

        if os.path.isfile(os.path.join(path_data, "experiment.xenium")):
            technology = "Xenium"
            transformation_matrix = pd.read_csv(
                os.path.join(path_landscape_files, "micron_to_image_transform.csv"),
                sep=" ",
                header=None,
            ).values[:3, :3]

            x = "x_location"
            y = "y_location"
            cell_id_col = "cell_id"
            segmentation_approach = "default"

            gdf_trx = gpd.GeoDataFrame(trx, geometry=gpd.points_from_xy(trx[x], trx[y]))

            gdf_trx["geometry_image_space"] = batch_transform_geometries(
                gdf_trx["geometry"], transformation_matrix, 1
            )
            gdf_trx["geometry_image_space"] = gdf_trx["geometry_image_space"].apply(
                _to_geometry
            )

            gdf_trx.set_geometry("geometry", inplace=True)

        elif os.path.isfile(os.path.join(path_data, "segmentation_parameters.json")):

            with open(os.path.join(path_data, "segmentation_parameters.json"), "r") as parameters_file:
                parameters = json.load(parameters_file)
                technology = parameters["technology"]

            x = "x"
            y = "y"
            cell_id_col = "cell_index"
            segmentation_approach = parameters["segmentation_approach"]

            if type(trx['geometry'].iloc[0]) == str:
                trx['geometry'] = trx['geometry'].apply(wkt.loads)

            if type(trx['geometry_image_space'].iloc[0]) == str:
                trx['geometry_image_space'] = trx['geometry_image_space'].apply(wkt.loads)

            gdf_trx = gpd.GeoDataFrame(trx, geometry="geometry")
            gdf_trx.set_geometry("geometry", inplace=True)

        else:
            raise ValueError("Unsupported or missing transcriptomics technology files.")

    else:
        gdf_trx = gdf_transcripts.copy()
        gdf_trx["geometry_image_space"] = gdf_trx["geometry"].copy()
        gdf_trx.set_geometry("geometry", inplace=True)

        technology = "PYTEST"
        cell_id_col = "cell_index"
        x = "x"
        y = "y"

    print("Transcripts file read.")
    print("Assignment of transcripts started...")

    gdf_hextile.set_geometry("geometry", inplace=True)

    hextile_assigned_trx = gpd.sjoin(
        gdf_trx, gdf_hextile, how="left", predicate="within"
    )

    hextile_assigned_trx.rename(columns={"index_right": "polygon_index", "geometry_image_space_left": "geometry_image_space"}, inplace=True)
    hextile_assigned_trx.drop(["geometry_image_space_right"], axis=1, inplace=True)

    hextile_assigned_trx["polygon_index"] = (
        hextile_assigned_trx["polygon_index"].astype(str) + "_polygon"
    )

    gdf_hextile_assigned_trx = gpd.GeoDataFrame(
        hextile_assigned_trx, geometry="geometry"
    )

    gdf_hextile_assigned_trx.set_geometry("geometry", inplace=True)

    if technology != "PYTEST":

        gdf_hextile_assigned_trx.to_parquet(
        os.path.join(
            path_landscape_files,
            f"hextile_assigned_trx_{technology}_{segmentation_approach}.parquet",
        )
        )

    print("Assignment of transcripts done and saved.")

    print("Calculating percentage of hextile-specific unassigned transcripts...")

    counts = gdf_hextile_assigned_trx.groupby("polygon_index")[cell_id_col].agg(
        total="size", unassigned=lambda x: (x == "UNASSIGNED").sum()
    )
    percentage_unassigned = (counts["unassigned"] / counts["total"]) * 100

    percentage_unassigned = percentage_unassigned.fillna(0)

    percentage_unassigned = percentage_unassigned[
        percentage_unassigned < percentage_unassigned_threshold
    ]

    percentage_unassigned.index = percentage_unassigned.index.str.replace(
        "_polygon", "", regex=True
    ).astype(int)
    percentage_unassigned_df = pd.DataFrame(index=percentage_unassigned.index)
    percentage_unassigned_df["unassigned_trx_percentage"] = (
        percentage_unassigned.to_list()
    )

    tile_mapping = percentage_unassigned_df.to_dict()
    gdf_hextile["unassigned_trx_percentage"] = gdf_hextile.index.map(
        tile_mapping["unassigned_trx_percentage"]
    ).fillna(0)

    print("Calculation done.")

    return gdf_hextile_assigned_trx, gdf_hextile

def plot_hexatile_specific_unassigned_transcripts(gdf_hextile):

    print("Plotting a tiled view of hextile-specific unassigned transcripts...")

    # Normalize the assigned_percentage values between 0 and 1
    norm = (
        gdf_hextile["unassigned_trx_percentage"]
        - gdf_hextile["unassigned_trx_percentage"].min()
    ) / (
        gdf_hextile["unassigned_trx_percentage"].max()
        - gdf_hextile["unassigned_trx_percentage"].min()
    )

    # Map normalized values to a color in the Reds colormap
    colors = cm.Reds(norm)

    fig, ax = plt.subplots(1, 1, figsize=(40, 40))
    gdf_hextile.plot(ax=ax, alpha=1, linewidth=1, color=colors)

    # Invert y-axis if needed
    plt.gca().invert_yaxis()

    # Add titles and labels
    ax.set_title("Percentage of Unassigned Trx in Each Hextile", fontsize=30)
    ax.set_xlabel("Hextiles", fontsize=25)
    ax.set_ylabel("Percentage of Unassigned Trx (%)", fontsize=25)
    plt.xticks(fontsize=20)
    plt.yticks(fontsize=20)

    # Create colorbar
    sm = plt.cm.ScalarMappable(
        cmap=cm.Reds,
        norm=plt.Normalize(
            vmin=gdf_hextile["unassigned_trx_percentage"].min(),
            vmax=gdf_hextile["unassigned_trx_percentage"].max(),
        ),
    )
    sm._A = []  # required for some versions of matplotlib
    cbar = fig.colorbar(sm, ax=ax, shrink=0.5)
    cbar.set_label("Unassigned Trx Percentage", fontsize=20)
    cbar.ax.tick_params(labelsize=16)

    # Show and close
    plt.show()
    plt.close()