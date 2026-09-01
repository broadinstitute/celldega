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
    mat = Matrix(df, disable_processing=True)
    mat.clust()
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


def test_clustergram_enrich_preserves_current_genes_on_single_row_label():
    cgm = _clustergram()
    box = clustergram_enrich(cgm)
    enrich = box.children[1]

    assert enrich.height == 700

    enrich.gene_list = ["g0", "g1"]
    cgm.click_info = {"type": "row_label", "value": {"name": "g1"}}
    cgm.selected_genes = ["g1"]

    assert enrich.gene_list == ["g0", "g1"]

    # Row dendrogram selections remain meaningful gene sets and continue to
    # populate the enrichment widget under the default configuration.
    cgm.click_info = {
        "type": "row_dendro",
        "value": {"selected_names": ["g0", "g1"]},
    }
    cgm.selected_genes = ["g0", "g1"]

    assert enrich.gene_list == ["g0", "g1"]
    assert enrich.source_label == "Dendrogram selection"

    # Gene row crops are also meaningful enrichment gene sets. A brush crop
    # (no dendro crop_source) reads as a brush selection...
    cgm.click_info = {
        "type": "row_crop",
        "value": {"selected_names": ["g2", "g3"]},
    }
    cgm.selected_genes = ["g2", "g3"]

    assert enrich.gene_list == ["g2", "g3"]
    assert enrich.source_label == "Brush selection"

    # ...while a dendrogram double-click crop names the gesture.
    cgm.click_info = {
        "type": "row_crop",
        "value": {"selected_names": ["g0", "g2"], "crop_source": "dendrogram"},
    }
    cgm.selected_genes = ["g0", "g2"]

    assert enrich.source_label == "Dendrogram selection"

    # Column-label clicks (single or double) send the column's top genes with
    # the column name as the source ("Clustergram" is implied).
    cgm.click_info = {"type": "col_label", "value": {"name": "s2", "index": 2}}
    cgm.selected_genes = ["g1", "g0"]

    assert enrich.gene_list == ["g1", "g0"]
    assert enrich.source_label == "s2"

    # Clicking a gene in Enrich focuses the matching Clustergram row without
    # changing the enrichment gene list.
    enrich.focused_gene = "g1"
    assert cgm.focused_gene == "g1"
    assert enrich.gene_list == ["g1", "g0"]


def test_clustergram_enrich_mirrors_term_genes_to_highlighted_genes():
    cgm = _clustergram()
    box = clustergram_enrich(cgm)
    enrich = box.children[1]

    assert cgm.highlighted_genes == []

    # Selecting an enriched term (Enrich lowercases its member genes) should
    # highlight those genes' row labels in the Clustergram.
    enrich.term_genes = ["g0", "g2"]
    assert cgm.highlighted_genes == ["g0", "g2"]

    # CLEAR / term deselection resets term_genes and clears the highlight.
    enrich.term_genes = []
    assert cgm.highlighted_genes == []


def test_clustergram_enrich_refocuses_the_same_gene():
    cgm = _clustergram()
    box = clustergram_enrich(cgm)
    enrich = box.children[1]

    focus_events = []
    cgm.observe(lambda change: focus_events.append(change["new"]), names="focused_gene")

    enrich.focused_gene = "g1"
    assert cgm.focused_gene == "g1"

    # Enrich CLEAR blanks its own focused_gene; the Clustergram keeps focus.
    enrich.focused_gene = ""
    assert cgm.focused_gene == "g1"

    # Re-clicking the same gene must still notify the front end (traitlets
    # suppresses no-change sets), so the link blanks then re-sets the trait.
    focus_events.clear()
    enrich.focused_gene = "g1"
    assert cgm.focused_gene == "g1"
    assert focus_events == ["", "g1"]


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
