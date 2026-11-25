"""A Clustergram with several matrices: Clustergram(matrix={name: Matrix})."""

import json

from ipywidgets.widgets.widget import _remove_buffers
import numpy as np
import pandas as pd
import pytest
import traitlets

from celldega.clust import Matrix
from celldega.viz import Clustergram
from celldega.viz.reopen import from_png
from celldega.viz.screenshots import widget_source


CLUSTERS = ["0", "1", "2", "3"]


def _expression(name="expr_multi"):
    rng = np.random.default_rng(0)
    data = pd.DataFrame(rng.random((6, 4)), index=[f"GENE{i}" for i in range(6)], columns=CLUSTERS)
    matrix = Matrix(data, name=name, description="Mean expression per cluster.")
    matrix.set_size_matrix(data / 2)
    matrix.cluster()
    return matrix


def _enrichment(name="nhood_multi"):
    rng = np.random.default_rng(1)
    z = rng.normal(size=(4, 4))
    data = pd.DataFrame((z + z.T) / 2, index=CLUSTERS, columns=CLUSTERS)
    matrix = Matrix(
        data,
        row_entity="cluster",
        col_entity="cluster",
        name=name,
        description="Neighborhood enrichment z-scores.",
    )
    matrix.cluster()
    return matrix


@pytest.fixture
def matrices():
    return {"Gene expression": _expression(), "Neighborhood enrichment": _enrichment()}


def test_several_matrices_sync_their_data_and_start_on_the_first(matrices):
    cgm = Clustergram(matrix=matrices)

    assert cgm.matrix_names == ["Gene expression", "Neighborhood enrichment"]
    assert cgm.active_matrix == "Gene expression"
    assert cgm.get_matrix() is matrices["Gene expression"]
    entries = {entry["name"]: entry for entry in cgm.matrices}
    assert entries["Gene expression"]["description"] == "Mean expression per cluster."
    assert entries["Gene expression"]["viz_mode"] == "dotplot"
    assert entries["Neighborhood enrichment"]["viz_mode"] == "heatmap"
    assert json.loads(entries["Neighborhood enrichment"]["row_entity"])["entity"] == "cell"
    assert all(isinstance(entry["mat"], bytes) and entry["mat"] for entry in cgm.matrices)
    # The data travel once, in `matrices`; the single-matrix traits stay empty.
    assert cgm.mat_parquet == b""
    assert cgm.viz_mode == "dotplot"
    # Sent to the browser as binary buffers, not JSON.
    _, paths, _ = _remove_buffers(cgm.get_state())
    assert ["matrices", 1, "mat"] in paths


def test_active_matrix_chooses_and_switches(matrices):
    cgm = Clustergram(matrix=matrices, active_matrix="Neighborhood enrichment")
    assert cgm.get_matrix() is matrices["Neighborhood enrichment"]
    assert json.loads(cgm.row_entity)["entity"] == "cell"

    cgm.active_matrix = "Gene expression"
    assert cgm.get_matrix() is matrices["Gene expression"]
    assert json.loads(cgm.row_entity)["entity"] == "gene"
    assert cgm.network_meta["name"] == "expr_multi"
    with pytest.raises(traitlets.TraitError, match="unknown matrix"):
        cgm.active_matrix = "Spatial"
    with pytest.raises(ValueError, match="not one of the matrices"):
        Clustergram(matrix=matrices, active_matrix="Spatial", name="other")
    with pytest.raises(ValueError, match="needs several matrices"):
        Clustergram(matrix=_expression("expr_single"), active_matrix="Gene expression")


def test_one_matrix_in_a_dict_is_a_plain_clustergram():
    cgm = Clustergram(matrix={"Only": _expression("expr_only")})
    assert cgm.matrix_names == []
    assert cgm.active_matrix == ""
    assert cgm.mat_parquet != b""
    with pytest.raises(traitlets.TraitError, match="one matrix"):
        cgm.active_matrix = "Only"


def test_apply_state_switches_and_checks_names_of_the_target_matrix(matrices):
    cgm = Clustergram(matrix=matrices)
    sent = []
    cgm.send = sent.append
    cgm.row_names = list(matrices["Gene expression"].data.index)

    done = cgm.apply_state({"matrix": "Neighborhood enrichment", "focus_gene": "2"})
    assert done[0] == "matrix -> Neighborhood enrichment"
    assert cgm.active_matrix == "Neighborhood enrichment"
    assert sent[-1]["changes"]["matrix"] == "Neighborhood enrichment"

    # Names are checked against the matrix the changes apply to.
    with pytest.raises(ValueError, match="not a row"):
        cgm.apply_state({"matrix": "Gene expression", "focus_gene": "2"})
    with pytest.raises(ValueError, match="unknown matrix"):
        cgm.apply_state({"matrix": "Spatial"})
    single = Clustergram(matrix=_expression("expr_single_apply"))
    with pytest.raises(ValueError, match="one matrix"):
        single.apply_state({"matrix": "Gene expression"})


def test_categories_stay_in_the_first_matrix(matrices):
    cgm = Clustergram(matrix=matrices, active_matrix="Neighborhood enrichment")
    cgm.send = lambda message: None
    cgm.set_categories({"1": "Podocyte"}, attribute="cell_type")
    assert cgm.manual_cat_dict["col"]["cell_type"]["values"] == {"1": "Podocyte"}
    with pytest.raises(ValueError, match="not row names"):
        # Rows of the first matrix are genes, not clusters.
        cgm.set_categories({"1": "x"}, axis="row", attribute="info")


def test_same_matrices_replace_each_other_but_other_sets_do_not(matrices):
    first = Clustergram(matrix=matrices)
    second = Clustergram(matrix=matrices)
    other = Clustergram(matrix={"Gene expression": matrices["Gene expression"]})
    assert first._registry_key == second._registry_key == "expr_multi|nhood_multi"
    assert other._registry_key == "expr_multi"


def test_matrix_description_is_saved_with_the_store(tmp_path):
    matrix = _enrichment("nhood_store")
    assert matrix.export_viz_parquet()["meta"]["description"].startswith("Neighborhood")
    matrix.write_zarr(tmp_path / "nhood.zarr")
    assert Matrix.read_zarr(tmp_path / "nhood.zarr").description == matrix.description


def test_saved_views_record_and_reopen_every_matrix(tmp_path):
    expression = _expression("expr_reopen")
    enrichment = _enrichment("nhood_reopen")
    expression.write_zarr(tmp_path / "expr.zarr")
    enrichment.write_zarr(tmp_path / "nhood.zarr")
    stored = {
        "Gene expression": Matrix.read_zarr(tmp_path / "expr.zarr"),
        "Neighborhood enrichment": Matrix.read_zarr(tmp_path / "nhood.zarr"),
    }
    cgm = Clustergram(matrix=stored, active_matrix="Neighborhood enrichment", name="reopen")

    source = widget_source(cgm)
    assert [item["name"] for item in source["matrices"]] == list(stored)
    assert source["matrices"][1]["description"].startswith("Neighborhood")
    assert source["active_matrix"] == "Neighborhood enrichment"
    assert source["options"]["matrices"][0]["url"].endswith("expr.zarr")
    assert source["requires_data"] is False

    # In memory only: reopening needs the matrices passed again.
    in_memory = widget_source(Clustergram(matrix={"A": _expression("a"), "B": _enrichment("b")}))
    assert in_memory["requires_data"] is True
    assert "url" not in in_memory["options"]


def test_from_png_rebuilds_several_matrices(tmp_path, monkeypatch):
    expression = _expression("expr_png")
    enrichment = _enrichment("nhood_png")
    expression.write_zarr(tmp_path / "expr.zarr")
    enrichment.write_zarr(tmp_path / "nhood.zarr")
    stored = {
        "Gene expression": Matrix.read_zarr(tmp_path / "expr.zarr"),
        "Neighborhood enrichment": Matrix.read_zarr(tmp_path / "nhood.zarr"),
    }
    cgm = Clustergram(matrix=stored, active_matrix="Neighborhood enrichment", name="png")
    snapshot = {
        "schema": "celldega.view",
        "version": 2,
        "kind": "clustergram",
        "source": {"active_matrix": "Neighborhood enrichment"},
        "state": {},
        "identity": {"rows": {"count": 4, "hash": "x"}},
        "viewport": {"width": 500, "height": 500},
    }
    import celldega.viz.reopen as reopen

    monkeypatch.setattr(
        reopen,
        "_png_panel",
        lambda path, panel: ({"source": widget_source(cgm)}, snapshot),
    )
    rebuilt = from_png("view.png")
    assert rebuilt.matrix_names == ["Gene expression", "Neighborhood enrichment"]
    assert rebuilt.active_matrix == "Neighborhood enrichment"
