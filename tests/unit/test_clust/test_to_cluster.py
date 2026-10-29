"""Tests for dendrogram cutting via Matrix.cut_tree / Clustergram.to_cluster."""

import numpy as np
import pandas as pd
import pytest

from celldega.clust import Matrix


def _two_block_matrix(seed=0):
    rng = np.random.default_rng(seed)
    rows = [f"r{i}" for i in range(6)]
    cols = [f"c{j}" for j in range(8)]
    block = np.vstack(
        [
            rng.normal(0, 0.1, (3, 8)) + np.array([5, 5, 5, 5, 0, 0, 0, 0]),
            rng.normal(0, 0.1, (3, 8)) + np.array([0, 0, 0, 0, 5, 5, 5, 5]),
        ]
    )
    return Matrix(pd.DataFrame(block, index=rows, columns=cols))


def test_cut_tree_n_clusters_splits_blocks():
    mat = _two_block_matrix()
    mat.cluster()
    labels = mat.cut_tree(axis="row", n_clusters=2)
    assert isinstance(labels, pd.Series)
    assert list(labels.index) == list(mat.data.index)
    assert labels["r0"] == labels["r1"] == labels["r2"]
    assert labels["r3"] == labels["r4"] == labels["r5"]
    assert labels["r0"] != labels["r3"]


def test_cut_tree_threshold_and_axis():
    mat = _two_block_matrix()
    mat.cluster()
    row_labels = mat.cut_tree(axis="row", threshold=0.5)
    col_labels = mat.cut_tree(axis="col", n_clusters=2)
    assert row_labels.nunique() == 2
    assert list(col_labels.index) == list(mat.data.columns)


def test_cut_tree_requires_clustering():
    mat = _two_block_matrix()
    with pytest.raises(ValueError, match="no linkage for axis"):
        mat.cut_tree(axis="row", n_clusters=2)


def test_cut_tree_requires_exactly_one_cut_argument():
    mat = _two_block_matrix()
    mat.cluster()
    with pytest.raises(ValueError, match="exactly one"):
        mat.cut_tree(axis="row")
    with pytest.raises(ValueError, match="exactly one"):
        mat.cut_tree(axis="row", n_clusters=2, threshold=0.5)


def test_deprecated_to_cluster_alias():
    mat = _two_block_matrix()
    mat.cluster()
    with pytest.deprecated_call(match="cut_tree"):
        labels = mat.to_cluster(axis="row", n_clusters=2)
    assert labels.nunique() == 2


def test_clustergram_to_cluster_reads_slider_state():
    from celldega.viz import Clustergram

    mat = _two_block_matrix()
    mat.cluster()
    cgm = Clustergram(matrix=mat)

    explicit = cgm.to_cluster(axis="row", n_clusters=2)
    assert explicit.nunique() == 2

    # front-end slider contract: dendro_cut[axis] supplies the cut
    cgm.dendro_cut = {"row": {"n_clusters": 2}}
    from_slider = cgm.to_cluster(axis="row")
    assert from_slider.equals(explicit)

    with pytest.raises(ValueError, match="move the dendrogram slider"):
        cgm.to_cluster(axis="col")
