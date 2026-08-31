"""Tests for Clustergram widget with Parquet input."""

import asyncio
import io
import json

from anndata import AnnData
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import traitlets


try:
    import geopandas as gpd
    from shapely.geometry import Polygon

    from celldega.clust import Matrix
    from celldega.dataset import DatasetCollection
    from celldega.nbhd import NeighborhoodCollection
    from celldega.viz import (
        Clustergram,
        Composition,
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

    # `dot_mat` is always present but empty unless a dot-size matrix was attached.
    assert set(pq) == expected_bytes_keys | expected_entity_keys | {"meta", "dot_mat"}

    for key in expected_bytes_keys:
        assert isinstance(pq[key], bytes | bytearray)
        assert pq[key]  # non-empty
    assert isinstance(pq["dot_mat"], bytes | bytearray)
    assert pq["dot_mat"] == b""  # no dot matrix set on this fixture
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


def test_matrix_infers_population_ann_data_entities() -> None:
    population = AnnData(
        X=np.array([[2, 1], [0, 3]]),
        obs=pd.DataFrame(
            {"neighborhood_id": ["n1", "n2"], "n_cells": [3, 3]},
            index=["n1", "n2"],
        ),
        var=pd.DataFrame(
            {"entity_type": ["cell_population", "cell_population"]},
            index=["T cell", "B cell"],
        ),
        uns={"category": "cell_type", "output": "counts"},
    )

    mat = Matrix(population, disable_processing=True)

    assert mat.row_entity == {"entity": "cell", "attr": "cell_type"}
    assert mat.col_entity == {"entity": "nbhd", "attr": "name"}
    assert list(mat.data.index) == ["T cell", "B cell"]
    assert list(mat.data.columns) == ["n1", "n2"]


def test_matrix_custom_entities_override_population_inference() -> None:
    population = AnnData(
        X=np.array([[1]]),
        obs=pd.DataFrame({"neighborhood_id": ["n1"]}, index=["n1"]),
        var=pd.DataFrame({"entity_type": ["cell_population"]}, index=["T cell"]),
        uns={"category": "cell_type"},
    )

    mat = Matrix(
        population,
        row_entity={"entity": "custom_row", "attr": "id"},
        col_entity={"entity": "custom_col", "attr": "id"},
        disable_processing=True,
    )

    assert mat.row_entity == {"entity": "custom_row", "attr": "id"}
    assert mat.col_entity == {"entity": "custom_col", "attr": "id"}


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


def test_clustergram_highlighted_genes_trait() -> None:
    widget = Clustergram(matrix=make_simple_matrix())

    assert widget.highlighted_genes == []

    widget.highlighted_genes = ["brd4", "sox2"]
    assert widget.highlighted_genes == ["brd4", "sox2"]


def test_clustergram_label_scales_are_configurable() -> None:
    mat = make_simple_matrix()
    widget = Clustergram(matrix=mat, row_label_scale=1.1, col_label_scale=0.7)

    assert widget.row_label_scale == 1.1
    assert widget.col_label_scale == 0.7


def test_clustergram_matrix_slice_request_is_nonblocking() -> None:
    widget = Clustergram(matrix=make_simple_matrix())

    req_id = widget.request_matrix_slice("row", index=2, max_entries=10)

    assert widget.matrix_slice_request == {
        "req_id": req_id,
        "op": "row",
        "index": 2,
        "max_entries": 10,
    }
    assert widget.matrix_slice_result == {}


def test_clustergram_matrix_slice_async_waits_for_matching_response() -> None:
    widget = Clustergram(matrix=make_simple_matrix())

    async def request_and_reply() -> dict | None:
        pending = asyncio.create_task(widget.request_matrix_slice_async("cell", row=1, col=3))
        await asyncio.sleep(0)
        req_id = widget.matrix_slice_request["req_id"]
        widget.matrix_slice_result = {"req_id": req_id, "value": 42}
        return await pending

    assert asyncio.run(request_and_reply()) == {
        "req_id": widget.matrix_slice_request["req_id"],
        "value": 42,
    }


def test_clustergram_category_colors_from_matrix() -> None:
    mat = make_simple_matrix()
    mat.set_global_cat_colors({"dog": "#123456"})
    widget = Clustergram(matrix=mat)
    assert widget.category_colors.get("dog") == "#123456"


def test_clustergram_dot_size_encoded_defaults_true() -> None:
    mat = make_simple_matrix()
    widget = Clustergram(matrix=mat)
    assert widget.dot_size_encoded is True


def test_clustergram_rejects_composition_viz_mode() -> None:
    # composition is only supported via the dedicated Composition widget.
    mat = make_simple_matrix()

    with pytest.raises(traitlets.TraitError):
        Clustergram(matrix=mat, viz_mode="composition")

    widget = Clustergram(matrix=mat)
    with pytest.raises(traitlets.TraitError):
        widget.viz_mode = "composition"


def test_clustergram_rejects_size_viz_mode() -> None:
    # standalone "size" mode isn't supported -- use "dotplot" instead.
    mat = make_simple_matrix()

    with pytest.raises(traitlets.TraitError):
        Clustergram(matrix=mat, viz_mode="size")

    widget = Clustergram(matrix=mat)
    with pytest.raises(traitlets.TraitError):
        widget.viz_mode = "size"


def test_composition_is_a_clustergram_subclass() -> None:
    df = pd.DataFrame(
        {"T": [10, 20], "B": [5, 15]},
        index=["s1", "s2"],
    )
    comp = Composition(df, category="cell_type")

    assert isinstance(comp, Clustergram)
    assert type(comp).__name__ == "Composition"
    assert comp.viz_mode == "composition"
    assert comp.composition_normalized is True


def test_composition_normalized_false_for_counts_output() -> None:
    df = pd.DataFrame(
        {"T": [10, 20], "B": [5, 15]},
        index=["s1", "s2"],
    )
    comp = Composition(df, category="cell_type", normalized=False)
    assert comp.composition_normalized is False


def test_composition_col_weights_default_empty_for_dataframe_input() -> None:
    # A bare DataFrame carries no per-group cell-count metadata.
    df = pd.DataFrame(
        {"T": [10, 20], "B": [5, 15]},
        index=["s1", "s2"],
    )
    comp = Composition(df, category="cell_type")
    assert comp.composition_col_weights == {}


def test_composition_col_weights_from_dataset_collection_n_cells() -> None:
    obs = pd.DataFrame(
        {
            "sample_id": ["s1"] * 10 + ["s2"] * 40,
            "cell_type": (["T"] * 6 + ["B"] * 4) + (["T"] * 20 + ["B"] * 20),
        },
        index=[f"c{i}" for i in range(50)],
    )
    adata = AnnData(X=np.zeros((50, 3)), obs=obs)

    dc = DatasetCollection(adata, dataset_col="sample_id")
    dc.calc_population(adata, category="cell_type")

    comp = Composition(dc, category="cell_type", adata=adata)

    assert comp.composition_col_weights == {"s1": 10.0, "s2": 40.0}
    # Explicit override wins over the auto-derived n_cells.
    comp_override = Composition(
        dc, category="cell_type", adata=adata, col_weights={"s1": 1.0, "s2": 1.0}
    )
    assert comp_override.composition_col_weights == {"s1": 1.0, "s2": 1.0}


def test_landscape_nbhd_geojson_and_metadata() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["a"], "cat": ["x"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    )
    meta_nbhd = pd.DataFrame({"area": [1]}, index=["a"])

    widget = Landscape(nbhd=gdf, meta_nbhd=meta_nbhd, transform=np.eye(3))

    # drop geometry_pixel column from gdf
    gdf = gdf.copy()
    gdf["color"] = "#4f80ff"
    gdf["area"] = gdf.geometry.area
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


def test_landscape_accepts_neighborhood_collection() -> None:
    gdf = gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
        ],
    )
    collection = NeighborhoodCollection(gdf=gdf, nbhd_type="hextile")
    collection.obs["cat"] = ["0", "1"]
    collection.obs["color"] = ["#ff0000", "#00ff00"]

    widget = Landscape(nbhd=collection, transform=np.eye(3))

    features = widget.nbhd_geojson["features"]
    properties = [feature["properties"] for feature in features]

    assert [prop["name"] for prop in properties] == ["a", "b"]
    assert [prop["cat"] for prop in properties] == ["0", "1"]
    assert [prop["color"] for prop in properties] == ["#ff0000", "#00ff00"]
    assert hasattr(widget, "meta_nbhd_parquet")
    assert isinstance(widget.meta_nbhd_parquet, bytes | bytearray)
    assert len(widget.nbhd) == 2


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


def _make_spatial_adata() -> AnnData:
    obs = pd.DataFrame({"Z": [10.0, 20.0, 30.0]}, index=["cell_1", "cell_2", "cell_3"])
    adata = AnnData(np.zeros((3, 0)), obs=obs)
    adata.obsm["spatial"] = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    return adata


def test_landscape_cluster_attr_synced_for_custom_cluster_key() -> None:
    """meta_cluster_parquet's key field must match cluster_attr, not a hardcoded
    'leiden' — the frontend reads this back via `model.get('cluster_attr')`."""
    obs = pd.DataFrame({"my_cluster": ["a", "b", "a"]}, index=["cell_1", "cell_2", "cell_3"])
    adata = AnnData(np.zeros((3, 0)), obs=obs)

    widget = Landscape(adata=adata, transform=np.eye(3), cluster_attr="my_cluster")

    assert widget.cluster_attr == "my_cluster"

    # Check the raw Arrow schema (what the JS frontend keys off of via
    # `objects_from_parquet`), not `pd.read_parquet`, which would silently
    # restore "my_cluster" as the DataFrame index instead of a column.
    table = pq.read_table(io.BytesIO(widget.meta_cluster_parquet))
    assert "my_cluster" in table.schema.names


def test_landscape_use_adata_3d_centroids_default_true() -> None:
    adata = _make_spatial_adata()

    widget = Landscape(adata=adata, transform=np.eye(3))

    assert widget.use_adata_3d_centroids is True
    assert hasattr(widget, "centroids_parquet")

    centroid_df = pd.read_parquet(io.BytesIO(widget.centroids_parquet))
    centroid_df = centroid_df.set_index("cell_id").loc[["cell_1", "cell_2", "cell_3"]]

    assert list(centroid_df["x"]) == [0.0, 1.0, 2.0]
    assert list(centroid_df["y"]) == [0.0, 1.0, 2.0]
    assert list(centroid_df["z"]) == [10.0, 20.0, 30.0]


def test_landscape_use_adata_3d_centroids_disabled() -> None:
    adata = _make_spatial_adata()

    widget = Landscape(adata=adata, transform=np.eye(3), use_adata_3d_centroids=False)

    assert widget.use_adata_3d_centroids is False
    assert not hasattr(widget, "centroids_parquet")


def test_landscape_use_adata_3d_centroids_serves_file_for_local_base_url(
    tmp_path, monkeypatch
) -> None:
    """For a local (get_local_server-style) base_url, centroids should be written
    to a small sidecar file and served by URL — not synced through the comm
    channel, which doesn't scale to millions of per-cell rows."""
    monkeypatch.chdir(tmp_path)
    dega_files_dir = tmp_path / "some_dataset_point-cloud"
    dega_files_dir.mkdir()

    adata = _make_spatial_adata()
    base_url = "http://localhost:1234/some_dataset_point-cloud"

    widget = Landscape(adata=adata, transform=np.eye(3), base_url=base_url)

    assert widget.centroids_url.startswith(f"{base_url}/.celldega_centroids_")
    assert not hasattr(widget, "centroids_parquet")

    written_files = list(dega_files_dir.glob(".celldega_centroids_*.parquet"))
    assert len(written_files) == 1

    centroid_df = pd.read_parquet(written_files[0]).set_index("cell_id")
    centroid_df = centroid_df.loc[["cell_1", "cell_2", "cell_3"]]
    assert list(centroid_df["x"]) == [0.0, 1.0, 2.0]
    assert list(centroid_df["z"]) == [10.0, 20.0, 30.0]


def test_yearbook_cluster_attr_synced_for_custom_cluster_key() -> None:
    """Yearbook must sync cluster_attr like Landscape does -- js/celldega.js reads
    `model.get('cluster_attr')` to pick meta_cluster_parquet's key column, and
    without a declared/synced trait it always falls back to 'leiden' regardless
    of what was actually passed in."""
    obs = pd.DataFrame({"my_cluster": ["a", "b", "a"]}, index=["cell_1", "cell_2", "cell_3"])
    adata = AnnData(np.zeros((3, 0)), obs=obs)

    widget = Yearbook(base_url="https://example.org/data", adata=adata, cluster_attr="my_cluster")

    assert widget.cluster_attr == "my_cluster"

    table = pq.read_table(io.BytesIO(widget.meta_cluster_parquet))
    assert "my_cluster" in table.schema.names


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


def test_yearbook_accepts_explicit_cell_list() -> None:
    widget = Yearbook(base_url="https://example.org/data", cells=["cell_1", "cell_2"])

    assert widget.cells == ["cell_1", "cell_2"]


def test_yearbook_query_argument_maps_to_front_end_query() -> None:
    with pytest.warns(DeprecationWarning, match="`query` is deprecated"):
        widget = Yearbook(
            base_url="https://example.org/data",
            query={"gene": "BRCA1"},
        )

    assert widget.front_end_query == {"gene": "BRCA1"}


def test_yearbook_front_end_query_is_accepted_directly() -> None:
    widget = Yearbook(
        base_url="https://example.org/data",
        front_end_query={"cluster": {"attr": "leiden", "value": "5"}},
    )

    assert widget.front_end_query == {"cluster": {"attr": "leiden", "value": "5"}}
