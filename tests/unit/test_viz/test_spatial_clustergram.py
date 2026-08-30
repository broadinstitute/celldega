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
