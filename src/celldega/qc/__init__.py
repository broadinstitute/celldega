import pandas as pd
import geopandas as gpd
import seaborn as sns
import matplotlib.pyplot as plt
from ..pre.landscape import read_cbg_mtx
from ..pre.boundary_tile import get_cell_polygons
from ..pre.trx_tile import transform_transcript_coordinates

def qc_segmentation(transcript_metadata_file, transcript_data_file, cell_polygon_metadata_file, cell_polygon_data_file, dataset_name, segmentation_approach, technology_name, transform_file, cell_boundaries_file, path_output_cell_metrics, path_output_gene_metrics, path_output=None, path_meta_cell_micron=None):

    """
    Calculate segmentation quality control (QC) metrics for imaging spatial transcriptomics data.

    This function computes QC metrics to assess the quality of cell segmentation and transcript assignment
    in spatial transcriptomics datasets. Metrics include transcript assignment proportion, cell count,
    mean cell area, and transcript and gene distribution statistics.

    Parameters
    ----------
    transcript_metadata_file : str
        Path to the transcript metadata file, containing details about transcript assignments.

    transcript_data_file : str
        Path to the transcript data file, containing raw transcript information.

    cell_polygon_metadata_file : str
        Path to the cell polygon metadata file, containing cell attributes such as area and centroid.

    cell_polygon_data_file : str
        Path to the cell polygon data file, containing cell polygon geometries.

    dataset_name : str
        Name of the dataset being processed.

    segmentation_approach : str
        Description of the segmentation method used.

    subset_interval_y_x : tuple
        Tuple defining the spatial subset interval for analysis (y, x).

    transform_file : str
        Path to the transformation matrix file, required for coordinate transformations (used for MERSCOPE/Xenium data).

    cell_boundaries_file : str
        Path to the cell boundaries file, required for generating cell polygons (used for MERSCOPE/Xenium data).

    path_output_cell_metrics : str
        Path to save the output CSV file containing cell-level metrics.

    path_output_gene_metrics : str
        Path to save the output CSV file containing gene-specific metrics.

    Returns
    -------
    None
        Outputs two CSV files containing cell-level and gene-specific QC metrics.

    Notes
    -----
    - For data from STP, transcript metadata and cell polygons are read directly from provided files.
    - For Xenium data, transcripts are transformed and cell polygons are derived using provided transformation files.
    - Metrics calculated include:
        * Proportion of assigned transcripts
        * Number of cells
        * Mean and median transcripts per cell
        * Mean and median genes per cell
        * Proportion of empty cells
    - Gene-specific metrics include proportion of cells expressing a gene, average expression, and assigned transcripts.

    Example
    -------
    qc_segmentation(
         transcript_metadata_file="path/to/trx_metadata.parquet",
         transcript_data_file="path/to/trx_data.csv",
         cell_polygon_metadata_file="path/to/cell_meta.parquet",
         cell_polygon_data_file="path/to/cell_data.parquet",
         dataset_name="Dataset1",
         segmentation_approach="MethodA",
         subset_interval_y_x=(0, 1000, 0, 1000),
         transform_file="path/to/transform.mat",
         cell_boundaries_file="path/to/cell_boundaries.csv",
         from_stp=True,
         path_output_cell_metrics="output/cell_metrics.csv",
         path_output_gene_metrics="output/gene_metrics.csv"
         )

    """

    metrics = {}
    
    if technology_name == 'STP':
        cell_index = "cell_index"
        gene = "gene"
        transcript_index = "transcript_index"

        trx = pd.read_csv(transcript_data_file)
        trx_meta = pd.read_parquet(transcript_metadata_file)
        cell_gdf = gpd.read_parquet(cell_polygon_data_file)
        cell_meta_gdf = gpd.read_parquet(cell_polygon_metadata_file)
        
    elif technology_name == 'Xenium':
        cell_index = "cell_id"
        gene = "feature_name"
        transcript_index = "transcript_id"

        trx = transform_transcript_coordinates(technology=technology_name, chunk_size=1000000,
                                 path_trx=transcript_data_file,
                                 path_transformation_matrix=transform_file)

        trx = trx.to_pandas()
        trx = trx.rename(columns={'transformed_x': 'x_location', 'transformed_y': 'y_location', 'name': gene})
        trx_meta = trx[trx[cell_index] != 'UNASSIGNED'][[transcript_index, cell_index, gene]]
        
        transformation_matrix = pd.read_csv(transform_file, header=None, sep=" ").values

        cell_gdf = get_cell_polygons(technology=technology_name, path_cell_boundaries=cell_boundaries_file, transformation_matrix=transformation_matrix)
        cell_gdf.reset_index(inplace=True)
        cell_gdf['area'] = cell_gdf['geometry'].area
        cell_gdf['centroid'] = cell_gdf['geometry'].centroid
        cell_meta_gdf = cell_gdf[['cell_id', 'area', 'centroid']]

    elif technology_name == 'MERSCOPE':
        cell_index = 'EntityID' # cell_id
        gene = "gene"
        transcript_index = 'transcript_id'
        
        trx = transform_transcript_coordinates(technology=technology_name, chunk_size=1000000,
                                 path_trx=transcript_data_file,
                                 path_transformation_matrix=transform_file,
                                 )
        
        trx = trx.to_pandas()
        trx = trx.rename(columns={'transformed_x': 'global_x', 'transformed_y': 'global_y', 'name': gene})
        trx_meta = trx[trx[cell_index] != -1][[transcript_index, cell_index, gene]]

        transformation_matrix = pd.read_csv(transform_file, header=None, sep=" ").values

        cell_gdf = get_cell_polygons(technology=technology_name, 
                                     path_cell_boundaries=cell_boundaries_file, 
                                     transformation_matrix=transformation_matrix,
                                     path_output=path_output,
                                     path_meta_cell_micron=path_meta_cell_micron)
        
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
    
    """
    Analyze and visualize mixed expression patterns of cell-type-specific genes across multiple segmentation algorithms.

    This function calculates the overlap of specific genes for two cell types (A and B) within cells across multiple segmentation algorithms. 
    It then generates a histogram comparing the total transcripts for each cell type in cells that express genes from both cell types.

    Parameters
    ----------
    default_segmentation_segmentation_name : str
        Name of the default segmentation algorithm.

    default_segmentation_cell_feature_matrix_path : str
        Path to the cell-by-gene feature matrix for the default segmentation algorithm.

    algorithm_names : list of str
        Names of the segmentation algorithms being compared.

    algorithm_specific_cbg_files : list of str
        File paths to cell-by-gene feature matrices for the corresponding segmentation algorithms.

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

    Notes
    -----
    - The function reads cell-by-gene matrices, identifies cells expressing genes from both cell types, and calculates the number of transcripts for those genes.
    - Generates a FacetGrid of histograms showing the relationship between total transcripts for the two cell types, stratified by segmentation algorithm.
    - Histograms use `sns.histplot` with a `coolwarm` colormap and are displayed for each segmentation algorithm.

    Example
    -------
    mixed_expression_calc(
        default_segmentation_segmentation_name="DefaultAlgo",
        default_segmentation_cell_feature_matrix_path="path/to/default_algo_cbg.parquet",
        algorithm_names=["Algo1", "Algo2"],
        algorithm_specific_cbg_files=["path/to/algo1_cbg.parquet", "path/to/algo2_cbg.parquet"],
        cell_type_A_specific_genes=["GeneA1", "GeneA2"],
        cell_type_B_specific_genes=["GeneB1", "GeneB2"],
        cell_A_name="CellTypeA",
        cell_B_name="CellTypeB"
    )
    """
        
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
                cmap='cividis',
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