import json

import anndata as ad
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
