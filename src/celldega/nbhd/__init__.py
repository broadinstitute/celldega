"""
Module for performing neighborhood analysis.
"""

from libpysal.cg import alpha_shape as libpysal_alpha_shape
import geopandas as gpd
from shapely import Point, MultiPolygon
from shapely.ops import transform
import numpy as np
import json
from shapely.geometry import shape, Point, Polygon, box
from shapely.affinity import affine_transform
from PIL import Image
import random
import tifffile as tiff
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import xml.etree.ElementTree as ET

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

def create_hexatile(radius, path_landscape_files=None, img_height=100, img_width=100):

    if isinstance(path_landscape_files, str):

        tree = ET.parse(os.path.join(path_landscape_files, "pyramid_images/bound.dzi"))
        root = tree.getroot()
        img_width = int(root[0].attrib['Width'])
        img_height = int(root[0].attrib['Height'])

    hex_width = 2 * radius
    hex_height = np.sqrt(3) * radius
    horiz_spacing = 3/4 * hex_width  # = 1.5 * r
    vert_spacing = hex_height

    # Calculate number of hexes
    n_cols = int(np.ceil(img_width / horiz_spacing)) + 2
    n_rows = int(np.ceil(img_height / vert_spacing)) + 2

    # Generate hexagons
    hexagons = []

    for col in range(n_cols):
        for row in range(n_rows):
            x = col * horiz_spacing
            y = row * vert_spacing
            if col % 2 == 1:
                y += vert_spacing / 2  # stagger every other column

            # Flat-topped hexagon (aligned horizontally)
            hexagon = Polygon([
                (
                    x + radius * np.cos(np.radians(angle)),
                    y + radius * np.sin(np.radians(angle))
                )
                for angle in range(0, 360, 60)
            ])

            hexagons.append(hexagon)

    # Define image boundary as a shapely box (left, bottom, right, top)
    image_bounds = box(0, 0, img_width, img_height)

    # Clip each hexagon to this box
    clipped_hexes = [hex.intersection(image_bounds) for hex in hexagons if hex.intersects(image_bounds)]

    # Replace original GeoDataFrame
    gdf_hexatile = gpd.GeoDataFrame(geometry=clipped_hexes)

    if isinstance(path_landscape_files, str):

        gdf_hexatile.to_parquet(os.path.join(path_landscape_files, "hexatile.parquet"))

    return gdf_hexatile

def generate_random_points_gdf(n_points=10, x_range=(0, 100), y_range=(0, 100)):
    points = [
        Point(random.uniform(*x_range), random.uniform(*y_range))
        for _ in range(n_points)
    ]
    gdf_trx = gpd.GeoDataFrame(geometry=points)
    return gdf_trx

def generate_dummy_image(width=100, height=100):

    data = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(data, 'RGB')
    img_np = np.array(img)
    return img_np

def hexatile_area(gdf_hexatile, tissue_img_shape):

    return round(sum(gdf_hexatile.area.tolist())) == round(tissue_img_shape[0] * tissue_img_shape[1])

def hexatile_trx_assignment(hexatile_assigned_trx):

    more_than_one_matches = 'more_than_one_matches' in hexatile_assigned_trx['polygon_index'].unique()
    unassigned = 'UNASSIGNED' in hexatile_assigned_trx['polygon_index'].unique()

    return more_than_one_matches, unassigned

def unassigned_transcripts_tiled_view(gdf_hexatile, path_data, path_landscape_files):

    from ..pre.merge_segmentations import assigning_transcripts

    transformation_matrix = pd.read_csv(os.path.join(path_landscape_files, "micron_to_image_transform.csv"), sep=" ", header=None).values[:3,:3]

    if os.path.isfile(os.path.join(path_data, 'experiment.xenium')):

        with open(os.path.join(path_landscape_files, 'landscape_parameters.json'), 'r') as parameters_file:
            parameters = json.load(parameters_file)

    else:

        with open(os.path.join(path_data, 'segmentation_parameters.json'), 'r') as parameters_file:
            parameters = json.load(parameters_file)

    ## only Xenium and Custom Tech supported for now

    if parameters['technology'] == 'Xenium':
        x = 'x_location'
        y = 'y_location'
        cell_id_col = 'cell_id'
        segmentation_approach = 'default'

    else:
        x = 'x'
        y = 'y'
        cell_id_col = 'cell_index'
        segmentation_approach = parameters['segmentation_approach']

    print("Reading transcripts file...")

    trx = pd.read_parquet(os.path.join(path_data, "transcripts.parquet"))

    print("Transcripts file read.")

    if parameters['technology'] == 'Xenium' or 'geometry_image_space' not in trx.columns.to_list():

        gdf_trx = gpd.GeoDataFrame(trx, geometry=gpd.points_from_xy(trx[x], trx[y]))
        gdf_trx['geometry_image_space'] = gdf_trx['geometry'].apply(lambda geom: affine_transform(geom, [transformation_matrix[0, 0],
                                                                                                transformation_matrix[0, 1],
                                                                                                transformation_matrix[1, 0],
                                                                                                transformation_matrix[1, 1],
                                                                                                transformation_matrix[0, 2],
                                                                                                transformation_matrix[1, 2]]))

        gdf_trx.set_geometry('geometry_image_space', inplace=True)

    else:

        gdf_trx = gpd.GeoDataFrame(trx, geometry='geometry_image_space')
        gdf_trx.set_geometry('geometry_image_space', inplace=True)

    print("Assignment of transcripts started...")

    hexatile_assigned_trx = assigning_transcripts(gdf_polygons = gdf_hexatile,
                                                  gdf_transcripts = gdf_trx)

    gdf_hexatile_assigned_trx = gpd.GeoDataFrame(hexatile_assigned_trx,
                                                      geometry='geometry_image_space')

    gdf_hexatile_assigned_trx.set_geometry('geometry_image_space', inplace=True)

    gdf_hexatile_assigned_trx.to_parquet(os.path.join(path_landscape_files, f"hexatile_assigned_trx_{parameters['technology']}_{segmentation_approach}.parquet"))

    print("Assignment of transcripts done and saved.")

    print("Calculating percentage of hexatile-specific unassigned transcripts...")

    unassigned_counts = gdf_hexatile_assigned_trx[gdf_hexatile_assigned_trx[cell_id_col] == "UNASSIGNED"].groupby('polygon_index').size()
    total_counts = gdf_hexatile_assigned_trx.groupby('polygon_index').size()

    percentage_unassigned = (unassigned_counts / total_counts) * 100
    percentage_unassigned = percentage_unassigned.fillna(0)

    percentage_unassigned = percentage_unassigned[percentage_unassigned < 75]

    percentage_unassigned.index = percentage_unassigned.index.str.replace('_polygon', '', regex=True).astype(int)
    percentage_unassigned_df = pd.DataFrame(index=percentage_unassigned.index)
    percentage_unassigned_df['unassigned_trx_percentage'] = percentage_unassigned.to_list()

    tile_mapping = percentage_unassigned_df.to_dict()
    gdf_hexatile['unassigned_trx_percentage'] = gdf_hexatile.index.map(tile_mapping['unassigned_trx_percentage']).fillna(0)

    print("Calculation done, plotting a tiled view of hexatile-specific unassigned transcripts...")

    # Normalize the assigned_percentage values between 0 and 1
    norm = (gdf_hexatile['unassigned_trx_percentage'] - gdf_hexatile['unassigned_trx_percentage'].min()) / \
           (gdf_hexatile['unassigned_trx_percentage'].max() - gdf_hexatile['unassigned_trx_percentage'].min())

    # Map normalized values to a color in the Reds colormap
    colors = cm.Reds(norm)

    fig, ax = plt.subplots(1, 1, figsize=(40, 40))
    gdf_hexatile.plot(ax=ax, alpha=1, linewidth=1, color=colors)

    # Invert y-axis if needed
    plt.gca().invert_yaxis()

    # Add titles and labels
    ax.set_title('Percentage of Unassigned Trx in Each Hexagrid Tile', fontsize=30)
    ax.set_xlabel('Hexagrid Tiles', fontsize=25)
    ax.set_ylabel('Percentage of Unassigned Trx (%)', fontsize=25)
    plt.xticks(fontsize=20)
    plt.yticks(fontsize=20)

    # Create colorbar
    sm = plt.cm.ScalarMappable(cmap=cm.Reds, norm=plt.Normalize(
        vmin=gdf_hexatile['unassigned_trx_percentage'].min(),
        vmax=gdf_hexatile['unassigned_trx_percentage'].max()
    ))
    sm._A = []  # required for some versions of matplotlib
    cbar = fig.colorbar(sm, ax=ax, shrink=0.5)
    cbar.set_label('Unassigned Trx Percentage', fontsize=20)
    cbar.ax.tick_params(labelsize=16)

    # Show and close
    plt.show()
    plt.close()

    print("Done.")