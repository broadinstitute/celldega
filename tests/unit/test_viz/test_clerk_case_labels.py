"""A Clerk case keeps the Clustergram's cell-type labels (yours and Clerk's), and they
come back when it's reopened, in either saved format; its evidence links also work
without a kernel."""

import json
import warnings

import numpy as np
import pandas as pd
import pytest


try:
    from celldega import clerk as clerk_llm
    from celldega.clust import Matrix
    from celldega.viz import Clerk, Clustergram, Landscape, link_clerk, spatial_clustergram
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _clustergram(**kwargs) -> Clustergram:
    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=["MUC2", "TFF3", "JCHAIN"],
        columns=["4", "5", "6", "7"],
    )
    mat = Matrix(df)
    mat.cluster()
    cgm = Clustergram(matrix=mat, **kwargs)
    cgm.col_names = ["4", "5", "6", "7"]
    cgm.row_names = ["MUC2", "TFF3", "JCHAIN"]
    return cgm


def _landscape() -> Landscape:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # no transform file: identity
        return Landscape()


# What the browser syncs back once labels are on the Clustergram: column 4 labeled by
# Clerk, column 5 by the scientist, and MUC2 marked as a goblet-cell marker by Clerk.
LABELS = {
    "col": {
        "cell_type": {
            "values": {"4": "Goblet cells", "5": "Plasma cells"},
            "colors": {"Goblet cells": "#1f77b4", "Plasma cells": "#ff7f0e"},
        }
    },
    "row": {"info": {"values": {"MUC2": "Goblet cells"}, "colors": {"Goblet cells": "#1f77b4"}}},
}
MARKS = {"col": {"4": "Goblet cells"}, "row": {"MUC2": "Goblet cells"}}


def _labeled_case(name="labeled"):
    cgm = _clustergram(manual_col_cat="cell_type", manual_row_cat="info")
    clerk = Clerk(name=name, clustergram=cgm, context_info="Human colon.")
    clerk.messages = [
        {"role": "user", "content": "What is cluster 4?"},
        {"role": "assistant", "content": "Cluster 4 is goblet cells (MUC2).", "genes": ["MUC2"]},
    ]
    clerk.findings = [
        {"cluster": "4", "label": "Goblet cells", "confidence": "high", "markers": ["MUC2"]},
        {"cluster": "6", "label": "Enterocytes", "confidence": "low", "markers": []},
    ]
    clerk._clerk_marks = json.loads(json.dumps(MARKS))
    cgm.manual_cat = json.dumps(LABELS)  # as the browser syncs it
    return clerk, cgm


def _no_claude(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("reopening a case must not call Claude")

    monkeypatch.setattr(clerk_llm, "ask", fail)


def _column_labels(cgm) -> dict:
    return cgm.manual_cat_dict["col"]["cell_type"]["values"]


SET_BY = ["Clerk", "you", ""]  # clusters 4 (Clerk's), 5 (yours), 6 (only proposed)


def test_cell_types_lists_labels_with_who_set_them():
    clerk, _cgm = _labeled_case()
    assert clerk.cell_types().to_dict("records") == [
        {
            "cluster": "4",
            "label": "Goblet cells",
            "set_by": "Clerk",
            "clerk_proposal": "Goblet cells",
            "confidence": "high",
        },
        {
            "cluster": "5",
            "label": "Plasma cells",
            "set_by": "you",
            "clerk_proposal": "",
            "confidence": "",
        },
        # Proposed by Clerk but never put on the Clustergram.
        {
            "cluster": "6",
            "label": "",
            "set_by": "",
            "clerk_proposal": "Enterocytes",
            "confidence": "low",
        },
    ]


def test_a_saved_conversation_reopens_with_its_cell_types(tmp_path, monkeypatch):
    clerk, _cgm = _labeled_case()
    saved = clerk.save_conversation(tmp_path, title="colon")
    _no_claude(monkeypatch)
    cgm = _clustergram()  # a new session's Clustergram, without manual categories
    fresh = Clerk(name="fresh", clustergram=cgm, clerk_files=saved)
    assert _column_labels(cgm) == {"4": "Goblet cells", "5": "Plasma cells"}
    # Clerk still knows which labels are its own: yours stay yours.
    assert fresh.cell_types()["set_by"].tolist() == SET_BY


def test_a_case_saved_with_the_earlier_label_format_reopens_with_them(tmp_path):
    # Cases saved with the labels as clustergram_categories + clerk_marks.
    clerk, _cgm = _labeled_case()
    saved = clerk.save_conversation(tmp_path / "earlier.json")
    payload = json.loads(saved.read_text())
    payload.pop("annotations", None)
    payload["clustergram_categories"] = LABELS
    payload["clerk_marks"] = MARKS
    saved.write_text(json.dumps(payload))

    cgm = _clustergram()
    fresh = Clerk(name="earlier", clustergram=cgm, clerk_files=saved)
    assert _column_labels(cgm) == {"4": "Goblet cells", "5": "Plasma cells"}
    assert cgm.manual_cat_dict["row"]["info"]["values"] == {"MUC2": "Goblet cells"}
    assert fresh._clerk_marks["col"] == {"4": "Goblet cells"}
    assert fresh.cell_types()["set_by"].tolist() == SET_BY


def test_cell_types_are_known_before_a_clustergram_is_linked(tmp_path):
    clerk, _cgm = _labeled_case()
    saved = clerk.save_conversation(tmp_path / "case.json")
    reopened = Clerk(name="reopened", clerk_files=saved)  # nothing linked yet
    assert reopened.cell_types()["label"].tolist() == ["Goblet cells", "Plasma cells", ""]
    landscape, cgm = _landscape(), _clustergram()
    spatial_clustergram(landscape, cgm, clerk=reopened)
    assert _column_labels(cgm) == {"4": "Goblet cells", "5": "Plasma cells"}


def test_an_exported_report_writes_the_cell_types_table(tmp_path):
    clerk, _cgm = _labeled_case()
    written = clerk.export(tmp_path / "report", html=False)
    table = pd.read_csv(written["cluster_labels"], dtype=str, keep_default_na=False)
    assert table["cluster"].tolist() == ["4", "5", "6"]
    assert table["set_by"].tolist() == SET_BY


def test_evidence_links_reach_the_widgets_in_the_browser():
    landscape, cgm = _landscape(), _clustergram()
    clerk = Clerk(name="links")
    link_clerk(clerk, landscape=landscape, clustergram=cgm)
    links = dict(clerk._view_links)
    assert set(links) == {"landscape", "clustergram"}
    request, answer = links["landscape"]
    assert request.source == (clerk, "landscape_request")
    assert request.target == (landscape, "view_request")
    # Each widget's answer comes back, so the panel sends the next request in turn.
    assert answer.source == (landscape, "view_result")
    assert answer.target == (clerk, "landscape_result")
    assert links["clustergram"][0].target == (cgm, "view_request")
    assert links["clustergram"][1].target == (clerk, "clustergram_result")
    # Linking again replaces the links rather than adding more.
    link_clerk(clerk, clustergram=cgm)
    assert clerk._view_links["clustergram"] is not links["clustergram"]


def test_the_panel_finds_out_whether_a_kernel_answers():
    clerk = Clerk(name="ping")
    sent = []
    clerk.send = sent.append
    clerk._on_panel_msg(clerk, {"event": "ping"}, [])
    assert sent == [{"event": "pong"}]
