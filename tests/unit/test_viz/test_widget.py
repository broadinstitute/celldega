"""Tests for Clustergram widget with Parquet input."""

import numpy as np
import pandas as pd
import pytest

try:
    from celldega.clust import Matrix
    from celldega.viz import Clustergram
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def make_simple_matrix() -> Matrix:
    np.random.seed(0)
    df = pd.DataFrame(np.random.rand(4, 5))
    mat = Matrix(df, disable_processing=True)
    mat.cluster()
    return mat


def test_export_viz_parquet_returns_bytes() -> None:
    mat = make_simple_matrix()
    pq = mat.export_viz_parquet()

    expected_keys = {
        "mat",
        "row_nodes",
        "col_nodes",
        "row_linkage",
        "col_linkage",
        "meta",
    }

    assert set(pq) == expected_keys
    for key in expected_keys - {"meta"}:
        assert isinstance(pq[key], (bytes, bytearray))
        assert pq[key]  # non-empty
    assert isinstance(pq["meta"], dict)


def test_clustergram_initializes_with_parquet() -> None:
    mat = make_simple_matrix()
    pq = mat.export_viz_parquet()

    widget = Clustergram(parquet_data=pq)

    assert widget.network_meta == pq["meta"]
    for attr in [
        "mat_parquet",
        "row_nodes_parquet",
        "col_nodes_parquet",
        "row_linkage_parquet",
        "col_linkage_parquet",
    ]:
        assert getattr(widget, attr) == pq[attr]
