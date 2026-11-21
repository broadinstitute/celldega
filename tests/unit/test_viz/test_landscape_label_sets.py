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


def _record(clerk, *pairs):
    clerk._record_findings(
        {"cell_types": [{"cluster": c, "label": label} for c, label in pairs]}, "q"
    )


def test_clerk_and_manual_labels_share_one_clustergram_category() -> None:
    """Clerk's cell types go into the Clustergram's manual column category (the one
    the scientist edits), which the Landscape shows; the scientist's labels win."""
    ls, cgm = _landscape(), _clustergram()
    cgm.manual_col_cat = True
    clerk = Clerk(capture_on_select=False)
    spatial_clustergram(ls, cgm, clerk=clerk)
    cgm.send = lambda msg: None  # no browser

    _record(clerk, ("4", "Goblet"), ("7", "Tuft"))
    manual = cgm.manual_cat_dict["col"]
    assert manual == {"manual_cat": {"values": {"4": "Goblet", "7": "Tuft"}, "colors": {}}}
    assert ls.label_sets == {"manual_cat": {"labels": {"4": "Goblet", "7": "Tuft"}}}

    # The scientist relabels 7; Clerk's next proposal for 7 doesn't overwrite it.
    cgm.set_categories({"7": "My tuft"})
    _record(clerk, ("7", "Enteroendocrine"), ("9", "Plasma"))
    assert ls.label_sets["manual_cat"]["labels"] == {"4": "Goblet", "7": "My tuft", "9": "Plasma"}


def test_without_a_clustergram_clerk_cell_types_are_a_label_set() -> None:
    ls = _landscape()
    clerk = Clerk(landscape=ls, capture_on_select=False)
    _record(clerk, ("4", "Goblet"), ("7", "Tuft"))
    _record(clerk, ("7", "Goblet"))  # a later proposal wins
    assert ls.label_sets == {"clerk_cell_type": {"labels": {"4": "Goblet", "7": "Goblet"}}}


@pytest.mark.parametrize("kind", ["conversation", "report"])
def test_a_reopened_case_restores_its_annotations(tmp_path, kind) -> None:
    ls, cgm = _landscape(), _clustergram()
    cgm.manual_col_cat = "cell_type"
    clerk = Clerk(capture_on_select=False)
    clerk.output_dir = tmp_path
    spatial_clustergram(ls, cgm, clerk=clerk)
    cgm.send = lambda msg: None
    _record(clerk, ("4", "Goblet"), ("7", "Tuft"))
    cgm.set_categories({"7": "My tuft", "9": "Plasma"}, colors={"Plasma": "#ff00ff"})
    clerk.messages = [*clerk.messages, {"role": "user", "content": "q"}]
    path = (
        clerk.save_conversation(tmp_path / "case.json")
        if kind == "conversation"
        else clerk.export(title="Case", html=False)["record"]
    )

    # A fresh session: the Clustergram isn't displayed yet when the case opens.
    ls2, cgm2 = _landscape(), _clustergram()
    cgm2.manual_col_cat = "cell_type"
    sent = []
    cgm2.send = sent.append
    reopened = Clerk(clerk_files=path, landscape=ls2, clustergram=cgm2)
    spatial_clustergram(ls2, cgm2, clerk=reopened)
    expected = {"4": "Goblet", "7": "My tuft", "9": "Plasma"}
    # In its synced state (shown when it is displayed) and sent to a displayed one.
    assert cgm2.manual_cat_dict["col"]["cell_type"]["values"] == expected
    assert cgm2.manual_cat_dict["col"]["cell_type"]["colors"] == {"Plasma": "#ff00ff"}
    assert [m["values"] for m in sent if m["event"] == "set_categories"] == [expected]
    assert ls2.label_sets["cell_type"]["labels"] == expected
    # Which labels are Clerk's survives: its next proposal for 7 leaves yours.
    _record(reopened, ("7", "Enteroendocrine"), ("4", "Enterocyte"))
    assert cgm2.manual_cat_dict["col"]["cell_type"]["values"] == {
        "4": "Enterocyte",
        "7": "My tuft",
        "9": "Plasma",
    }


def test_a_case_saved_without_annotations_labels_the_clustergram(tmp_path) -> None:
    clerk = Clerk()
    _record(clerk, ("4", "Goblet"))
    clerk.messages = [{"role": "user", "content": "q"}]
    path = clerk.save_conversation(tmp_path / "old.json")
    data = json.loads(path.read_text())
    data.pop("annotations")
    path.write_text(json.dumps(data))
    ls, cgm = _landscape(), _clustergram()
    cgm.send = lambda msg: None
    reopened = Clerk(clerk_files=path, landscape=ls, clustergram=cgm)
    spatial_clustergram(ls, cgm, clerk=reopened)
    assert cgm.manual_cat_dict["col"]["clerk_cell_type"]["values"] == {"4": "Goblet"}
    assert ls.label_sets == {"clerk_cell_type": {"labels": {"4": "Goblet"}}}


def test_set_categories_before_display_shows_when_displayed() -> None:
    cgm = _clustergram()
    cgm.send = lambda msg: None
    cgm.set_categories({"4": "Goblet"}, attribute="cell_type", colors={"Goblet": "#00ff00"})
    cgm.set_categories({"7": "Tuft", "4": None})
    assert cgm.manual_col_cat == "cell_type"
    assert json.loads(cgm.manual_cat_config)["col"]["attribute"] == "cell_type"
    assert cgm.manual_cat_dict["col"] == {
        "cell_type": {"values": {"7": "Tuft"}, "colors": {"Goblet": "#00ff00"}}
    }
    cgm.set_categories({"9": "Plasma"}, replace=True)
    assert cgm.manual_cat_dict["col"]["cell_type"]["values"] == {"9": "Plasma"}


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


def test_manual_category_flags_name_the_category() -> None:
    """``True`` turns manual categories on under the default name, not "True"."""
    df = pd.DataFrame(np.ones((2, 3)), index=["a", "b"], columns=["4", "7", "9"])
    mat = Matrix(df)
    mat.cluster()
    config = json.loads(
        Clustergram(matrix=mat, manual_row_cat=True, manual_col_cat="cell_type").manual_cat_config
    )
    assert config["row"]["attribute"] == "manual_cat"
    assert config["col"]["attribute"] == "cell_type"
    assert Clustergram(matrix=mat).manual_cat_config == "{}"
