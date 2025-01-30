import os
import json
import pandas as pd
import geopandas as gpd
import seaborn as sns
import matplotlib.pyplot as plt
from ..pre.landscape import read_cbg_mtx
from ..pre.boundary_tile import get_cell_polygons
from ..pre.trx_tile import transform_transcript_coordinates

def qc_segmentation(base_path, path_output=None, path_meta_cell_micron=None):

    """
    Calculate segmentation quality control (QC) metrics for imaging spatial transcriptomics data.

    This function computes QC metrics to assess the quality of cell segmentation and transcript assignment
    in spatial transcriptomics datasets. Metrics include transcript assignment proportion, cell count,
    mean cell area, and transcript and gene distribution statistics.

    Parameters
    ----------
    base_path : str
        Path to the data directory

    Returns
    -------
    None
        Outputs two CSV files containing cell-level and gene-specific QC metrics.

    Example
    -------
    qc_segmentation(base_path="path/to/data")

    """

    metrics = {}

    with open(os.path.join(base_path, "segmentation_parameters.json"), 'r') as parameter_file:
        segmentation_parameters = json.load(parameter_file)

    if segmentation_parameters['technology'] == 'custom':
        cell_index = "cell_index"
        gene = "gene"
        transcript_index = "transcript_index"

        trx = pd.read_parquet(os.path.join(base_path, "transcripts.parquet"))
        trx_meta = trx[trx[cell_index] != -1][[transcript_index, cell_index, gene]]
        cell_gdf = gpd.read_parquet(os.path.join(base_path, "cell_polygons.parquet"))
        cell_meta_gdf = gpd.read_parquet(os.path.join(base_path, "cell_metadata.parquet"))
        
    elif segmentation_parameters['technology'] == 'Xenium':
        cell_index = "cell_id"
        gene = "feature_name"
        transcript_index = "transcript_id"

        transformation_matrix = pd.read_csv(os.path.join(base_path, "transformation_matrix.csv"), header=None, sep=" ").values

        # transcripts in micron space. converting them to mosaic below. 
        # let me know if this should be removed
        trx = transform_transcript_coordinates(technology=segmentation_parameters['technology'], chunk_size=1000000,
                                 path_trx=os.path.join(base_path, "transcripts.parquet"),
                                 transformation_matrix=transformation_matrix)

        trx = pd.read_parquet(os.path.join(base_path, "transcripts.parquet"))
        trx = trx.rename(columns={'transformed_x': 'x_location', 'transformed_y': 'y_location', 'name': gene})
        trx_meta = trx[trx[cell_index] != 'UNASSIGNED'][[transcript_index, cell_index, gene]]
        
        # cells in micron space. converting them to mosaic below. micron and mosaic space could result in different centroids.
        # let me know if this should be removed
        cell_gdf = get_cell_polygons(technology=segmentation_parameters['technology'], 
                                     path_cell_boundaries=os.path.join(base_path, "cell_boundaries.parquet"), 
                                     transformation_matrix=transformation_matrix)
        
        cell_gdf.reset_index(inplace=True)
        cell_gdf['area'] = cell_gdf['geometry'].area
        cell_gdf['centroid'] = cell_gdf['geometry'].centroid
        cell_meta_gdf = cell_gdf[['cell_id', 'area', 'centroid']]

    elif segmentation_parameters['technology'] == 'MERSCOPE':
        cell_index = 'EntityID'
        gene = "gene"
        transcript_index = 'transcript_id'
        
        transformation_matrix = pd.read_csv(os.path.join(base_path, "transformation_matrix.csv"), header=None, sep=" ").values

        # transcripts in micron space. converting them to mosaic below. 
        # let me know if this should be removed
        trx = transform_transcript_coordinates(technology=segmentation_parameters['technology'], chunk_size=1000000,
                                 path_trx=os.path.join(base_path, "detected_transcripts.csv"),
                                 transformation_matrix=transformation_matrix)
        
        trx = trx.to_pandas()
        trx = trx.rename(columns={'transformed_x': 'global_x', 'transformed_y': 'global_y', 'name': gene})
        trx_meta = trx[trx[cell_index] != -1][[transcript_index, cell_index, gene]]

        # cells in micron space. converting them to mosaic below. micron and mosaic space could result in different centroids.
        # let me know if this should be removed
        cell_gdf = get_cell_polygons(technology=segmentation_parameters['technology'], 
                                     path_cell_boundaries=os.path.join(base_path, "cell_boundaries.parquet"), 
                                     transformation_matrix=transformation_matrix,
                                     path_output=path_output,
                                     path_meta_cell_micron=path_meta_cell_micron)
        
        cell_gdf.reset_index(inplace=True)
        cell_gdf['area'] = cell_gdf['geometry'].area
        cell_gdf['centroid'] = cell_gdf['geometry'].centroid
        cell_meta_gdf = cell_gdf[['cell_id', 'area', 'centroid']]

    percentage_of_assigned_transcripts = (len(trx_meta) / len(trx))

    metrics['dataset_name'] = segmentation_parameters['dataset_name']
    metrics['segmentation_approach'] = segmentation_parameters['segmentation_approach']
    
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
    metrics_df.columns = [f"{segmentation_parameters['dataset_name']}_{segmentation_parameters['segmentation_approach']}"]
    metrics_df = metrics_df.T
    
    gene_specific_metrics_df = pd.DataFrame({
        "proportion_of_cells_expressing": (trx_meta.groupby(gene)[cell_index].nunique()) / len(cell_gdf),
        "average_expression": (trx_meta.groupby(gene)[cell_index].nunique()) / (trx_meta.groupby(gene)[cell_index].nunique().sum()),
        "assigned_transcripts": (trx_meta.groupby(gene)[transcript_index].count() / trx.groupby(gene)[transcript_index].count()).fillna(0)
    })

    metrics_df.to_csv(os.path.join(base_path, "cell_specific_qc.csv"))
    gene_specific_metrics_df.to_csv(os.path.join(base_path, "gene_specific_qc.csv"))

    print("segmentation metrics calculation completed")

def mixed_expression_calc(base_paths, cell_type_A_specific_genes, 
                          cell_type_B_specific_genes, cell_A_name, cell_B_name, cmap='cividis'):
    
    """
    Analyze and visualize mixed expression patterns of cell-type-specific genes across multiple segmentation algorithms.

    This function calculates the overlap of specific genes for two cell types (A and B) within cells across multiple segmentation algorithms. 
    It then generates a histogram comparing the total transcripts for each cell type in cells that express genes from both cell types.

    Parameters
    ----------
    base_path : str
        Path to the data directory

    cell_type_A_specific_genes : list of str
        List of genes specific to cell type A.

    cell_type_B_specific_genes : list of str
        List of genes specific to cell type B.

    cell_A_name : str
        Name or label for cell type A (used in plot labeling).

    cell_B_name : str
        Name or label for cell type B (used in plot labeling).


    Returns
    -------
    None
        Displays histograms comparing total transcripts for cell types A and B, grouped by segmentation algorithm.

    Example
    -------
    
    mixed_expression_calc(
        base_path="path/to/data",
        cell_type_A_specific_genes=["GeneA1", "GeneA2"],
        cell_type_B_specific_genes=["GeneB1", "GeneB2"],
        cell_A_name="CellTypeA",
        cell_B_name="CellTypeB"
    )
    
    """
        
    cbg_dict = {}

    for base_path in base_paths:

        with open(os.path.join(base_path, "segmentation_parameters.json"), 'r') as parameter_file:
            segmentation_parameters = json.load(parameter_file)

            if segmentation_parameters['technology'] == 'custom':
                cbg_dict[segmentation_parameters['segmentation_approach']] = pd.read_parquet(os.path.join(base_path, 
                                                                                                    "cell_by_gene_matrix.parquet"))
            elif segmentation_parameters['technology'] == 'Xenium':
                cbg_dict[segmentation_parameters['segmentation_approach']] = read_cbg_mtx(os.path.join(base_path, "cell_feature_matrix"))
                
            elif segmentation_parameters['technology'] == 'MERSCOPE':
                cbg_dict[segmentation_parameters['segmentation_approach']] = pd.read_csv(os.path.join(base_path, 
                                                                                                    "cell_by_gene_matrix.csv"))

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
                cmap=cmap,
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