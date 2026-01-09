"""
Landscape processing module for handling gene expression data.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import mmread

from .boundary_tile import _get_name_mapping


# =============================================================================
# Function List:
# -----------------------------------------------------------------------------
# calc_meta_gene_data : Calculate gene metadata from the cell-by-gene matrix.
# read_cbg_mtx         : Read the cell-by-gene matrix from the mtx files.
# save_cbg_gene_parquets : Save the cell-by-gene matrix as gene-specific Parquet files.
# =============================================================================


def _convert_to_dense(series):
    """
    Convert a pandas Series to dense format if it's sparse.

    Parameters
    ----------
    series : pandas.Series

    Returns
    -------
    pandas.Series
        Dense Series if input was sparse; original Series otherwise.
    """
    return series.sparse.to_dense() if pd.api.types.is_sparse(series) else series


def calc_meta_gene_data(cbg):
    """
    Calculate gene metadata from the cell-by-gene matrix

    Args:
        cbg (pandas.DataFrame): A sparse DataFrame with genes as columns and barcodes as rows.

    Returns:
        pandas.DataFrame: A DataFrame with gene metadata including mean, standard deviation,
            maximum expression, and proportion of non-zero expression.
    """
    # Ensure cbg is a DataFrame
    if not isinstance(cbg, pd.DataFrame):
        raise TypeError("cbg must be a pandas DataFrame")

    # Determine if cbg is sparse
    if pd.api.types.is_sparse(cbg):
        # Ensure cbg has SparseDtype with float and fill_value=0
        cbg = cbg.astype(pd.SparseDtype("float", fill_value=0))
        print("cbg is a sparse DataFrame. Proceeding with sparse operations.")
    else:
        print("cbg is a dense DataFrame. Proceeding with dense operations.")

    # Calculate mean expression across tiles
    print("Calculating mean expression")
    mean_expression = cbg.mean(axis=0)

    # Calculate variance as the average of the squared deviations
    print("Calculating variance")
    num_tiles = cbg.shape[1]
    variance = cbg.apply(lambda x: ((x - mean_expression[x.name]) ** 2).sum() / num_tiles, axis=0)
    std_deviation = np.sqrt(variance)

    # Calculate maximum expression
    max_expression = cbg.max(axis=0)

    # Calculate proportion of tiles with non-zero expression
    proportion_nonzero = (cbg != 0).sum(axis=0) / len(cbg)

    # Create a DataFrame to hold all these metrics
    meta_gene = pd.DataFrame(
        {
            "mean": _convert_to_dense(mean_expression),
            "std": std_deviation,
            "max": _convert_to_dense(max_expression),
            "non-zero": _convert_to_dense(proportion_nonzero),
        }
    )

    return pd.DataFrame(meta_gene.values, index=meta_gene.index.tolist(), columns=meta_gene.columns)


def read_cbg_mtx(base_path, barcodes_name="barcodes", features_name="features", technology=None):
    """
    Read the cell-by-gene matrix from the mtx files.

    Parameters
    ----------
    base_path : str
        The base path to the directory containing the mtx files.

    Returns
    -------
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows.
    """
    base_path = Path(base_path)

    # File paths
    barcodes_path = base_path / (barcodes_name + ".tsv.gz")
    features_path = base_path / (features_name + ".tsv.gz")
    matrix_path = base_path / "matrix.mtx.gz"

    # Read barcodes and features
    barcodes = pd.read_csv(barcodes_path, header=None, compression="gzip")
    barcodes = barcodes[0]

    features = pd.read_csv(features_path, header=None, compression="gzip", sep="\t")

    # Read the gene expression matrix and transpose it
    # Transpose and convert to CSC format for fast column slicing
    matrix = mmread(matrix_path).transpose().tocsc()

    # Create a sparse DataFrame with genes as columns and barcodes as rows
    cbg = pd.DataFrame.sparse.from_spmatrix(matrix, index=barcodes, columns=features[1])

    return cbg.rename_axis("__index_level_0__", axis="columns")


def save_cbg_gene_parquets(
    technology, base_path, cbg, verbose=False, segmentation_approach="default"
):
    """
    Save the cell-by-gene matrix as gene-specific Parquet files.

    Parameters
    ----------
    technology : str
        The technology used for the data.
    base_path : str
        The base path to the parent directory containing the landscape_files directory.
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows.
    verbose : bool, optional
        Whether to print progress information, by default False.
    segmentation_approach : str, optional
        The segmentation approach used, by default "default".

    Returns
    -------
    None
    """
    segmentation_suffix = f"_{segmentation_approach}" if segmentation_approach != "default" else ""
    output_dir = Path(base_path) / f"cbg{segmentation_suffix}"
    output_dir.mkdir(exist_ok=True)

    # convert cell index from string to integer
    cell_str_to_int_mapping = _get_name_mapping(
        base_path, layer="boundary", segmentation=segmentation_approach
    )

    cbg.index = cbg.index.map(cell_str_to_int_mapping)

    for index, gene in enumerate(cbg.columns):
        if verbose and index % 1000 == 0:
            print(f"Processing gene {index}: {gene}")

        # Extract the column as a DataFrame as a copy
        col_df = cbg[[gene]].copy()

        # Create a DataFrame necessary to prevent error in to_parquet
        inst_df = pd.DataFrame(col_df.values, columns=[gene], index=col_df.index.tolist())

        # Replace 0 with NA and drop rows where all values are NA
        inst_df.replace(0, pd.NA, inplace=True)
        inst_df.dropna(how="all", inplace=True)

        # Save to Parquet if DataFrame is not empty
        if not inst_df.empty:
            output_path = output_dir / f"{gene}.parquet"
            inst_df.to_parquet(output_path)

    print("All gene-specific parquet files are succesfully saved.")


def save_cbg_gene_parquets_row_groups(
    technology,
    base_path,
    cbg,
    verbose=False,
    segmentation_approach="default",
    max_row_groups_per_file=400,
):
    """
    Save the cell-by-gene matrix as chunked Parquet files with one row group per gene.

    This is an alternative to save_cbg_gene_parquets that creates chunked files
    with row groups instead of many individual gene files. Files are chunked to
    keep metadata size manageable for parquet-wasm.

    Parameters
    ----------
    technology : str
        The technology used for the data.
    base_path : str
        The base path to the parent directory containing the landscape_files directory.
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows.
    verbose : bool, optional
        Whether to print progress information, by default False.
    segmentation_approach : str, optional
        The segmentation approach used, by default "default".
    max_row_groups_per_file : int, optional
        Maximum number of row groups (genes) per chunk file, by default 2000.

    Returns
    -------
    dict
        Chunk info with gene mapping and file list for landscape_parameters.json
    """
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    segmentation_suffix = f"_{segmentation_approach}" if segmentation_approach != "default" else ""
    output_dir = Path(base_path) / f"cbg{segmentation_suffix}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert cell index from string to integer
    cell_str_to_int_mapping = _get_name_mapping(
        base_path, layer="boundary", segmentation=segmentation_approach
    )

    cbg.index = cbg.index.map(cell_str_to_int_mapping)

    # Prepare gene tables - each gene becomes a row group
    gene_tables = []
    gene_to_row_group = {}

    for index, gene in enumerate(cbg.columns):
        if verbose and index % 1000 == 0:
            print(f"Processing gene {index}: {gene}")

        # Extract the column as a DataFrame
        col_df = cbg[[gene]].copy()

        # Create a DataFrame
        inst_df = pd.DataFrame(col_df.values, columns=[gene], index=col_df.index.tolist())

        # Replace 0 with NA and drop rows where all values are NA
        inst_df.replace(0, pd.NA, inplace=True)
        inst_df.dropna(how="all", inplace=True)

        if not inst_df.empty:
            # Add gene name column for identification
            inst_df = inst_df.reset_index()
            inst_df.columns = ["cell_id", "expression"]
            inst_df["gene"] = gene

            # Store global row group index for this gene
            global_index = len(gene_tables)
            gene_tables.append((gene, inst_df))
            gene_to_row_group[gene] = global_index

    if not gene_tables:
        print("Warning: No genes with expression data")
        return {}

    # Get schema from first gene
    first_table = pa.Table.from_pandas(gene_tables[0][1], preserve_index=False)

    # Calculate number of chunk files needed
    num_genes = len(gene_tables)
    num_files = (num_genes + max_row_groups_per_file - 1) // max_row_groups_per_file

    print(
        f"Chunking {num_genes} genes into {num_files} files (max {max_row_groups_per_file} per file)"
    )

    # Create metadata (stored in each chunk file)
    metadata = {
        b"gene_to_row_group": json.dumps(gene_to_row_group).encode("utf-8"),
        b"storage_mode": b"row_groups_cbg_chunked",
        b"num_genes": str(num_genes).encode("utf-8"),
        b"max_row_groups_per_file": str(max_row_groups_per_file).encode("utf-8"),
    }
    schema = first_table.schema.with_metadata(metadata)

    # Write genes to chunked files
    file_list = []
    current_file_index = -1
    writer = None

    for i, (_gene_name, gene_df) in enumerate(gene_tables):
        file_index = i // max_row_groups_per_file

        # Start new file if needed
        if file_index != current_file_index:
            if writer is not None:
                writer.close()

            current_file_index = file_index
            file_name = f"chunk_{file_index}.parquet"
            file_path = output_dir / file_name
            file_list.append(file_name)

            # Disable statistics to reduce footer size
            writer = pq.ParquetWriter(file_path, schema, write_statistics=False)

        # Write gene as row group
        gene_table = pa.Table.from_pandas(gene_df, preserve_index=False)
        writer.write_table(gene_table)

    # Close last file
    if writer is not None:
        writer.close()

    print(f"Wrote {num_genes} genes as row groups across {len(file_list)} files")

    # Return chunk info for landscape_parameters.json
    return {
        "directory": f"cbg{segmentation_suffix}",
        "files": file_list,
        "max_row_groups_per_file": max_row_groups_per_file,
        "total_row_groups": num_genes,
        "gene_to_row_group": gene_to_row_group,
    }
