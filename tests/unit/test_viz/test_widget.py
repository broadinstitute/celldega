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
        Yearbook,
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

    expected_entity_keys = {"row_entity", "col_entity"}

    assert set(pq) == expected_bytes_keys | expected_entity_keys | {"meta"}

    for key in expected_bytes_keys:
        assert isinstance(pq[key], bytes | bytearray)
        assert pq[key]  # non-empty
    assert isinstance(pq["meta"], dict)

    # Entity info should be dicts with entity and attr keys
    for key in expected_entity_keys:
        assert isinstance(pq[key], dict), f"{key} should be a dict"
        assert "entity" in pq[key], f"{key} should have 'entity' key"
        assert "attr" in pq[key], f"{key} should have 'attr' key"


def test_matrix_entity_normalization() -> None:
    """Test that entity specifications are normalized correctly."""
    from celldega.clust.constants import normalize_axis_entity

    # Test legacy string format
    result = normalize_axis_entity("gene")
    assert result == {"entity": "gene", "attr": "name"}

    result = normalize_axis_entity("cell_cluster")
    assert result == {"entity": "cell", "attr": "leiden"}

    result = normalize_axis_entity("nbhd")
    assert result == {"entity": "nbhd", "attr": "name"}

    # Test dict format
    result = normalize_axis_entity({"entity": "cell", "attr": "leiden"})
    assert result == {"entity": "cell", "attr": "leiden"}

    result = normalize_axis_entity({"entity": "hextile", "attr": "nbhd_cluster"})
    assert result == {"entity": "hextile", "attr": "nbhd_cluster"}

    # Test None
    result = normalize_axis_entity(None)
    assert result == {"entity": "gene", "attr": "name"}


def test_matrix_with_custom_entity_spec() -> None:
    """Test Matrix initialization with custom entity specifications."""
    np.random.seed(0)
    df = pd.DataFrame(np.random.rand(4, 5))

    # Test with new dict format
    mat = Matrix(
        df,
        row_entity={"entity": "cell", "attr": "leiden"},
        col_entity={"entity": "nbhd", "attr": "name"},
        disable_processing=True,
    )
    mat.cluster()

    assert mat.row_entity == {"entity": "cell", "attr": "leiden"}
    assert mat.col_entity == {"entity": "nbhd", "attr": "name"}

    pq = mat.export_viz_parquet()
    assert pq["row_entity"]["entity"] == "cell"
    assert pq["row_entity"]["attr"] == "leiden"
    assert pq["col_entity"]["entity"] == "nbhd"
    assert pq["col_entity"]["attr"] == "name"


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


def test_yearbook_accepts_selection_result() -> None:
    from anndata import AnnData

    from celldega.select import Selector

    obs = pd.DataFrame(
        {"cluster": ["B cell", "T cell", "B cell"]},
        index=["cell_1", "cell_2", "cell_3"],
    )
    adata = AnnData(np.ones((3, 1)), obs=obs, var=pd.DataFrame(index=["MS4A1"]))
    selector = Selector(adata)
    selection = selector.select(query=selector.attr("cluster") == "B cell")

    widget = Yearbook(base_url="https://example.org/data", selection=selection, current_page=4)

    assert widget.cells == ["cell_1", "cell_3"]
    assert widget.current_page == 0
    assert widget.selection["query"] == selection.to_json()["query"]
    assert widget.selection["candidate_count"] == 2


def test_yearbook_rejects_cells_and_selection() -> None:
    with pytest.raises(ValueError, match="either `selection` or `cells`"):
        Yearbook(base_url="https://example.org/data", cells=["cell_1"], selection=["cell_2"])
