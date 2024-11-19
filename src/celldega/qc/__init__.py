import pandas as pd
import numpy as np
import os
import geopandas as gpd
import tifffile as tiff
from skimage.exposure import equalize_adapthist

def processing(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, image_files, thickness, subset_interval_y_x, pixel_size):

    dataset_metrics = {}    
    trx_meta = pd.read_parquet(transcript_metadata_file)  

    if transcript_data_file.endswith(".csv"):
        trx = pd.read_csv(transcript_data_file)
    elif transcript_data_file.endswith(".parquet"):
        trx = gpd.read_parquet(transcript_data_file)
    else:
        raise ValueError("Invalid file type. A .csv or .parquet file must be provided.")

    cell_gdf = gpd.read_parquet(cell_polygon_data_file)
    cell_meta_gdf = gpd.read_parquet(cell_polygon_metadata_file)
    
    percentage_of_assigned_transcripts = (len(trx_meta) / len(trx)) * 100
    
    for image_index, image_path in enumerate(image_files):
        with tiff.TiffFile(image_path, is_ome=False) as image_file:

            series = image_file.series[0]
            plane = series.pages[0]

            subset_channel_image = equalize_adapthist(plane.asarray()[subset_interval_y_x[0]:subset_interval_y_x[1], subset_interval_y_x[2]:subset_interval_y_x[3]], kernel_size=[100, 100], clip_limit=0.01, nbins=256)

            dataset_metrics[f"{image_index}_indexed_image_channel_intensity"] = np.mean(subset_channel_image)

    dataset_metrics['proportion_transcripts_assigned_to_cells'] = percentage_of_assigned_transcripts
    dataset_metrics['total_number_of_cells'] = len(cell_gdf)
    dataset_metrics['average_cell_area'] = cell_gdf['geometry'].area.mean()
    dataset_metrics['average_cell_volume'] = (cell_gdf['geometry'].area * thickness).mean()
    
    dataset_metrics['average_transcripts_per_cell'] = trx_meta.groupby('cell_index').size().mean()
    dataset_metrics['median_transcripts_per_cell'] = trx_meta.groupby("cell_index")["transcript_index"].count().median()

    dataset_metrics['average_genes_per_cell'] = trx_meta.groupby('cell_index')['gene'].nunique().mean()
    dataset_metrics['median_genes_per_cell'] = trx_meta.groupby("cell_index")["gene"].nunique().median()

    width_um = subset_interval_y_x[3] * pixel_size
    height_um = subset_interval_y_x[1] * pixel_size
    total_area_um2 = width_um * height_um
    num_units = total_area_um2 / 100
    polygons_per_unit = len(cell_gdf) / num_units

    dataset_metrics['cells_per_100_um^2'] = polygons_per_unit

    dataset_metrics['percent_empty_cells'] = ((len(cell_meta_gdf) - len(cell_gdf)) / len(cell_meta_gdf)) * 100

    return dataset_metrics

def calculate_proportion_cells_expressing_each_gene(trx_meta, cell_gdf):
    gene_cell_count = trx_meta.groupby('gene')['cell_index'].nunique()
    total_cells = len(cell_gdf)
    return (gene_cell_count / total_cells) # returns pandas series

def calculate_average_expression_of_each_gene(trx_meta):
    return trx_meta.groupby('gene')['cell_index'].mean() # returns pandas series

def proportion_of_assigned_transcripts_per_gene(trx_meta, trx):
    transcripts_per_gene = trx_meta.groupby("gene")["transcript_index"].count()
    total_transcripts_per_gene = trx.groupby("feature_name")["transcript_id"].count()
    return (transcripts_per_gene / total_transcripts_per_gene).fillna(0) # returns pandas series

# Proportion of tissue area that is segmented
# Cell morphology
# elongation metric (ratio of longest length to the shortest length)
# Disjoint marker expression
# Nearby unassigned transcripts

def ist_segmentation_metrics(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, image_files, subset_interval_y_x, pixel_size, thickness=1):
    """
    A function to calculate segmentation quality control
    metrics for imaging spatial transcriptomics data.
    """

    dataset_metrics = processing(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, image_files, thickness, subset_interval_y_x, pixel_size)

    dataset_metrics_df = pd.DataFrame([dataset_metrics])

    dataset_metrics_df.T.rename(columns={0: "Xenium-Prostate-Cellpose2"}, inplace=True)

    print("segmentation metrics calculation completed")

    return dataset_metrics_df