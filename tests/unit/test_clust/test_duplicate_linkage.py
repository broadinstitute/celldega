"""Identical vectors must keep valid zero-height merges in every clustering path."""

import numpy as np
import pandas as pd
import pytest
from scipy.cluster.hierarchy import is_valid_linkage

from celldega.clust import Matrix
from celldega.clust.utils import fast_cosine_distance


@pytest.mark.parametrize("metric", ["cosine", "euclidean"])
@pytest.mark.parametrize(
    "values",
    [
        [[1, 1, 2, 4], [1, 1, 2, 4], [2, 2, 1, 3], [4, 4, 3, 1]],
        np.zeros((4, 4)),
        np.ones((4, 4)),
        [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 3], [0, 0, 3, 1]],
    ],
)
def test_duplicate_rows_and_columns(metric, values):
    matrix = Matrix(pd.DataFrame(values))
    matrix.cluster(dist_type=metric)
    for axis in ("row", "col"):
        linkage = np.asarray(matrix.viz["linkage"][axis])
        assert is_valid_linkage(linkage)
        assert np.all(np.isfinite(linkage))
        assert linkage[0, 2] == pytest.approx(0, abs=1e-14)
        labels = matrix.cut_tree(axis=axis, threshold=1e-10)
        assert labels.iloc[0] == labels.iloc[1]
        # The reduced-view path must use the same distances and leaf identities.
        data = matrix.data.values if axis == "row" else matrix.data.values.T
        view_linkage, leaves = Matrix._subset_axis_linkage(data, metric, "average")
        np.testing.assert_allclose(view_linkage, linkage)
        assert sorted(leaves) == list(range(4))


def test_high_dimensional_duplicates_do_not_produce_negative_linkage():
    row = np.random.default_rng(0).normal(size=1001)
    data = np.array([row, row, -row])
    distances = fast_cosine_distance(data)
    assert np.all(distances >= 0)
    assert distances[0] == pytest.approx(0, abs=1e-14)
    matrix = Matrix(pd.DataFrame(data))
    matrix.cluster()
    assert is_valid_linkage(np.asarray(matrix.viz["linkage"]["row"]))
    linkage, leaves = Matrix._subset_axis_linkage(data, "cosine", "average")
    assert is_valid_linkage(linkage)
    assert sorted(leaves) == [0, 1, 2]


def test_zero_vector_cosine_convention():
    np.testing.assert_allclose(
        fast_cosine_distance(np.array([[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]])),
        [0, 1, 1],
    )
