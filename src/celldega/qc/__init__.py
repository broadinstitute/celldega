import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from shapely.geometry import MultiPolygon

from ..pre.boundary_tile import get_cell_polygons
from ..pre.landscape import read_cbg_mtx


def get_largest_polygon(geometry):  # TODO: underscore
    """
    Get the largest polygon from a geometry.

    Parameters:
    - geometry: Shapely geometry object

    Returns:
    - Largest polygon if MultiPolygon, otherwise the original geometry
    """
    if isinstance(geometry, MultiPolygon):
        return max(geometry.geoms, key=lambda p: p.area)
    return geometry


def _load_segmentation_parameters(base_path):
    """
    Load segmentation parameters from JSON file.

    Parameters:
    - base_path: Path to the data directory

    Returns:
    - Dictionary of segmentation parameters or None if error
    """
    parameters_file = Path(base_path) / "segmentation_parameters.json"

    if not parameters_file.exists():
        print("segmentation_parameters.json does not exist")
        return None

    try:
        with parameters_file.open() as parameter_file:
            return json.load(parameter_file)
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def _process_custom_technology(base_path):
    """
    Process data for custom technology.

    Parameters:
    - base_path: Path to the data directory

    Returns:
    - Tuple of (cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf)
    """
    cell_index = "cell_index"
    gene = "gene"
    transcript_index = "transcript_index"

    trx = pd.read_parquet(Path(base_path) / "transcripts.parquet")
    trx_meta = trx[trx[cell_index] != -1][[transcript_index, cell_index, gene]]
    cell_gdf = gpd.read_parquet(Path(base_path) / "cell_polygons.parquet")
    cell_meta_gdf = gpd.read_parquet(Path(base_path) / "cell_metadata.parquet")

    return cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf


def _process_xenium_technology(base_path, segmentation_parameters):
    """
    Process data for Xenium technology.

    Parameters:
    - base_path: Path to the data directory
    - segmentation_parameters: Dictionary of segmentation parameters

    Returns:
    - Tuple of (cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf)
    """
    cell_index = "cell_id"
    gene = "feature_name"
    transcript_index = "transcript_id"

    trx = pd.read_parquet(Path(base_path) / "transcripts.parquet")
    trx = trx.rename(columns={"name": gene})
    trx_meta = trx[trx[cell_index] != "UNASSIGNED"][[transcript_index, cell_index, gene]]

    cell_gdf = get_cell_polygons(
        technology=segmentation_parameters["technology"],
        path_cell_boundaries=Path(base_path) / "cell_boundaries.parquet",
    )

    cell_gdf = gpd.GeoDataFrame(geometry=cell_gdf["geometry"])
    cell_gdf["geometry"] = cell_gdf["geometry"].apply(get_largest_polygon)
    cell_gdf.reset_index(inplace=True)
    cell_gdf["area"] = cell_gdf["geometry"].area
    cell_gdf["centroid"] = cell_gdf["geometry"].centroid
    cell_meta_gdf = cell_gdf[["cell_id", "area", "centroid"]]

    return cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf


def _process_merscope_technology(
    base_path, segmentation_parameters, path_output, path_meta_cell_micron
):
    """
    Process data for MERSCOPE technology.

    Parameters:
    - base_path: Path to the data directory
    - segmentation_parameters: Dictionary of segmentation parameters
    - path_output: Output path
    - path_meta_cell_micron: Path to meta cell micron data

    Returns:
    - Tuple of (cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf)
    """
    cell_index = "EntityID"
    gene = "gene"
    transcript_index = "transcript_id"

    trx = pd.read_csv(Path(base_path) / "detected_transcripts.csv")
    trx = trx.rename(columns={"name": gene})
    trx_meta = trx[trx[cell_index] != -1][[transcript_index, cell_index, gene]]

    cell_gdf = get_cell_polygons(
        technology=segmentation_parameters["technology"],
        path_cell_boundaries=Path(base_path) / "cell_boundaries.parquet",
        path_output=path_output,
        path_meta_cell_micron=path_meta_cell_micron,
    )

    cell_gdf["geometry"] = cell_gdf["Geometry"].apply(get_largest_polygon)
    cell_gdf.drop(["Geometry"], axis=1, inplace=True)
    cell_gdf = gpd.GeoDataFrame(geometry=cell_gdf["Geometry"])

    cell_gdf.reset_index(inplace=True)
    cell_gdf["area"] = cell_gdf["geometry"].area
    cell_gdf["centroid"] = cell_gdf["geometry"].centroid
    cell_meta_gdf = cell_gdf[["cell_id", "area", "centroid"]]

    return cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf


def _calculate_metrics(
    segmentation_parameters,
    trx,
    trx_meta,
    cell_gdf,
    cell_meta_gdf,
    cell_index,
    transcript_index,
    gene,
):
    """
    Calculate QC metrics.

    Parameters:
    - segmentation_parameters: Dictionary of segmentation parameters
    - trx: Transcripts dataframe
    - trx_meta: Filtered transcripts metadata
    - cell_gdf: Cell geodataframe
    - cell_meta_gdf: Cell metadata geodataframe
    - cell_index: Column name for cell index
    - transcript_index: Column name for transcript index
    - gene: Column name for gene

    Returns:
    - Dictionary of calculated metrics
    """
    metrics = {}
    percentage_of_assigned_transcripts = len(trx_meta) / len(trx)

    metrics["dataset_name"] = segmentation_parameters["dataset_name"]
    metrics["segmentation_approach"] = segmentation_parameters["segmentation_approach"]
    metrics["proportion_assigned_transcripts"] = percentage_of_assigned_transcripts
    metrics["number_cells"] = len(cell_gdf)
    metrics["mean_cell_area"] = cell_gdf["geometry"].area.mean()

    metrics["mean_transcripts_per_cell"] = trx_meta.groupby(cell_index).size().mean()
    metrics["median_transcripts_per_cell"] = (
        trx_meta.groupby(cell_index)[transcript_index].count().median()
    )

    metrics["average_genes_per_cell"] = trx_meta.groupby(cell_index)[gene].nunique().mean()
    metrics["median_genes_per_cell"] = trx_meta.groupby(cell_index)[gene].nunique().median()

    metrics["proportion_empty_cells"] = (len(cell_meta_gdf) - len(cell_gdf)) / len(cell_meta_gdf)

    return metrics


def _save_qc_results(base_path, metrics, gene_specific_metrics_df, segmentation_parameters):
    """
    Save QC results to CSV files.

    Parameters:
    - base_path: Path to the data directory
    - metrics: Dictionary of calculated metrics
    - gene_specific_metrics_df: DataFrame of gene-specific metrics
    - segmentation_parameters: Dictionary of segmentation parameters
    """
    metrics_df = pd.DataFrame([metrics])
    metrics_df = metrics_df.T
    metrics_df.columns = [
        f"{segmentation_parameters['dataset_name']}_{segmentation_parameters['segmentation_approach']}"
    ]
    metrics_df = metrics_df.T

    metrics_df.to_csv(Path(base_path) / "cell_specific_qc.csv")
    gene_specific_metrics_df.to_csv(Path(base_path) / "gene_specific_qc.csv")


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
    path_output : str, optional
        Output path for results
    path_meta_cell_micron : str, optional
        Path to meta cell micron data

    Returns
    -------
    None
        Outputs two CSV files containing cell-level and gene-specific QC metrics.

    Example
    -------
    qc_segmentation(base_path="path/to/data")
    """
    segmentation_parameters = _load_segmentation_parameters(base_path)
    if segmentation_parameters is None:
        return

    if segmentation_parameters["technology"] == "custom":
        cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf = (
            _process_custom_technology(base_path)
        )
        trx = pd.read_parquet(Path(base_path) / "transcripts.parquet")
    elif segmentation_parameters["technology"] == "Xenium":
        cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf = (
            _process_xenium_technology(base_path, segmentation_parameters)
        )
        trx = pd.read_parquet(Path(base_path) / "transcripts.parquet")
        trx = trx.rename(columns={"name": gene})
    elif segmentation_parameters["technology"] == "MERSCOPE":
        cell_index, gene, transcript_index, trx_meta, cell_gdf, cell_meta_gdf = (
            _process_merscope_technology(
                base_path, segmentation_parameters, path_output, path_meta_cell_micron
            )
        )
        trx = pd.read_csv(Path(base_path) / "detected_transcripts.csv")
        trx = trx.rename(columns={"name": gene})
    else:
        print(f"Unknown technology: {segmentation_parameters['technology']}")
        return

    metrics = _calculate_metrics(
        segmentation_parameters,
        trx,
        trx_meta,
        cell_gdf,
        cell_meta_gdf,
        cell_index,
        transcript_index,
        gene,
    )

    gene_specific_metrics_df = pd.DataFrame(
        {
            "proportion_of_cells_expressing": (trx_meta.groupby(gene)[cell_index].nunique())
            / len(cell_gdf),
            "average_expression": (trx_meta.groupby(gene)[cell_index].nunique())
            / (trx_meta.groupby(gene)[cell_index].nunique().sum()),
            "assigned_transcripts": (
                trx_meta.groupby(gene)[transcript_index].count()
                / trx.groupby(gene)[transcript_index].count()
            ).fillna(0),
        }
    )

    _save_qc_results(base_path, metrics, gene_specific_metrics_df, segmentation_parameters)
    print("segmentation metrics calculation completed")


def classify_cells(
    dataframe,
    cell_a_name,
    cell_b_name,
    threshold_for_a_cell_classification,
    threshold_for_b_cell_classification,
):
    """
    Classify cells based on transcript thresholds.

    Parameters:
    - dataframe: Input dataframe
    - cell_a_name: Name of cell type A
    - cell_b_name: Name of cell type B
    - threshold_for_a_cell_classification: Threshold for classifying cell type A
    - threshold_for_b_cell_classification: Threshold for classifying cell type B

    Returns:
    - Dataframe with classification column added
    """
    dataframe["Classification"] = np.where(
        dataframe[f"Total {cell_a_name} transcripts"] >= threshold_for_a_cell_classification,
        cell_a_name,
        np.where(
            dataframe[f"Total {cell_b_name} transcripts"] >= threshold_for_b_cell_classification,
            cell_b_name,
            "Orthogonal Expression",
        ),
    )
    return dataframe


def filter_orthogonal_expression(dataframe, cell_a_name, cell_b_name, threshold_for_orthogonal_exp):
    """
    Filter cells with orthogonal expression.

    Parameters:
    - dataframe: Input dataframe
    - cell_a_name: Name of cell type A
    - cell_b_name: Name of cell type B
    - threshold_for_orthogonal_exp: Threshold for orthogonal expression

    Returns:
    - Tuple of proportions (A cells with B genes, B cells with A genes)
    """
    a_cells_with_b_genes = dataframe[
        (dataframe["Classification"] == cell_a_name)
        & (dataframe[f"Total {cell_b_name} transcripts"] > threshold_for_orthogonal_exp)
    ]
    b_cells_with_a_genes = dataframe[
        (dataframe["Classification"] == cell_b_name)
        & (dataframe[f"Total {cell_a_name} transcripts"] > threshold_for_orthogonal_exp)
    ]
    return (
        len(a_cells_with_b_genes) / len(dataframe[f"Total {cell_a_name} transcripts"]),
        len(b_cells_with_a_genes) / len(dataframe[f"Total {cell_b_name} transcripts"]),
    )


def _load_cbg_data(base_paths):
    """
    Load cell-by-gene data for multiple base paths.

    Parameters:
    - base_paths: List of base paths

    Returns:
    - Dictionary mapping algorithm names to cell-by-gene dataframes
    """
    cbg_dict = {}

    for base_path in base_paths:
        parameters_file = Path(base_path) / "segmentation_parameters.json"
        with parameters_file.open() as parameter_file:
            segmentation_parameters = json.load(parameter_file)

            if segmentation_parameters["technology"] == "custom":
                cbg_dict[segmentation_parameters["segmentation_approach"]] = pd.read_parquet(
                    Path(base_path) / "cell_by_gene_matrix.parquet"
                )
            elif segmentation_parameters["technology"] == "Xenium":
                cbg_dict[segmentation_parameters["segmentation_approach"]] = read_cbg_mtx(
                    Path(base_path) / "cell_feature_matrix"
                )
            elif segmentation_parameters["technology"] == "MERSCOPE":
                cbg_dict[segmentation_parameters["segmentation_approach"]] = pd.read_csv(
                    Path(base_path) / "cell_by_gene_matrix.csv"
                )

    return cbg_dict


def _create_histogram_plot(results, cell_a_name, cell_b_name, cmap):
    """
    Create histogram plot for orthogonal expression visualization.

    Parameters:
    - results: Results dataframe
    - cell_a_name: Name of cell type A
    - cell_b_name: Name of cell type B
    - cmap: Colormap for visualization
    """
    sns.set(
        style="white",
        rc={
            "figure.dpi": 250,
            "axes.facecolor": (0, 0, 0, 0),
            "figure.facecolor": (0, 0, 0, 0),
        },
    )
    height_of_each_facet = 3
    aspect_ratio_of_each_facet = 1

    g = sns.FacetGrid(
        results,
        col="Technology",
        sharex=False,
        sharey=False,
        margin_titles=True,
        despine=True,
        col_wrap=4,
        height=height_of_each_facet,
        aspect=aspect_ratio_of_each_facet,
        gridspec_kws={"wspace": 0.01},
    )

    g.map_dataframe(
        lambda data, **kwargs: sns.histplot(
            data=data,
            x=f"Total {cell_a_name} transcripts",
            y=f"Total {cell_b_name} transcripts",
            bins=15,
            cbar=True,
            cmap=cmap,
            vmin=1,
            vmax=data[f"Total {cell_a_name} transcripts"].max(),
            **kwargs,
        )
    )

    g.set_axis_labels(f"Total {cell_a_name} transcripts", f"Total {cell_b_name} transcripts")
    for ax in g.axes.flat:
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax.tick_params(axis="both", which="major", labelsize=8)

    plt.tight_layout()
    plt.show()


def _create_barplot_visualization(
    cell_a_with_b_cell_specific_genes, cell_b_with_a_cell_specific_genes, cell_a_name, cell_b_name
):
    """
    Create barplot visualization for orthogonal expression summary.

    Parameters:
    - cell_a_with_b_cell_specific_genes: Dictionary of A cells with B genes
    - cell_b_with_a_cell_specific_genes: Dictionary of B cells with A genes
    - cell_a_name: Name of cell type A
    - cell_b_name: Name of cell type B
    """
    orthogonal_data = pd.DataFrame(
        {
            "Technology": [i for i in cell_a_with_b_cell_specific_genes for _ in range(2)],
            "Category": [
                f"{cell_a_name} with {cell_b_name} genes",
                f"{cell_b_name} with {cell_a_name} genes",
            ]
            * 4,
            "Count": [
                gene
                for pair in zip(
                    cell_a_with_b_cell_specific_genes.values(),
                    cell_b_with_a_cell_specific_genes.values(),
                    strict=False,
                )
                for gene in pair
            ],
        }
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    sns.barplot(data=orthogonal_data, x="Technology", y="Count", hue="Category", ax=ax)

    ax.set_title(
        f"Orthogonal Expression: Classified {cell_a_name} and {cell_b_name} Expressing Opposite Gene Type",
        fontsize=15,
    )
    ax.set_xlabel("Technology", fontsize=15, labelpad=10)
    ax.set_ylabel("Proportion of Cells", fontsize=15, labelpad=10)
    plt.yticks(fontsize=15)
    plt.xticks(fontsize=15)

    ax.legend(
        title="Category",
        title_fontsize=15,
        bbox_to_anchor=(1.05, 1),
        loc="upper left",
        facecolor="white",
        edgecolor="black",
        fontsize=15,
    )

    plt.tight_layout()
    plt.show()


def orthogonal_expression_calc(
    base_paths,
    cell_type_a_specific_genes,
    cell_type_b_specific_genes,
    cell_a_name,
    cell_b_name,
    threshold_for_a_cell_classification=3,
    threshold_for_b_cell_classification=3,
    threshold_for_orthogonal_exp=3,
    cmap="cividis",
):
    """
    Analyze and visualize orthogonal expression patterns of cell-type-specific genes across multiple segmentation algorithms.

    This function calculates the overlap of specific genes for two cell types (A and B) within cells across multiple segmentation algorithms.
    It then generates a histogram comparing the total transcripts for each cell type in cells that express genes from both cell types.

    Parameters
    ----------
    base_paths : list of str
        List of paths to data directories
    cell_type_a_specific_genes : list of str
        List of genes specific to cell type A.
    cell_type_b_specific_genes : list of str
        List of genes specific to cell type B.
    cell_a_name : str
        Name or label for cell type A (used in plot labeling).
    cell_b_name : str
        Name or label for cell type B (used in plot labeling).
    threshold_for_a_cell_classification : int, optional
        Threshold for classifying cell type A (default: 3).
    threshold_for_b_cell_classification : int, optional
        Threshold for classifying cell type B (default: 3).
    threshold_for_orthogonal_exp : int, optional
        Threshold to perform orthogonal expression quantification (default: 3).
    cmap : str, optional
        Colormap for visualization (default: "cividis").

    Returns
    -------
    None
        Displays histograms comparing total transcripts for cell types A and B, grouped by segmentation algorithm.

    Example
    -------
    orthogonal_expression_calc(
        base_paths=["path/to/data1", "path/to/data2"],
        cell_type_a_specific_genes=["GeneA1", "GeneA2"],
        cell_type_b_specific_genes=["GeneB1", "GeneB2"],
        cell_a_name="CellTypeA",
        cell_b_name="CellTypeB"
    )
    """
    cbg_dict = _load_cbg_data(base_paths)

    cell_a_with_b_cell_specific_genes = {}
    cell_b_with_a_cell_specific_genes = {}

    for algorithm_name, cbg in cbg_dict.items():
        a_cell_overlap = [gene for gene in cell_type_a_specific_genes if gene in cbg.columns]
        b_cell_overlap = [gene for gene in cell_type_b_specific_genes if gene in cbg.columns]

        cells_with_a_genes = cbg[a_cell_overlap].sum(axis=1) > 0
        cells_with_b_genes = cbg[b_cell_overlap].sum(axis=1) > 0

        cells_with_both = cbg[cells_with_a_genes & cells_with_b_genes]

        a_cell_genes_expressed = cells_with_both[a_cell_overlap].apply(
            lambda row: {gene: int(row[gene]) for gene in row[row > 0].index}, axis=1
        )

        b_cell_genes_expressed = cells_with_both[b_cell_overlap].apply(
            lambda row: {gene: int(row[gene]) for gene in row[row > 0].index}, axis=1
        )

        results = pd.DataFrame(
            {
                f"{cell_a_name} genes and transcripts": a_cell_genes_expressed,
                f"{cell_b_name} genes and transcripts": b_cell_genes_expressed,
            },
            index=cells_with_both.index,
        )

        results[f"Total {cell_a_name} transcripts"] = a_cell_genes_expressed.apply(
            lambda x: sum(x.values())
        )
        results[f"Total {cell_b_name} transcripts"] = b_cell_genes_expressed.apply(
            lambda x: sum(x.values())
        )

        results["Total"] = a_cell_genes_expressed.apply(
            lambda x: sum(x.values())
        ) + b_cell_genes_expressed.apply(lambda x: sum(x.values()))
        results["Technology"] = algorithm_name

        _create_histogram_plot(results, cell_a_name, cell_b_name, cmap)

        results = classify_cells(
            results,
            cell_a_name,
            cell_b_name,
            threshold_for_a_cell_classification,
            threshold_for_b_cell_classification,
        )
        (
            cell_a_with_b_cell_specific_genes[algorithm_name],
            cell_b_with_a_cell_specific_genes[algorithm_name],
        ) = filter_orthogonal_expression(
            results, cell_a_name, cell_b_name, threshold_for_orthogonal_exp
        )

    _create_barplot_visualization(
        cell_a_with_b_cell_specific_genes,
        cell_b_with_a_cell_specific_genes,
        cell_a_name,
        cell_b_name,
    )
