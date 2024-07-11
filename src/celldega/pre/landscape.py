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

    print('read mtx file from ', base_path) 

    # File paths
    barcodes_path = base_path + 'cell_feature_matrix/barcodes.tsv.gz'
    features_path = base_path + 'cell_feature_matrix/features.tsv.gz'
    matrix_path   = base_path + 'cell_feature_matrix/matrix.mtx.gz'

    # Read barcodes and features
    barcodes = pd.read_csv(barcodes_path, header=None, compression='gzip')
    features = pd.read_csv(features_path, header=None, compression='gzip', sep='\t')

    # Read the gene expression matrix and transpose it
    # Transpose and convert to CSC format for fast column slicing   
    matrix = mmread(matrix_path).transpose().tocsc()  

    # Create a sparse DataFrame with genes as columns and barcodes as rows
    cbg = pd.DataFrame.sparse.from_spmatrix(matrix, index=barcodes[0], columns=features[1])

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
    print('calculating mean expression from sparse float data')
    mean_expression = cbg.astype(pd.SparseDtype("float", 0)).mean(axis=0)

    # Calculate the variance as the average of the squared deviations
    print('calculating variance by looping over rows')
    num_tiles = cbg.shape[1]
    variance = cbg.apply(lambda x: ((x - mean_expression[x.name]) ** 2).sum() / num_tiles, axis=0)
    std_deviation = np.sqrt(variance)

    # Calculate maximum expression
    max_expression = cbg.max(axis=0)

    # Calculate proportion of tiles with non-zero expression
    proportion_nonzero = (cbg != 0).sum(axis=0) / len(cbg)

    # Create a DataFrame to hold all these metrics
    meta_gene = pd.DataFrame({
        'mean': mean_expression,
        'std': std_deviation,
        'max': max_expression,
        'non-zero': proportion_nonzero
    })

    return meta_gene