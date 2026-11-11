"""Clerk as a sidecar or wide panel beside linked views, and inline Enrichr results."""

import inspect
import json
import warnings

import numpy as np
import pandas as pd
import pytest

from tests.unit.test_viz.test_clerk_lookups import _clerk


try:
    from ipywidgets import HBox, VBox

    from celldega import clerk as clerk_llm
    from celldega import viz
    from celldega.clerk import lookups
    from celldega.clust import Matrix
    from celldega.viz import Clerk, Clustergram, Enrich, Landscape
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _views():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        landscape = Landscape(base_url="https://example.org/sample")
    mat = Matrix(
        pd.DataFrame(
            np.arange(6).reshape(2, 3).astype(float), index=["G1", "G2"], columns=["A", "B", "C"]
        )
    )
    mat.cluster()
    return landscape, Clustergram(matrix=mat)


def test_sidecar_clerk_ends_the_row_linked_to_every_view():
    landscape, cgm = _views()
    enrich = Enrich(width=250, height=700)
    row = viz.spatial_clustergram(landscape, cgm, enrich=enrich, clerk=True, height="640px")
    assert isinstance(row, HBox)
    *views, clerk = row.children
    assert views == [landscape, cgm, enrich] and isinstance(clerk, Clerk)
    # A narrow column the row's height, like Enrich.
    # Clerk fills the room the row leaves, within a narrow column's bounds...
    assert clerk.width == 0 and clerk.height == 640
    assert (clerk.layout.min_width, clerk.layout.max_width) == ("240px", "300px")
    # ...the views keep their widths, and a row too wide for the notebook scrolls.
    assert landscape.layout.width == "600px"
    assert landscape.layout.flex == cgm.layout.flex == enrich.layout.flex == "0 0 auto"
    assert (row.layout.width, row.layout.overflow) == ("100%", "auto hidden")
    assert row.layout.padding == "0 0 14px 0"  # room for the scrollbar under the views
    assert clerk._linked_widgets == {"landscape": landscape, "clustergram": cgm, "enrich": enrich}
    assert clerk.fetch_enrichr is False  # it reads the Enrich panel instead


def test_wide_clerk_goes_full_width_under_the_row():
    landscape, cgm = _views()
    clerk = Clerk(width=500, height=520)
    layout = viz.spatial_clustergram(landscape, cgm, clerk=clerk, clerk_layout="wide")
    assert isinstance(layout, VBox)
    row, below = layout.children
    assert list(row.children) == [landscape, cgm] and below is clerk
    assert clerk.width == 0 and clerk.height == 520
    with pytest.raises(ValueError, match="clerk_layout"):
        viz.spatial_clustergram(landscape, cgm, clerk=True, clerk_layout="tall")


def test_a_prelinked_clerk_is_not_linked_twice():
    landscape, cgm = _views()
    clerk = Clerk(landscape=landscape, clustergram=cgm)
    observers = len(landscape._trait_notifiers["raster_png"]["change"])
    viz.spatial_clustergram(landscape, cgm, clerk=clerk)
    assert len(landscape._trait_notifiers["raster_png"]["change"]) == observers
    assert clerk.layout.max_width == f"{viz.CLERK_SIDECAR_MAX_WIDTH}px"  # still a sidecar


def test_a_sidecar_keeps_a_width_the_caller_set():
    landscape, cgm = _views()
    clerk = Clerk(width=300)
    viz.spatial_clustergram(landscape, cgm, clerk=clerk)
    assert clerk.width == 300 and clerk.layout.flex == "0 0 auto"


def _enrichr_question(monkeypatch, results):
    w, _cgm, _requests = _clerk(monkeypatch)
    monkeypatch.setattr(lookups, "enrichr", lambda genes, libraries: results(genes))
    monkeypatch.setattr(lookups, "pubmed", lambda query: [])
    block = {"lookup": {"markers": {"clusters": ["4"], "n": 5}, "enrichr": [{"cluster": "4"}]}}
    replies = iter([f"```celldega-actions\n{json.dumps(block)}\n```", "Cluster 4 is goblet-like."])
    monkeypatch.setattr(clerk_llm, "ask", lambda question, **kwargs: next(replies))
    w.request = {"id": "1", "question": "What is cluster 4?"}
    assert w.wait(timeout=5)
    return w


def test_enrichr_lookups_show_inline_like_the_enrich_panel(monkeypatch):
    terms = [
        {
            "name": f"Term {i}",
            "score": 10.0 - i,
            "adjusted_p": 0.01,
            "odds_ratio": 3,
            "genes": ["MUC2"],
        }
        for i in range(12)
    ]
    w = _enrichr_question(monkeypatch, lambda genes: {"CellMarker_2024": terms, "Empty": []})
    cards = [m for m in w.messages if m["role"] == "enrichment"]
    assert len(cards) == 1
    card = cards[0]
    assert card["label"] == "cluster 4's top 1 markers" and card["genes"] == ["MUC2"]
    # The top terms per library, as the Enrich panel shows; empty libraries are left out.
    assert list(card["libraries"]) == ["CellMarker_2024"]
    shown = card["libraries"]["CellMarker_2024"]
    assert len(shown) == w.ENRICHMENT_TERMS and shown[0]["name"] == "Term 0"
    assert shown[0] == {
        "name": "Term 0",
        "score": 10.0,
        "genes": ["MUC2"],
        "adjusted_p": 0.01,
        "odds_ratio": 3.0,
    }
    # The results reach the model as text already, so the card stays out of its history.
    assert clerk_llm.llm._format_history(w.messages).count("Term 0") == 0


def test_failed_enrichr_lookups_show_no_card(monkeypatch):
    def fail(genes):
        raise OSError("Enrichr is down")

    w = _enrichr_question(monkeypatch, fail)
    assert not [m for m in w.messages if m["role"] == "enrichment"]


def _strict_ask(question, **kwargs):
    """Like clerk.ask: refuses options it doesn't take, as the real one would."""
    inspect.signature(clerk_llm.llm.ask).bind(question, **kwargs)
    return "An answer."


def test_the_panels_own_enrichr_results_show_once_per_gene_list(monkeypatch):
    w, _cgm, _requests = _clerk(monkeypatch)
    # Panel-only fields (enrichr_library) must not reach clerk.ask.
    monkeypatch.setattr(clerk_llm, "ask", _strict_ask)
    terms = [{"name": "Goblet cell", "score": 5, "genes": ["MUC2", "TFF3"]}]
    for i in range(2):
        w.request = {
            "id": str(i),
            "question": f"Question {i}",
            "gene_list": ["MUC2", "TFF3"],
            "enrichr_terms": terms,
            "enrichr_library": "CellMarker_2024",
        }
        assert w.wait(timeout=5)
    cards = [m for m in w.messages if m["role"] == "enrichment"]
    assert len(cards) == 1
    assert cards[0]["label"] == "2 selected genes"
    assert cards[0]["libraries"]["CellMarker_2024"][0]["name"] == "Goblet cell"
