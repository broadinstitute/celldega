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
from ..pre.landscape import read_cbg_mtx
from ..pre.boundary_tile import get_cell_polygons
from ..pre.trx_tile import transform_transcript_coordinates

def qc_segmentation(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, dataset_name, segmentation_approach, subset_interval_y_x, transform_file, cell_boundaries_file, from_stp, path_output_cell_metrics, path_output_gene_metrics):

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

        trx = transform_transcript_coordinates(technology='Xenium', chunk_size=1000000,
                                 path_trx=transcript_data_file,
                                 path_transformation_matrix=transform_file)

        trx = trx.to_pandas()
        trx = trx.rename(columns={'transformed_x': 'x_location', 'transformed_y': 'y_location', 'name': 'feature_name'})
        trx_meta = trx[trx['cell_id'] != 'UNASSIGNED'][['transcript_id', 'cell_id', 'feature_name']]
        
        cell_gdf = get_cell_polygons(technology='Xenium', path_cell_boundaries=cell_boundaries_file, transformation_matrix=transform_file)
        cell_gdf.reset_index(inplace=True)
        cell_gdf['area'] = cell_gdf['geometry'].area
        cell_gdf['centroid'] = cell_gdf['geometry'].centroid
        cell_meta_gdf = cell_gdf[['cell_id', 'area', 'centroid']]
        
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

    metrics_df.to_csv(path_output_cell_metrics)
    gene_specific_metrics_df.to_csv(path_output_gene_metrics)

    print("segmentation metrics calculation completed")

def mixed_expression_calc(default_segmentation_segmentation_name, default_segmentation_cell_feature_matrix_path, algorithm_names, algorithm_specific_cbg_files, cell_type_A_specific_genes, cell_type_B_specific_genes, cell_A_name, cell_B_name):
    
    cbg_dict = {}

    for cbg_file, algorithm_name in zip(algorithm_specific_cbg_files, algorithm_names):
        cbg_dict[algorithm_name] = pd.read_parquet(cbg_file)

    cbg_dict[default_segmentation_segmentation_name] = read_cbg_mtx(default_segmentation_cell_feature_matrix_path)

    for algorithm_name, cbg in cbg_dict.items():

        A_cell_overlap = [gene for gene in cell_type_A_specific_genes if gene in cbg.columns]
        B_cell_overlap = [gene for gene in cell_type_B_specific_genes if gene in cbg.columns]
        
        cells_with_A_genes = cbg[A_cell_overlap].sum(axis=1) > 0
        cells_with_B_genes = cbg[B_cell_overlap].sum(axis=1) > 0
        
        cells_with_both = cbg[cells_with_A_genes & cells_with_B_genes]
        
        A_cell_genes_expressed = cells_with_both[A_cell_overlap].apply(
            lambda row: {gene: int(row[gene]) for gene in row[row > 0].index}, axis=1
        )
        
        B_cell_genes_expressed = cells_with_both[B_cell_overlap].apply(
            lambda row: {gene: int(row[gene]) for gene in row[row > 0].index}, axis=1
        )
        
        results = pd.DataFrame({
            f"{cell_A_name} genes and transcripts": A_cell_genes_expressed,
            f"{cell_B_name} genes and transcripts": B_cell_genes_expressed
        }, index=cells_with_both.index)
        
        results[f"Total {cell_A_name} transcripts"] = A_cell_genes_expressed.apply(lambda x: sum(x.values()))
        results[f"Total {cell_B_name} transcripts"] = B_cell_genes_expressed.apply(lambda x: sum(x.values()))
        
        results["Total"] = A_cell_genes_expressed.apply(lambda x: sum(x.values())) + B_cell_genes_expressed.apply(lambda x: sum(x.values()))
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
                x=f"Total {cell_A_name} transcripts",
                y=f"Total {cell_B_name} transcripts",
                bins=15,
                cbar=True,
                cmap='coolwarm',
                vmin=1,
                vmax=data[f"Total {cell_A_name} transcripts"].max(),
                **kwargs
            )
        )
        
        g.set_axis_labels(f"Total {cell_A_name} transcripts", f"Total {cell_B_name} transcripts")
        for ax in g.axes.flat:
            ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
            ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
            ax.tick_params(axis='both', which='major', labelsize=8)
        
        plt.tight_layout()
        plt.show()