import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import numpy as np
import alphashape
import json
from shapely.validation import make_valid
from ..nbhd import *

def find_containing_polygon(transcript, CELL_POLYGONS_sindex, CELL_POLYGONS_GDF):
    point = transcript.geometry
    possible_matches_index = list(CELL_POLYGONS_sindex.query(point, predicate='intersects'))

    if len(possible_matches_index) == 0:
        return 'UNASSIGNED'

    return CELL_POLYGONS_GDF.iloc[possible_matches_index[0]].name

def transcript_process_chunk(transcript_chunk, CELL_POLYGONS_sindex, CELL_POLYGONS_GDF):
    if not transcript_chunk.empty:
        transcript_chunk['new_cell_index'] = transcript_chunk.apply(find_containing_polygon, axis=1, CELL_POLYGONS_sindex=CELL_POLYGONS_sindex, CELL_POLYGONS_GDF=CELL_POLYGONS_GDF)
    else:
        transcript_chunk['new_cell_index'] = 'UNASSIGNED'

    return transcript_chunk

def partitioning_transcripts(CELL_POLYGONS_GDF, chunked_transcripts_gdf):

    CELL_POLYGONS_sindex = CELL_POLYGONS_GDF.sindex

    partitioned_transcripts = gpd.GeoDataFrame()

    chunk_result = transcript_process_chunk(transcript_chunk = chunked_transcripts_gdf,
                                CELL_POLYGONS_sindex = CELL_POLYGONS_sindex,
                                CELL_POLYGONS_GDF = CELL_POLYGONS_GDF)

    partitioned_transcripts = pd.concat([partitioned_transcripts, chunk_result], ignore_index=True)

    partitioned_transcripts = gpd.GeoDataFrame(partitioned_transcripts, geometry='geometry')

    partitioned_transcripts.drop(['geometry'], axis=1, inplace=True)

    return partitioned_transcripts

def get_largest_polygon(geometry):
    if geometry.geom_type == 'MultiPolygon':
        largest_polygon = max(geometry.geoms, key=lambda p: p.area)
        return largest_polygon
    else:
        return geometry

def add_or_merge_into_gdf_nc(gdf_nc, default_clustering, clusters_within_cutout_region, poly, ioa_thresh, ID, tech):

    """
    This function allows us to add a new polygon to gdf_nc
    gdf_nc contains the no conflict polygons. We define conflict to mean
    a non-trivial intersection between polygons with a ioa_small above
    our threshold.

    This function will check for conflicts before adding poly and
    merge if necessary
    """

    possible_intersections = gdf_nc.sindex.query(poly, predicate='intersects')

    if len(possible_intersections) == 0:

        new_data = {
            'geometry': poly
        }

        new_row = gpd.GeoDataFrame([new_data])
        new_row['cell_id'] = ID
        new_row['technology'] = tech
        new_row['centroid'] = poly.centroid
        gdf_nc = gpd.GeoDataFrame(pd.concat([gdf_nc, new_row], ignore_index=True))

    else:

        max_ioa_merged = 0
        max_ioa_merged_index = 0

        if not poly.is_valid:
            poly = make_valid(poly)

        for index in possible_intersections:

            poly_intersect = gdf_nc.iloc[index]['geometry']

            if not poly_intersect.is_valid:
                poly_intersect = make_valid(poly_intersect).buffer(0)
                poly_intersect = poly_intersect.simplify(0.001)

            if min(poly.area, poly_intersect.area) > 0:
                ioa_merged = poly_intersect.intersection(poly).area / min(poly.area, poly_intersect.area)
            else:
                ioa_merged = 0

            if ioa_merged >= max_ioa_merged:
                max_ioa_merged = ioa_merged
                max_ioa_merged_index = index

        if max_ioa_merged >= ioa_thresh:

            poly_intersect = gdf_nc.loc[max_ioa_merged_index, 'geometry']

            poly_intersect = make_valid(poly_intersect).buffer(0)
            poly_intersect = poly_intersect.simplify(0.001)

            if gdf_nc.loc[max_ioa_merged_index, 'cell_id'] in default_clustering[~default_clustering['Cluster'].isin(clusters_within_cutout_region)].index.to_list():
                return gdf_nc

            else:
                gdf_nc = gdf_nc.drop(max_ioa_merged_index)

        else:

            new_data = {'geometry': poly}
            new_row = gpd.GeoDataFrame([new_data])
            new_row['cell_id'] = ID
            new_row['technology'] = tech
            new_row['centroid'] = poly.centroid
            gdf_nc = gpd.GeoDataFrame(pd.concat([gdf_nc, new_row], ignore_index=True))

    return gdf_nc

def merge_segmentation(default_data_path, custom_data_path, output_path, clusters_within_cutout_region, inv_alpha_value_for_cutout_region, buffer_for_cutout_region_alpha_shape, inv_alpha_value_for_full_tissue, buffer_for_full_tisse_alpha_shape, ioa_small_thresh = 0.5):

    default_clustering = pd.read_csv(f"{default_data_path}/analysis/clustering/gene_expression_graphclust/clusters.csv", index_col=0)

    default_cell_boundaries = pd.read_parquet(f"{default_data_path}/cell_boundaries.parquet")
    grouped = default_cell_boundaries.groupby("cell_id")[["vertex_x", "vertex_y"]].agg(
        lambda x: x.tolist()
    )
    grouped["geometry"] = grouped.apply(
        lambda row: Polygon(zip(row["vertex_x"], row["vertex_y"])), axis=1
    )
    cells_default = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]

    cells_custom = gpd.read_parquet(f"{custom_data_path}/cell_polygons.parquet")

    print("Completed reading cell boundary and default clustering files.")

    with open(f"{default_data_path}/segmentation_parameters.json", 'r') as file_default:
        default_segmentation_parameters = json.load(file_default)

    with open(f"{custom_data_path}/segmentation_parameters.json", 'r') as file_custom:
        custom_segmentation_parameters = json.load(file_custom)

    default_technology_name = default_segmentation_parameters['technology']
    custom_technology_name = custom_segmentation_parameters['technology']

    cells_default_within_clusters = default_clustering[default_clustering['Cluster'].isin(clusters_within_cutout_region)]
    filtered_cells_default_within_cutout_region = cells_default[cells_default.index.isin(cells_default_within_clusters.index.to_list())]

    filtered_cells_default_within_cutout_region['centroid'] = filtered_cells_default_within_cutout_region['geometry'].centroid
    filtered_cell_centroids_default_within_cutout_region = np.array(list(zip(filtered_cells_default_within_cutout_region['centroid'].x,
                                                                             filtered_cells_default_within_cutout_region['centroid'].y)))

    cutout_region_alpha_shape = alpha_shape(filtered_cell_centroids_default_within_cutout_region, inv_alpha_value_for_cutout_region)

    if len(cutout_region_alpha_shape.geoms) == 1:
        largest_cutout_region_alpha_shape = cutout_region_alpha_shape

    else:
        largest_cutout_region_alpha_shape_temp = max(cutout_region_alpha_shape.geoms, key=lambda p: p.area)
        largest_cutout_region_alpha_shape = largest_cutout_region_alpha_shape_temp.buffer(buffer_for_cutout_region_alpha_shape)

    cells_custom_within_cutout_region = cells_custom[cells_custom.geometry.intersects(largest_cutout_region_alpha_shape) == True]

    cells_custom_within_cutout_region.drop(['shard','job','color','geometry_image_space','area','centroid'], axis=1, inplace=True)
    cells_custom_within_cutout_region.index.name = 'cell_id'
    cells_custom_within_cutout_region['technology'] = [custom_technology_name for i in range(len(cells_custom_within_cutout_region))]

    cells_default_within_cutout_region = cells_default[cells_default.geometry.intersects(largest_cutout_region_alpha_shape) == True]

    indices_cells_default_within_cutout_region = cells_default_within_cutout_region.index
    cells_default = cells_default.drop(indices_cells_default_within_cutout_region)
    cells_default['technology'] = [default_technology_name for i in range(len(cells_default))]

    cells_before_harmonization = pd.concat([cells_default, cells_custom_within_cutout_region], ignore_index=False)

    cells_before_harmonization['centroid'] = cells_before_harmonization['geometry'].centroid
    cell_centroids_before_harmonization = np.array(list(zip(cells_before_harmonization['centroid'].x,
                                                            cells_before_harmonization['centroid'].y)))

    full_tissue_alpha_shape = alpha_shape(cell_centroids_before_harmonization, inv_alpha_value_for_full_tissue)

    if len(full_tissue_alpha_shape.geoms) == 1:
        largest_full_tissue_alpha_shape = full_tissue_alpha_shape

    else:
        largest_full_tissue_alpha_shape_temp = max(full_tissue_alpha_shape.geoms, key=lambda p: p.area)
        largest_full_tissue_alpha_shape = largest_full_tissue_alpha_shape_temp.buffer(buffer_for_full_tisse_alpha_shape)

    print("Default segmented and custom segmented cells within cutout region extracted.")

    gpd.GeoDataFrame(geometry=[largest_full_tissue_alpha_shape]).to_parquet(f'{output_path}/largest_full_tissue_alpha_shape.parquet', index=False)
    gpd.GeoDataFrame(geometry=[largest_cutout_region_alpha_shape]).to_parquet(f'{output_path}/largest_cutout_region_alpha_shape.parquet', index=False)

    print("Alphashapes saved.")

    intersecting_boundary = largest_cutout_region_alpha_shape.boundary.buffer(50)

    intersecting_cells_before_harmonization = cells_before_harmonization[cells_before_harmonization['geometry'].intersects(intersecting_boundary)]

    indices_intersecting_cells_before_harmonization = intersecting_cells_before_harmonization.index.tolist()
    intersecting_cell_pairs_before_harmonization = intersecting_cells_before_harmonization.sindex.query(intersecting_cells_before_harmonization.geometry, predicate='intersects')

    intersecting_cell_pairs_before_harmonization_DF = pd.DataFrame(intersecting_cell_pairs_before_harmonization).T
    intersecting_cell_pairs_before_harmonization_DF.columns = ['cell_id_1', 'cell_id_2']

    intersecting_cell_pairs_before_harmonization_DF['cell_id_1'] = intersecting_cells_before_harmonization.index[intersecting_cell_pairs_before_harmonization_DF['cell_id_1']].values
    intersecting_cell_pairs_before_harmonization_DF['cell_id_2'] = intersecting_cells_before_harmonization.index[intersecting_cell_pairs_before_harmonization_DF['cell_id_2']].values
    intersecting_cell_pairs_before_harmonization_DF['cell_id_1_technology'] = intersecting_cells_before_harmonization.technology[intersecting_cell_pairs_before_harmonization_DF['cell_id_1']].values
    intersecting_cell_pairs_before_harmonization_DF['cell_id_2_technology'] = intersecting_cells_before_harmonization.technology[intersecting_cell_pairs_before_harmonization_DF['cell_id_2']].values

    intersecting_cell_pairs_before_harmonization_DF = intersecting_cell_pairs_before_harmonization_DF[intersecting_cell_pairs_before_harmonization_DF['cell_id_1'] != intersecting_cell_pairs_before_harmonization_DF['cell_id_2']]

    intersecting_cell_pairs_before_harmonization_DF['sorted_cell_id_pair'] = intersecting_cell_pairs_before_harmonization_DF.apply(lambda row: tuple(sorted([row['cell_id_1'], row['cell_id_2']])), axis=1)

    intersecting_cell_pairs_before_harmonization_DF = intersecting_cell_pairs_before_harmonization_DF.drop_duplicates(subset='sorted_cell_id_pair')

    intersecting_cell_pairs_before_harmonization_DF = intersecting_cell_pairs_before_harmonization_DF.drop(columns=['sorted_cell_id_pair'])

    intersecting_cell_pairs_before_harmonization_DF = intersecting_cell_pairs_before_harmonization_DF[intersecting_cell_pairs_before_harmonization_DF['cell_id_1_technology'] != intersecting_cell_pairs_before_harmonization_DF['cell_id_2_technology']]

    intersecting_cell_pairs_before_harmonization_DF.reset_index(inplace=True)
    intersecting_cell_pairs_before_harmonization_DF.drop(['index'], inplace=True, axis=1)

    list_conflict_cell_ids = sorted(list(set(intersecting_cell_pairs_before_harmonization_DF['cell_id_1'].unique().tolist() + intersecting_cell_pairs_before_harmonization_DF['cell_id_2'].unique().tolist())))
    list_no_conflict_cell_ids = sorted(list(set(indices_intersecting_cells_before_harmonization).difference(set(list_conflict_cell_ids))))

    for inst_row in intersecting_cell_pairs_before_harmonization_DF.index.tolist():

        # look up pair of intersecting polygons
        id_1 = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'cell_id_1']
        id_2 = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'cell_id_2']

        poly_1 = intersecting_cells_before_harmonization.loc[id_1, 'geometry']

        poly_2 = intersecting_cells_before_harmonization.loc[id_2, 'geometry']

        if isinstance(poly_1, pd.Series):
            poly_1 = poly_1.values[0]
        if isinstance(poly_2, pd.Series):
            poly_2 = poly_2.values[0]

        poly_1 = make_valid(poly_1).buffer(0)
        poly_2 = make_valid(poly_2).buffer(0)

        poly_1 = poly_1.simplify(0.001)
        poly_2 = poly_2.simplify(0.001)

        area_1 = poly_1.area
        area_2 = poly_2.area

        area_intersection = poly_1.intersection(poly_2).area
        area_union = poly_1.union(poly_2).area

        if area_union <= 0:
            iou = 0
        else:
            iou = area_intersection/area_union

        intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'iou'] = iou
        intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'area_1'] = area_1
        intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'area_2'] = area_2

        if area_1 > 0 and area_2 > 0:
            ioa_1 = area_intersection/area_1
            ioa_2 = area_intersection/area_2

            if area_1 <= area_2:
                ioa_small = ioa_1
            else:
                ioa_small = ioa_2

            intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_1'] = ioa_1
            intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_2'] = ioa_2
            intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_small'] = ioa_small

        else:
            if area_1 <= 0:
                ioa_1 = 0
                intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_1'] = 0

            else:
                ioa_1 = area_intersection/area_1
                intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_1'] = ioa_1

            if area_2 <= 0:
                ioa_2 = 0
                intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_2'] = 0

            else:
                ioa_2 = area_intersection/area_2
                intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_2'] = ioa_2

            if area_1 <= area_2:
                ioa_small = ioa_1
                intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_small'] = ioa_small

            else:
                ioa_small = ioa_2
                intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_small'] = ioa_small

    intersecting_cell_pairs_before_harmonization_DF.sort_values(by='ioa_small', ascending=False, inplace=True)

    gdf_nc = intersecting_cells_before_harmonization.loc[list_no_conflict_cell_ids]
    gdf_nc.reset_index(inplace=True)

    gdf_ = intersecting_cells_before_harmonization.copy()

    print("Resolving boundary region cell conflicts...")

    for inst_row in intersecting_cell_pairs_before_harmonization_DF.index.tolist():

        inst_ioa_small = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'ioa_small']

        id_1 = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'cell_id_1']
        id_2 = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'cell_id_2']

        tech_1 = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'cell_id_1_technology']
        tech_2 = intersecting_cell_pairs_before_harmonization_DF.loc[inst_row, 'cell_id_2_technology']

        poly_1 = gdf_.loc[id_1, 'geometry']
        poly_2 = gdf_.loc[id_2, 'geometry']

        poly_1 = make_valid(poly_1).buffer(0)
        poly_1 = poly_1.simplify(0.001)

        poly_2 = make_valid(poly_2).buffer(0)
        poly_2 = poly_2.simplify(0.001)

        if inst_ioa_small < ioa_small_thresh :

            gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, default_clustering=default_clustering, clusters_within_cutout_region=clusters_within_cutout_region, poly=poly_1, ioa_thresh=ioa_small_thresh, ID=id_1, tech=tech_1)
            gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, default_clustering=default_clustering, clusters_within_cutout_region=clusters_within_cutout_region, poly=poly_2, ioa_thresh=ioa_small_thresh, ID=id_2, tech=tech_2)

        else:

            if id_1 in default_clustering[~default_clustering['Cluster'].isin(clusters_within_cutout_region)].index.to_list():
                gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, default_clustering=default_clustering, clusters_within_cutout_region=clusters_within_cutout_region, poly=poly_1, ioa_thresh=ioa_small_thresh, ID=id_1, tech=tech_1)
            elif id_2 in default_clustering[~default_clustering['Cluster'].isin(clusters_within_cutout_region)].index.to_list():
                gdf_nc = add_or_merge_into_gdf_nc(gdf_nc=gdf_nc, default_clustering=default_clustering, clusters_within_cutout_region=clusters_within_cutout_region, poly=poly_2, ioa_thresh=ioa_small_thresh, ID=id_2, tech=tech_2)
            else:
                continue

    gdf_nc['geometry'] = gdf_nc['geometry'].apply(get_largest_polygon)
    gdf_nc.set_index('cell_id', inplace=True)

    remaining_cells = cells_before_harmonization[~cells_before_harmonization['geometry'].intersects(intersecting_boundary)]

    merged_cells = gpd.GeoDataFrame(pd.concat([remaining_cells, gdf_nc], ignore_index=False))

    merged_cells.drop(['centroid'], axis=1, inplace=True)

    merged_cells.to_parquet(f'{output_path}/merged_cell_segmentation.parquet')

    print("Merged Segmentation saved.")

    ## add cell meta data in micron space (parquet)
    ## add cell by gene matrix (parquet)
    ## add segmentation parameters (json)
    ## add transformation matrix (csv)

    transcripts_default = pd.read_parquet(f"{default_data_path}/transcripts.parquet")

    transcripts_default_GDF = gpd.GeoDataFrame(transcripts_default, geometry=gpd.points_from_xy(transcripts_default['x_location'], transcripts_default['y_location']))

    print("Calculating new assignment of transcripts...")
    newly_assigned_transcripts = partitioning_transcripts(CELL_POLYGONS_GDF = merged_cells,
                                                       chunked_transcripts_gdf = transcripts_default_GDF)

    newly_assigned_transcripts_GDF = gpd.GeoDataFrame(newly_assigned_transcripts, geometry=gpd.points_from_xy(newly_assigned_transcripts['x_location'], newly_assigned_transcripts['y_location']))

    newly_assigned_transcripts_GDF.to_parquet(f'{output_path}/merged_segmentation_assigned_transcripts.parquet', index=False)

    print("New transcript assignment of merged segmentation saved.")