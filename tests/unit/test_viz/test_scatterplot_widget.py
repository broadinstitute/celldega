"""Behavioral tests for AnnData scatterplots and their linked widget API."""

import io
import json

from anndata import AnnData, read_h5ad
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from scipy import sparse
from traitlets import TraitError

from celldega.viz.scatterplot_widget import Scatterplot


@pytest.fixture
def adata():
    data = AnnData(
        X=np.array([[0.0, 2.0, 8.0], [1.0, 4.0, 4.0], [3.0, 6.0, 0.0]]),
        obs=pd.DataFrame(
            {"cell_type": pd.Categorical(["T", "B", "T"])},
            index=["cell-a", "cell-b", "cell-c"],
        ),
        var=pd.DataFrame(index=["GeneA", "GeneB", "GeneC"]),
    )
    data.obsm["X_umap"] = np.array([[-2.0, 1.0], [0.0, 2.0], [2.0, 3.0]])
    data.obsm["spatial"] = np.array([[100.0, 300.0], [200.0, 250.0], [300.0, 100.0]])
    data.layers["counts"] = data.X * 10
    data.uns["cell_type_colors"] = ["#ff0000", "#0000ff"]
    return data


@pytest.fixture
def widgets():
    created = []

    def make(*args, **kwargs):
        widget = Scatterplot(*args, **kwargs)
        created.append(widget)
        return widget

    yield make
    for widget in created:
        widget.close()


def _points(widget):
    return pq.read_table(io.BytesIO(widget.points_parquet)).to_pandas()


def test_defaults_prefer_umap_and_expose_controls(adata, widgets):
    widget = widgets(adata)
    assert widget.component == "Scatterplot"
    assert widget.view == "umap"
    assert widget.available_views == ["umap", "spatial", "genes"]
    assert widget.gene_names == ["GeneA", "GeneB", "GeneC"]
    assert widget.layers == ["counts"]
    assert widget.obs_columns == ["cell_type"]
    assert widget.plot_meta == {
        "view": "umap",
        "x_label": "UMAP 1",
        "y_label": "UMAP 2",
        "x_nonnegative": False,
        "y_nonnegative": True,
        "n_cells": 3,
        "revision": 1,
    }
    points = _points(widget)
    assert list(points.columns) == ["cell_id", "x", "y", "color", "label"]
    assert points.cell_id.tolist() == adata.obs_names.tolist()
    np.testing.assert_array_equal(points[["x", "y"]], adata.obsm["X_umap"])


def test_default_falls_back_to_spatial_then_genes(adata, widgets):
    del adata.obsm["X_umap"]
    assert widgets(adata).view == "spatial"
    del adata.obsm["spatial"]
    widget = widgets(adata)
    assert widget.view == "genes"
    assert (widget.x, widget.y) == ("GeneA", "GeneB")


def test_explicit_axes_layers_and_repeated_gene(adata, widgets):
    widget = widgets(adata, view="genes", x="GeneC", y="GeneA", layer="counts")
    np.testing.assert_array_equal(_points(widget)[["x", "y"]], adata.layers["counts"][:, [2, 0]])
    widget.set_axes("GeneB", "GeneB", layer="")
    np.testing.assert_array_equal(_points(widget)[["x", "y"]], adata.X[:, [1, 1]])


@pytest.mark.parametrize("matrix_type", [sparse.csr_matrix, sparse.csc_matrix])
def test_sparse_extracts_only_requested_columns(adata, widgets, monkeypatch, matrix_type):
    expected = adata.X[:, [2, 0]].copy()
    adata.X = matrix_type(adata.X)
    original = matrix_type.toarray
    shapes = []

    def toarray(self, *args, **kwargs):
        shapes.append(self.shape)
        assert self.shape[1] <= 2, "full expression matrix must not be densified"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(matrix_type, "toarray", toarray)
    widget = widgets(adata, view="genes", x="GeneC", y="GeneA")
    np.testing.assert_array_equal(_points(widget)[["x", "y"]], expected)
    assert shapes == [(3, 2)]
    widget.set_axes(y="GeneC")
    assert shapes[-1] == (3, 1)


@pytest.mark.parametrize("sparse_x", [False, True])
def test_backed_gene_reads_and_selection_copy(adata, widgets, tmp_path, sparse_x):
    expected = adata.X[:, [2, 0]].copy()
    if sparse_x:
        adata.X = sparse.csr_matrix(adata.X)
    path = tmp_path / "cells.h5ad"
    adata.write_h5ad(path)
    backed = read_h5ad(path, backed="r")
    try:
        widget = widgets(backed, view="genes", x="GeneC", y="GeneA")
        np.testing.assert_array_equal(_points(widget)[["x", "y"]], expected)
        widget.select_cells(["cell-c", "cell-a"])
        subset = widget.get_selection(as_adata=True)
        assert subset.obs_names.tolist() == ["cell-c", "cell-a"]
        assert not subset.isbacked
        assert not subset.is_view
    finally:
        backed.file.close()


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("x", "missing"),
        ("y", "missing"),
        ("layer", "missing"),
        ("color_by", "missing"),
        ("view", "invalid"),
    ],
)
def test_invalid_trait_does_not_change_plot(adata, widgets, attribute, value):
    widget = widgets(adata, view="genes")
    before = widget.get_view_state()
    payload = widget.points_parquet
    with pytest.raises((ValueError, TypeError, TraitError)):
        setattr(widget, attribute, value)
    assert widget.get_view_state() == before
    assert widget.points_parquet == payload


def test_invalid_second_axis_is_atomic(adata, widgets):
    widget = widgets(adata)
    before = widget.get_view_state()
    with pytest.raises(ValueError, match="unknown y gene"):
        widget.set_axes("GeneC", "unknown")
    assert widget.get_view_state() == before


def test_invalid_data_change_is_atomic(adata, widgets):
    widget = widgets(adata, view="genes", x="GeneA", y="GeneB")
    adata.X[0, 2] = np.nan
    before = widget.get_view_state()
    with pytest.raises(ValueError, match="finite"):
        widget.x = "GeneC"
    assert widget.get_view_state() == before


@pytest.mark.parametrize("names", ["obs_names", "var_names"])
def test_duplicate_names_rejected(adata, names):
    setattr(adata, names, ["duplicate"] * 3)
    with pytest.raises(ValueError, match="must be unique"):
        Scatterplot(adata)


def test_requires_anndata_and_available_view(adata, widgets):
    with pytest.raises(TypeError, match="AnnData"):
        Scatterplot(np.ones((3, 2)))
    del adata.obsm["X_umap"]
    with pytest.raises(ValueError, match="unavailable"):
        widgets(adata, view="umap")


def test_embedding_without_genes_supported(widgets):
    adata = AnnData(obs=pd.DataFrame(index=["a", "b"]))
    adata.obsm["spatial"] = np.array([[1, 2], [3, 4]])
    widget = widgets(adata)
    assert widget.available_views == ["spatial"]
    np.testing.assert_array_equal(_points(widget)[["x", "y"]], adata.obsm["spatial"])
    with pytest.raises(ValueError, match="unavailable"):
        widget.set_view("genes")


@pytest.mark.parametrize("coords", [np.ones((3, 1)), np.array([[0, 1], [2, np.inf], [3, 4]])])
def test_invalid_embedding_rejected(adata, coords):
    adata.obsm["X_umap"] = coords
    with pytest.raises(ValueError, match=r"two coordinate|finite"):
        Scatterplot(adata)


def test_absent_expression_can_use_a_layer(adata, widgets):
    adata.X = None
    with pytest.raises(ValueError, match=r"require adata\.X"):
        widgets(adata, view="genes")
    assert widgets(adata, view="genes", layer="counts").plot_meta["n_cells"] == 3


def test_scale_changes_retain_payload_and_negative_axes_reset(adata, widgets):
    widget = widgets(adata, view="genes")
    payload = widget.points_parquet
    revision = widget.plot_meta["revision"]
    widget.set_scale("log1p")
    assert (widget.x_scale, widget.y_scale) == ("log1p", "log1p")
    assert widget.points_parquet == payload
    assert widget.plot_meta["revision"] == revision
    widget.set_view("umap")
    assert (widget.x_scale, widget.y_scale) == ("linear", "log1p")
    with pytest.raises(ValueError, match="nonnegative"):
        widget.x_scale = "log1p"
    with pytest.raises(ValueError, match="nonnegative"):
        widgets(adata, x_scale="log1p")


def test_scale_method_validates_both_before_updating(adata, widgets):
    widget = widgets(adata)
    with pytest.raises(ValueError, match="nonnegative"):
        widget.set_scale(x="log1p", y="log1p")
    assert (widget.x_scale, widget.y_scale) == ("linear", "linear")


def test_selection_validates_identity_and_survives_views(adata, widgets):
    widget = widgets(adata)
    widget.highlight_cells(["cell-c", "cell-a", "cell-c"])
    assert widget.get_selection() == ["cell-c", "cell-a"]
    widget.set_axes("GeneC", "GeneB")
    widget.set_view("spatial")
    assert widget.get_selection() == ["cell-c", "cell-a"]
    with pytest.raises(ValueError, match="unknown cell"):
        widget.select_cells(["missing"])
    with pytest.raises(TypeError, match="sequence"):
        widget.select_cells("cell-a")
    assert widget.get_selection() == ["cell-c", "cell-a"]
    copied = widget.get_selection(as_adata=True)
    copied.obs["new"] = "label"
    assert "new" not in adata.obs
    widget.select_cells([])
    assert widget.get_selection(as_adata=True).n_obs == 0


@pytest.mark.parametrize(
    "event",
    [
        {"type": "row_label", "value": {"name": "GeneC", "entity": "gene", "attr": "name"}},
        {"type": "row_label", "value": "GeneC"},
        {"click_type": "row-label", "click_value": {"name": "GeneC"}},
    ],
)
def test_linked_gene_events_choose_y_axis(adata, widgets, event):
    widget = widgets(adata)
    widget.update_trigger = event
    assert (widget.view, widget.x, widget.y) == ("genes", "GeneA", "GeneC")


def test_unknown_linked_events_are_ignored(adata, widgets):
    widget = widgets(adata)
    before = widget.get_view_state()
    for event in [
        {"type": "row_label", "value": {"name": "missing"}},
        {"type": "row_label", "value": {"name": "GeneC", "entity": "cell"}},
        {"type": "row_label", "value": []},
    ]:
        widget.update_trigger = event
        assert widget.get_view_state() == before


def test_annotation_is_explicit_and_missing_column_preserves_unselected(adata, widgets):
    original = adata.obs.copy()
    widget = widgets(adata)
    widget.select_cells(["cell-a", "cell-c"])
    pd.testing.assert_frame_equal(adata.obs, original)
    assert widget.annotate_selection("gate", "positive") == 2
    assert adata.obs.loc["cell-a", "gate"] == "positive"
    assert adata.obs.loc["cell-c", "gate"] == "positive"
    assert pd.isna(adata.obs.loc["cell-b", "gate"])
    assert "gate" in widget.obs_columns
    widget.select_cells([])
    assert widget.annotate_selection("unused", "label") == 0
    assert "unused" not in adata.obs


def test_categorical_annotation_refreshes_colors(adata, widgets):
    widget = widgets(adata, color_by="cell_type")
    points = _points(widget)
    assert points.color.tolist() == ["#0000ff", "#ff0000", "#0000ff"]
    widget.select_cells(["cell-a"])
    revision = widget.plot_meta["revision"]
    widget.annotate_selection("cell_type", "new type")
    assert isinstance(adata.obs.cell_type.dtype, pd.CategoricalDtype)
    assert adata.obs.cell_type.tolist() == ["new type", "B", "T"]
    assert _points(widget).label.tolist() == ["new type", "B", "T"]
    assert widget.plot_meta["revision"] == revision + 1


def test_annotation_rejects_invalid_inputs(adata, widgets):
    widget = widgets(adata)
    with pytest.raises(ValueError, match="nonempty"):
        widget.annotate_selection("", "value")
    with pytest.raises(TypeError, match="scalar"):
        widget.annotate_selection("gate", ["a", "b"])


def test_agent_methods_and_ipywidget_serialization(adata, widgets):
    widget = widgets(adata)
    assert json.loads(json.dumps(widget.describe()))["component"] == "Scatterplot"
    assert widget.get_state(key="component") == {"component": "Scatterplot"}
    assert widget.request_raster() == 1
    assert widget.request_raster() == 2


def test_close_and_named_replacement_stop_linked_updates(adata, widgets):
    first = widgets(adata, name="scatterplot-replacement-test")
    second = widgets(adata, name="scatterplot-replacement-test")
    assert first.comm is None
    assert first._closed
    first.update_trigger = {"type": "row_label", "value": {"name": "GeneC"}}
    assert first.view == "umap"
    second.close()
    assert second.comm is None
    second.close()
