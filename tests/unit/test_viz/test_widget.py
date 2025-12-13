"""Tests for Clustergram widget with Parquet input."""

import json

import numpy as np
import pandas as pd
import pytest


try:
    import geopandas as gpd
    from shapely.geometry import Polygon

    from celldega.clust import Matrix
    from celldega.viz import (
        Clustergram,
        Landscape,
    )
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

    expected_bytes_keys = {
        "mat",
        "row_nodes",
        "col_nodes",
        "row_linkage",
        "col_linkage",
    }

    expected_str_keys = {"row_entity", "col_entity"}

    assert set(pq) == expected_bytes_keys | expected_str_keys | {"meta"}

    for key in expected_bytes_keys:
        assert isinstance(pq[key], bytes | bytearray)
        assert pq[key]  # non-empty
    assert isinstance(pq["meta"], dict)
    for key in expected_str_keys:
        assert isinstance(pq[key], str)
        assert pq[key]


def test_clustergram_initializes_with_parquet() -> None:
    mat = make_simple_matrix()
    pq = mat.export_viz_parquet()

    widget = Clustergram(matrix=mat)

    # Confirm meta is set correctly
    assert widget.network_meta == pq["meta"]

    # Confirm dynamic parquet attributes exist and match expected values
    for attr, key in [
        ("mat_parquet", "mat"),
        ("row_nodes_parquet", "row_nodes"),
        ("col_nodes_parquet", "col_nodes"),
        ("row_linkage_parquet", "row_linkage"),
        ("col_linkage_parquet", "col_linkage"),
    ]:
        assert hasattr(widget, attr), f"Missing attribute: {attr}"
        assert getattr(widget, attr) == pq[key], (
            f"Attribute {attr} does not match expected parquet value"
        )


def test_clustergram_selected_genes_trait() -> None:
    mat = make_simple_matrix()
    widget = Clustergram(matrix=mat)

    assert widget.selected_genes == []
    assert widget.top_n_genes == 50

    widget.selected_genes = ["A", "B"]
    assert widget.selected_genes == ["A", "B"]


def test_clustergram_category_colors_from_matrix() -> None:
    mat = make_simple_matrix()
    mat.set_global_cat_colors({"dog": "#123456"})
    widget = Clustergram(matrix=mat)
    assert widget.category_colors.get("dog") == "#123456"


def test_landscape_nbhd_geojson_and_metadata() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["a"], "cat": ["x"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    )
    meta_nbhd = pd.DataFrame({"area": [1]}, index=["a"])

    widget = Landscape(nbhd=gdf, meta_nbhd=meta_nbhd)

    # drop geometry_pixel column from gdf
    gdf = gdf.drop(columns=["geometry_pixel"], errors="ignore")

    assert widget.nbhd_geojson == json.loads(gdf.to_json())
    assert hasattr(widget, "meta_nbhd_parquet")
    assert isinstance(widget.meta_nbhd_parquet, bytes | bytearray)


def test_landscape_nbhd_edit_with_preloaded_data() -> None:
    """Test that nbhd_edit=True works with pre-loaded neighborhood data."""
    gdf = gpd.GeoDataFrame(
        {"name": ["a"], "cat": ["x"], "color": ["#ff0000"], "area": [1.0]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    )
    # Should NOT raise an error - editing pre-loaded neighborhoods is now supported
    widget = Landscape(nbhd=gdf, nbhd_edit=True)

    # Verify that nbhd_edit is True
    assert widget.nbhd_edit is True

    # Verify that the nbhd GeoDataFrame is stored
    assert widget.nbhd is not None
    assert len(widget.nbhd) == 1

    # Verify that nbhd_geojson is populated with the neighborhood data
    assert "features" in widget.nbhd_geojson
    assert len(widget.nbhd_geojson["features"]) == 1


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
