"""Landscape and Clustergram setters (Viz API) and Clerk's use of them."""

import json
import warnings

import numpy as np
import pandas as pd
import pytest

from tests.unit.test_viz.snapshot_helpers import snapshot_browser


try:
    from celldega import clerk as clerk_llm
    from celldega.clust import Matrix
    from celldega.viz import Clerk, Clustergram, Landscape
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _landscape() -> Landscape:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # no transform file: identity
        return Landscape()


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


# ---- Landscape -------------------------------------------------------------------


def test_format_landscape_state() -> None:
    state = {
        "space": "spatial",
        "view_state": {"target": [100.5, 200.25, 0], "zoom": 2.5},
        "color_by": "cluster",
        "selected_clusters": ["4"],
        "viewport": {
            "clusters": [{"name": "4", "value": 1203}, {"name": "5", "value": 980}],
            "genes": [{"name": "MUC2", "value": 512}],
        },
    }
    nbhds = [
        {
            "name": "crypt_A",
            "space": "spatial",
            "n_cells": 3,
            "clusters": [{"name": "4", "count": 2, "fraction": 0.667}],
        }
    ]
    text = clerk_llm.format_landscape_state(state, nbhds)
    assert "Space: spatial; camera at (100.5, 200.25), zoom 2.5" in text
    assert "Highlighted clusters: 4" in text
    assert "Cells in view by cluster: 4 (1203), 5 (980)" in text
    assert "Gene bars (scope and method not recorded): MUC2 (512)" in text
    assert "Drawn neighborhood crypt_A (spatial): 3 cells; clusters 4 67%" in text


# ---- Clustergram manual categories ------------------------------------------------


# ---- Clerk ---------------------------------------------------------------------------
def test_clerk_drives_the_landscape_and_waits_for_it(monkeypatch) -> None:
    ls = _landscape()
    w = Clerk(landscape=ls, capture_on_select=False)
    w.snapshot_timeout = 5
    applied = []

    def fake_send(content):
        event = content.get("event")
        if event == "capture_raster":
            ls._on_custom_msg(ls, {"event": "raster", "id": content["id"], "png": "P"}, [])
        elif event == "get_state":
            state = {"kind": "landscape", "selected_clusters": list(applied)}
            ls._on_state_msg(ls, {"event": "state", "id": content["id"], "state": state}, [])
        elif event == "apply_state":
            applied.extend(content["changes"].get("clusters", []))
            ls._on_apply_msg(ls, {"event": "applied", "id": content["id"], "done": []}, [])

    monkeypatch.setattr(ls, "send", snapshot_browser(ls, fake_send))
    calls = []
    replies = [
        '```celldega-actions\n{"landscape": {"clusters": ["4"]}, "continue": true}\n```',
        "Cluster 4 lines the crypts.",
    ]

    def fake_ask(question, **kwargs):
        calls.append(kwargs)
        return replies[len(calls) - 1]

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "Show me cluster 4"}
    assert w.wait(timeout=5)

    assert "zoom_to" in calls[0]["actions_help"]  # Landscape actions offered
    assert w.messages[1]["content"] == "Changed the Landscape: highlighted clusters 4"
    assert calls[1]["landscape_state"]["selected_clusters"] == ["4"]
    assert w.messages[-1]["content"] == "Cluster 4 lines the crypts."


def test_clerk_labels_clustergram_but_keeps_scientist_labels(monkeypatch) -> None:
    cgm = _clustergram(manual_col_cat="cell_type")
    cgm.manual_cat = json.dumps(
        {"col": {"cell_type": {"values": {"5": "My plasma label"}, "colors": {}}}}
    )
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 0.05
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)
    findings = {
        "cell_types": [
            {"cluster": "4", "label": "Goblet cells", "confidence": "high"},
            {"cluster": "5", "label": "Plasma cells", "confidence": "high"},
        ]
    }
    answer = f"4 goblet, 5 plasma.\n```celldega-findings\n{json.dumps(findings)}\n```"
    monkeypatch.setattr(clerk_llm, "ask", lambda question, **kw: answer)

    w.request = {"id": "1", "question": "label 4 and 5"}
    assert w.wait(timeout=5)

    labels = [m for m in sent if m.get("event") == "set_categories"]
    assert labels[-1]["values"] == {"4": "Goblet cells"}  # 5 was the scientist's
    note = w.messages[-1]["content"]
    assert "Labeled Clustergram columns (cell_type): 4 → Goblet cells" in note
    assert "kept your labels for 5 (My plasma label)" in note


def test_clerk_marks_marker_genes_in_the_clustergram_rows(monkeypatch) -> None:
    cgm = _clustergram(manual_col_cat="cell_type")
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 0.05
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)

    def answer_with(label, markers):
        findings = {"cell_types": [{"cluster": "4", "label": label, "markers": markers}]}
        return f"4 is {label}.\n```celldega-findings\n{json.dumps(findings)}\n```"

    monkeypatch.setattr(
        clerk_llm, "ask", lambda q, **kw: answer_with("Goblet cells", ["MUC2", "tff3", "NOPE"])
    )
    w.request = {"id": "1", "question": "what is 4?"}
    assert w.wait(timeout=5)

    labels = [m for m in sent if m.get("event") == "set_categories"]
    assert [(m["axis"], m["attribute"]) for m in labels] == [
        ("col", "cell_type"),
        ("row", "clerk_marker"),  # no manual row category: Clerk's own attribute
    ]
    assert labels[-1]["values"] == {"MUC2": "Goblet cells", "TFF3": "Goblet cells"}
    assert "marked marker genes (clerk_marker): MUC2, TFF3" in w.messages[-1]["content"]
    assert w.findings[-1]["markers"] == ["MUC2", "tff3", "NOPE"]

    # The browser syncs the labels back; then Clerk relabels cluster 4. Its old marks
    # are cleared unless cited again, and the scientist's row label is kept.
    cgm.manual_cat = json.dumps(
        {
            "col": {"cell_type": {"values": {"4": "Goblet cells"}, "colors": {}}},
            "row": {
                "clerk_marker": {
                    "values": {"MUC2": "Goblet cells", "TFF3": "Goblet cells", "JCHAIN": "Mine"},
                    "colors": {},
                }
            },
        }
    )
    monkeypatch.setattr(
        clerk_llm, "ask", lambda q, **kw: answer_with("Enterocytes", ["MUC2", "JCHAIN"])
    )
    w.request = {"id": "2", "question": "look again"}
    assert w.wait(timeout=5)
    rows = [m for m in sent if m.get("event") == "set_categories" and m["axis"] == "row"]
    assert rows[-1]["values"] == {"MUC2": "Enterocytes", "TFF3": None}


def test_marker_marks_share_the_column_color() -> None:
    """A category already colored on the other axis keeps its color (JS behavior is
    covered in manual_categories.test.js); here, Clerk sends no colors of its own."""
    cgm = _clustergram(manual_col_cat="cell_type")
    sent = []
    cgm.send = sent.append
    w = Clerk(clustergram=cgm)
    w._label_clustergram({"4": "Goblet cells"}, {"4": ["MUC2"]})
    assert all(m["colors"] == {} for m in sent if m.get("event") == "set_categories")


def test_clerk_records_captures_with_reproduction_state(monkeypatch) -> None:
    ls = _landscape()
    w = Clerk(landscape=ls, capture_on_select=False)
    w.snapshot_timeout = 5
    selected = []

    def fake_send(content):
        event = content.get("event")
        if event == "capture_raster":
            ls._on_custom_msg(ls, {"event": "raster", "id": content["id"], "png": "P"}, [])
        elif event == "get_state":
            state = {
                "kind": "landscape",
                "space": "spatial",
                "view_state": {"target": [10.0, 20.0, 0], "zoom": -2.5},
                "color_by": "cluster",
                "selected_clusters": list(selected),
                "selected_genes": [],
            }
            ls._on_state_msg(ls, {"event": "state", "id": content["id"], "state": state}, [])
        elif event == "apply_state":
            selected[:] = content["changes"].get("clusters", [])
            ls._on_apply_msg(ls, {"event": "applied", "id": content["id"], "done": []}, [])

    monkeypatch.setattr(ls, "send", snapshot_browser(ls, fake_send))
    monkeypatch.setattr(
        clerk_llm,
        "ask",
        lambda q, **kw: 'Crypts.\n```celldega-actions\n{"landscape": {"clusters": ["4"]}}\n```',
    )
    w.request = {"id": "1", "question": "What is here?"}
    assert w.wait(timeout=5)

    entry = w.record[-1]
    assert entry["question"] == "What is here?"
    captures = [s for s in entry["steps"] if s["kind"] == "capture"]
    assert [c["text"] for c in captures] == [
        "When asked",
        "Changed the Landscape: highlighted clusters 4",
    ]
    assert captures[0]["image"] == "P"
    assert captures[0]["landscape"] == {
        "space": "spatial",
        "view": {"target": [10.0, 20.0, 0], "zoom": -2.5},
        "clusters": [],
    }
    assert captures[1]["landscape"]["clusters"] == ["4"]
    assert [s["kind"] for s in entry["steps"]] == ["capture", "answer", "action", "capture"]


def test_clerk_records_clustergram_screenshots(monkeypatch) -> None:
    cgm = _clustergram()
    w = Clerk(clustergram=cgm)
    w.capture_clustergram = True
    w.snapshot_timeout = 5

    def fake_send(content):
        event = content.get("event")
        if event == "capture_raster":
            cgm._on_custom_msg(cgm, {"event": "raster", "id": content["id"], "png": "C"}, [])
        elif event == "get_state":
            state = {"kind": "clustergram", "marker_level": {"current": 25}, "display": {}}
            cgm._on_state_msg(cgm, {"event": "state", "id": content["id"], "state": state}, [])

    monkeypatch.setattr(cgm, "send", snapshot_browser(cgm, fake_send))
    monkeypatch.setattr(clerk_llm, "ask", lambda q, **kw: "Answer.")
    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    capture = w.record[-1]["steps"][0]
    assert capture["kind"] == "capture"
    assert capture["clustergram_image"] == "C"
    assert capture["clustergram"] == {"marker_level": 25}


@pytest.mark.parametrize("reply", ["error", "timeout"])
@pytest.mark.parametrize("kind", ["landscape", "clustergram"])
def test_failed_browser_action_is_not_recorded_as_success(monkeypatch, reply, kind):
    widget = _landscape() if kind == "landscape" else _clustergram()
    w = Clerk(**{kind: widget}, capture_on_select=False)
    w.snapshot_timeout = 0.01

    def send(content):
        if content.get("event") == "apply_state" and reply == "error":
            widget._on_apply_msg(
                widget,
                {"event": "apply_error", "id": content["id"], "error": "no matching cells"},
                [],
            )

    monkeypatch.setattr(widget, "send", send)
    w.record = [{"steps": []}]
    changes = {"clusters": ["4"]} if kind == "landscape" else {"marker_level": 5}
    w._work("show it", {}, 0, answer=f"```celldega-actions\n{json.dumps({kind: changes})}\n```")
    assert w.messages[-1]["role"] == "error"
    assert all(m["role"] != "action" for m in w.messages)
    assert w.record[0]["steps"][-1]["kind"] == "error"
