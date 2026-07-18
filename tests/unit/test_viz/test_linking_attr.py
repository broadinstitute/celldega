"""Linked views should color cells by the Clustergram's actual attribute, not 'leiden'."""

import numpy as np
import pandas as pd
import pytest


try:
    from celldega.clust import Matrix
    from celldega.viz import (
        Clustergram,
        Landscape,
        Yearbook,
        _clustergram_col_attr,
        landscape_yearbook_clustergram,
    )
except Exception as e:  # pragma: no cover
    pytest.skip(f"celldega viz unavailable: {e}", allow_module_level=True)


def _clustergram_with_col_attr(attr):
    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=[f"g{i}" for i in range(3)],
        columns=[f"s{j}" for j in range(4)],
    )
    mat = Matrix(df, col_entity={"entity": "cell", "attr": attr}, disable_processing=True)
    mat.clust()
    return Clustergram(matrix=mat)


def test_clustergram_col_attr_helper_reads_col_entity():
    cgm = _clustergram_with_col_attr("cell_type")
    assert _clustergram_col_attr(cgm) == "cell_type"


def test_clustergram_col_attr_helper_defaults_to_leiden_when_missing():
    df = pd.DataFrame(np.zeros((2, 2)), index=["g0", "g1"], columns=["a", "b"])
    cgm = Clustergram(matrix=Matrix(df, disable_processing=True))
    # default col_entity is the cell_cluster/leiden shorthand
    assert _clustergram_col_attr(cgm) == "leiden"


def test_yearbook_query_uses_clustergram_attribute_not_leiden():
    cgm = _clustergram_with_col_attr("cell_type")
    yearbook = Yearbook(base_url="https://example.org/data")
    landscape = Landscape(nbhd_edit=True)

    landscape_yearbook_clustergram(landscape, yearbook, cgm)

    # Simulate clicking a column label in the Clustergram
    cgm.click_info = {"type": "col_label", "value": {"name": "T"}}

    assert yearbook.front_end_query.get("cluster") == {"attr": "cell_type", "value": "T"}
