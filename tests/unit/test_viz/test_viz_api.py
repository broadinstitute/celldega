"""Visualization API regressions, independent of any agent interface."""

import warnings

import numpy as np
import pandas as pd
import pytest

from celldega.clust import Matrix
from celldega.viz import Clustergram, Landscape


def _landscape():

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # no transform file: identity is fine
        return Landscape()


def _clustergram():
    import numpy as np
    import pandas as pd

    from celldega.clust import Matrix
    from celldega.viz import Clustergram

    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=[f"g{i}" for i in range(3)],
        columns=[f"s{j}" for j in range(4)],
    )
    mat = Matrix(df)
    mat.cluster()
    return Clustergram(matrix=mat)


def _named_clustergram(**kwargs) -> Clustergram:
    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=["MUC2", "TFF3", "JCHAIN"],
        columns=["4", "5", "6", "7"],
    )
    mat = Matrix(df)
    mat.cluster()
    cgm = Clustergram(matrix=mat, **kwargs)
    cgm.col_names = ["4", "5", "6", "7"]
    cgm.row_names = ["MUC2", "TFF3", "JCHAIN"]
    return cgm


def test_landscape_raster_traits_are_not_synced() -> None:
    ls = _landscape()
    for name in ("raster_png", "raster_thumb", "raster_view_state", "raster_capture_id"):
        assert ls.trait_metadata(name, "sync") is None


def test_landscape_request_raster_sends_message(monkeypatch) -> None:
    ls = _landscape()
    sent = []
    monkeypatch.setattr(ls, "send", sent.append)

    first = ls.request_raster()
    second = ls.request_raster(max_size=512, thumb_size=64)

    assert (first, second) == (1, 2)
    assert sent[-1] == {"event": "capture_raster", "id": 2, "max_size": 512, "thumb_size": 64}


def test_landscape_raster_reply_sets_traits_and_ignores_stale() -> None:
    ls = _landscape()
    reply = {"event": "raster", "id": 2, "png": "UE5H", "thumb": "VEhN", "view_state": {"zoom": 3}}
    ls._on_custom_msg(ls, reply, [])
    assert (ls.raster_png, ls.raster_thumb, ls.raster_view_state) == ("UE5H", "VEhN", {"zoom": 3})
    assert ls.raster_capture_id == 2

    # A late reply to an older request does not overwrite the newer capture.
    ls._on_custom_msg(ls, {"event": "raster", "id": 1, "png": "T0xE"}, [])
    assert ls.raster_png == "UE5H"

    ls._on_custom_msg(ls, {"event": "raster_error", "id": 3, "error": "no canvas"}, [])
    assert ls.raster_error == "no canvas"
    assert ls.raster_capture_id == 3


def test_clustergram_request_state_sends_message(monkeypatch) -> None:
    cgm = _clustergram()
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)

    assert cgm.request_state() == 1
    assert cgm.request_state(rows="ranked", cols=["s1", "s2"], max_rows=5) == 2
    assert sent[-1] == {
        "event": "get_state",
        "id": 2,
        "options": {
            "rows": "ranked",
            "cols": ["s1", "s2"],
            "max_rows": 5,
            "max_cols": 50,
            "extra_rows": [],
            "extra_cols": [],
            "include_values": True,
            "markers": None,
        },
    }
    with pytest.raises(ValueError):
        cgm.request_state(rows="everything")


def test_clustergram_state_reply_sets_traits_and_ignores_stale() -> None:
    cgm = _clustergram()
    for name in ("latest_state", "state_error", "state_capture_id"):
        assert cgm.trait_metadata(name, "sync") is None

    cgm._on_state_msg(cgm, {"event": "state", "id": 2, "state": {"kind": "clustergram"}}, [])
    assert cgm.latest_state == {"kind": "clustergram"}
    assert cgm.state_capture_id == 2

    cgm._on_state_msg(cgm, {"event": "state", "id": 1, "state": {"kind": "old"}}, [])
    assert cgm.latest_state == {"kind": "clustergram"}

    cgm._on_state_msg(cgm, {"event": "state_error", "id": 3, "error": "no data"}, [])
    assert cgm.state_error == "no data"
    assert cgm.state_capture_id == 3


_ENRICH_STATE = {
    "kind": "enrich",
    "library": "CellMarker_2024",
    "gene_list": ["MUC2", "TFF3", "SPINK4"],
    "n_genes": 3,
    "source_label": "Clustergram row crop",
    "loading": False,
    "terms": [
        {
            "name": "Goblet Cell Colon Human",
            "score": 812.4,
            "adjusted_p": 1.2e-6,
            "odds_ratio": 95.1,
            "genes": ["MUC2", "TFF3"],
        }
    ],
    "selected_term": "Goblet Cell Colon Human",
    "term_genes": ["MUC2", "TFF3"],
    "link": "https://maayanlab.cloud/Enrichr/enrich?dataset=abc",
}


def test_enrich_request_state_round_trip(monkeypatch) -> None:
    from celldega.viz import Enrich

    en = Enrich()
    sent = []
    monkeypatch.setattr(en, "send", sent.append)
    assert en.request_state(max_terms=5) == 1
    assert sent[-1] == {"event": "get_state", "id": 1, "options": {"max_terms": 5}}

    en._on_state_msg(en, {"event": "state", "id": 1, "state": _ENRICH_STATE}, [])
    assert en.latest_state["library"] == "CellMarker_2024"
    assert en.trait_metadata("latest_state", "sync") is None


def test_clustergram_apply_state_sets_controls(monkeypatch) -> None:
    cgm = _clustergram()
    cgm.row_names = ["MUC2", "TFF3"]
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)
    cgm.apply_state({"marker_level": 10, "mode": "dotplot", "size": "unit"})
    assert sent[-1]["changes"] == {"marker_level": 10, "mode": "dotplot", "size": "unit"}
    assert cgm.get_apply_result(cgm.apply_request_id) is None
    # Browser owns mutation and acknowledgement; submission must not claim completion.
    assert cgm.viz_mode == "heatmap"
    cgm.apply_state({"focus_gene": "MUC2"})
    assert sent[-1]["event"] == "apply_state" and sent[-1]["id"] == 2
    assert cgm.focused_gene == ""


def test_clustergram_apply_state_validates_before_changing() -> None:
    cgm = _clustergram()
    cgm.row_names = ["MUC2"]
    before = (cgm.rank_dim, cgm.viz_mode)
    for bad in (
        {"zoom": 2},
        {"marker_level": "lots"},
        {"marker_level": 5, "mode": "pie"},
        {"focus_gene": "NOPE"},
    ):
        with pytest.raises(ValueError):
            cgm.apply_state(bad)
    assert (cgm.rank_dim, cgm.viz_mode) == before


def test_landscape_apply_state_sends_validated_changes(monkeypatch) -> None:
    ls = _landscape()
    sent = []
    monkeypatch.setattr(ls, "send", sent.append)

    done = ls.apply_state(
        {
            "clusters": ["4", "5"],
            "genes": ["MUC2"],
            "zoom_to": {"clusters": ["4"]},
            "space": "spatial",
        }
    )
    assert done == [
        "highlighted clusters 4, 5",
        "colored cells by MUC2",
        "zoomed to clusters 4",
        "switched to the spatial view",
    ]
    assert ls.landscape_state == "spatial"  # space is a synced trait
    assert sent[-1] == {
        "event": "apply_state",
        "id": 1,
        "changes": {
            "clusters": ["4", "5"],
            "genes": ["MUC2"],
            "zoom_to": {"clusters": ["4"]},
            "space": "spatial",
        },
    }

    for bad in ({"colour": 1}, {"clusters": "4"}, {"space": "3d"}, {"zoom_to": {}}):
        with pytest.raises(ValueError):
            ls.apply_state(bad)
    assert len(sent) == 1 and ls.landscape_state == "spatial"


def test_landscape_apply_replies_and_state_traits() -> None:
    ls = _landscape()
    ls._on_apply_msg(ls, {"event": "apply_error", "id": 2, "error": "no cells"}, [])
    assert (ls.apply_error, ls.apply_capture_id) == ("no cells", 2)
    ls._on_apply_msg(ls, {"event": "applied", "id": 3, "done": ["x"]}, [])
    assert (ls.apply_error, ls.apply_capture_id) == ("", 3)
    for name in ("latest_state", "apply_error", "apply_capture_id"):
        assert ls.trait_metadata(name, "sync") is None


def test_landscape_neighborhood_summary() -> None:
    ls = _landscape()
    ls.cluster_attr = "leiden"
    ls.meta_cell = pd.DataFrame(
        {"leiden": ["4", "4", "5", "6"]}, index=pd.Index(["c1", "c2", "c3", "c4"])
    )
    ls.nbhd_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "properties": {"name": "crypt_A", "cell_ids": ["c1", "c2", "c3"]},
            }
        ],
    }
    assert ls.neighborhood_summary() == [
        {
            "name": "crypt_A",
            "space": "spatial",
            "n_cells": 3,
            "clusters": [
                {"name": "4", "count": 2, "fraction": 0.667},
                {"name": "5", "count": 1, "fraction": 0.333},
            ],
        }
    ]


def test_clustergram_set_categories(monkeypatch) -> None:
    cgm = _named_clustergram(manual_col_cat="cell_type")
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)

    done = cgm.apply_state({"categories": {"values": {"4": "Goblet cells", "5": "Plasma cells"}}})
    assert done == ["submitted col categories (cell_type)"]
    assert sent[-1] == {
        "event": "apply_state",
        "id": 1,
        "changes": {
            "categories": {
                "attribute": "cell_type",
                "values": {"4": "Goblet cells", "5": "Plasma cells"},
            }
        },
    }
    with pytest.raises(ValueError, match="not col names"):
        cgm.set_categories({"99": "x"})


def test_clustergram_set_categories_needs_an_attribute(monkeypatch) -> None:
    cgm = _named_clustergram()
    monkeypatch.setattr(cgm, "send", lambda content: None)
    with pytest.raises(ValueError, match="no manual col category"):
        cgm.set_categories({"4": "Goblet cells"})
    assert cgm.set_categories({"4": "Goblet cells"}, attribute="clerk_cell_type") == 1


def test_clustergram_screenshot_reply_sets_raster_traits(monkeypatch) -> None:
    cgm = _named_clustergram()
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)
    request_id = cgm.request_raster(max_size=512)
    assert sent[-1] == {
        "event": "capture_raster",
        "id": request_id,
        "max_size": 512,
        "thumb_size": 192,
    }
    cgm._on_custom_msg(cgm, {"event": "raster", "id": request_id, "png": "C", "thumb": "c"}, [])
    assert (cgm.raster_png, cgm.raster_thumb, cgm.raster_capture_id) == ("C", "c", request_id)
    # Like the Landscape's, screenshots are never saved into the notebook.
    assert "raster_png" not in cgm.keys


def test_navigation_controls_validate_before_mutation(monkeypatch):
    cgm = _named_clustergram()
    sent = []
    monkeypatch.setattr(cgm, "send", sent.append)
    settings = {
        "order": {"row": "rank", "col": ["7", "6", "5", "4"]},
        "crop": {"row": ["MUC2"], "col": None},
        "view": {"target": [12, 20], "zoom": [0, 2]},
    }
    cgm.apply_state(settings)
    assert sent[-1]["changes"] == settings
    original = cgm.rank_dim
    for invalid in (
        {"crop": {"row": ["missing"]}},
        {"order": {"col": ["4"]}},
        {"view": {"zoom": [0, float("nan")]}},
    ):
        with pytest.raises(ValueError):
            cgm.apply_state({"marker_level": 25, **invalid})
        assert cgm.rank_dim == original
    assert len(sent) == 1
    cgm._on_apply_msg(cgm, {"event": "apply_error", "id": 1, "error": "unavailable"}, [])
    assert cgm.apply_error == "unavailable"


def test_landscape_controls_and_invalid_camera(monkeypatch):
    landscape = _landscape()
    sent = []
    monkeypatch.setattr(landscape, "send", sent.append)
    settings = {
        "layers": {"image": False, "cells": True},
        "channels": {"DAPI": {"visible": True, "intensity": 30}},
        "sliders": {"cell": 37, "trx": {"opacity": 80}},
        "image_source": "primary",
    }
    landscape.apply_state(settings)
    assert sent[-1]["changes"] == settings
    for invalid in (
        {"view": {"target": [1]}},
        {"view": {"zoom": float("inf")}},
        {"layers": {"cells": "yes"}},
        {"sliders": {"cell": 101}},
        {"space": "umap", "zoom_to": {"clusters": ["4"]}},
    ):
        with pytest.raises(ValueError):
            landscape.apply_state(invalid)
    assert len(sent) == 1
