"""Tests for Clustergram widget with Parquet input."""

import json

import numpy as np
import pandas as pd
import pytest


try:
    import geopandas as gpd
    from shapely.geometry import Polygon

    from celldega.clust import Matrix
    from celldega.viz import Clustergram, Landscape, clustergram_enrich
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
        assert isinstance(pq[key], bytes | bytearray)
        assert pq[key]  # non-empty
    assert isinstance(pq["meta"], dict)


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


def test_manual_col_attribute_initializes_na() -> None:
    mat = make_simple_matrix()
    widget = Clustergram(matrix=mat, manual_col_cat=True)

    widget.col_names = [f"col{i}" for i in range(4)]

    df = widget.col_attributes_df
    assert df is not None
    assert "Manual column attribute" in df.columns
    assert set(df["Manual column attribute"].unique()) == {"N.A."}

    colors = widget.col_attribute_colors or {}
    assert colors["Manual column attribute"]["N.A."] == "#d1d5db"

    payload = json.loads(widget.manual_cat)
    assert "Manual column attribute" in payload["col"]
    assert widget.category_colors.get("N.A.") == "#d1d5db"


def test_clustergram_category_colors_from_matrix() -> None:
    mat = make_simple_matrix()
    mat.set_global_cat_colors({"dog": "#123456"})
    widget = Clustergram(matrix=mat)
    assert widget.category_colors.get("dog") == "#123456"


def test_clustergram_enrich_sets_membership_column() -> None:
    mat = make_simple_matrix()
    widget = Clustergram(matrix=mat)
    widget.row_names = [f"gene{i}" for i in range(4)]

    holder = clustergram_enrich(widget)
    enrich_widget = holder.children[1]

    enrich_widget.term_genes = [widget.row_names[0]]

    df = widget.row_attributes_df
    assert df is not None
    assert "Enrichment membership" in df.columns
    assert df.loc[widget.row_names[0], "Enrichment membership"] == "In term"


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
