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


@pytest.fixture(autouse=True)
def _no_lookup_cache_on_disk(monkeypatch):
    """Clerk caches Enrichr / PubMed results in ``<output_dir>/lookup_cache``. Keep
    tests' fake results off the disk (and out of each other's way) unless a test
    sets ``clerk.lookup_cache`` (with a temporary ``output_dir``)."""
    try:
        from celldega.clerk import lookups
        from celldega.viz import Clerk
    except Exception:  # pragma: no cover - deps missing; the tests skip themselves
        return
    monkeypatch.setattr(Clerk, "lookup_cache", None)
    monkeypatch.setattr(lookups, "cache_dir", None)
