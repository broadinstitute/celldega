"""Pins: Snapshots pinned on a Landscape, like photos and notes on a map."""

import base64
import warnings

import pytest


try:
    from celldega import viz
    from celldega.viz import Landscape, Snapshots
    from celldega.viz.screenshots import write_screenshot
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def _view(kind="landscape", space="spatial", target=(10.0, 20.0, 0)):
    state = {"view": {"target": list(target), "zoom": -2}, "clusters": ["4"]}
    if space:
        state["space"] = space
    return {
        "schema": "celldega.view",
        "version": 2,
        "kind": kind,
        "state": state,
        "identity": {"cells": {"count": 3, "names": "abc"}},
    }


def _snapshot(folder, name, memo, **view):
    kind = view.get("kind", "landscape")
    return write_screenshot(
        folder / f"{name}.png",
        [
            {
                "image": PNG,
                "source": {"widget": kind.title(), "base_url": "https://example.com/data"},
                "snapshot": _view(**view),
            }
        ],
        title=name,
        description=memo,
    )


def _landscape(**kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return Landscape(base_url="https://example.com/data", **kwargs)


def test_snapshots_become_pins_at_their_view_centers(tmp_path):
    glom = _snapshot(tmp_path, "Glomerulus", "Podocytes ring the tuft.")
    medulla = _snapshot(tmp_path, "Medulla", "Collecting ducts.", target=(30, 40, 0))
    _snapshot(tmp_path, "Markers", "Clustergram view", kind="clustergram")
    _snapshot(tmp_path, "UMAP island", "", space="umap", target=(5, 6, 0))
    _snapshot(tmp_path, "Two genes", "", space="xy")

    poi = Snapshots(tmp_path)  # every Snapshot PNG in the folder
    assert poi.names() == ["Glomerulus", "Markers", "Medulla", "Two genes", "UMAP island"]
    pins = poi.pins()
    # Landscape Snapshots of the tissue or the UMAP have a place there; a Clustergram's
    # (shown as a card instead) or XY's (whose axes depend on the genes) don't.
    assert [p["name"] for p in pins] == ["Glomerulus", "Medulla", "UMAP island"]
    assert [p["space"] for p in pins] == ["spatial", "spatial", "umap"]
    assert pins[2]["target"] == [5.0, 6.0]
    assert pins[0]["description"] == "Podocytes ring the tuft."
    assert pins[0]["target"] == [10.0, 20.0]
    assert pins[1]["target"] == [30.0, 40.0]
    assert pins[0]["snapshot"]["state"]["clusters"] == ["4"]
    assert "image" not in pins[0]["snapshot"]  # the saved view only, no pixels

    # Paths, named collections and repeated names.
    named = Snapshots({"Start here": glom, "Then": medulla})
    assert named.names() == ["Start here", "Then"]
    again = Snapshots([glom, glom])
    assert again.names() == ["Glomerulus", "Glomerulus (2)"]
    assert len(again) == 2 and "Glomerulus (2)" in again


def test_a_landscape_takes_pins_at_creation_or_later(tmp_path):
    glom = _snapshot(tmp_path, "Glomerulus", "Podocytes ring the tuft.")
    ls = _landscape(pins=[glom])
    assert [p["name"] for p in ls.pins] == ["Glomerulus"]
    assert ls.pin_data == ls.pins and ls.show_pins is False

    # A viewer's own snap collection works too, and None clears the pins.
    ls.snap = {"Mine": {**viz.load_snapshot(glom), "_path": str(glom)}}
    ls.pins = ls.snap
    assert [p["name"] for p in ls.pins] == ["Mine"]
    ls.pins = None
    assert ls.pin_data == []


def test_bad_pins_are_refused(tmp_path):
    plain = tmp_path / "plain.png"
    plain.write_bytes(base64.b64decode(PNG))
    with pytest.raises(ValueError, match="no Celldega Snapshot record"):
        Snapshots([plain])
    with pytest.raises(ValueError, match="PNG path"):
        Snapshots([42])


def test_snapshots_of_other_data_are_not_pinned(tmp_path):
    mine = _snapshot(tmp_path, "Mine", "")
    other = write_screenshot(
        tmp_path / "Other.png",
        [
            {
                "image": PNG,
                "source": {"widget": "Landscape", "base_url": "https://example.com/other"},
                "snapshot": {**_view(), "source": {"base_url": "https://example.com/other"}},
            }
        ],
        title="Other",
    )
    ls = _landscape()
    with pytest.warns(UserWarning, match="other data than this Landscape: Other"):
        ls.pins = [mine, other]
    assert [p["name"] for p in ls.pins] == ["Mine"]
    # snapshots= at creation (pins= is an alias).
    assert [p["name"] for p in _landscape(snapshots=[mine]).pins] == ["Mine"]


def test_a_card_is_chosen_by_name_and_opens_its_view_in_the_browser(tmp_path):
    poi = Snapshots([_snapshot(tmp_path, "Glomerulus", "Podocytes ring the tuft.")])
    ls = _landscape()
    card = poi.card("Glomerulus", landscape=ls)
    assert card.name == "Glomerulus" and card.description == "Podocytes ring the tuft."
    # Linked in the browser, so the card's link works without a kernel too.
    assert card.can_restore and card.js_link
    assert card.view["state"]["clusters"] == ["4"]
    card.view_request = {"id": "1", "snapshot": card.view}
    with pytest.raises(KeyError, match="No Snapshot named"):
        poi.card("Nope")
