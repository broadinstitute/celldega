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

from celldega.viz.scatterplot_widget import Scatter


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
        widget = Scatter(*args, **kwargs)
        created.append(widget)
        return widget

    yield make
    for widget in created:
        widget.close()


def _points(widget):
    return pq.read_table(io.BytesIO(widget.points_parquet)).to_pandas()


def test_defaults_prefer_umap_and_expose_controls(adata, widgets):
    widget = widgets(adata)
    assert widget.component == "Scatter"
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
        "color_by": "",
        "color_type": "uniform",
        "color_min": None,
        "color_max": None,
        "color_categories": [],
        "color_scale": [],
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
        Scatter(adata)


def test_requires_anndata_and_available_view(adata, widgets):
    with pytest.raises(TypeError, match="AnnData"):
        Scatter(np.ones((3, 2)))
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
        Scatter(adata)


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
    assert json.loads(json.dumps(widget.describe()))["component"] == "Scatter"
    assert widget.get_state(key="component") == {"component": "Scatter"}
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


def _annotation_request(**updates):
    return {
        "request_id": "label-request-1",
        "column": "gate",
        "value": "high",
        "cell_ids": ["cell-a", "cell-c"],
        "color": "#AB12EF",
        **updates,
    }


def test_browser_annotation_uses_captured_ids_and_preserves_current_selection(adata, widgets):
    widget = widgets(adata)
    request = _annotation_request()
    widget.select_cells(["cell-b"])
    widget.annotation_request = request
    assert widget.annotation_result == {
        "request_id": "label-request-1",
        "ok": True,
        "count": 2,
        "column": "gate",
        "value": "high",
    }
    assert widget.get_selection() == ["cell-b"]
    assert adata.obs.gate.loc[["cell-a", "cell-c"]].tolist() == ["high", "high"]
    assert pd.isna(adata.obs.gate.loc["cell-b"])
    assert widget.color_by == "gate"
    assert _points(widget).color.tolist() == ["#ab12ef", "#9ca3af", "#ab12ef"]
    assert adata.uns["gate_colors"] == ["#ab12ef"]
    assert widget.describe()["component"] == "Scatter"


@pytest.mark.parametrize(
    "updates,error",
    [
        ({"request_id": ""}, "request_id"),
        ({"request_id": 2}, "request_id"),
        ({"column": " "}, "column"),
        ({"column": []}, "column"),
        ({"value": ""}, "value"),
        ({"value": " "}, "value"),
        ({"value": 42}, "value"),
        ({"cell_ids": "cell-a"}, "cell_ids"),
        ({"cell_ids": []}, "cell_ids"),
        ({"cell_ids": ["cell-a", "missing"]}, "unknown cell"),
        ({"cell_ids": ["cell-a", 1]}, "string observation"),
        ({"cell_ids": ["cell-a", "cell-a"]}, "unique"),
        ({"color": "red"}, "hex color"),
        ({"color": "#12345g"}, "hex color"),
        ({"color": [1, 2, 3]}, "hex color"),
    ],
)
def test_invalid_browser_annotation_returns_error_without_any_write(adata, widgets, updates, error):
    widget = widgets(adata, color_by="cell_type")
    before_obs = adata.obs.copy()
    before_uns = dict(adata.uns)
    before_state = widget.get_view_state()
    widget.annotation_request = _annotation_request(**updates)
    assert widget.annotation_result["ok"] is False
    assert error in widget.annotation_result["error"]
    pd.testing.assert_frame_equal(adata.obs, before_obs)
    assert dict(adata.uns) == before_uns
    assert widget.get_view_state() == before_state


def test_annotation_rejects_invalid_current_coordinates_before_writing(adata, widgets):
    widget = widgets(adata, view="genes")
    adata.X[0, 0] = np.nan
    before_obs = adata.obs.copy()
    widget.annotation_request = _annotation_request()
    assert not widget.annotation_result["ok"]
    assert "finite" in widget.annotation_result["error"]
    pd.testing.assert_frame_equal(adata.obs, before_obs)
    assert "gate_colors" not in adata.uns
    assert widget.color_by == ""


def test_duplicate_request_id_replays_result_without_reapplying(adata, widgets):
    widget = widgets(adata)
    widget.annotation_request = _annotation_request()
    first_result = widget.annotation_result.copy()
    first_revision = widget.plot_meta["revision"]
    widget.annotation_request = _annotation_request(
        value="different", cell_ids=["cell-b"], color="#000000"
    )
    assert widget.annotation_result == first_result
    assert widget.plot_meta["revision"] == first_revision
    assert adata.obs.gate.loc["cell-a"] == "high"
    assert pd.isna(adata.obs.gate.loc["cell-b"])
    assert adata.uns["gate_colors"] == ["#ab12ef"]


def test_error_request_id_is_also_idempotent(adata, widgets):
    widget = widgets(adata)
    widget.annotation_request = _annotation_request(color="not a color")
    first_result = widget.annotation_result.copy()
    widget.annotation_request = _annotation_request()
    assert widget.annotation_result == first_result
    assert "gate" not in adata.obs


def test_category_color_persists_and_preserves_existing_colors(adata, widgets):
    widget = widgets(adata)
    widget.annotation_request = _annotation_request(column="cell_type", cell_ids=["cell-a"])
    assert widget.annotation_result["ok"]
    assert adata.obs.cell_type.cat.categories.tolist() == ["B", "T", "high"]
    assert adata.uns["cell_type_colors"] == ["#ff0000", "#0000ff", "#ab12ef"]
    second = widgets(adata, color_by="cell_type")
    assert _points(second).color.tolist() == ["#ab12ef", "#ff0000", "#0000ff"]
    widget.annotation_request = _annotation_request(
        request_id="label-request-2",
        column="cell_type",
        value="T",
        cell_ids=["cell-c"],
        color="#345",
    )
    assert adata.uns["cell_type_colors"] == ["#ff0000", "#334455", "#ab12ef"]
    third = widgets(adata, color_by="cell_type")
    assert _points(third).color.tolist() == ["#ab12ef", "#ff0000", "#334455"]


def test_browser_annotation_without_color_and_existing_object_column(adata, widgets):
    adata.obs["gate"] = ["first", "second", "third"]
    widget = widgets(adata)
    request = _annotation_request(cell_ids=["cell-a"])
    del request["color"]
    widget.annotation_request = request
    assert widget.annotation_result["ok"]
    assert adata.obs.gate.tolist() == ["high", "second", "third"]
    assert "gate_colors" not in adata.uns
    assert widget.color_by == "gate"


def test_python_annotation_color_and_invalid_color(adata, widgets):
    widget = widgets(adata)
    widget.select_cells(["cell-a"])
    with pytest.raises(ValueError, match="hex color"):
        widget.annotate_selection("gate", "high", color="bad")
    assert "gate" not in adata.obs
    assert widget.annotate_selection("gate", "high", color="#112233") == 1
    assert adata.uns["gate_colors"] == ["#112233"]
    assert widget.color_by == ""
    widget.color_by = "gate"
    assert _points(widget).color.tolist() == ["#112233", "#9ca3af", "#9ca3af"]


@pytest.mark.parametrize("dtype", ["float64", "int64", "Float64", "Int64"])
def test_real_numeric_obs_uses_continuous_scale(adata, widgets, dtype):
    adata.obs["score"] = pd.Series([0, 5, 10], index=adata.obs_names, dtype=dtype)
    widget = widgets(adata, color_by="score")
    meta = widget.plot_meta
    assert meta["color_type"] == "numeric"
    assert meta["color_by"] == "score"
    assert (meta["color_min"], meta["color_max"]) == (0.0, 10.0)
    assert meta["color_categories"] == []
    assert len(meta["color_scale"]) == 5
    assert _points(widget).color.tolist() == ["#440154", "#21918c", "#fde725"]
    assert "score_colors" not in adata.uns


@pytest.mark.parametrize("values", [[2.0, np.nan, np.inf], [2.0, -np.inf, np.nan]])
def test_numeric_missing_and_nonfinite_values_are_gray(adata, widgets, values):
    adata.obs["score"] = values
    widget = widgets(adata, color_by="score")
    assert widget.plot_meta["color_min"] == widget.plot_meta["color_max"] == 2.0
    assert _points(widget).color.tolist() == ["#21918c", "#9ca3af", "#9ca3af"]
    json.dumps(widget.plot_meta, allow_nan=False)


def test_nullable_numeric_values_and_all_missing_range(adata, widgets):
    adata.obs["score"] = pd.Series([pd.NA, 2, pd.NA], index=adata.obs_names, dtype="Int64")
    widget = widgets(adata, color_by="score")
    assert _points(widget).color.tolist() == ["#9ca3af", "#21918c", "#9ca3af"]
    adata.obs["empty"] = [np.nan, np.inf, -np.inf]
    widget.color_by = "empty"
    assert widget.plot_meta["color_type"] == "numeric"
    assert widget.plot_meta["color_min"] is None
    assert widget.plot_meta["color_max"] is None
    assert _points(widget).color.tolist() == ["#9ca3af"] * 3
    json.dumps(widget.plot_meta, allow_nan=False)


def test_constant_and_extreme_numeric_values_have_valid_colors(adata, widgets):
    adata.obs["constant"] = [1.0, 1.0, 1.0]
    adata.obs["extreme"] = [-1e308, 0.0, 1e308]
    widget = widgets(adata, color_by="constant")
    assert _points(widget).color.tolist() == ["#21918c"] * 3
    widget.color_by = "extreme"
    assert _points(widget).color.tolist() == ["#440154", "#21918c", "#fde725"]


@pytest.mark.parametrize(
    "values",
    [
        [True, False, True],
        pd.array([True, False, None], dtype="boolean"),
        pd.Categorical([1, 2, 1]),
    ],
)
def test_boolean_and_categorical_numeric_obs_use_categories(adata, widgets, values):
    adata.obs["group"] = values
    widget = widgets(adata, color_by="group")
    assert widget.plot_meta["color_type"] == "categorical"
    assert widget.plot_meta["color_min"] is None
    assert widget.plot_meta["color_max"] is None
    assert widget.plot_meta["color_scale"] == []
    assert len(widget.plot_meta["color_categories"]) in (2, 3)


def test_category_metadata_reuses_palette_and_includes_missing(adata, widgets):
    adata.obs.loc["cell-c", "cell_type"] = pd.NA
    widget = widgets(adata, color_by="cell_type")
    assert widget.plot_meta["color_categories"] == [
        {"name": "B", "color": "#ff0000"},
        {"name": "T", "color": "#0000ff"},
        {"name": "N.A.", "color": "#9ca3af"},
    ]
    widget.select_categories(["N.A."])
    assert widget.get_selection() == ["cell-c"]


def test_missing_category_does_not_collide_with_existing_label(adata, widgets):
    adata.obs["group"] = ["N.A.", None, "T"]
    widget = widgets(adata, color_by="group")
    labels = [category["name"] for category in widget.plot_meta["color_categories"]]
    assert labels == ["N.A.", "T", "N.A. (missing)"]
    widget.select_categories(["N.A."])
    assert widget.get_selection() == ["cell-a"]
    widget.select_categories(["N.A. (missing)"])
    assert widget.get_selection() == ["cell-b"]


def test_selecting_multiple_categories_unions_cells_and_survives_axes(adata, widgets):
    widget = widgets(adata, color_by="cell_type")
    widget.select_categories(["T", "T"])
    assert widget.selected_categories == ["T"]
    assert widget.get_selection() == ["cell-a", "cell-c"]
    widget.select_categories(["B"], additive=True)
    assert widget.selected_categories == ["T", "B"]
    assert widget.get_selection() == adata.obs_names.tolist()
    widget.set_axes("GeneC", "GeneB")
    assert widget.selected_categories == ["T", "B"]
    assert widget.get_view_state()["selected_categories"] == ["T", "B"]
    widget.select_categories([])
    assert widget.get_selection() == []


def test_category_selection_from_constructor_and_direct_trait(adata, widgets):
    widget = widgets(adata, color_by="cell_type", selected_categories=["T"])
    assert widget.get_selection() == ["cell-a", "cell-c"]
    widget.selected_categories = ["B", "T"]
    assert widget.get_selection() == adata.obs_names.tolist()


def test_invalid_category_selection_is_atomic(adata, widgets):
    adata.obs["score"] = [1.0, 2.0, 3.0]
    widget = widgets(adata, color_by="cell_type")
    widget.select_categories(["T"])
    before = widget.get_view_state()
    with pytest.raises(ValueError, match="unknown categories"):
        widget.select_categories(["B", "missing"])
    assert widget.get_view_state() == before
    with pytest.raises(TypeError, match="sequence"):
        widget.select_categories("T")
    widget.color_by = "score"
    with pytest.raises(ValueError, match="categorical color_by"):
        widget.select_categories(["1.0"])
    widget.color_by = ""
    with pytest.raises(ValueError, match="categorical color_by"):
        widget.select_categories(["T"])


def test_manual_selection_and_color_changes_clear_categories_preserving_ids(adata, widgets):
    widget = widgets(adata, color_by="cell_type")
    widget.select_categories(["T"])
    widget.select_cells(["cell-b"])
    assert widget.selected_categories == []
    assert widget.get_selection() == ["cell-b"]
    widget.select_categories(["T"])
    widget.color_by = ""
    assert widget.selected_categories == []
    assert widget.get_selection() == ["cell-a", "cell-c"]
    widget.select_categories([])
    assert widget.get_selection() == []


def test_browser_category_and_cell_batch_preserves_matching_categories(adata, widgets):
    widget = widgets(adata, color_by="cell_type")
    widget.set_state({"selected_categories": ["T"], "selected_cells": ["cell-a", "cell-c"]})
    assert widget.selected_categories == ["T"]
    assert widget.get_selection() == ["cell-a", "cell-c"]


def test_annotation_clears_categories_without_changing_selected_cells(adata, widgets):
    widget = widgets(adata, color_by="cell_type")
    widget.select_categories(["T"])
    widget.annotation_request = _annotation_request(column="cell_type", cell_ids=["cell-a"])
    assert widget.annotation_result["ok"]
    assert widget.selected_categories == []
    assert widget.get_selection() == ["cell-a", "cell-c"]
