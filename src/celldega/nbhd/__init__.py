"""
Module for performing neighborhood analysis.
"""

from libpysal.cg import alpha_shape as libpysal_alpha_shape
import geopandas as gpd
from shapely import Point, MultiPoint, MultiPolygon
from shapely.ops import transform
import numpy as np
import json
from shapely.geometry import shape, Point, Polygon, MultiPoint, LineString

import alphashape
import matplotlib.pyplot as plt
from descartes import PolygonPatch
import pandas as pd
from skimage.exposure import equalize_adapthist
import tifffile as tiff
from libpysal.cg.alpha_shapes import alpha_shape_auto
from shapely.affinity import translate

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


"""
gdf = gpd.read_parquet("../../../Downloads/XENIUM_SKIN/harmonization/harmonized_cell_polygons.parquet")

default_clustering_skin = pd.read_csv("../segmentation_data/original_data/Xenium_Prime_Human_Skin_FFPE_outs/analysis/clustering/gene_expression_graphclust/clusters.csv", index_col=0)
default_clustering_skin

transcripts_gdf = gpd.read_parquet("../../../Downloads/partitioned_transcripts_skin_prostate_IMPORTANT/skin_cellpose_custom_partitioned_transcripts_lenient.parquet")
# skin, clusters where xenium default segmentation was good
# 20, 26, 27, 28
selected_clusters = default_clustering_skin[default_clustering_skin['Cluster'].isin([5])]

#selected_clusters = default_clustering[~default_clustering['Cluster'].isin([2, 4, 10, 12, 13, 14, 17, 20, 21, 22, 23])]
selected_clusters

filtered_5 = transcripts_gdf[transcripts_gdf['cell_id'].isin(selected_clusters.index.to_list())]

cells_pros = gpd.read_parquet("../../../Downloads/submissions_19e43573-a156-44e4-837b-62d2131f2974_MAIN_WORKFLOW_e6046a8c-7228-405e-aad9-d393b2b0d5a7_call-instanseg_cell_polygons.parquet")

cells_pros['centroid'] = cells_pros['geometry'].centroid

tuple_list = list(zip(cells_pros['centroid'].x, cells_pros['centroid'].y))
points_full = np.array(tuple_list)

#concave_hull = alpha_shape_auto(points, step=1)

fig, ax = plt.subplots(figsize=(40, 40))
ax.scatter(points_full[:, 0], points_full[:, 1], color='blue', s=100)  # Plot the points

#x, y = concave_hull.exterior.xy
#ax.plot(x, y, color='red', label='Alpha Shape', linewidth=20)

#ax.legend(fontsize=30)

plt.show()

alpha_value = 0.0065
alpha_shape = alphashape.alphashape(points_full, alpha_value)
alpha_shape

largest_polygon = max(alpha_shape.geoms, key=lambda p: p.area)

# Sort the polygons by area in descending order and select the second one
#sorted_polygons = sorted(alpha_shape.geoms, key=lambda p: p.area, reverse=True)
#second_largest_polygon = sorted_polygons[1]

fig, ax = plt.subplots(figsize=(40, 40))
ax.scatter(points_full[:, 0], points_full[:, 1], color='blue', label='Vertices', s=50)

x, y = largest_polygon.exterior.xy
ax.plot(x, y, color='red', label='Alpha Shape', linewidth=20)

ax.legend(fontsize=30)
plt.show()

gdf_alphashape = gpd.GeoDataFrame(geometry=[largest_polygon])
gdf_alphashape.to_parquet('../../../Downloads/alphashape_entire_prostate.parquet', index=False)

import geopandas as gpd

# Step 1: Extract the boundaries of the two alphashapes
boundary1 = largest_polygon_dermis.unary_union.boundary
boundary2 = alpha_shape.unary_union.boundary

# Step 2: Apply a small buffer to both boundaries to create a "nearby" region where they might face each other
#buffer_distance = 1  # Adjust the distance based on how close the polygons should be
#buffered_boundary1 = boundary1.buffer(buffer_distance)
#buffered_boundary2 = boundary2.buffer(buffer_distance)

# Step 3: Find the overlap of the buffered boundaries
#buffered_intersection = buffered_boundary1.intersection(buffered_boundary2)

buffered_intersection = boundary1.intersection(boundary2)

# Step 4: Find polygons in gdf that are within the buffered intersection region
intersecting_polygons = gdf[gdf['geometry'].intersects(buffered_intersection)]

# Step 5: Plot or work with the filtered polygons
intersecting_polygons.plot()

fig, ax = plt.subplots(1, 1, figsize=(60, 80))
#gdf.plot(ax=ax, alpha=1, linewidth=2, edgecolor='black', color=gdf['color'])
largest_polygon_dermis.plot(ax=ax, alpha=1, linewidth=10, facecolor='none', edgecolor='blue')
alpha_shape.plot(ax=ax, alpha=0.7, linewidth=10, facecolor='none', edgecolor='red')
intersecting_polygons.plot(ax=ax, alpha=0.7, linewidth=2, edgecolor='black', color='yellow')
plt.show()

all_cells = intersecting_polygons.index.tolist()
intersecting_pairs = intersecting_polygons.sindex.query(intersecting_polygons.geometry, predicate='intersects')

df_intersect = pd.DataFrame(intersecting_pairs).T
df_intersect.columns = ['id_1', 'id_2']

df_intersect = df_intersect[df_intersect['id_1'] != df_intersect['id_2']]

# Add a new column that contains a sorted tuple of the id columns
df_intersect['sorted_id_pair'] = df_intersect.apply(lambda row: tuple(sorted([row['id_1'], row['id_2']])), axis=1)

# Drop duplicate rows based on the sorted_id_pair column
df_intersect = df_intersect.drop_duplicates(subset='sorted_id_pair')
# Optional: Drop the sorted_id_pair column if it is no longer needed
df_intersect = df_intersect.drop(columns=['sorted_id_pair'])

df_intersect.reset_index(inplace=True)
df_intersect.drop(['index'], inplace=True, axis=1)

list_conflict_ids = sorted(list(set(df_intersect['id_1'].unique().tolist() + df_intersect['id_2'].unique().tolist())))

list_conflict_ids = sorted(list(set(df_intersect['id_1'].unique().tolist() + df_intersect['id_2'].unique().tolist())))

list_conflict_cells = [all_cells[x] for x in list_conflict_ids]

list_no_conflict_cells = sorted(list(set(all_cells).difference(set(list_conflict_cells))))

print("df_intersect before ioa calculation", df_intersect)

for inst_row in df_intersect.index.tolist():

    # look up pair of intersecting polygons
    id_1 = df_intersect.loc[inst_row, 'id_1']
    id_2 = df_intersect.loc[inst_row, 'id_2']

    cell_1 = all_cells[id_1]
    cell_2 = all_cells[id_2]

    poly_1 = intersecting_polygons.loc[cell_1, 'geometry']

    poly_2 = intersecting_polygons.loc[cell_2, 'geometry']

    if isinstance(poly_1, pd.Series):
        poly_1 = poly_1.values[0]
    if isinstance(poly_2, pd.Series):
        poly_2 = poly_2.values[0]

    poly_1 = make_valid(poly_1).buffer(0)
    poly_2 = make_valid(poly_2).buffer(0)

    poly_1 = poly_1.simplify(tolerance)
    poly_2 = poly_2.simplify(tolerance)

    area_1 = poly_1.area
    area_2 = poly_2.area

    area_intersection = poly_1.intersection(poly_2).area
    area_union = poly_1.union(poly_2).area

    if area_union <= 0:
        iou = 0
    else:
        iou = area_intersection/area_union

    df_intersect.loc[inst_row, 'iou'] = iou
    df_intersect.loc[inst_row, 'area_1'] = area_1
    df_intersect.loc[inst_row, 'area_2'] = area_2

    if area_1 > 0 and area_2 > 0:
        ioa_1 = area_intersection/area_1
        ioa_2 = area_intersection/area_2

        if area_1 <= area_2:
            ioa_small = ioa_1
        else:
            ioa_small = ioa_2

        df_intersect.loc[inst_row, 'ioa_1'] = ioa_1
        df_intersect.loc[inst_row, 'ioa_2'] = ioa_2
        df_intersect.loc[inst_row, 'ioa_small'] = ioa_small

    else:
        if area_1 <= 0:
            ioa_1 = 0
            df_intersect.loc[inst_row, 'ioa_1'] = 0

        else:
            ioa_1 = area_intersection/area_1
            df_intersect.loc[inst_row, 'ioa_1'] = ioa_1

        if area_2 <= 0:
            ioa_2 = 0
            df_intersect.loc[inst_row, 'ioa_2'] = 0

        else:
            ioa_2 = area_intersection/area_2
            df_intersect.loc[inst_row, 'ioa_2'] = ioa_2

        if area_1 <= area_2:
            ioa_small = ioa_1
            df_intersect.loc[inst_row, 'ioa_small'] = ioa_small

        else:
            ioa_small = ioa_2
            df_intersect.loc[inst_row, 'ioa_small'] = ioa_small

print("df_intersect after ioa calculation", df_intersect)
# rank by easiest to resolve
df_intersect.sort_values(by='ioa_small', ascending=False, inplace=True)

# initialize gdf_nc
gdf_nc = intersecting_polygons.loc[list_no_conflict_cells]
gdf_nc.reset_index(inplace=True)
#gdf_nc.drop([0], axis=1, inplace=True)

fig, ax = plt.subplots(figsize=(60, 80))
gdf_nc['geometry'].plot(ax=ax, linewidth=5, alpha=1, facecolor='none', edgecolor='red')
plt.show()

gdf_ = intersecting_polygons.reset_index()
ioa_small_thresh = 0.5
warnings.simplefilter(action='ignore', category=FutureWarning)

def add_or_merge_into_gdf_nc(gdf_nc, poly, ioa_thresh):


    This function allows us to add a new polygon to gdf_nc
    gdf_nc contains the no conflict polygons. We define conflict to mean
    a non-trivial intersection between polygons with a ioa_small above
    our threshold.

    This function will check for conflicts before adding poly and
    merge if necessary


    possible_intersections = gdf_nc.sindex.query(poly, predicate='intersects')

    if len(possible_intersections) == 0:

        new_data = {
            'geometry': poly
        }

        new_row = gpd.GeoDataFrame([new_data])
        gdf_nc = gpd.GeoDataFrame(pd.concat([gdf_nc, new_row], ignore_index=True))

    else:

        max_ioa_merged = 0
        max_ioa_merged_index = 0

        if not poly.is_valid:
            poly = make_valid(poly)

        for index in possible_intersections:

            poly_intersect = gdf_nc.loc[index, 'geometry']

            if not poly_intersect.is_valid:
                poly_intersect = make_valid(poly_intersect).buffer(0)
                poly_intersect = poly_intersect.simplify(tolerance)

            if min(poly.area, poly_intersect.area) > 0:
                ioa_merged = poly_intersect.intersection(poly).area / min(poly.area, poly_intersect.area)

            else:
                ioa_merged = 0

            if ioa_merged >= max_ioa_merged:
                max_ioa_merged = ioa_merged
                max_ioa_merged_index = index

        if max_ioa_merged >= ioa_small_thresh:

            poly_intersect = gdf_nc.loc[max_ioa_merged_index, 'geometry']

            poly_intersect = make_valid(poly_intersect).buffer(0)
            poly_intersect = poly_intersect.simplify(tolerance)

            poly_merged = poly_intersect.union(poly)

            gdf_nc = gdf_nc.drop(max_ioa_merged_index)

            new_data = {'geometry': poly_merged}
            new_row = gpd.GeoDataFrame([new_data])
            gdf_nc = gpd.GeoDataFrame(pd.concat([gdf_nc, new_row], ignore_index=True))

        else:

            new_data = {'geometry': poly}
            new_row = gpd.GeoDataFrame([new_data])
            gdf_nc = gpd.GeoDataFrame(pd.concat([gdf_nc, new_row], ignore_index=True))

    return gdf_nc

for inst_row in df_intersect.index.tolist():

    inst_ioa_small = df_intersect.loc[inst_row, 'ioa_small']

    id_1 = df_intersect.loc[inst_row, 'id_1']
    id_2 = df_intersect.loc[inst_row, 'id_2']

    poly_1 = gdf_.loc[id_1, 'geometry']
    poly_2 = gdf_.loc[id_2, 'geometry']

    poly_1 = make_valid(poly_1).buffer(0)
    poly_1 = poly_1.simplify(tolerance)

    poly_2 = make_valid(poly_2).buffer(0)
    poly_2 = poly_2.simplify(tolerance)

    if inst_ioa_small < ioa_small_thresh :

        gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_1, ioa_thresh=ioa_small_thresh)
        gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_2, ioa_thresh=ioa_small_thresh)

    else:
        if gdf_.loc[id_1, 'cell_id'] in selected_clusters.index.to_list():
            gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_1, ioa_thresh=ioa_small_thresh)

        if gdf_.loc[id_2, 'cell_id'] in selected_clusters.index.to_list():
            gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_2, ioa_thresh=ioa_small_thresh)

        if gdf_.loc[id_1, 'cell_id'] in default_clustering_skin.index.to_list():
            gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_2, ioa_thresh=ioa_small_thresh)

        if gdf_.loc[id_2, 'cell_id'] in default_clustering_skin.index.to_list():
            gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_1, ioa_thresh=ioa_small_thresh)

        else:
            print(id_1, id_2)

        #poly_merged = poly_1.union(poly_2)
        #gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, poly=poly_merged, ioa_thresh=ioa_small_thresh)

def find_valid_buffer(geom, initial_step=0.01, max_iterations=100):

    step = initial_step

    buffer_direction = 1

    for i in range(max_iterations):
        buffered_geom = geom.buffer(step * buffer_direction).buffer(step * (-buffer_direction)).simplify(tolerance=1, preserve_topology=True)

        if buffered_geom.is_valid and buffered_geom.geom_type == 'Polygon':
            return buffered_geom

        step += initial_step

    if geom.geom_type == 'MultiPolygon':
        largest_polygon = max(geom.geoms, key=lambda p: p.area)
        return largest_polygon

    return geom

for index, value in enumerate(gdf_nc.geometry.geom_type=='MultiPolygon'):
    if value == True:
        gdf_nc.iloc[index].geometry = find_valid_buffer(geom=gdf_nc.iloc[index].geometry)

gdf_nc.index = [str(x) for x in gdf_nc.index.tolist()]
gdf_nc.columns = [str(col) for col in gdf_nc.columns]

gdf_without_intersecting_polygons = gdf[~gdf['geometry'].intersects(buffered_intersection)]

gdf_final = gpd.GeoDataFrame(pd.concat([gdf_without_intersecting_polygons, gdf_nc], ignore_index=True))

CELL_POLYGONS_GDF, partitioned_transcripts_gdf = stp_processing(TRANSCRIPTS_FILE="../../../Downloads/XENIUM_SKIN/full_xen_skin_custom_boundary_merging_fixed_LENIENT_cp_parameters/submissions_80160a61-1de1-4311-b95e-879aa106ac0a_MAIN_WORKFLOW_a441721f-6d4b-4a80-bc9e-1a4e8544f7d5_call-create_subset_subset_coordinates.csv", CELL_POLYGONS_GDF=gdf_final, TECHNOLOGY="XENIUM", TRANSCRIPT_CHUNK_SIZE=100000)

# Check which points are within the alphashape
within_alpha_shape_FULL = partitioned_transcripts_gdf.geometry.within(alpha_shape_full_region.unary_union)

# Extract the points that are within the alphashape
points_within_FULL = partitioned_transcripts_gdf.geometry[within_alpha_shape_FULL]
partitioned_transcripts_gdf['within_alpha_shape_FULL'] = within_alpha_shape_FULL
within_alphashape_FULL_transcripts = partitioned_transcripts_gdf[partitioned_transcripts_gdf['within_alpha_shape_FULL'] == True]

within_alphashape_FULL_transcripts_assigned = within_alphashape_FULL_transcripts[within_alphashape_FULL_transcripts['assigned'] == 'red']
(len(within_alphashape_FULL_transcripts_assigned)/len(within_alphashape_FULL_transcripts)) * 100

original_gdf = gpd.read_parquet("../../../Downloads/XENIUM_SKIN/full_xen_skin_custom_boundary_merging_fixed_LENIENT_cp_parameters/skin_boundary_fixed_code_partitioned_transcripts_LENIENT.parquet")

original_gdf_within_alpha_shape_FULL = original_gdf.geometry.within(alpha_shape_full_region.unary_union)

original_gdf['harmonize_within_alpha_shape_FULL'] = original_gdf_within_alpha_shape_FULL
outside_alphashape_FULL_transcripts = original_gdf[original_gdf['harmonize_within_alpha_shape_FULL'] == False]

outside_alphashape_FULL_transcripts_assigned = outside_alphashape_FULL_transcripts[outside_alphashape_FULL_transcripts['assigned'] == 'red']
#(len(within_alphashape_FULL_transcripts_assigned)/len(within_alphashape_FULL_transcripts)) * 100

all_transcripts_harmonized = gpd.GeoDataFrame(pd.concat([outside_alphashape_FULL_transcripts, within_alphashape_FULL_transcripts], ignore_index=True))

all_transcripts_harmonized_assigned = all_transcripts_harmonized[all_transcripts_harmonized['assigned'] == 'red']
(len(all_transcripts_harmonized_assigned)/len(all_transcripts_harmonized)) * 100


def plot_segmentation(CELL_POLYGONS_GDF, partitioned_transcripts_gdf, TECHNOLOGY, largest_polygon_dermis, alpha_shape, intersecting_polygons):

    fig, ax = plt.subplots(figsize=(40, 40))
    ax.set_facecolor('grey')

    ax.scatter(x=partitioned_transcripts_gdf['x_location'], y=partitioned_transcripts_gdf['y_location'], alpha=1, s=0.02, color=partitioned_transcripts_gdf['assigned'])
    CELL_POLYGONS_GDF.plot(ax=ax, alpha=1, linewidth=2, facecolor='none', edgecolor='black')
    largest_polygon_dermis.plot(ax=ax, alpha=1, linewidth=10, facecolor='none', color='green')
    alpha_shape.plot(ax=ax, alpha=1, linewidth=10, facecolor='none', color='yellow')

    ax.set_title(f'{TECHNOLOGY} Segmentation', size=35)
    plt.show()

plot_segmentation(CELL_POLYGONS_GDF=gdf_final, partitioned_transcripts_gdf=within_alphashape_FULL_transcripts, TECHNOLOGY='STP', largest_polygon_dermis=largest_polygon_dermis, alpha_shape=alpha_shape, intersecting_polygons=intersecting_polygons)


"""