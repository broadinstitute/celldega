"""spatial_clustergram should generalize landscape_clustergram to CellCloud /
NeighborhoodCloud / Yearbook, without breaking the original two-widget
(Landscape + Clustergram) behavior landscape_clustergram already provided.
"""

import numpy as np
import pandas as pd
import pytest


try:
    from ipywidgets import HBox

    from celldega.clust import Matrix
    import celldega.viz as viz_mod
    from celldega.viz import (
        CellCloud,
        Clustergram,
        Landscape,
        NeighborhoodCloud,
        Yearbook,
        clustergram_enrich,
        landscape_clustergram,
        spatial_clustergram,
    )
except Exception as e:  # pragma: no cover
    pytest.skip(f"celldega viz unavailable: {e}", allow_module_level=True)


def _clustergram() -> Clustergram:
    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=[f"g{i}" for i in range(3)],
        columns=[f"s{j}" for j in range(4)],
    )
    mat = Matrix(df)
    mat.cluster()
    return Clustergram(matrix=mat)


@pytest.mark.parametrize("widget_cls", [Landscape, CellCloud, NeighborhoodCloud])
def test_spatial_clustergram_links_update_trigger_for_every_spatial_widget(widget_cls):
    spatial = widget_cls(base_url="https://example.com/data")
    cgm = _clustergram()

    box = spatial_clustergram(spatial, cgm, width="1000px", height="700px")

    assert isinstance(box, HBox)
    assert spatial in box.children
    assert cgm in box.children

    # jslink is front-end-only, but clicking the Clustergram row/col also
    # calls trigger_update via the front end; here we only assert the link
    # itself was established without raising (widget_cls must expose
    # update_trigger for jslink to succeed at all).
    cgm.click_info = {"type": "col_label", "value": {"name": "0"}}


def test_landscape_clustergram_is_still_a_working_alias():
    landscape = Landscape(base_url="https://example.com/data")
    cgm = _clustergram()

    box = landscape_clustergram(landscape, cgm)

    assert isinstance(box, HBox)
    assert landscape in box.children
    assert cgm in box.children


def _capture_links(monkeypatch):
    links = []

    def capture(kind):
        def _link(source, target):
            links.append((kind, source, target))

        return _link

    monkeypatch.setattr(viz_mod, "jslink", capture("jslink"))
    monkeypatch.setattr(viz_mod, "jsdlink", capture("jsdlink"))
    return links


@pytest.mark.parametrize(("row_enrich", "col_enrich"), [(True, False), (False, True)])
def test_clustergram_enrich_links_entirely_in_the_browser(monkeypatch, row_enrich, col_enrich):
    links = _capture_links(monkeypatch)
    cgm = _clustergram()

    box = clustergram_enrich(cgm, row_enrich=row_enrich, col_enrich=col_enrich)
    enrich = box.children[1]

    assert enrich.height == 700
    # The front end reads these to decide which selections become gene sets.
    assert cgm.row_enrich_enabled is row_enrich
    assert cgm.col_enrich_enabled is col_enrich
    assert links == [
        ("jslink", (cgm, "enrichment_genes"), (enrich, "gene_list")),
        ("jsdlink", (cgm, "enrichment_source_label"), (enrich, "source_label")),
        ("jslink", (enrich, "focused_gene"), (cgm, "focused_gene")),
        ("jsdlink", (enrich, "term_genes"), (cgm, "highlighted_genes")),
    ]

    # No Python observers: a kernel-side selection change must not touch Enrich,
    # so live and static notebooks follow the same (browser) code path.
    cgm.click_info = {"type": "row_dendro", "value": {"selected_names": ["g0", "g1"]}}
    cgm.selected_genes = ["g0", "g1"]
    assert enrich.gene_list == []


def test_spatial_clustergram_uses_browser_native_gene_focus_links(monkeypatch):
    links = []

    def capture_link(source, target):
        links.append((source, target))
        return

    monkeypatch.setattr(viz_mod, "jslink", capture_link)

    spatial = Landscape(base_url="https://example.com/data")
    cgm = _clustergram()
    box = viz_mod.spatial_clustergram(spatial, cgm, enrich=True)
    enrich = box.children[2]

    assert ((cgm, "enrichment_genes"), (enrich, "gene_list")) in links
    assert ((enrich, "focused_gene"), (cgm, "focused_gene")) in links
    assert ((enrich, "focused_gene"), (spatial, "focused_gene")) in links


def test_spatial_clustergram_matches_enrich_height_to_linked_widgets():
    spatial = Landscape(base_url="https://example.com/data")
    cgm = _clustergram()

    box = spatial_clustergram(spatial, cgm, height="840px", enrich=True)

    enrich = box.children[2]
    assert enrich.height == 840


def test_spatial_clustergram_yearbook_uses_front_end_query():
    yearbook = Yearbook(base_url="https://example.com/data")
    cgm = _clustergram()

    box = spatial_clustergram(yearbook, cgm)

    assert isinstance(box, HBox)
    assert yearbook in box.children

    cgm.click_info = {"type": "col_label", "value": {"name": "s1"}}
    assert yearbook.front_end_query.get("cluster") == {"attr": "leiden", "value": "s1"}

    cgm.click_info = {"type": "row_label", "value": {"name": "g2"}}
    assert yearbook.front_end_query.get("gene") == "g2"
