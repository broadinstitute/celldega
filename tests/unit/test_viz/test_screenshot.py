"""Screenshots with provenance: PNG (record embedded) + .json + .md, from manual visualization workflows."""

import base64
import io
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import pytest

from tests.unit.test_viz.snapshot_helpers import snapshot_browser


try:
    from ipywidgets import HBox
    from PIL import Image

    from celldega.clust import Matrix
    from celldega.viz import (
        Clustergram,
        Landscape,
        load_screenshot,
        screenshots as screenshot_module,
    )
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _png(width: int, height: int, color=(200, 30, 30)) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _landscape() -> Landscape:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        ls = Landscape(dataset_name="Kidney section", base_url="https://example.org/kidney")
    ls.screenshot_metadata = {"adata": "data/kidney.h5ad"}
    return ls


def _clustergram() -> Clustergram:
    df = pd.DataFrame(
        np.arange(6).reshape(2, 3).astype(float), index=["G1", "G2"], columns=["A", "B", "C"]
    )
    mat = Matrix(df)
    mat.cluster()
    mat._source = "https://example.org/markers.zarr"
    return Clustergram(matrix=mat)


LANDSCAPE_STATE = {
    "kind": "landscape",
    "space": "spatial",
    "view_state": {"target": [10.0, 20.0, 0], "zoom": -2.0},
    "color_by": "cluster",
    "selected_clusters": ["A"],
    "selected_genes": [],
    "viewport": {"clusters": [{"name": "A", "value": 120}], "genes": []},
}


def _browser(widget, png: str, state: dict | None):
    """A fake browser that answers screenshot and state requests."""

    def send(content):
        event = content.get("event")
        if event == "capture_raster":
            reply = {"event": "raster", "id": content["id"], "png": png, "view_state": {"zoom": -2}}
            widget._on_custom_msg(widget, reply, [])
        elif event == "get_state" and state is not None:
            widget._on_state_msg(
                widget, {"event": "state", "id": content["id"], "state": state}, []
            )
        elif event == "apply_state":
            widget._on_apply_msg(widget, {"event": "applied", "id": content["id"]}, [])

    widget.send = snapshot_browser(widget, send)


def test_write_screenshot_files_and_embedded_record(tmp_path) -> None:
    shots = [
        {
            "image": _png(40, 30),
            "source": {"widget": "Landscape", "dataset_name": "Kidney"},
            "state": {"clusters": ["A"]},
            "in_view": {"clusters": [{"name": "A", "value": 3}]},
        }
    ]
    target = screenshot_module.write_screenshot(
        tmp_path, shots, description="A ring of cluster A.", title="Ring", author="you"
    )
    assert target.parent == tmp_path and target.name.startswith("ring_")
    record = json.loads(target.with_suffix(".json").read_text())
    assert record["description"] == "A ring of cluster A."
    assert record["widgets"][0]["state"] == {"clusters": ["A"]}
    # The PNG carries its own record, so the file alone can be reproduced.
    assert screenshot_module.read_png_record(target) == record
    md = target.with_suffix(".md").read_text()
    assert "A ring of cluster A." in md and f"![Ring]({target.name})" in md
    assert "landscape.apply_state({'clusters': ['A']})" in md
    # An explicit .png path is used as given; a second auto-named file doesn't clash.
    explicit = screenshot_module.write_screenshot(tmp_path / "fig" / "1a.png", shots)
    assert explicit == tmp_path / "fig" / "1a.png" and explicit.is_file()
    again = screenshot_module.write_screenshot(tmp_path, shots, title="Ring")
    assert again != target and again.is_file()


def test_compose_places_widgets_side_by_side() -> None:
    image = screenshot_module.compose([_png(100, 50), _png(40, 100)])
    # Scaled to the smaller height, with a gap between.
    assert image.size == (100 + screenshot_module.GAP + 20, 50)


def test_landscape_screenshot_saves_when_the_browser_replies(tmp_path) -> None:
    ls = _landscape()
    _browser(ls, _png(60, 40), LANDSCAPE_STATE)
    shot = ls.screenshot("Cluster A rings the structure.", path=tmp_path, title="Ring")
    assert shot.wait(timeout=5) and not shot.error
    record = load_screenshot(shot.path)
    widget = record["widgets"][0]
    assert widget["snapshot"]["description"] == "Cluster A rings the structure."
    assert widget["snapshot"]["author"] == "you"
    # One copy of the replay settings, in the saved view.
    assert "state" not in widget
    assert widget["snapshot"]["state"] == {
        "space": "spatial",
        "view": {"target": [10.0, 20.0, 0], "zoom": -2.0},
        "clusters": ["A"],
    }
    md = shot.path.with_suffix(".md").read_text()
    assert f"record = dega.viz.load_screenshot('{shot.path.name}')" in md
    assert "landscape.restore_snapshot(record['widgets'][0]['snapshot'])" in md
    assert widget["source"]["dataset_name"] == "Kidney section"
    assert widget["source"]["base_url"] == "https://example.org/kidney"
    assert widget["source"]["adata"] == "data/kidney.h5ad"  # screenshot_metadata
    assert widget["in_view"]["clusters"][0]["name"] == "A"
    assert "Saved" in shot._html()


def test_linked_widgets_make_one_composite_screenshot(tmp_path) -> None:
    ls, cgm = _landscape(), _clustergram()
    _browser(ls, _png(80, 60), LANDSCAPE_STATE)
    cgm_state = {
        "kind": "clustergram",
        "marker_level": {"current": 5},
        "display": {"mode": "dotplot"},
    }
    _browser(cgm, _png(60, 60), cgm_state)
    shot = screenshot_module.screenshot(HBox([ls, HBox([cgm])]), description="Both", path=tmp_path)
    assert shot.wait(timeout=5) and not shot.error
    record = load_screenshot(shot.path)
    assert [w["source"]["widget"] for w in record["widgets"]] == ["Landscape", "Clustergram"]
    assert screenshot_module.replay_settings(record["widgets"][1]) == {
        "marker_level": 5,
        "mode": "dotplot",
        "focus_gene": "",
    }
    assert record["widgets"][1]["source"]["matrix"]["source"] == "https://example.org/markers.zarr"
    assert record["size"] == [80 + screenshot_module.GAP + 60, 60]


def test_a_widget_that_never_replies_reports_why(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(screenshot_module, "CAPTURE_TIMEOUT", 0.2)
    ls = _landscape()
    ls.send = lambda content: None  # not displayed
    shot = ls.screenshot("x", path=tmp_path)
    assert shot.wait(timeout=5)
    assert "are they displayed" in shot.error
    assert not list(tmp_path.iterdir())


def test_pic_button_save_from_the_browser(tmp_path) -> None:
    ls = _landscape()
    ls.screenshot_dir = tmp_path
    sent = []
    ls.send = sent.append
    replay = {"space": "spatial", "clusters": ["A"], "selected_cells": ["c1", "c2"]}
    saved_view = {
        "schema": "celldega.view",
        "version": 2,
        "kind": "landscape",
        "state": replay,
        "observed_state": LANDSCAPE_STATE,
        "identity": {"revision": "", "cells": {"count": 2, "hash": "0" * 14}},
        "image": {"png": _png(30, 30), "view_state": {"zoom": -2}},
    }
    ls._on_pic_msg(
        ls,
        {
            "event": "pic",
            "id": 3,
            "title": "Glomerulus",
            "description": "Tight cluster of A cells.",
            "snapshot": saved_view,
        },
        [],
    )
    assert sent[-1]["event"] == "pic_saved" and sent[-1]["id"] == 3
    record = load_screenshot(sent[-1]["path"])
    assert record["title"] == "Glomerulus" and record["author"] == "you"
    widget = record["widgets"][0]
    # Recorded like screenshot(): the browser's complete replay settings, once.
    assert widget["snapshot"]["state"] == replay and "state" not in widget
    assert widget["observed_state"] == LANDSCAPE_STATE
    assert widget["in_view"]["clusters"][0]["name"] == "A"
    assert "png" not in widget["snapshot"].get("image", {})

    ls._on_pic_msg(ls, {"event": "pic", "id": 4, "snapshot": {}}, [])
    assert sent[-1]["event"] == "pic_error"


def test_briefing_summaries_shorten_long_settings() -> None:
    names = [f"G{i}" for i in range(500)]
    record = {
        "celldega_screenshot": 3,
        "title": "Reordered",
        "widgets": [
            {
                "source": {"widget": "Clustergram"},
                "snapshot": {"state": {"order": {"row": names}, "mode": "dotplot"}},
            }
        ],
    }
    text = screenshot_module.summarize([record])
    assert '"mode": "dotplot"' in text
    assert "G7" in text and "G8" not in text and "492 more" in text


def test_widget_screenshots_default_to_celldega_files(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    ls = _landscape()
    _browser(ls, _png(20, 20), LANDSCAPE_STATE)
    shot = ls.screenshot("x")
    assert shot.wait(timeout=5) and not shot.error
    assert shot.path.parent == Path("celldega_files/screenshots")


def test_screenshot_keeps_observations_and_layer_replay_settings(tmp_path):
    ls = _landscape()
    state = {
        **LANDSCAPE_STATE,
        "layers": {"image": False, "cells": True},
        "channels": {"DAPI": {"intensity": 25, "visible": True}},
        "sliders": {"cell": 35},
    }
    _browser(ls, _png(20, 20), state)
    shot = ls.screenshot("layer settings", path=tmp_path)
    assert shot.wait(5) and not shot.error
    record = load_screenshot(shot.path)
    assert record["restoration"] == "partial"
    widget = record["widgets"][0]
    assert widget["observed_state"] == state
    for key in ("layers", "channels", "sliders"):
        assert widget["snapshot"]["state"][key] == state[key]
