"""
Module for performing neighborhood analysis.
"""

from libpysal.cg import alpha_shape as libpysal_alpha_shape
import geopandas as gpd
from shapely import Point, MultiPolygon
from shapely.ops import transform
import numpy as np
import json
from shapely.geometry import shape
from shapely.geometry import Point, Polygon, box
from shapely.affinity import affine_transform
import os
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import pandas as pd

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

    hex_height = 2 * radius
    hex_width = np.sqrt(3) * radius
    vert_spacing = 3 / 4 * hex_height  # = 1.5 * r for pointy-topped hexagons
    horiz_spacing = hex_width

    # Calculate number of hexes
    n_cols = int(np.ceil(img_width / horiz_spacing)) + 2
    n_rows = int(np.ceil(img_height / vert_spacing)) + 2

    # Generate hexagons
    hexagons = []

    for row in range(n_rows):
        for col in range(n_cols):
            x = col * horiz_spacing
            y = row * vert_spacing
            if row % 2 == 1:
                x += horiz_spacing / 2  # stagger every other row for pointy-top hexes

            # Pointy-topped hexagon (aligned vertically)
            hexagon = Polygon(
                [
                    (
                        x + radius * np.sin(np.radians(angle)),
                        y + radius * np.cos(np.radians(angle)),
                    )
                    for angle in range(0, 360, 60)
                ]
            )

            hexagons.append(hexagon)

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

    transformation_matrix = pd.read_csv(
        f"{path_landscape_files}/micron_to_image_transform.csv", sep=" ", header=None
    ).values[:3, :3]

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

def hextile_area(gdf_hextile, img_width, img_height):

    return round(sum(gdf_hextile.area.tolist())) == round(
        img_width * img_height
    )