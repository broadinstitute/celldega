import os
import numpy as np
import pandas as pd
from scipy.io import mmread
from scipy.sparse import csr_matrix


# function for pre-processing landscape data
def read_cbg_mtx(base_path):
    """
    Read the cell-by-gene matrix from the mtx files

    Parameters
    ----------
    base_path : str
        The base path to the directory containing the mtx files

    Returns
    -------
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows

    """

    print("read mtx file from ", base_path)

    # File paths
    barcodes_path = base_path + "barcodes.tsv.gz"
    features_path = base_path + "features.tsv.gz"
    matrix_path = base_path + "matrix.mtx.gz"

    # Read barcodes and features
    barcodes = pd.read_csv(barcodes_path, header=None, compression="gzip")
    features = pd.read_csv(features_path, header=None, compression="gzip", sep="\t")

    # Read the gene expression matrix and transpose it
    # Transpose and convert to CSC format for fast column slicing
    matrix = mmread(matrix_path).transpose().tocsc()

    # Create a sparse DataFrame with genes as columns and barcodes as rows
    cbg = pd.DataFrame.sparse.from_spmatrix(
        matrix, index=barcodes[0], columns=features[1]
    )

    return cbg


def calc_meta_gene_data(cbg):
    """
    Calculate gene metadata from the cell-by-gene matrix

    Parameters
    ----------
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows

    Returns
    -------
    meta_gene : pandas.DataFrame

    """

    # Calculate mean expression across tiles with float precision
    print("calculating mean expression from sparse float data")
    mean_expression = cbg.astype(pd.SparseDtype("float", 0)).mean(axis=0)

    # Calculate the variance as the average of the squared deviations
    print("calculating variance by looping over rows")
    num_tiles = cbg.shape[1]
    variance = cbg.apply(
        lambda x: ((x - mean_expression[x.name]) ** 2).sum() / num_tiles, axis=0
    )
    std_deviation = np.sqrt(variance)

    # Calculate maximum expression
    max_expression = cbg.max(axis=0)

    # Calculate proportion of tiles with non-zero expression
    proportion_nonzero = (cbg != 0).sum(axis=0) / len(cbg)

    # Create a DataFrame to hold all these metrics
    meta_gene = pd.DataFrame(
        {
            "mean": mean_expression.sparse.to_dense(),
            "std": std_deviation,
            "max": max_expression.sparse.to_dense(),
            "non-zero": proportion_nonzero.sparse.to_dense(),
        }

    )

    meta_gene_clean = pd.DataFrame(meta_gene.values, index=meta_gene.index.tolist(), columns=meta_gene.columns)

    return meta_gene_clean


def save_cbg_gene_parquets(base_path, cbg, verbose=False):
    """
    Save the cell-by-gene matrix as gene specific Parquet files

    Parameters
    ----------
    base_path : str
        The base path to the parent directory containing the landscape_files directory
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows
    verbose : bool
        Whether to print progress information

    Returns
    -------
    None

    """

    output_dir = base_path + "cbg/"
    os.makedirs(output_dir, exist_ok=True)

    for index, gene in enumerate(cbg.columns):

        if verbose:
            if index % 100 == 0:
                print(index)

        # Extract the column as a DataFrame as a copy
        col_df = cbg[[gene]].copy()

        col_df = col_df.sparse.to_dense()
        col_df = col_df.astype(int)

        # necessary to prevent error in to_parquet
        inst_df = pd.DataFrame(
            col_df.values, columns=[gene], index=col_df.index.tolist()
        )

        inst_df.replace(0, pd.NA, inplace=True)
        inst_df.dropna(how="all", inplace=True)

        if inst_df.shape[0] > 0:
            inst_df.to_parquet(os.path.join(output_dir, f"{gene}.parquet"))
