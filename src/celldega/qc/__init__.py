import pandas as pd
import numpy as np
import os
import geopandas as gpd
import tifffile as tiff
import alphashape
import seaborn as sns
import matplotlib.pyplot as plt

def qc_segmentation(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, dataset_name, segmentation_approach, from_stp):

    """
    A function to calculate segmentation quality control
    metrics for imaging spatial transcriptomics data.
    """

    metrics = {}
    trx_meta = pd.read_parquet(transcript_metadata_file)

    if transcript_data_file.endswith(".csv"):
        trx = pd.read_csv(transcript_data_file)
    elif transcript_data_file.endswith(".parquet"):
        trx = pd.read_parquet(transcript_data_file)
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

    metrics_df.to_csv(f"data/segmentation_metrics_data/outputs/qc_segmentation_{dataset_name}-{segmentation_approach}.csv")
    gene_specific_metrics_df.to_parquet(f"data/segmentation_metrics_data/outputs/gene_specific_qc_segmentation_{dataset_name}-{segmentation_approach}.parquet")

    print("segmentation metrics calculation completed")

def mixed_expression_calc(cbg_xenium_file, cbg_stp_cellpose_default_file, cbg_stp_instanseg_file, cbg_stp_cellpose2_file, t_cell_specific_genes, b_cell_specific_genes):
    
    cbg_stp_cellpose2 = pd.read_parquet(cbg_stp_cellpose2_file)
    cbg_stp_cellpose_default = pd.read_parquet(cbg_stp_cellpose_default_file)
    cbg_stp_instanseg = pd.read_parquet(cbg_stp_instanseg_file)
    cbg_xenium = pd.read_parquet(cbg_xenium_file)

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