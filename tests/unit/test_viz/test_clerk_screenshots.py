"""Clerk capture and briefing integration over the manual screenshot API."""

import json

import pytest

from celldega import clerk as clerk_llm
from celldega.viz import Clerk, load_screenshot, load_screenshots
from tests.unit.test_viz.test_screenshot import LANDSCAPE_STATE, _browser, _landscape, _png


def test_clerk_takes_a_screenshot_and_reads_screenshots_as_a_briefing(
    tmp_path, monkeypatch
) -> None:
    ls = _landscape()
    _browser(ls, _png(50, 50), LANDSCAPE_STATE)
    w = Clerk(landscape=ls, capture_on_select=False)
    w.snapshot_timeout = 5
    w.screenshot_dir = tmp_path
    block = {
        "landscape": {"clusters": ["A"]},
        "snapshot": {"title": "Cluster A", "description": "Cluster A forms a ring."},
    }
    monkeypatch.setattr(
        clerk_llm, "ask", lambda q, **kw: f"```celldega-actions\n{json.dumps(block)}\n```"
    )
    w.request = {"id": "1", "question": "Save the evidence for cluster A"}
    assert w.wait(timeout=10)
    assert w.messages[-1]["content"].startswith("Saved a screenshot: ")
    record = load_screenshot(w.screenshots[-1])
    assert record["author"] == "Clerk"
    assert record["description"] == "Cluster A forms a ring."
    assert record["metadata"]["question"] == "Save the evidence for cluster A"
    assert any(s["kind"] == "screenshot" for s in w.record[-1]["steps"])

    # A folder of screenshots (Clerk's and the scientist's) is a briefing.
    reader = Clerk()
    text = reader.load_briefing(tmp_path)
    assert "Cluster A forms a ring." in text and "(Clerk," in text
    assert "clusters in view: A" in text
    assert len(load_screenshots(tmp_path)) == 1
    # So is a single screenshot PNG.
    assert "Cluster A forms a ring." in reader.load_briefing(w.screenshots[-1])


def test_invalid_snapshot_actions_are_rejected() -> None:
    w = Clerk()
    with pytest.raises(ValueError, match="snapshot"):
        w._apply_actions({"snapshot": "yes please"})


def test_clerk_writes_under_clerk_files_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    ls = _landscape()
    w = Clerk(landscape=ls, capture_on_select=False)
    w.image_b64 = _png(20, 20)
    views = {"image_fresh": True, "landscape_state": LANDSCAPE_STATE}
    w._save_snapshot(views, {"description": "x"}, "q")
    assert w.screenshots[-1].startswith("clerk_files/screenshots/")
    assert w.export(html=False)["record"].parts[:2][0] == "clerk_files"
