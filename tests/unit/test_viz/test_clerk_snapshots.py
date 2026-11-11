"""Clerk completion and Back behavior over the shared snapshot API."""

import pytest

from celldega.viz import Clerk
from tests.unit.test_viz.test_snapshots import snapshot, widget


def test_newer_apply_reply_cannot_confirm_an_older_failed_request():
    w = widget()
    clerk = Clerk(landscape=w)
    clerk.snapshot_timeout = 0.01
    w._on_apply_msg(w, {"event": "applied", "id": 2}, [])
    clerk._pending_landscape_apply = 1
    with pytest.raises(ValueError, match="timeout"):
        clerk._wait_for_landscape_apply()
    w._on_apply_msg(w, {"event": "apply_error", "id": 1, "error": "wrong dataset"}, [])
    assert w.apply_error == ""  # latest request succeeded; the old one did not
    clerk._pending_landscape_apply = 1
    with pytest.raises(ValueError, match="wrong dataset"):
        clerk._wait_for_landscape_apply()


def test_failed_back_keeps_saved_view_for_retry():
    w = widget()
    clerk = Clerk(landscape=w)
    saved = {"snapshots": {"landscape": snapshot("original")}}
    clerk._saved_view = saved
    clerk.can_restore = True
    w.send = lambda msg: w._on_apply_msg(
        w, {"event": "apply_error", "id": msg["id"], "error": "wrong dataset"}, []
    )
    clerk._restore_view()
    assert clerk._saved_view == saved and clerk.can_restore
    assert "wrong dataset" in clerk.error
    w.send = lambda msg: w._on_apply_msg(w, {"event": "applied", "id": msg["id"]}, [])
    clerk._restore_view()
    assert clerk._saved_view is None and not clerk.can_restore


@pytest.mark.parametrize("failure", ["wrong dataset", "timeout"])
def test_image_restore_failure_is_visible_and_keeps_back(failure):
    w = widget()
    clerk = Clerk(landscape=w)
    clerk.snapshot_timeout = 0.01
    saved = {"snapshots": {"landscape": snapshot("original")}}
    clerk._saved_view = saved
    clerk.can_restore = True

    def send(msg):
        if failure != "timeout":
            w._on_apply_msg(w, {"event": "apply_error", "id": msg["id"], "error": failure}, [])

    w.send = send
    clerk.request = {"id": "image", "show_snapshot": {"landscape": snapshot("image")}}
    clerk._last_evidence.result(timeout=5)
    assert clerk._saved_view == saved and clerk.can_restore
    assert clerk.messages[-1] == {"role": "error", "content": clerk.error}
    assert ("wrong dataset" if failure != "timeout" else "did not confirm") in clerk.error
