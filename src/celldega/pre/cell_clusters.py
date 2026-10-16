"""Cluster assignments and their per-cluster gene-expression signatures.

Everything here produces the same pair of DegaFiles artefacts -- ``cluster.parquet`` and
``meta_cluster.parquet`` -- plus ``df_sig.parquet``, from three different sources: a Xenium
graph-clustering CSV, an existing custom segmentation, or an AnnData object.
"""

from pathlib import Path

import pandas as pd

from .colors import _create_cluster_colors


def _load_xenium_cluster_data(data_dir, meta_cell):
    """
    Load and process Xenium clustering data.

    Parameters:
    - data_dir: Path to data directory
    - meta_cell: Meta cell dataframe

    Returns:
    - Tuple of (default_clustering, clusters)
    """
    # Load the default clustering data
    default_clustering = pd.read_csv(
        Path(data_dir) / "analysis" / "clustering" / "gene_expression_graphclust" / "clusters.csv",
        index_col=0,
    )
    default_clustering.columns = default_clustering.columns.str.lower()

    # Prepare the clustering data
    default_clustering_ini = default_clustering.copy()
    default_clustering_ini["cluster"] = default_clustering_ini["cluster"].astype("string")

    # Align the clustering data with the cell metadata
    default_clustering = pd.DataFrame(index=meta_cell["name"].tolist())
    default_clustering.loc[default_clustering_ini.index.tolist(), "cluster"] = (
        default_clustering_ini["cluster"]
    )

    # Count the number of cells in each cluster
    ser_counts = default_clustering["cluster"].value_counts()
    clusters = ser_counts.index.tolist()

    return default_clustering, clusters, ser_counts


def _save_cluster_data(cell_clusters_dir, default_clustering, clusters, ser_counts):
    """
    Save cluster and meta cluster data.

    Parameters:
    - cell_clusters_dir: Directory to save cluster data
    - default_clustering: Clustering dataframe
    - clusters: List of cluster names
    - ser_counts: Series with cluster counts
    """
    # Save the clustering data
    default_clustering.to_parquet(Path(cell_clusters_dir) / "cluster.parquet")

    # Assign colors to clusters
    colors = _create_cluster_colors(clusters)

    # Create the meta cluster DataFrame
    ser_color = pd.Series(colors, index=clusters, name="color")
    meta_cluster = pd.DataFrame(ser_color)
    meta_cluster["count"] = ser_counts

    # Save the meta cluster data
    meta_cluster.to_parquet(Path(cell_clusters_dir) / "meta_cluster.parquet")


def cluster_gene_expression(
    technology,
    path_dega_files,
    cbg,
    data_dir=None,
    segmentation_approach="default",
):
    """
    Calculates cluster-specific gene expression signatures for Xenium data.

    Args:
        technology (str): The technology used (e.g., "Xenium" or "MERSCOPE"). Currently, only "Xenium" is supported.
        data_dir (str): Path to the directory containing the Xenium data.
        path_dega_files (str): Path to the directory where the gene expression signature file will be saved.
        cbg (pd.DataFrame): A cell-by-gene matrix where rows represent cells and columns represent genes.
                            The index of the DataFrame should match the cell IDs in the Xenium metadata.

    Raises:
        ValueError: If the specified technology is not supported.
        FileNotFoundError: If the required input files are not found.
    """
    print("\n========Create cluster gene expression (df_sig)========")
    if technology not in ["Xenium", "custom"]:
        raise ValueError(
            f"Unsupported technology: {technology}. Currently, only 'Xenium' and 'Custom' is supported."
        )

    if technology == "Xenium":
        cells_csv_path = Path(data_dir) / "cells.csv.gz"
        clusters_csv_path = (
            Path(data_dir)
            / "analysis"
            / "clustering"
            / "gene_expression_graphclust"
            / "clusters.csv"
        )

        # Load the cell metadata
        usecols = ["cell_id", "x_centroid", "y_centroid"]
        meta_cell = pd.read_csv(cells_csv_path, index_col=0, usecols=usecols)
        meta_cell.columns = ["center_x", "center_y"]

        # Load the clustering data
        df_meta = pd.read_csv(clusters_csv_path, index_col=0)
        df_meta["Cluster"] = df_meta["Cluster"].astype("string")
        df_meta.columns = ["cluster"]

        # Add cluster information to the cell metadata
        meta_cell["cluster"] = df_meta["cluster"]
        clusters = meta_cell["cluster"].unique().tolist()

        # Calculate cluster-specific gene expression signatures
        list_ser = []
        for inst_cat in meta_cell["cluster"].unique().tolist():
            if inst_cat is not None:
                inst_cells = meta_cell[meta_cell["cluster"] == inst_cat].index.tolist()
                inst_ser = cbg.loc[inst_cells].sum() / len(inst_cells)
                inst_ser.name = inst_cat
                list_ser.append(inst_ser)

    elif technology == "custom":
        df_cluster = pd.read_parquet(
            Path(path_dega_files) / f"cell_clusters_{segmentation_approach}" / "cluster.parquet"
        )
        clusters = df_cluster["cluster"].unique().tolist()

        list_ser = []
        for inst_cat in df_cluster["cluster"].unique():
            if inst_cat is not None:
                inst_cells = df_cluster[df_cluster["cluster"] == inst_cat].index.tolist()

                if set(inst_cells) & set(cbg.index):
                    common_cells = list(set(inst_cells) & set(cbg.index))
                    inst_ser = cbg.loc[common_cells].sum() / len(common_cells)
                else:
                    genes = cbg.columns
                    inst_ser = pd.Series(0.0, index=genes)

                inst_ser.name = inst_cat
                list_ser.append(inst_ser)

    # Combine the signatures into a DataFrame
    df_sig = pd.concat(list_ser, axis=1)

    # Handle potential multiindex issues
    df_sig.columns = df_sig.columns.tolist()
    df_sig.index = df_sig.index.tolist()

    # Filter out unwanted genes
    keep_genes = df_sig.index.tolist()
    keep_genes = [x for x in keep_genes if "Unassigned" not in x]
    keep_genes = [x for x in keep_genes if "NegControl" not in x]
    keep_genes = [x for x in keep_genes if "DeprecatedCodeword" not in x]

    # Subset the DataFrame to keep only relevant genes and clusters
    df_sig = df_sig.loc[keep_genes, clusters]

    # drop columns with Nan values
    df_sig = df_sig.dropna(axis=1, how="all")

    df_sig = df_sig.loc[sorted(df_sig.index), sorted(df_sig.columns)]

    # Save the gene expression signatures
    segmentation_suffix = f"_{segmentation_approach}" if segmentation_approach != "default" else ""
    output_path = Path(path_dega_files) / f"df_sig{segmentation_suffix}.parquet"

    if any(isinstance(dtype, pd.SparseDtype) for dtype in df_sig.dtypes):
        df_sig.sparse.to_dense().to_parquet(output_path)
    else:
        df_sig.to_parquet(output_path)

    print("Cluster-specific gene expression signatures saved successfully.")

    return df_sig


def create_cluster_and_meta_cluster(
    technology, path_dega_files, data_dir=None, segmentation_approach="default"
):
    """
    Creates cell clusters and meta cluster files for visualization.
    Currently supports only Xenium.

    Args:
        technology (str): The technology used (e.g., "Xenium" or "MERSCOPE"). Currently, only "Xenium" is supported.
        data_dir (str): Path to the directory containing the Xenium data.
        path_dega_files (str): Path to the directory where the cluster and meta cluster files will be saved.

    Raises:
        ValueError: If the specified technology is not supported.
        FileNotFoundError: If the required input files are not found.
    """
    print("\n========Create clusters and meta clusters files========")

    if technology not in ["Xenium", "custom"]:
        raise ValueError(
            f"Unsupported technology: {technology}. Currently, only 'Xenium' and 'Custom' is supported."
        )

    # Check if the cell metadata file exists
    segmentation_suffix = f"_{segmentation_approach}" if segmentation_approach != "default" else ""
    cell_metadata_path = Path(path_dega_files) / f"cell_metadata{segmentation_suffix}.parquet"

    if not cell_metadata_path.exists():
        raise FileNotFoundError(
            f"The file '{cell_metadata_path.name}' does not exist in directory '{path_dega_files}'."
        )

    # Create the cell_clusters directory if it doesn't exist
    cell_clusters_dir = Path(path_dega_files) / f"cell_clusters{segmentation_suffix}"
    cell_clusters_dir.mkdir(exist_ok=True)

    # Load the cell metadata
    meta_cell = pd.read_parquet(cell_metadata_path)

    if technology == "Xenium":
        default_clustering, clusters, ser_counts = _load_xenium_cluster_data(data_dir, meta_cell)
        _save_cluster_data(cell_clusters_dir, default_clustering, clusters, ser_counts)

    elif technology == "custom":
        df_cluster = pd.DataFrame(index=meta_cell["name"].tolist())
        df_cluster["cluster"] = "0"
        df_cluster["cluster"] = df_cluster["cluster"].astype("string")
        df_cluster.to_parquet(cell_clusters_dir / "cluster.parquet")

        meta_cluster = pd.DataFrame(index=["0"])
        meta_cluster.loc["0", "color"] = "#1f77b4"
        meta_cluster.loc["0", "count"] = len(meta_cell["name"].tolist())
        meta_cluster.to_parquet(cell_clusters_dir / "meta_cluster.parquet")

        ser_counts = df_cluster["cluster"].value_counts()
        clusters = ser_counts.index.tolist()

    print("Cell clusters and meta cluster files created successfully.")

    return clusters


def add_clustering_from_adata(
    adata,
    path_dega_files: str,
    cluster_key: str = "leiden",
    segmentation_name: str | None = None,
) -> None:
    """
    Add cell clustering data from an AnnData object to LandscapeFiles.

    This function exports clustering assignments and associated colors from an
    AnnData object to the LandscapeFiles format, enabling the Landscape and
    Yearbook widgets to use custom clustering results.

    Parameters
    ----------
    adata : AnnData
        AnnData object containing clustering results in `obs[cluster_key]`.
        Colors can be provided in `uns[f"{cluster_key}_colors"]`.
    path_dega_files : str or Path
        Path to the LandscapeFiles directory.
    cluster_key : str, default "leiden"
        Column name in `adata.obs` containing cluster assignments.
    segmentation_name : str, optional
        Name for this segmentation/clustering result. If provided, files will be
        saved as `cell_clusters_{segmentation_name}/`. If None, files are saved
        to the default `cell_clusters/` directory.

    Returns
    -------
    None

    Examples
    --------
    >>> import scanpy as sc
    >>> import celldega as dega
    >>>
    >>> # Load and cluster your data
    >>> adata = sc.read_h5ad("my_data.h5ad")
    >>> sc.tl.leiden(adata, resolution=0.5)
    >>>
    >>> # Add clustering to LandscapeFiles
    >>> dega.pre.add_clustering_from_adata(
    ...     adata,
    ...     path_dega_files="./my_landscape_files",
    ...     cluster_key="leiden"
    ... )
    >>>
    >>> # For a custom segmentation with a specific name
    >>> dega.pre.add_clustering_from_adata(
    ...     adata,
    ...     path_dega_files="./my_landscape_files",
    ...     cluster_key="leiden",
    ...     segmentation_name="cellpose2"
    ... )

    Notes
    -----
    The Landscape widget can use the custom clustering by setting the
    `segmentation` parameter to match the `segmentation_name`.
    """
    path_lf = Path(path_dega_files)

    # Determine output directory
    if segmentation_name:
        cluster_dir = path_lf / f"cell_clusters_{segmentation_name}"
    else:
        cluster_dir = path_lf / "cell_clusters"
    cluster_dir.mkdir(exist_ok=True)

    # Get cluster assignments
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Cluster key '{cluster_key}' not found in adata.obs")

    # Create cluster DataFrame
    df_cluster = pd.DataFrame(index=adata.obs.index)
    df_cluster["cluster"] = adata.obs[cluster_key].astype("string")
    df_cluster.to_parquet(cluster_dir / "cluster.parquet")

    # Get or generate colors
    cluster_counts = df_cluster["cluster"].value_counts().sort_index()
    clusters = cluster_counts.index.tolist()

    color_key = f"{cluster_key}_colors"
    colors = adata.uns.get(color_key)

    # Fallback to generated colors
    if colors is None:
        colors = _create_cluster_colors(clusters)

    # Ensure we have enough colors
    if len(colors) < len(clusters):
        extra_colors = _create_cluster_colors(clusters[len(colors) :])
        colors = list(colors) + extra_colors

    # Create meta_cluster DataFrame
    meta_cluster = pd.DataFrame(index=clusters)
    meta_cluster["color"] = [
        colors[i] if i < len(colors) else "#808080" for i in range(len(clusters))
    ]
    meta_cluster["count"] = cluster_counts.values
    meta_cluster.to_parquet(cluster_dir / "meta_cluster.parquet")

    print(f"Clustering data saved to {cluster_dir}")
