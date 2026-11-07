"""Landscape and Clustergram setters (Viz API) and Clerk's use of them."""

import json
import warnings

import numpy as np
import pandas as pd
import pytest


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
def test_landscape_apply_state_sends_validated_changes(monkeypatch) -> None:
    ls = _landscape()
    sent = []
    monkeypatch.setattr(ls, "send", sent.append)

    done = ls.apply_state(
        {"clusters": ["4", "5"], "genes": ["MUC2"], "zoom_to": {"clusters": ["4"]}, "space": "umap"}
    )
    assert done == [
        "highlighted clusters 4, 5",
        "colored cells by MUC2",
        "zoomed to clusters 4",
        "switched to the umap view",
    ]
    assert ls.landscape_state == "umap"  # space is a synced trait
    assert sent[-1] == {
        "event": "apply_state",
        "id": 1,
        "changes": {"clusters": ["4", "5"], "genes": ["MUC2"], "zoom_to": {"clusters": ["4"]}},
    }

    for bad in ({"colour": 1}, {"clusters": "4"}, {"space": "3d"}, {"zoom_to": {}}):
        with pytest.raises(ValueError):
            ls.apply_state(bad)
    assert len(sent) == 1 and ls.landscape_state == "umap"


def test_landscape_apply_replies_and_state_traits() -> None:
    ls = _landscape()
    ls._on_apply_msg(ls, {"event": "apply_error", "id": 2, "error": "no cells"}, [])
    assert (ls.apply_error, ls.apply_capture_id) == ("no cells", 2)
    ls._on_apply_msg(ls, {"event": "applied", "id": 3, "done": ["x"]}, [])
    assert (ls.apply_error, ls.apply_capture_id) == ("", 3)
    for name in ("latest_state", "apply_error", "apply_capture_id"):
        assert ls.trait_metadata(name, "sync") is None


def test_landscape_neighborhood_summary() -> None:
    ls = _landscape()
    ls.cluster_attr = "leiden"
    ls.meta_cell = pd.DataFrame(
        {"leiden": ["4", "4", "5", "6"]}, index=pd.Index(["c1", "c2", "c3", "c4"])
    )
    ls.nbhd_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "properties": {"name": "crypt_A", "cell_ids": ["c1", "c2", "c3"]},
            }
        ],
    }
    assert ls.neighborhood_summary() == [
        {
            "name": "crypt_A",
            "space": "spatial",
            "n_cells": 3,
            "clusters": [
                {"name": "4", "count": 2, "fraction": 0.667},
                {"name": "5", "count": 1, "fraction": 0.333},
            ],
        }
    ]


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
    assert "Top genes in view: MUC2 (512)" in text
    assert "Drawn neighborhood crypt_A (spatial): 3 cells; clusters 4 67%" in text


# ---- Clustergram manual categories ------------------------------------------------
def test_clustergram_set_categories(monkeypatch) -> None:
    cgm = _clustergram(manual_col_cat="cell_type")
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)

    done = cgm.apply_state({"categories": {"values": {"4": "Goblet cells", "5": "Plasma cells"}}})
    assert done == ["labeled columns (cell_type): 4 → Goblet cells, 5 → Plasma cells"]
    assert sent[-1] == {
        "event": "set_categories",
        "id": 1,
        "axis": "col",
        "attribute": "cell_type",
        "values": {"4": "Goblet cells", "5": "Plasma cells"},
        "colors": {},
        "replace": False,
    }
    with pytest.raises(ValueError, match="not col names"):
        cgm.set_categories({"99": "x"})


def test_clustergram_set_categories_needs_an_attribute(monkeypatch) -> None:
    cgm = _clustergram()
    monkeypatch.setattr(cgm, "send", lambda content: None)
    with pytest.raises(ValueError, match="no manual col category"):
        cgm.set_categories({"4": "Goblet cells"})
    assert cgm.set_categories({"4": "Goblet cells"}, attribute="clerk_cell_type") == 1


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

    monkeypatch.setattr(ls, "send", fake_send)
    calls = []
    replies = [
        '```celldega-actions\n{"landscape": {"clusters": ["4"]}}\n```',
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
