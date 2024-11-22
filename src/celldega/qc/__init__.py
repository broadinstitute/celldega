import pandas as pd
import numpy as np
import os
import geopandas as gpd
import tifffile as tiff
import alphashape

def qc_segmentation(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, subset_interval_y_x, pixel_size, dataset_name, segmentation_approach, from_stp):

    """
    A function to calculate segmentation quality control
    metrics for imaging spatial transcriptomics data.
    """

    metrics = {}
    trx_meta = pd.read_parquet(transcript_metadata_file)

    if transcript_data_file.endswith(".csv"):
        trx = pd.read_csv(transcript_data_file)
    elif transcript_data_file.endswith(".parquet"):
        trx = gpd.read_parquet(transcript_data_file)
    else:
        raise ValueError("Invalid file type. A .csv or .parquet file must be provided.")
    
    if from_stp:
        cell_index = "cell_index"
        gene = "gene"
        transcript_index = "transcript_index"
    else:
        cell_index = "cell_id"
        gene = "feature_name"
        transcript_index = "transcript_id"

    cell_gdf = gpd.read_parquet(cell_polygon_data_file)
    cell_meta_gdf = gpd.read_parquet(cell_polygon_metadata_file)
    
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
        "average_expression": trx_meta.groupby(gene)[cell_index].mean(),
        "assigned_transcripts": (trx_meta.groupby(gene)[transcript_index].count() / trx.groupby("feature_name")["transcript_id"].count()).fillna(0)
    })

    metrics_df.to_csv(f"qc_segmentation_{dataset_name}-{segmentation_approach}.csv")
    gene_specific_metrics_df.to_parquet(f"gene_specific_qc_segmentation_{dataset_name}-{segmentation_approach}.parquet")

    print("segmentation metrics calculation completed")