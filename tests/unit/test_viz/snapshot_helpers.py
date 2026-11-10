"""Adapt existing deterministic fake renderers to the coordinated snapshot protocol.

Only test fixtures call the legacy handlers to assemble their fake scene. Production
capture sends one message; transport/order assertions live in test_snapshots.py.
"""

from copy import deepcopy

from celldega.viz.widget import _clustergram_reproduction, _landscape_reproduction


def snapshot_browser(widget, render):
    def send(content):
        if content.get("event") == "restore_snapshot":
            render(content)
            state = content["snapshot"]["state"]
            if "space" in state:
                widget.landscape_state = state["space"]
            if "focus_gene" in state:
                widget.focused_gene = state["focus_gene"]
            widget._on_apply_msg(widget, {"event": "applied", "id": content["id"]}, [])
            return None
        if content.get("event") != "capture_snapshot":
            return render(content)
        rid = content["id"]
        render({"event": "capture_raster", "id": rid})
        render({"event": "get_state", "id": rid, "options": content["options"]["state"]})
        state = deepcopy(widget.latest_state)
        kind = "clustergram" if hasattr(widget, "set_categories") else "landscape"
        settings = (
            _clustergram_reproduction if kind == "clustergram" else _landscape_reproduction
        )(state)
        if kind == "clustergram":
            settings.setdefault("focus_gene", "")
        snapshot = {
            "schema": "celldega.view",
            "version": 2,
            "kind": kind,
            "identity": {"revision": "", "cells": {"count": 2, "hash": "0" * 14}},
            "viewport": {"width": 640, "height": 480},
            "state": settings,
            "observed_state": state,
            "image": {
                "png": widget.raster_png,
                "thumb": widget.raster_thumb,
                "view_state": dict(widget.raster_view_state),
            },
        }
        widget._on_snapshot_msg(widget, {"event": "snapshot", "id": rid, "snapshot": snapshot}, [])
        return None

    return send
