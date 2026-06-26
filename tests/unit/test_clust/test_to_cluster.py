"""Tests for dendrogram cutting via Matrix.to_cluster / Clustergram.to_cluster."""

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
    return Matrix(pd.DataFrame(block, index=rows, columns=cols), disable_processing=True)


def test_to_cluster_n_clusters_splits_blocks():
    mat = _two_block_matrix()
    mat.clust()
    labels = mat.to_cluster(axis="row", n_clusters=2)
    assert isinstance(labels, pd.Series)
    assert list(labels.index) == list(mat.data.index)
    assert labels["r0"] == labels["r1"] == labels["r2"]
    assert labels["r3"] == labels["r4"] == labels["r5"]
    assert labels["r0"] != labels["r3"]


def test_to_cluster_threshold_and_axis():
    mat = _two_block_matrix()
    mat.clust()
    row_labels = mat.to_cluster(axis="row", threshold=0.5)
    col_labels = mat.to_cluster(axis="col", n_clusters=2)
    assert row_labels.nunique() == 2
    assert list(col_labels.index) == list(mat.data.columns)


def test_to_cluster_requires_clustering():
    mat = _two_block_matrix()
    with pytest.raises(ValueError, match="no linkage for axis"):
        mat.to_cluster(axis="row", n_clusters=2)


def test_to_cluster_requires_a_cut_argument():
    mat = _two_block_matrix()
    mat.clust()
    with pytest.raises(ValueError, match="n_clusters or threshold"):
        mat.to_cluster(axis="row")


def test_clustergram_to_cluster_reads_slider_state():
    from celldega.viz import Clustergram

    mat = _two_block_matrix()
    mat.clust()
    cgm = Clustergram(matrix=mat)

    explicit = cgm.to_cluster(axis="row", n_clusters=2)
    assert explicit.nunique() == 2

    # front-end slider contract: dendro_cut[axis] supplies the cut
    cgm.dendro_cut = {"row": {"n_clusters": 2}}
    from_slider = cgm.to_cluster(axis="row")
    assert from_slider.equals(explicit)

    with pytest.raises(ValueError, match="move the dendrogram slider"):
        cgm.to_cluster(axis="col")
