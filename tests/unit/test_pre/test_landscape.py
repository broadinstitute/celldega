"""Gene summaries must agree for dense and sparse expression matrices."""

import numpy as np
import pandas as pd
import pytest
from scipy.sparse import csr_matrix

from celldega.pre.landscape import calc_meta_gene_data


@pytest.mark.parametrize("sparse", [False, True])
@pytest.mark.parametrize("dtype", [np.uint32, np.float64])
def test_gene_statistics_match_numpy(sparse, dtype):
    values = np.array([[1, 0, 0], [0, 2, 0], [4, 0, 0], [0, 3, 0]], dtype=dtype)
    genes = ["A", "B", "zero"]
    cbg = (
        pd.DataFrame.sparse.from_spmatrix(csr_matrix(values), columns=genes)
        if sparse
        else pd.DataFrame(values, columns=genes)
    )

    summary = calc_meta_gene_data(cbg)

    assert summary.index.tolist() == genes
    np.testing.assert_allclose(summary["mean"], values.mean(axis=0))
    np.testing.assert_allclose(summary["std"], values.std(axis=0))
    np.testing.assert_allclose(summary["max"], values.max(axis=0))
    np.testing.assert_allclose(summary["non-zero"], np.count_nonzero(values, axis=0) / len(values))
