"""Tests for Clustergram and Landscape widgets with Parquet input."""

import io
import json
from unittest.mock import patch
import warnings

import numpy as np
import pandas as pd
import pytest


try:
    import geopandas as gpd
    from shapely.geometry import Polygon

    from celldega.clust import Matrix
    from celldega.viz import Clustergram, Landscape
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def test_landscape_deprecated_technology_argument_warning():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _ = Landscape(technology="MERSCOPE")
        messages = [str(warn.message) for warn in w]
        assert any("deprecated" in msg.lower() for msg in messages), (
            "Expected deprecation warning for `technology` argument"
        )


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
        assert isinstance(pq[key], bytes | bytearray)
        assert pq[key]  # ensure non-empty
    assert isinstance(pq["meta"], dict)


def test_clustergram_initializes_with_parquet() -> None:
    mat = make_simple_matrix()
    pq = mat.export_viz_parquet()

    widget = Clustergram(matrix=mat)
    assert widget.network_meta == pq["meta"]

    for attr, key in [
        ("mat_parquet", "mat"),
        ("row_nodes_parquet", "row_nodes"),
        ("col_nodes_parquet", "col_nodes"),
        ("row_linkage_parquet", "row_linkage"),
        ("col_linkage_parquet", "col_linkage"),
    ]:
        assert hasattr(widget, attr), f"Missing attribute: {attr}"
        assert getattr(widget, attr) == pq[key]


def test_clustergram_selected_genes_trait() -> None:
    mat = make_simple_matrix()
    widget = Clustergram(matrix=mat)
    assert widget.selected_genes == []
    assert widget.top_n_genes == 50

    widget.selected_genes = ["A", "B"]
    assert widget.selected_genes == ["A", "B"]


# ---------- Landscape Patch and Tests ----------


class MockHTTPResponse(io.BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.headers = {}  # Mimic real HTTPResponse


def mock_urlopen_with_technology(*args, **kwargs):
    """Valid JSON containing technology."""
    return MockHTTPResponse(json.dumps({"technology": "Xenium"}).encode("utf-8"))


def mock_urlopen_missing_technology(*args, **kwargs):
    """JSON missing the technology field."""
    return MockHTTPResponse(json.dumps({}).encode("utf-8"))


@patch("celldega.viz.widget.urllib.request.urlopen", side_effect=mock_urlopen_with_technology)
def test_landscape_nbhd_geojson_and_metadata(mock_urlopen) -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["a"], "cat": ["x"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    )
    meta_nbhd = pd.DataFrame({"area": [1]}, index=["a"])

    widget = Landscape(nbhd=gdf, meta_nbhd=meta_nbhd)
    gdf = gdf.drop(columns=["geometry_pixel"], errors="ignore")

    assert widget.nbhd_geojson == json.loads(gdf.to_json())
    assert hasattr(widget, "meta_nbhd_parquet")
    assert isinstance(widget.meta_nbhd_parquet, (bytes, bytearray))


def test_landscape_nbhd_edit_mutual_exclusion() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["a"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    )
    with pytest.raises(ValueError):
        Landscape(nbhd=gdf, nbhd_edit=True)


def test_landscape_nbhd_edit_syncs_geojson() -> None:
    widget = Landscape(nbhd_edit=True)
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "a"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
                },
            }
        ],
    }
    widget.nbhd_geojson = geojson
    assert isinstance(widget.nbhd, gpd.GeoDataFrame)
    assert list(widget.nbhd["name"]) == ["a"]
