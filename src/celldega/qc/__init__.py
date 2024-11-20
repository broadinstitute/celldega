import pandas as pd
import numpy as np
import os
import geopandas as gpd
import tifffile as tiff
from skimage.exposure import equalize_adapthist

def processing(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, image_files, thickness, subset_interval_y_x, pixel_size, tech_name):

    metrics = {}    
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

            metrics[f"{image_index}_indexed_image_channel_intensity"] = np.mean(subset_channel_image)

    metrics['proportion_transcripts_assigned_to_cells'] = percentage_of_assigned_transcripts
    metrics['total_number_of_cells'] = len(cell_gdf)
    metrics['average_cell_area'] = cell_gdf['geometry'].area.mean()
    metrics['average_cell_volume'] = (cell_gdf['geometry'].area * thickness).mean()
    
    metrics['average_transcripts_per_cell'] = trx_meta.groupby('cell_index').size().mean()
    metrics['median_transcripts_per_cell'] = trx_meta.groupby("cell_index")["transcript_index"].count().median()

    metrics['average_genes_per_cell'] = trx_meta.groupby('cell_index')['gene'].nunique().mean()
    metrics['median_genes_per_cell'] = trx_meta.groupby("cell_index")["gene"].nunique().median()

    width_um = subset_interval_y_x[3] * pixel_size
    height_um = subset_interval_y_x[1] * pixel_size
    total_area_um2 = width_um * height_um
    num_units = total_area_um2 / 100
    polygons_per_unit = len(cell_gdf) / num_units

    metrics['cells_per_100_um^2'] = polygons_per_unit

    metrics['percent_empty_cells'] = ((len(cell_meta_gdf) - len(cell_gdf)) / len(cell_meta_gdf)) * 100

    metrics_df = pd.DataFrame([metrics])
    metrics_df = metrics_df.T
    metrics_df.columns = [tech_name]
    metrics_df = metrics_df.T
    
    gene_specific_metrics_df = pd.DataFrame({
        "proportion_of_cells_expressing_gene": (trx_meta.groupby('gene')['cell_index'].nunique()) / len(cell_gdf),
        "average_expression_of_gene": trx_meta.groupby('gene')['cell_index'].mean(),
        "assigned_transcripts_per_gene": (trx_meta.groupby("gene")["transcript_index"].count() / trx.groupby("feature_name")["transcript_id"].count()).fillna(0)
    }).T

    gene_specific_metrics_df.index.name = "metric_name"

    return metrics_df, gene_specific_metrics_df

def ist_segmentation_metrics(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, image_files, subset_interval_y_x, pixel_size, tech_name, thickness=1):
    
    """
    A function to calculate segmentation quality control
    metrics for imaging spatial transcriptomics data.
    """

    metrics_df, gene_specific_metrics_df = processing(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, image_files, thickness, subset_interval_y_x, pixel_size, tech_name)

    print("segmentation metrics calculation completed")

    return metrics_df, gene_specific_metrics_df