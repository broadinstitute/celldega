import pandas as pd
import numpy as np
import os
import geopandas as gpd
import tifffile as tiff
import alphashape
import seaborn as sns
import matplotlib.pyplot as plt
import tarfile
import pyarrow.parquet as pq
from scipy.io import mmread
from shapely.geometry import Polygon

def transform_xenium_coordinates(subset_interval_y_x, transform_file, transcript_data_file):

    start_y, end_y, start_x, end_x = int(subset_interval_y_x[0]), int(subset_interval_y_x[1]), int(subset_interval_y_x[2]), int(subset_interval_y_x[3])

    transformation_matrix = pd.read_csv(transform_file).values[:3,:3]

    inverse_transformation_matrix = np.linalg.inv(transformation_matrix)

    pixel_bounds = np.array([[start_x, start_y, 1],
                                [end_x, end_y, 1]])

    # Convert pixel bounds to micron coordinates
    micron_coordinates = np.dot(inverse_transformation_matrix, pixel_bounds.T).T

    # Removing the homogeneous coordinate, if not necessary
    micron_coordinates = micron_coordinates[:, :2]

    x_min = micron_coordinates[0,0]
    x_max = micron_coordinates[1,0]

    y_min = micron_coordinates[0,1]
    y_max = micron_coordinates[1,1]

    x_col = 'x_location'
    y_col = 'y_location'  
    
    batch_size = 100000
    batch_list = []
    trx_subset = pd.DataFrame()

    parquet_file = pq.ParquetFile(transcript_data_file)
    
    for batch in parquet_file.iter_batches(batch_size=batch_size):

        batch_df = batch.to_pandas()

        trx_subset_temp = batch_df[
            (batch_df[x_col] >= x_min) & 
            (batch_df[x_col] < x_max) & 
            (batch_df[y_col] >= y_min) & 
            (batch_df[y_col] < y_max)
        ]
        batch_list.append(trx_subset_temp)

    trx_subset = pd.concat(batch_list, ignore_index=True)

    temp = trx_subset[[x_col, y_col]].values
    transcript_positions = np.ones((temp.shape[0], temp.shape[1]+1))
    transcript_positions[:, :-1] = temp

    # Transform coordinates to mosaic pixel coordinates

    transformed_positions = np.matmul(transformation_matrix, np.transpose(transcript_positions))[:-1]
    trx_subset.loc[:, 'local_x'] = transformed_positions[0, :]
    trx_subset.loc[:,'local_y'] = transformed_positions[1, :]

    trx_subset['local_x'] = trx_subset['local_x'] - start_x
    trx_subset['local_y'] = trx_subset['local_y'] - start_y

    trx_subset = trx_subset.drop([x_col, y_col], axis=1)
    trx_subset = trx_subset.rename(columns={'local_x': x_col, 'local_y': y_col})

    trx_meta = trx_subset[trx_subset['cell_id'] != 'UNASSIGNED'][['transcript_id', 'cell_id', 'feature_name']]

    return trx_subset, trx_meta

def create_xenium_cell_polygons(transform_file, subset_interval_y_x, cell_boundaries_file):
    
    transformation_matrix = pd.read_csv(transform_file).values[:3,:3]

    inverse_transformation_matrix = np.linalg.inv(transformation_matrix)

    pixel_bounds = np.array([[subset_interval_y_x[2], subset_interval_y_x[0], 1],
                             [subset_interval_y_x[3], subset_interval_y_x[1], 1]])

    micron_coordinates = np.dot(inverse_transformation_matrix, pixel_bounds.T).T

    micron_coordinates = micron_coordinates[:, :2]

    x_min = micron_coordinates[0,0]
    x_max = micron_coordinates[1,0]

    y_min = micron_coordinates[0,1]
    y_max = micron_coordinates[1,1]

    POLYGON_VERTICES = pd.read_parquet(cell_boundaries_file)
    
    POLYGON_SUBSET = POLYGON_VERTICES[(POLYGON_VERTICES['vertex_x'] >= x_min) & 
                                       (POLYGON_VERTICES['vertex_x'] < x_max) & 
                                       (POLYGON_VERTICES['vertex_y'] >= y_min) & 
                                       (POLYGON_VERTICES['vertex_y'] < y_max) 
                                      ]

    TEMPORARY_POLYGON_SUBSET = POLYGON_SUBSET[['vertex_x', 'vertex_y']].values
    transcript_positions = np.ones((TEMPORARY_POLYGON_SUBSET.shape[0], TEMPORARY_POLYGON_SUBSET.shape[1]+1))
    transcript_positions[:, :-1] = TEMPORARY_POLYGON_SUBSET

    transformed_positions = np.matmul(transformation_matrix, np.transpose(transcript_positions))[:-1]
    POLYGON_SUBSET.loc[:, 'local_x'] = transformed_positions[0, :]
    POLYGON_SUBSET.loc[:,'local_y'] = transformed_positions[1, :]

    POLYGON_SUBSET['local_x'] = POLYGON_SUBSET['local_x'] - subset_interval_y_x[2]
    POLYGON_SUBSET['local_y'] = POLYGON_SUBSET['local_y'] - subset_interval_y_x[0]

    POLYGON_SUBSET = POLYGON_SUBSET.drop(['vertex_x', 'vertex_y'], axis=1)

    POLYGON_SUBSET = POLYGON_SUBSET.rename(columns={'local_x': 'vertex_x', 'local_y': 'vertex_y'})

    TEMPORARY_POLYGONS = {}
    for cell_id, group in POLYGON_SUBSET.groupby('cell_id'):
        points = group[['vertex_x', 'vertex_y']].values
        if len(points) >= 4:
            TEMPORARY_POLYGONS[cell_id] = Polygon(points)
            
    POLYGONS_DICTIONARY = {
        'cell_id': list(TEMPORARY_POLYGONS.keys()),
        'geometry': [TEMPORARY_POLYGONS[cell_id] for cell_id in TEMPORARY_POLYGONS.keys()]
    }

    CELL_POLYGONS_GDF = gpd.GeoDataFrame(POLYGONS_DICTIONARY, geometry='geometry')

    CELL_POLYGONS_GDF['area'] = CELL_POLYGONS_GDF['geometry'].area
    CELL_POLYGONS_GDF['centroid'] = CELL_POLYGONS_GDF['geometry'].centroid
    cell_meta = CELL_POLYGONS_GDF[['area', 'centroid']]
    
    return CELL_POLYGONS_GDF, cell_meta

def xenium_cbg_read(cell_feature_matrix_tar_gz_file):

    with tarfile.open(cell_feature_matrix_tar_gz_file, "r:gz") as tar:

        tar.extractall(path="data/segmentation_metrics_data/inputs/xenium_skin_xenium_default/")

    barcodes_path = os.path.join("data/segmentation_metrics_data/inputs/xenium_skin_xenium_default/cell_feature_matrix", "barcodes.tsv.gz")
    features_path = os.path.join("data/segmentation_metrics_data/inputs/xenium_skin_xenium_default/cell_feature_matrix", "features.tsv.gz")
    matrix_path = os.path.join("data/segmentation_metrics_data/inputs/xenium_skin_xenium_default/cell_feature_matrix", "matrix.mtx.gz")

    barcodes = pd.read_csv(barcodes_path, header=None, compression="gzip")
    features = pd.read_csv(features_path, header=None, compression="gzip", sep="\t")

    matrix = mmread(matrix_path).transpose().tocsc()

    cbg = pd.DataFrame.sparse.from_spmatrix(
        matrix, index=barcodes[0], columns=features[1]
    )
    cbg_xenium = cbg.rename_axis('__index_level_0__', axis='columns')

    return cbg_xenium

def qc_segmentation(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, dataset_name, segmentation_approach, subset_interval_y_x, transform_file, cell_boundaries_file, from_stp):

    """
    A function to calculate segmentation quality control
    metrics for imaging spatial transcriptomics data.
    """

    metrics = {}
    
    if from_stp:
        cell_index = "cell_index"
        gene = "gene"
        transcript_index = "transcript_index"

        trx = pd.read_csv(transcript_data_file)
        trx_meta = pd.read_parquet(transcript_metadata_file)
        cell_gdf = gpd.read_parquet(cell_polygon_data_file)
        cell_meta_gdf = gpd.read_parquet(cell_polygon_metadata_file)
        
    else:
        cell_index = "cell_id"
        gene = "feature_name"
        transcript_index = "transcript_id"

        trx, trx_meta = transform_xenium_coordinates(subset_interval_y_x, transform_file, transcript_data_file)
        cell_gdf, cell_meta_gdf = create_xenium_cell_polygons(transform_file, subset_interval_y_x, cell_boundaries_file)

    percentage_of_assigned_transcripts = (len(trx_meta) / len(trx))

    metrics['dataset_name'] = dataset_name
    metrics['segmentation_approach'] = segmentation_approach
    
    metrics['proportion_assigned_transcripts'] = percentage_of_assigned_transcripts
    metrics['number_cells'] = len(cell_gdf)
    metrics['mean_cell_area'] = cell_gdf['geometry'].area.mean()
    
    metrics['mean_transcripts_per_cell'] = trx_meta.groupby(cell_index).size().mean()
    metrics['median_transcripts_per_cell'] = trx_meta.groupby(cell_index)[transcript_index].count().median()

    metrics['average_genes_per_cell'] = trx_meta.groupby(cell_index)[gene].nunique().mean()
    metrics['median_genes_per_cell'] = trx_meta.groupby(cell_index)[gene].nunique().median()

    metrics['proportion_empty_cells'] = ((len(cell_meta_gdf) - len(cell_gdf)) / len(cell_meta_gdf))

    metrics_df = pd.DataFrame([metrics])
    metrics_df = metrics_df.T
    metrics_df.columns = [f"{dataset_name}-{segmentation_approach}"]
    metrics_df = metrics_df.T
    
    gene_specific_metrics_df = pd.DataFrame({
        "proportion_of_cells_expressing": (trx_meta.groupby(gene)[cell_index].nunique()) / len(cell_gdf),
        "average_expression": (trx_meta.groupby(gene)[cell_index].nunique()) / (trx_meta.groupby(gene)[cell_index].nunique().sum()),
        "assigned_transcripts": (trx_meta.groupby(gene)[transcript_index].count() / trx.groupby("feature_name")["transcript_id"].count()).fillna(0)
    })

    metrics_df.to_csv(f"data/segmentation_metrics_data/outputs/qc_segmentation_{dataset_name}-{segmentation_approach}.csv")
    gene_specific_metrics_df.to_parquet(f"data/segmentation_metrics_data/outputs/gene_specific_qc_segmentation_{dataset_name}-{segmentation_approach}.parquet")

    print("segmentation metrics calculation completed")

def mixed_expression_calc(cell_feature_matrix_tar_gz_xenium_file, cbg_stp_cellpose_default_file, cbg_stp_instanseg_file, cbg_stp_cellpose2_file, t_cell_specific_genes, b_cell_specific_genes):
    
    cbg_stp_cellpose2 = pd.read_parquet(cbg_stp_cellpose2_file)
    cbg_stp_cellpose_default = pd.read_parquet(cbg_stp_cellpose_default_file)
    cbg_stp_instanseg = pd.read_parquet(cbg_stp_instanseg_file)

    cbg_xenium = xenium_cbg_read(cell_feature_matrix_tar_gz_xenium_file)

    cbg_dict = {}
    cbg_dict['xenium_default'] = cbg_xenium
    cbg_dict['cellpose_default'] = cbg_stp_cellpose_default
    cbg_dict['instanseg'] = cbg_stp_instanseg
    cbg_dict['cellpose2'] = cbg_stp_cellpose2

    for algorithm_name, cbg in cbg_dict.items():
        t_cell_overlap = [gene for gene in t_cell_specific_genes if gene in cbg.columns]
        b_cell_overlap = [gene for gene in b_cell_specific_genes if gene in cbg.columns]
        
        cells_with_t_genes = cbg[t_cell_overlap].sum(axis=1) > 0
        cells_with_b_genes = cbg[b_cell_overlap].sum(axis=1) > 0
        
        cells_with_both = cbg[cells_with_t_genes & cells_with_b_genes]
        
        t_cell_genes_expressed = cells_with_both[t_cell_overlap].apply(
            lambda row: {gene: int(row[gene]) for gene in row[row > 0].index}, axis=1
        )
        
        b_cell_genes_expressed = cells_with_both[b_cell_overlap].apply(
            lambda row: {gene: int(row[gene]) for gene in row[row > 0].index}, axis=1
        )
        
        results = pd.DataFrame({
            "T-cell genes and transcripts": t_cell_genes_expressed,
            "B-cell genes and transcripts": b_cell_genes_expressed
        }, index=cells_with_both.index)
        
        results["Total T-cell transcripts"] = t_cell_genes_expressed.apply(lambda x: sum(x.values()))
        results["Total B-cell transcripts"] = b_cell_genes_expressed.apply(lambda x: sum(x.values()))
        
        results["Total"] = t_cell_genes_expressed.apply(lambda x: sum(x.values())) + b_cell_genes_expressed.apply(lambda x: sum(x.values()))
        results['Technology'] = algorithm_name
        
        sns.set(style='white', rc={'figure.dpi': 250, 'axes.facecolor': (0, 0, 0, 0), 'figure.facecolor': (0, 0, 0, 0)})
    
        height_of_each_facet = 3  
        aspect_ratio_of_each_facet = 1  
        
        g = sns.FacetGrid(results, col="Technology", sharex=False, sharey=False,
                        margin_titles=True, despine=True, col_wrap=3,
                        height=height_of_each_facet, aspect=aspect_ratio_of_each_facet,
                        gridspec_kws={"wspace": 0.01})
        
        g.map_dataframe(
            lambda data, **kwargs: sns.histplot(
                data=data,
                x="Total T-cell transcripts",
                y="Total B-cell transcripts",
                bins=15,
                cbar=True,
                cmap='coolwarm',
                vmin=1,
                vmax=data["Total T-cell transcripts"].max(),
                **kwargs
            )
        )
        
        g.set_axis_labels("Total T-cell transcripts", "Total B-cell transcripts")
        for ax in g.axes.flat:
            ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
            ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
            ax.tick_params(axis='both', which='major', labelsize=8)
        
        plt.tight_layout()
        plt.show()