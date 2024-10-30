import os
import numpy as np
import pandas as pd
from scipy.io import mmread
from scipy.sparse import csr_matrix

# =============================================================================
# Function List:
# -----------------------------------------------------------------------------
# calc_meta_gene_data : Calculate gene metadata from the cell-by-gene matrix.
# read_cbg_mtx         : Read the cell-by-gene matrix from the mtx files.
# save_cbg_gene_parquets : Save the cell-by-gene matrix as gene-specific Parquet files.
# =============================================================================

def calc_meta_gene_data(cbg):
    """
    Calculate gene metadata from the cell-by-gene matrix.

    Parameters
    ----------
    cbg : pandas.DataFrame
        A DataFrame with genes as columns and barcodes as rows. It can be either
        sparse or dense.

    Returns
    -------
    meta_gene : pandas.DataFrame
        A DataFrame containing metadata for each gene, including mean expression,
        standard deviation, maximum expression, and proportion of non-zero expressions.
    """
    
    # Helper function to convert to dense if sparse
    def convert_to_dense(series):
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
        if pd.api.types.is_sparse(series):
            return series.sparse.to_dense()
        return series

    # Ensure cbg is a DataFrame
    if not isinstance(cbg, pd.DataFrame):
        raise TypeError("cbg must be a pandas DataFrame")
    
    # Determine if cbg is sparse
    is_sparse = pd.api.types.is_sparse(cbg)
    
    if is_sparse:
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
    # Vectorized computation for variance
    variance = ((cbg - mean_expression) ** 2).sum(axis=0) / num_tiles
    std_deviation = np.sqrt(variance)
    
    # Calculate maximum expression
    print("Calculating maximum expression")
    max_expression = cbg.max(axis=0)
    
    # Calculate proportion of tiles with non-zero expression
    print("Calculating proportion of non-zero expression")
    proportion_nonzero = (cbg != 0).sum(axis=0) / len(cbg)
    
    # Create a DataFrame to hold all these metrics
    meta_gene = pd.DataFrame({
        "mean": convert_to_dense(mean_expression),
        "std": std_deviation,
        "max": convert_to_dense(max_expression),
        "non-zero": convert_to_dense(proportion_nonzero)
    })
    
    return meta_gene

def read_cbg_mtx(base_path):
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
    print("Reading mtx file from ", base_path)

    # File paths
    barcodes_path = os.path.join(base_path, "barcodes.tsv.gz")
    features_path = os.path.join(base_path, "features.tsv.gz")
    matrix_path = os.path.join(base_path, "matrix.mtx.gz")

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
    cbg = cbg.rename_axis('__index_level_0__', axis='columns')
    
    return cbg

def save_cbg_gene_parquets(base_path, cbg, verbose=False):
    """
    Save the cell-by-gene matrix as gene-specific Parquet files.

    Parameters
    ----------
    base_path : str
        The base path to the parent directory containing the landscape_files directory.
    cbg : pandas.DataFrame
        A sparse DataFrame with genes as columns and barcodes as rows.
    verbose : bool, optional
        Whether to print progress information, by default False.

    Returns
    -------
    None
    """
    output_dir = os.path.join(base_path, "cbg")
    os.makedirs(output_dir, exist_ok=True)

    for index, gene in enumerate(cbg.columns):
        if verbose and index % 100 == 0:
            print(f"Processing gene {index}: {gene}")

        # Extract the column as a DataFrame as a copy
        col_df = cbg[[gene]].copy()

        # Convert to dense and integer type
        col_df = col_df.sparse.to_dense().astype(int)

        # Create a DataFrame necessary to prevent error in to_parquet
        inst_df = pd.DataFrame(
            col_df.values, columns=[gene], index=col_df.index.tolist()
        )

        # Replace 0 with NA and drop rows where all values are NA
        inst_df.replace(0, pd.NA, inplace=True)
        inst_df.dropna(how="all", inplace=True)

        # Save to Parquet if DataFrame is not empty
        if not inst_df.empty:
            output_path = os.path.join(output_dir, f"{gene}.parquet")
            inst_df.to_parquet(output_path)

