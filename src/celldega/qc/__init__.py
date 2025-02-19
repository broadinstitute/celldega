import os
import json
import pandas as pd
import numpy as np
import geopandas as gpd
import seaborn as sns
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, MultiPolygon
from ..pre.landscape import read_cbg_mtx
from ..pre.boundary_tile import get_cell_polygons

def get_largest_polygon(geometry):
    if isinstance(geometry, MultiPolygon):
        return max(geometry.geoms, key=lambda p: p.area)
    return geometry

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

    try:
        if os.path.exists(os.path.join(base_path, "segmentation_parameters.json")):
            with open(os.path.join(base_path, "segmentation_parameters.json"), 'r') as parameter_file:
                segmentation_parameters = json.load(parameter_file)
        else:
            print("segmentation_parameters.json does not exist")
    except Exception as e:
        print(f"An error occurred: {e}")

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
        trx = pd.read_parquet(os.path.join(base_path, "transcripts.parquet"))
        trx = trx.rename(columns={'name': gene})
        trx_meta = trx[trx[cell_index] != 'UNASSIGNED'][[transcript_index, cell_index, gene]]
        
        cell_gdf = get_cell_polygons(technology=segmentation_parameters['technology'], 
                                     path_cell_boundaries=os.path.join(base_path, "cell_boundaries.parquet"))
        
        cell_gdf = gpd.GeoDataFrame(geometry=cell_gdf["geometry"])
        cell_gdf["geometry"] = cell_gdf["geometry"].apply(get_largest_polygon)
        cell_gdf.reset_index(inplace=True)
        cell_gdf['area'] = cell_gdf['geometry'].area
        cell_gdf['centroid'] = cell_gdf['geometry'].centroid
        cell_meta_gdf = cell_gdf[['cell_id', 'area', 'centroid']]

    elif segmentation_parameters['technology'] == 'MERSCOPE':
        cell_index = 'EntityID'
        gene = "gene"
        transcript_index = 'transcript_id'
        
        trx = pd.read_csv(os.path.join(base_path, "detected_transcripts.csv"))
        trx = trx.rename(columns={'name': gene})
        trx_meta = trx[trx[cell_index] != -1][[transcript_index, cell_index, gene]]

        cell_gdf = get_cell_polygons(technology=segmentation_parameters['technology'], 
                                     path_cell_boundaries=os.path.join(base_path, "cell_boundaries.parquet"), 
                                     path_output=path_output,
                                     path_meta_cell_micron=path_meta_cell_micron)
        
        cell_gdf["geometry"] = cell_gdf["Geometry"].apply(get_largest_polygon)
        cell_gdf.drop(['Geometry'], axis=1, inplace=True)
        cell_gdf = gpd.GeoDataFrame(geometry=cell_gdf["Geometry"])
        
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

    
def classify_cells(dataframe, cell_A_name, cell_B_name, threshold_for_A_cell_classification, threshold_for_B_cell_classification):
    dataframe['Classification'] = np.where(
        dataframe[f'Total {cell_A_name} transcripts'] >= threshold_for_A_cell_classification, cell_A_name,
        np.where(dataframe[f'Total {cell_B_name} transcripts'] >= threshold_for_B_cell_classification, cell_B_name, 'Orthogonal Expression')
    )
    return dataframe

def filter_orthogonal_expression(dataframe, cell_A_name, cell_B_name, threshold_for_orthogonal_exp):
    A_cells_with_B_genes = dataframe[
        (dataframe['Classification'] == cell_A_name) &
        (dataframe[f'Total {cell_B_name} transcripts'] > threshold_for_orthogonal_exp)
    ]
    B_cells_with_A_genes = dataframe[
        (dataframe['Classification'] == cell_B_name) &
        (dataframe[f'Total {cell_A_name} transcripts'] > threshold_for_orthogonal_exp)
    ]
    return len(A_cells_with_B_genes)/len(dataframe[f'Total {cell_A_name} transcripts']), len(B_cells_with_A_genes)/len(dataframe[f'Total {cell_B_name} transcripts'])

def orthogonal_expression_calc(base_paths, cell_type_A_specific_genes, 
                          cell_type_B_specific_genes, cell_A_name, cell_B_name, threshold_for_A_cell_classification=3, threshold_for_B_cell_classification=3, threshold_for_orthogonal_exp=3, cmap='cividis'):
    
    """
    Analyze and visualize orthogonal expression patterns of cell-type-specific genes across multiple segmentation algorithms.

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

    threshold : int
        Threshold to perform orthogonal expression quantification.


    Returns
    -------
    None
        Displays histograms comparing total transcripts for cell types A and B, grouped by segmentation algorithm.

    Example
    -------
    
    orthogonal_expression_calc(
        base_path="path/to/data",
        cell_type_A_specific_genes=["GeneA1", "GeneA2"],
        cell_type_B_specific_genes=["GeneB1", "GeneB2"],
        cell_A_name="CellTypeA",
        cell_B_name="CellTypeB"
    )
    
    """
    
    cbg_dict = {}

    cell_A_with_B_cell_specific_genes = {}
    cell_B_with_A_cell_specific_genes = {}

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
                        margin_titles=True, despine=True, col_wrap=4,
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

        results = classify_cells(results, cell_A_name, cell_B_name, threshold_for_A_cell_classification, threshold_for_B_cell_classification)
        cell_A_with_B_cell_specific_genes[algorithm_name], cell_B_with_A_cell_specific_genes[algorithm_name] = filter_orthogonal_expression(results, cell_A_name, cell_B_name, threshold_for_orthogonal_exp)

    orthogonal_data = pd.DataFrame({
        'Technology': [i for i in cell_A_with_B_cell_specific_genes.keys() for _ in range(2)],
        'Category': [f'{cell_A_name} with {cell_B_name} genes', f'{cell_B_name} with {cell_A_name} genes'] * 4,
        'Count': [gene for pair in zip(cell_A_with_B_cell_specific_genes.values(), 
                                        cell_B_with_A_cell_specific_genes.values()) 
                   for gene in pair]
    })

    fig, ax = plt.subplots(figsize=(10, 6))

    sns.barplot(data=orthogonal_data, x='Technology', y='Count', hue='Category', ax=ax)

    ax.set_title(f'Orthogonal Expression: Classified {cell_A_name} and {cell_B_name} Expressing Opposite Gene Type', fontsize=15)
    ax.set_xlabel('Technology', fontsize=15, labelpad=10)
    ax.set_ylabel('Proportion of Cells', fontsize=15, labelpad=10)
    plt.yticks(fontsize=15)
    plt.xticks(fontsize=15)

    ax.legend(title='Category', title_fontsize=15, bbox_to_anchor=(1.05, 1), loc='upper left', facecolor="white", edgecolor="black", fontsize=15)

    plt.tight_layout()
    plt.show()