import warnings

import pytest

from celldega.viz import Landscape, fingerprint_dataset
from celldega.viz.screenshots import Screenshot, _Capture


def widget():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Landscape()


def snapshot(value):
    return {
        "schema": "celldega.view",
        "version": 2,
        "kind": "landscape",
        "state": {"clusters": [value]},
        "observed_state": {"kind": "landscape", "value": value},
        "identity": {"revision": "", "cells": {"count": 2, "hash": "0" * 14}},
        "viewport": {"width": 10, "height": 10},
        "image": {"png": value},
    }


def test_coordinated_transport_and_out_of_order_replies():
    w = widget()
    sent = []
    w.send = sent.append
    first, second = w.request_snapshot(max_size=500, max_bars=10), w.request_snapshot()
    assert [m["event"] for m in sent] == ["capture_snapshot", "capture_snapshot"]
    assert sent[0]["options"] == {
        "max_size": 500,
        "thumb_size": 192,
        "background": "white",
        "state": {"max_bars": 10},
    }
    w.request_snapshot(background=None)
    assert sent[-1]["options"]["background"] is None
    with pytest.raises(ValueError, match="background"):
        w.request_snapshot(background=0)
    for rid, value in ((second, "new"), (first, "old")):
        w._on_snapshot_msg(w, {"event": "snapshot", "id": rid, "snapshot": snapshot(value)}, [])
    assert w.latest_snapshot["image"]["png"] == "new"
    assert w._snapshot_replies[first]["snapshot"]["image"]["png"] == "old"
    for name in ("latest_snapshot", "snapshot_capture_id", "snapshot_error"):
        assert not w.traits()[name].metadata.get("sync")


def test_manual_capture_uses_its_own_response_not_a_newer_request(tmp_path, monkeypatch):
    from celldega.viz import screenshots

    w = widget()
    w.send = lambda _msg: None
    result = Screenshot("test")
    captures = []
    monkeypatch.setattr(
        screenshots,
        "write_screenshot",
        lambda path, shots, **kw: captures.append(shots) or tmp_path / "saved.png",
    )
    capture = _Capture([w], result, tmp_path, "", "you", {}, 1024)
    later = w.request_snapshot()
    w._on_snapshot_msg(w, {"event": "snapshot", "id": later, "snapshot": snapshot("new")}, [])
    assert not result.done
    w._on_snapshot_msg(w, {"event": "snapshot", "id": 1, "snapshot": snapshot("old")}, [])
    assert result.done and captures[0][0]["image"] == "old"
    assert captures[0][0]["observed_state"]["value"] == "old"
    capture.timer.cancel()


def test_restore_validates_before_sending_or_changing_traits():
    w = widget()
    sent = []
    w.send = sent.append
    before = w.landscape_state
    for version in (1, 999):  # 1 hashed all loaded data; recapture those views
        invalid = snapshot("old")
        invalid["version"] = version
        with pytest.raises(ValueError, match="schema/version"):
            w.restore_snapshot(invalid)
    no_identity = snapshot("old")
    no_identity["identity"] = {}
    with pytest.raises(ValueError, match="no data identity"):
        w.restore_snapshot(no_identity)
    with pytest.raises(ValueError, match="allow_resize"):
        w.restore_snapshot(snapshot("old"), allow_resize="yes")
    assert sent == [] and w.landscape_state == before
    original = snapshot("old")
    w.restore_snapshot(original, allow_resize=True)
    original["state"]["clusters"].append("mutated")
    assert sent[0]["event"] == "restore_snapshot"
    assert sent[0]["snapshot"]["state"]["clusters"] == ["old"]
    assert sent[0]["options"] == {"allow_resize": True}


def test_dataset_fingerprint_covers_content_names_and_is_portable(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for root in (first, second):
        root.mkdir()
        (root / "values.bin").write_bytes(b"abc")
    assert fingerprint_dataset(first) == fingerprint_dataset(second)
    (second / "values.bin").write_bytes(b"abd")
    assert fingerprint_dataset(first) != fingerprint_dataset(second)
    (second / "values.bin").write_bytes(b"abc")
    (second / "values.bin").rename(second / "renamed.bin")
    assert fingerprint_dataset(first) != fingerprint_dataset(second)


def test_setter_acknowledgements_are_exact_and_timeouts_are_errors():
    import asyncio

    async def check():
        w = widget()
        w.send = lambda _msg: None
        pending = asyncio.create_task(w.apply_state_async({"space": "xy"}, timeout=0.05))
        await asyncio.sleep(0)
        rid = w.apply_request_id
        assert w.get_apply_result(rid) is None
        w._on_apply_msg(w, {"event": "applied", "id": rid + 1, "done": ["unrelated"]}, [])
        # The message says how to check from a notebook, where the reply can't
        # arrive while the requesting cell runs.
        with pytest.raises(TimeoutError, match=rf"get_apply_result\({rid}\)"):
            await pending
        assert w.get_apply_result(rid) is None
        w._on_apply_msg(
            w, {"event": "apply_error", "id": rid, "error": "expression unavailable"}, []
        )
        with pytest.raises(ValueError, match="expression unavailable"):
            await w.wait_for_apply(rid)
        w.send = lambda msg: w._on_apply_msg(
            w, {"event": "applied", "id": msg["id"], "done": ["restored"]}, []
        )
        assert await w.apply_state_async({"selected_cells": ["c1"]}) == ["restored"]

    asyncio.run(check())


def test_enrich_has_the_getter_but_no_setters():
    from celldega.viz import Enrich

    e = Enrich(gene_list=["G1"])
    sent = []
    e.send = sent.append
    e.request_state(max_terms=3)
    assert sent[-1] == {"event": "get_state", "id": 1, "options": {"max_terms": 3}}
    # Its front end only answers get_state, so it offers no setter to wait on.
    for name in ("apply_state", "apply_state_async", "restore_snapshot", "wait_for_apply"):
        assert not hasattr(e, name)
