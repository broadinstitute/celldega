"""Captions: Markdown under a figure whose links change it (``dega.viz.caption``)."""

import pytest


def test_caption_is_a_clerk_in_caption_mode_with_views():
    from celldega.viz import Clerk, caption

    widget = caption(
        "Cluster 4 sits with cluster 7 [in every glomerulus](view:glom).",
        {
            "glom": {
                "caption": "Glomeruli",
                "landscape": {"zoom_to": {"clusters": ["7"]}, "clusters": ["4", "7"]},
                "clustergram": {"matrix": "Neighborhood enrichment"},
            }
        },
    )
    assert isinstance(widget, Clerk)
    assert widget.mode == "caption"
    assert widget.caption.startswith("Cluster 4")
    view = widget.caption_views["glom"]
    assert view["clustergram"] == {"matrix": "Neighborhood enrichment"}
    assert view["landscape"]["clusters"] == ["4", "7"]


def test_caption_views_take_snapshots_and_reject_unknown_settings():
    from celldega.viz.caption import caption_view

    saved = {"kind": "landscape", "state": {"view": {}}, "description": "Glomerulus"}
    assert caption_view(saved) == {"caption": "Glomerulus", "snapshot": {"landscape": saved}}
    assert caption_view({"snapshot": {"clustergram": saved}})["snapshot"] == {"clustergram": saved}
    with pytest.raises(ValueError, match="unknown caption view"):
        caption_view({"table": {}})
    with pytest.raises(ValueError, match="unknown landscape"):
        caption_view({"landscape": {"explode": True}})
    with pytest.raises(TypeError):
        caption_view("view:1")


def test_caption_links_the_genes_it_names(monkeypatch):
    from celldega.viz import Clerk

    monkeypatch.setattr(Clerk, "_known_genes", lambda self: ["PODXL", "NPHS2", "EMCN"])
    widget = Clerk(mode="caption", caption="PODXL and NPHS2 but not EMCN")
    assert widget.caption_genes == ["PODXL", "NPHS2", "EMCN"]
    widget.caption = "Only NPHS2 here."
    assert widget.caption_genes == ["NPHS2"]
    with pytest.raises(Exception, match="mode"):
        Clerk(mode="journal-ish")
