import json

import anndata as ad
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import traitlets

from celldega.viz import Landscape


@pytest.fixture
def landscape():
    adata = ad.AnnData(np.zeros((3, 2)))
    adata.obs_names = ["a", "b", "c"]
    adata.var_names = ["A", "B"]
    adata.obs["leiden"] = pd.Categorical(["T", "B", "T"])
    adata.obsm["X_umap"] = np.array([[0, 0], [1, 1], [2, 2]])
    widget = Landscape(adata=adata, transform=np.eye(3), nbhd_edit=True)
    yield widget, adata
    widget.close()


def test_xy_configuration_and_selected_subset(landscape):
    widget, adata = landscape
    widget.set_xy("A", "B", scale="linear")
    assert widget.xy_genes == ["A", "B"]
    assert widget.xy_scale == "linear"
    assert widget.landscape_state == "xy"
    widget.highlight_cells(["a", "c"])
    assert widget.get_selected_cells() == ["a", "c"]
    subset = widget.get_selected_cells(adata)
    assert list(subset.obs_names) == ["a", "c"]
    assert not subset.is_view
    widget.set_xy()
    assert widget.xy_genes == []
    with pytest.raises(ValueError, match="Unknown genes"):
        widget.set_xy("missing")
    with pytest.raises(ValueError, match="X gene"):
        widget.set_xy(None, "B")
    with pytest.raises(traitlets.TraitError):
        widget.xy_genes = ["A", "B", "C"]


def test_gate_roundtrip_and_restored_coordinate_space(landscape, tmp_path):
    widget, _ = landscape
    widget.gates = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "gate 1",
                    "cell_ids": ["a", "c"],
                    "coordinate_space": {"kind": "xy", "genes": ["A", "B"], "scale": "log1p"},
                },
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            }
        ],
    }
    path = widget.save_gates(tmp_path / "gates.geojson")
    saved = json.loads(path.read_text())
    widget.gates = {}
    widget.load_gates(path)
    assert widget.gates == saved
    widget.select_gate("gate 1")
    assert widget.xy_genes == ["A", "B"]
    assert widget.landscape_state == "xy"
    assert widget.selected_cells == ["a", "c"]
    # Embedding gates must not flow through the spatial affine observer.
    assert widget.nbhd_geojson == {"type": "FeatureCollection", "features": []}
    assert list(widget.nbhd["name"]) == ["gate 1"]
    assert list(widget.nbhd["space"]) == ["xy"]
    with pytest.raises(ValueError, match="found 0"):
        widget.select_gate("missing")


def test_reject_non_embedding_geojson(landscape, tmp_path):
    widget, _ = landscape
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                        "properties": {},
                    }
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="polygon"):
        widget.load_gates(path)


def test_nbhd_vertex_coordinates_keep_spaces_and_invert_only_physical_affine(landscape, tmp_path):
    widget, _ = landscape
    widget._inv_transform = np.array([[0.5, 0, -5], [0, 1 / 3, -20 / 3], [0, 0, 1]])
    coordinates = [[[10, 20], [12, 20], [12, 23], [10, 20]]]
    widget.gates = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": coordinates},
                "properties": {
                    "name": kind,
                    "cell_ids": ["a"],
                    "coordinate_space": {"kind": kind, "genes": ["A", "B"], "scale": "log1p"},
                },
            }
            for kind in ["spatial", "umap", "xy"]
        ],
    }
    frame = widget.nbhd_polygons.set_index("space")
    pd.testing.assert_frame_equal(widget.nbhd, widget.nbhd_polygons)
    np.testing.assert_allclose(frame.loc["spatial", "x"], [[0, 1, 1, 0]])
    np.testing.assert_allclose(frame.loc["spatial", "y"], [[0, 0, 1, 0]], atol=1e-12)
    assert frame.loc["umap", "x"] == [[10, 12, 12, 10]]
    assert frame.loc["xy", "y"] == [[20, 20, 23, 20]]
    path = widget.save_nbhds(tmp_path / "nbhds.geojson")
    widget.gates = {}
    assert widget.nbhd_polygons.empty
    widget.load_nbhds(path)
    widget.select_nbhd("spatial")
    assert widget.landscape_state == "spatial"
    assert widget.selected_cells == ["a"]
    assert len(widget.nbhd_polygons) == 3


@pytest.mark.parametrize("technology", ["Xenium", "Chromium"])
def test_all_spaces_survive_physical_edits_and_gate_deletion(technology):
    square = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]]}
    physical = {"type": "Feature", "geometry": square, "properties": {"name": "tissue"}}
    initial = gpd.GeoDataFrame.from_features([physical])
    widget = Landscape(nbhd=initial, technology=technology, transform=np.eye(3))
    # Loaded polygons are also available when editing is disabled.
    widget.gates = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": square,
                "properties": {"name": kind, "coordinate_space": {"kind": kind}},
            }
            for kind in ["umap", "xy"]
        ],
    }
    assert list(widget.nbhd["space"]) == ["spatial", "umap", "xy"]
    widget.nbhd_geojson = {"type": "FeatureCollection", "features": []}
    assert list(widget.nbhd["space"]) == ["umap", "xy"]
    widget.nbhd_geojson = {"type": "FeatureCollection", "features": [physical]}
    assert list(widget.nbhd["name"]) == ["tissue", "umap", "xy"]
    widget.gates = {"type": "FeatureCollection", "features": []}
    assert list(widget.nbhd["space"]) == ["spatial"]
    widget.close()


def test_gates_supplied_to_constructor_populate_nbhd():
    gates = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "properties": {"name": "xy gate", "coordinate_space": {"kind": "xy"}},
            }
        ],
    }
    widget = Landscape(gates=gates, transform=np.eye(3))
    assert list(widget.nbhd["name"]) == ["xy gate"]
    widget.close()


@pytest.mark.parametrize("technology", ["Xenium", "Chromium"])
def test_nbhd_frame_can_initialize_another_landscape_without_transforming_embeddings(technology):
    transform = np.array([[2, 0, 10], [0, 3, 20], [0, 0, 1]])
    source = Landscape(technology=technology, transform=transform)
    source.gates = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10, 20], [12, 20], [12, 23], [10, 20]]],
                },
                "properties": {
                    "name": kind,
                    "coordinate_space": {"kind": kind, "genes": ["A", "B"], "scale": "linear"},
                    "cell_ids": ["a", "c"],
                },
            }
            for kind in ["spatial", "umap", "xy"]
        ],
    }
    original = source.nbhd.copy(deep=True)
    restored = Landscape(nbhd=source.nbhd, technology=technology, transform=transform)
    pd.testing.assert_frame_equal(source.nbhd, original)
    result = restored.nbhd.set_index("space")
    for _, row in original.iterrows():
        assert result.loc[row["space"], "geometry"].equals_exact(row.geometry, 1e-12)
        assert result.loc[row["space"], "coordinate_space"] == row.coordinate_space
        assert result.loc[row["space"], "cell_ids"] == row.cell_ids
    assert len(restored.nbhd_geojson["features"]) == 1
    assert len(restored.gates["features"]) == 2
    source.close()
    restored.close()


def test_empty_nbhd_frame_can_initialize_another_landscape(landscape):
    source, _ = landscape
    restored = Landscape(nbhd=source.nbhd, transform=np.eye(3))
    assert restored.nbhd.empty
    restored.close()
