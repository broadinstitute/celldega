"""Showing a Landscape's cells by another attribute: its ``cell_attr`` columns, or
label sets that name its clusters (Clustergram cell types, Clerk's proposals)."""

import json
import warnings

import numpy as np
import pandas as pd
import pytest


try:
    import anndata as ad

    from celldega.clust import Matrix
    from celldega.viz import Clerk, Clustergram, Landscape, link_clerk, spatial_clustergram
except Exception as e:  # pragma: no cover
    pytest.skip(f"celldega viz unavailable: {e}", allow_module_level=True)


def _landscape(**kwargs) -> Landscape:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return Landscape(base_url="https://example.com/data", **kwargs)


def _clustergram() -> Clustergram:
    df = pd.DataFrame(np.ones((2, 3)), index=["MUC2", "TFF3"], columns=["4", "7", "9"])
    mat = Matrix(df)
    mat.cluster()
    cgm = Clustergram(matrix=mat)
    cgm.col_names = ["4", "7", "9"]
    return cgm


def _manual(cgm, attribute, values, colors=None):
    """What the browser syncs back after the category editor or set_categories."""
    cgm.manual_cat = json.dumps({"col": {attribute: {"values": values, "colors": colors or {}}}})


def test_set_labels_adds_replaces_and_removes_a_set() -> None:
    ls = _landscape()
    ls.set_labels("cell_type", {"4": "Goblet", 7: "Goblet", "9": ""}, {"Goblet": "#00ff00"})
    assert ls.label_sets == {
        "cell_type": {"labels": {"4": "Goblet", "7": "Goblet"}, "colors": {"Goblet": "#00ff00"}}
    }
    ls.set_labels("cell_type", {"4": "Enterocyte"})
    assert ls.label_sets == {"cell_type": {"labels": {"4": "Enterocyte"}}}
    ls.set_labels("cell_type", None)
    assert ls.label_sets == {}
    with pytest.raises(ValueError, match="needs a name"):
        ls.set_labels("", {"4": "x"})


def test_apply_state_shows_cells_by_an_attribute() -> None:
    ls = _landscape()
    sent = []
    ls.send = sent.append
    assert ls.apply_state({"cell_attribute": "cell_type"}) == ["showed cells by cell_type"]
    assert sent[-1]["changes"] == {"cell_attribute": "cell_type"}
    assert ls.apply_state({"cell_attribute": ""}) == ["showed cells by cluster"]
    with pytest.raises(ValueError, match="cell_attribute must be a string"):
        ls.apply_state({"cell_attribute": None})


def test_clustergram_cell_types_become_landscape_label_sets() -> None:
    ls, cgm = _landscape(), _clustergram()
    spatial_clustergram(ls, cgm)
    assert ls.label_sets == {}
    _manual(cgm, "cell_type", {"4": "Goblet", "7": "Goblet", "9": "N.A."}, {"Goblet": "#0f0"})
    assert ls.label_sets == {
        "cell_type": {"labels": {"4": "Goblet", "7": "Goblet"}, "colors": {"Goblet": "#0f0"}}
    }
    # Edited, then removed in the Clustergram: so on the Landscape.
    _manual(cgm, "cell_type", {"4": "Enterocyte"})
    assert ls.label_sets["cell_type"]["labels"] == {"4": "Enterocyte"}
    cgm.manual_cat = "{}"
    assert ls.label_sets == {}
    # Sets from elsewhere are left alone.
    ls.set_labels("mine", {"9": "Plasma"})
    _manual(cgm, "cell_type", {"4": "Goblet"})
    cgm.manual_cat = "{}"
    assert set(ls.label_sets) == {"mine"}


def test_clerk_cell_types_become_a_label_set_until_the_clustergram_has_them() -> None:
    ls, cgm = _landscape(), _clustergram()
    clerk = Clerk(landscape=ls, clustergram=cgm, capture_on_select=False)
    clerk.label_clustergram = False
    clerk._record_findings(
        {"cell_types": [{"cluster": "4", "label": "Goblet"}, {"cluster": "7", "label": "Tuft"}]},
        "What are 4 and 7?",
    )
    assert ls.label_sets["clerk_cell_type"] == {"labels": {"4": "Goblet", "7": "Tuft"}}
    # A later proposal wins.
    clerk._record_findings({"cell_types": [{"cluster": "7", "label": "Goblet"}]}, "And 7?")
    assert ls.label_sets["clerk_cell_type"]["labels"] == {"4": "Goblet", "7": "Goblet"}

    # Accepted into the Clustergram (LABEL), its version (with edits) is shown.
    spatial_clustergram(ls, cgm)
    _manual(cgm, "clerk_cell_type", {"4": "Goblet", "7": "Goblet (edited)"})
    clerk._record_findings({"cell_types": [{"cluster": "9", "label": "Plasma"}]}, "9?")
    assert ls.label_sets["clerk_cell_type"]["labels"] == {"4": "Goblet", "7": "Goblet (edited)"}


def test_a_reopened_case_offers_its_cell_types(tmp_path) -> None:
    clerk = Clerk()
    clerk.output_dir = tmp_path
    clerk._record_findings({"cell_types": [{"cluster": "4", "label": "Goblet"}]}, "q")
    clerk.messages = [{"role": "user", "content": "q"}]
    path = clerk.save_conversation(tmp_path / "case.json")
    ls = _landscape()
    Clerk(clerk_files=path, landscape=ls)
    assert ls.label_sets == {"clerk_cell_type": {"labels": {"4": "Goblet"}}}


def test_anndata_cell_attr_colors_come_from_uns() -> None:
    obs = pd.DataFrame(
        {
            "leiden": pd.Categorical(["0", "1", "0"]),
            "cell_type": pd.Categorical(["B", "T", "B"]),
            "batch": ["x", "y", "x"],  # not categorical: no stored palette
        },
        index=["c1", "c2", "c3"],
    )
    adata = ad.AnnData(np.ones((3, 2), dtype=np.float32), obs=obs)
    adata.var_names = ["g1", "g2"]
    adata.uns["cell_type_colors"] = ["#0000ff", "#ff0000"]
    adata.uns["batch_colors"] = ["#111111", "#222222"]
    ls = _landscape(adata=adata, cell_attr=["leiden", "cell_type", "batch"])
    assert ls.cell_attr_colors == {"cell_type": {"B": "#0000ff", "T": "#ff0000"}}
    assert ls.cell_attribute == ""


def test_link_clerk_shares_cell_types_with_a_landscape_linked_later() -> None:
    clerk = Clerk()
    clerk._record_findings({"cell_types": [{"cluster": "4", "label": "Goblet"}]}, "q")
    ls = _landscape()
    link_clerk(clerk, landscape=ls, capture_on_select=False)
    assert ls.label_sets["clerk_cell_type"]["labels"] == {"4": "Goblet"}
