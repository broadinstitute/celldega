import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import numpy as np
import json
import os
from shapely.validation import make_valid
from ..nbhd import alpha_shape
from shapely.affinity import affine_transform

def find_containing_polygon(transcript, polygons_sindex, gdf_polygons):

    point = getattr(transcript, 'geometry_image_space', None) or getattr(transcript, 'geometry', None)
    #point = transcript.geometry_image_space
    possible_matches_index = list(polygons_sindex.query(point, predicate='within'))

    if len(possible_matches_index) == 0:
        return 'UNASSIGNED'
    elif len(possible_matches_index) > 1:
        return 'more_than_one_matches'
    else:
        if isinstance(gdf_polygons.iloc[possible_matches_index[0]].name, str):
            return gdf_polygons.iloc[possible_matches_index[0]].name
        else:
            return f"{gdf_polygons.iloc[possible_matches_index[0]].name}_polygon"

def transcript_process_chunk(gdf_transcripts, polygons_sindex, gdf_polygons):
    if not gdf_transcripts.empty:
        gdf_transcripts['polygon_index'] = gdf_transcripts.apply(find_containing_polygon,
                                                                   axis=1,
                                                                   polygons_sindex=polygons_sindex,
                                                                   gdf_polygons=gdf_polygons)
    else:
        gdf_transcripts['polygon_index'] = 'UNASSIGNED'

    return gdf_transcripts

def assigning_transcripts(gdf_polygons, gdf_transcripts):

    polygons_sindex = gdf_polygons.sindex

    assigned_transcripts = gpd.GeoDataFrame()

    processed_transcripts = transcript_process_chunk(gdf_transcripts = gdf_transcripts,
                                polygons_sindex = polygons_sindex,
                                gdf_polygons = gdf_polygons)

    assigned_transcripts = pd.concat([assigned_transcripts, processed_transcripts], ignore_index=True)
    assigned_transcripts = gpd.GeoDataFrame(assigned_transcripts, geometry='geometry')

    return assigned_transcripts

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

def merge_segmentation(default_data_path, custom_data_path, output_path, clusters_within_cutout_region, inv_alpha_value_for_cutout_region=1, buffer_for_cutout_region_alpha_shape=0, ioa_small_thresh = 0.5):

    os.makedirs(output_path, exist_ok=True)

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
    custom_technology_name = custom_segmentation_parameters['segmentation_approach']

    if os.path.exists(f'{custom_data_path}/cutout_region_alpha_shape.parquet'):
        largest_cutout_region_alpha_shape_gdf = gpd.read_parquet(f'{custom_data_path}/cutout_region_alpha_shape.parquet')
        largest_cutout_region_alpha_shape = largest_cutout_region_alpha_shape_gdf.loc[0]['geometry']

    else:
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

    print("Default segmented and custom segmented cells within cutout region extracted.")

    gpd.GeoDataFrame(geometry=[largest_cutout_region_alpha_shape]).to_parquet(f'{output_path}/cutout_region_alpha_shape.parquet', index=False)

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

    transformation_matrix = pd.read_csv(f"{custom_data_path}/transformation_matrix.csv").values[:3,:3]

    merged_cells['geometry_image_space'] = merged_cells['geometry'].apply(lambda geom: affine_transform(geom, [transformation_matrix[0, 0],
                                                                                           transformation_matrix[0, 1],
                                                                                           transformation_matrix[1, 0],
                                                                                           transformation_matrix[1, 1],
                                                                                           transformation_matrix[0, 2],
                                                                                           transformation_matrix[1, 2]]))

    merged_cells['area'] = merged_cells['geometry'].area
    merged_cells['centroid'] = merged_cells['geometry'].centroid

    merged_cells.to_parquet(f'{output_path}/cell_polygons.parquet')

    print("Merged Segmentation saved.")

    merged_cells[['area', 'centroid']].to_parquet(f'{output_path}/cell_metadata_micron_space.parquet')

    print("Merged Segmentation Meta data saved.")

    transcripts_default = pd.read_parquet(f"{default_data_path}/transcripts.parquet")

    transcripts_default_GDF = gpd.GeoDataFrame(transcripts_default, geometry=gpd.points_from_xy(transcripts_default['x_location'], transcripts_default['y_location']))

    print("Calculating new assignment of transcripts...")

    if default_technology_name == 'Xenium':
        trx_col = 'transcript_id'
        cell_id_col = 'cell_id'
        gene_col = 'feature_name'

    elif default_technology_name == 'MERSCOPE':
        trx_col = 'transcript_id'
        cell_id_col = 'cell_id'
        gene_col = 'gene'

    newly_assigned_transcripts = assigning_transcripts(gdf_polygons=merged_cells,
                          gdf_transcripts=transcripts_default_GDF)

    newly_assigned_transcripts_GDF = gpd.GeoDataFrame(newly_assigned_transcripts, geometry=gpd.points_from_xy(newly_assigned_transcripts['x_location'], newly_assigned_transcripts['y_location']))

    newly_assigned_transcripts_GDF.drop([cell_id_col], axis=1, inplace=True)
    newly_assigned_transcripts_GDF = newly_assigned_transcripts_GDF.rename(columns={trx_col: 'transcript_index', gene_col: 'gene'})

    newly_assigned_transcripts_GDF.to_parquet(f'{output_path}/transcripts.parquet', index=False)

    print("New transcript assignment of merged segmentation saved.")

    newly_assigned_transcripts_GDF['polygon_index'].fillna(-1, inplace=True)
    newly_assigned_transcripts_GDF = newly_assigned_transcripts_GDF[newly_assigned_transcripts_GDF['polygon_index'] != 'UNASSIGNED']

    merged_cells = merged_cells[merged_cells.index.isin(newly_assigned_transcripts_GDF['polygon_index'])]

    partitioned_transcripts_cleaned = newly_assigned_transcripts_GDF.groupby(['gene', 'polygon_index']).size().reset_index(name='count')
    cell_by_gene_matrix = partitioned_transcripts_cleaned.pivot_table(index='polygon_index', columns='gene', values='count', fill_value=0)

    cell_by_gene_matrix = cell_by_gene_matrix.rename_axis('cell_index')

    cell_by_gene_matrix.to_parquet(f'{output_path}/cell_by_gene_matrix.parquet')

    print("Cell-by-gene matrix of merged segmentation saved.")

    segmentation_parameters = {
                "technology": "custom",
                "segmentation_approach": custom_segmentation_parameters['segmentation_approach'] + "_" + default_technology_name + "_merged",
                "dataset_name": custom_segmentation_parameters["dataset_name"]
    }

    with open(f"{output_path}/segmentation_parameters.json", "w") as file:
        json.dump(segmentation_parameters, file, indent=4)

    print("Segmentation Parameters saved.")