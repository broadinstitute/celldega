"""Named capture storage and lightweight postcards, using a browser comm double."""

import base64
from copy import deepcopy

import pytest

from celldega.viz import Snapshot, Yearbook, from_png, load_snapshot
from celldega.viz.screenshots import save_from_browser, write_screenshot
from tests.unit.test_viz.test_screenshot import (
    LANDSCAPE_STATE,
    _browser,
    _clustergram,
    _landscape,
    _png,
)


@pytest.fixture
def landscape():
    viewer = _landscape()
    yield viewer
    viewer.close()


@pytest.fixture
def saved(landscape, tmp_path):
    _browser(landscape, _png(40, 30), LANDSCAPE_STATE)
    landscape.snapshot_dir = tmp_path
    result = landscape.snapshot(name="Glomerulus", description="Podocyte ring")
    assert result.done and not result.error
    return result


def test_named_capture_registers_record_and_memo(landscape, saved):
    entry = landscape.snap["Glomerulus"]
    assert load_snapshot(saved.path)["description"] == "Podocyte ring"
    assert saved.path.with_suffix(".md").exists()
    assert entry["widgets"][0]["snapshot"]["state"]["view"] == LANDSCAPE_STATE["view_state"]
    assert "snap" not in landscape.get_state()  # Do not duplicate images in the main viewer.
    other = landscape.snapshot(name="Glomerulus", description="Another view")
    assert other.done
    assert list(landscape.snap) == ["Glomerulus", "Glomerulus (2)"]


def test_named_and_path_cards_coexist(landscape, saved):
    cards = [
        Snapshot(landscape=landscape, snapshot="Glomerulus"),
        Snapshot(saved.path, landscape=landscape),
        Snapshot(landscape.snap["Glomerulus"], linked=landscape),
    ]
    try:
        for card in cards:
            assert card.name == "Glomerulus"
            assert card.description == "Podocyte ring"
            assert card.can_restore
            assert base64.b64decode(card.image) == saved.path.read_bytes()
            assert card.comm is not None
            assert "deck.gl" not in card._esm
            assert len(card._esm) < 10_000
    finally:
        for card in cards:
            card.close()


def test_card_waits_for_exact_ack_and_surfaces_errors(landscape, saved):
    sent = []
    landscape.send = sent.append
    card = Snapshot(saved.path, landscape=landscape)
    try:
        request = card.show_view()
        assert sent[-1]["event"] == "restore_snapshot"
        assert sent[-1]["options"] == {"allow_resize": True}
        assert card.busy and "Opening" in card.status
        assert card.show_view() is None
        landscape._on_apply_msg(landscape, {"event": "applied", "id": request + 1}, [])
        assert card.busy
        landscape._on_apply_msg(
            landscape,
            {"event": "apply_error", "id": request, "error": "Dataset differs"},
            [],
        )
        assert not card.busy and "Dataset differs" in card.status
        assert card._observer is None and card._timer is None
        request = card.show_view()
        landscape._on_apply_msg(landscape, {"event": "applied", "id": request}, [])
        assert not card.busy and card.status == "View opened in Landscape."
    finally:
        card.close()


def test_close_removes_pending_observer_and_timeout(landscape, saved):
    landscape.send = lambda _: None
    card = Snapshot(saved.path, landscape=landscape)
    card.show_view()
    timer = card._timer
    card.close()
    assert card._observer is None
    assert timer.finished.is_set()


def test_plain_png_and_unlinked_capture_are_static(landscape, saved, tmp_path):
    plain = tmp_path / "plain.png"
    plain.write_bytes(base64.b64decode(_png(30, 20)))
    for source in (plain, saved.path):
        card = Snapshot(source, name="A postcard", description="A memo")
        try:
            assert card.name == "A postcard"
            assert not card.can_restore
            assert card.show_view() is None
        finally:
            card.close()
    card = Snapshot(plain, landscape=landscape)
    assert not card.can_restore
    card.close()


def test_in_memory_snapshot_and_sync_ack(landscape, saved):
    card = Snapshot(landscape.latest_snapshot, landscape=landscape, name="In memory")
    try:
        assert card.can_restore
        card.show_view()
        assert not card.busy
        assert "View opened" in card.status
    finally:
        card.close()


def test_browser_save_registers_named_snapshot(landscape, saved):
    target = save_from_browser(
        landscape,
        {"snapshot": landscape.latest_snapshot, "title": "SNAP", "description": "From the panel"},
    )
    assert landscape.snap["SNAP"]["_path"] == str(target.resolve())
    assert landscape.snap["SNAP"]["description"] == "From the panel"


def test_clustergram_card(landscape, saved, tmp_path):
    cgm = _clustergram()
    _browser(cgm, _png(20, 30), {"kind": "clustergram", "row_order": ["G1", "G2"]})
    capture = cgm.snapshot(name="Markers", path=tmp_path)
    assert capture.done and not capture.error
    card = Snapshot(clustergram=cgm, snapshot="Markers")
    try:
        assert card.can_restore
        assert card._restore["kind"] == "clustergram"
        card.show_view()
        assert card.status == "View opened in Clustergram."
    finally:
        card.close()
        cgm.close()


def test_yearbook_named_snapshot_and_reopen(landscape, saved, tmp_path):
    yb = Yearbook(base_url="https://example.org/kidney", cells=["c1", "c2"], rows=1, cols=2)
    snapshot = deepcopy(landscape.latest_snapshot)
    snapshot.update(kind="yearbook", source={"widget": "Yearbook"})
    snapshot["state"] = {
        "cells": ["c2", "c1"],
        "page": 0,
        "zoom": 1.5,
        "query": {},
        "selected_cells": [],
        "display": {},
    }
    yb.snapshot_dir = tmp_path
    path = save_from_browser(yb, {"snapshot": snapshot, "title": "Portraits"})
    card = Snapshot(yearbook=yb, snapshot="Portraits")
    reopened = from_png(path)
    try:
        assert card.can_restore
        assert card._restore["state"]["cells"] == ["c2", "c1"]
        assert isinstance(reopened, Yearbook)
        assert reopened.num_rows == 1 and reopened.num_cols == 2
        assert reopened._initial_snapshot["snapshot"]["state"]["zoom"] == 1.5
    finally:
        card.close()
        yb.close()
        reopened.close()


def test_composite_uses_registered_panel(landscape, saved, tmp_path):
    snapshot = landscape.latest_snapshot
    other = deepcopy(snapshot)
    other["state"]["view"]["zoom"] = 8
    path = write_screenshot(
        tmp_path,
        [
            {"image": _png(20, 20), "source": {"widget": "Landscape"}, "snapshot": snapshot},
            {"image": _png(20, 20), "source": {"widget": "Landscape"}, "snapshot": other},
        ],
    )
    card = Snapshot({**load_snapshot(path), "_path": str(path), "_panel": 1}, landscape=landscape)
    assert card._restore["state"]["view"]["zoom"] == 8
    card.close()


def test_invalid_png_and_missing_capture_fail_clearly(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_text("not an image")
    with pytest.raises(ValueError, match="Not a PNG"):
        Snapshot(bad)
    with pytest.raises(ValueError, match="no PNG"):
        Snapshot({})
