"""Shared test setup for the viz widgets."""

import pytest


@pytest.fixture(autouse=True)
def _no_clustergram_screenshots_in_clerk(monkeypatch):
    """Clerk screenshots a linked Clustergram with each capture. Most tests' fake
    browsers only answer state requests, so turn that off unless a test asks for it
    (``clerk.capture_clustergram = True``)."""
    try:
        from celldega.viz import Clerk
    except Exception:  # pragma: no cover - deps missing; the tests skip themselves
        return
    monkeypatch.setattr(Clerk, "capture_clustergram", False)
