"""Evidence links: genes, clusters and cited views in Clerk's answers replay in the views."""

import json
import warnings

import numpy as np
import pandas as pd
import pytest

from tests.unit.test_viz.snapshot_helpers import snapshot_browser


try:
    from celldega import clerk as clerk_llm
    from celldega.clust import Matrix
    from celldega.viz import Clerk, Clustergram, Landscape
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _clustergram() -> Clustergram:
    df = pd.DataFrame(
        np.arange(12).reshape(3, 4).astype(float),
        index=["MUC2", "TFF3", "JCHAIN"],
        columns=["4", "5", "6", "7"],
    )
    mat = Matrix(df)
    mat.cluster()
    cgm = Clustergram(matrix=mat)
    cgm.col_names = ["4", "5", "6", "7"]
    cgm.row_names = ["MUC2", "TFF3", "JCHAIN"]
    return cgm


def _linked(monkeypatch):
    """A Clerk linked to a Landscape and Clustergram whose 'browsers' reply."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        ls = Landscape()
    cgm = _clustergram()
    w = Clerk(landscape=ls, clustergram=cgm, capture_on_select=False)
    w.snapshot_timeout = 5
    sent = {"landscape": [], "clustergram": []}
    ls_state = {
        "kind": "landscape",
        "space": "spatial",
        "view_state": {"target": [1.0, 2.0, 0], "zoom": -3.0},
        "color_by": "cluster",
        "selected_clusters": [],
        "selected_genes": [],
    }

    def ls_send(content):
        sent["landscape"].append(content)
        if content.get("event") == "capture_raster":
            ls._on_custom_msg(ls, {"event": "raster", "id": content["id"], "png": "P"}, [])
        if content.get("event") == "get_state":
            ls._on_state_msg(ls, {"event": "state", "id": content["id"], "state": ls_state}, [])

    def cgm_send(content):
        sent["clustergram"].append(content)
        if content.get("event") == "get_state":
            state = {"kind": "clustergram", "marker_level": {"current": 5}, "display": {}}
            cgm._on_state_msg(cgm, {"event": "state", "id": content["id"], "state": state}, [])

    monkeypatch.setattr(ls, "send", snapshot_browser(ls, ls_send))
    monkeypatch.setattr(cgm, "send", snapshot_browser(cgm, cgm_send))
    return w, ls, cgm, sent


def _applied(sent, widget):
    return [
        m["changes"] if m["event"] == "apply_state" else m["snapshot"]["state"]
        for m in sent[widget]
        if m.get("event") in ("apply_state", "restore_snapshot")
    ]


def test_extract_views_validates_and_drops_bad_views() -> None:
    answer = (
        "A ring [Fig 1A](view:1A).\n```celldega-views\n"
        + json.dumps(
            {
                "1A": {"caption": "Cluster 4", "landscape": {"clusters": ["4"]}},
                "1B": {"landscape": {"explode": True}},
                "1C": {"caption": "nothing"},
                "bad id!": {"landscape": {"clusters": ["5"]}},
            }
        )
        + "\n```"
    )
    text, views, problem = clerk_llm.extract_views(answer)
    assert text == "A ring [Fig 1A](view:1A)."
    assert views == {"1A": {"caption": "Cluster 4", "landscape": {"clusters": ["4"]}}}
    assert "1B: unknown landscape setting(s) ['explode']" in problem
    assert "1C changes nothing" in problem
    assert "'bad id!' is not a valid view" in problem
    assert clerk_llm.extract_views("no views") == ("no views", None, None)


def test_answers_carry_their_genes_and_views(monkeypatch) -> None:
    w, _ls, _cgm, _sent = _linked(monkeypatch)
    w.capture_clustergram = False
    views = {"1A": {"caption": "MUC2 in 4", "landscape": {"genes": ["MUC2"]}}}
    answer = f"MUC2 marks cluster 4 [Fig 1A](view:1A).\n```celldega-views\n{json.dumps(views)}\n```"
    monkeypatch.setattr(clerk_llm, "ask", lambda q, **kw: answer)
    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    message = w.messages[-1]
    assert message["genes"] == ["MUC2"]
    assert message["views"] == views
    assert w.cluster_names == ["4", "5", "6", "7"]  # "cluster 4" can be linked
    step = next(s for s in w.record[-1]["steps"] if s["kind"] == "answer")
    assert step["views"] == views  # kept for the report


def test_clicking_a_gene_shows_it_in_both_views_and_back_restores(monkeypatch) -> None:
    w, ls, cgm, sent = _linked(monkeypatch)
    w.request = {"id": "g1", "show_genes": ["MUC2"], "focus": "MUC2"}
    w._last_evidence.result(timeout=5)
    assert _applied(sent, "landscape")[-1] == {"genes": ["MUC2"]}
    assert cgm.highlighted_genes == ["MUC2"]
    assert cgm.focused_gene == "MUC2"  # one gene: the Clustergram zooms to it
    assert w.can_restore is True

    # Several genes: all shown and marked, but the focus (which a Landscape linked
    # through Enrich would turn into a one-gene selection) is left alone.
    w.request = {"id": "g1b", "show_genes": ["MUC2", "TFF3", "NOT_A_ROW"], "focus": "TFF3"}
    w._last_evidence.result(timeout=5)
    assert _applied(sent, "landscape")[-1] == {"genes": ["MUC2", "TFF3", "NOT_A_ROW"]}
    assert cgm.highlighted_genes == ["MUC2", "TFF3"]  # only Clustergram rows
    assert cgm.focused_gene == "MUC2"

    # A second click doesn't overwrite the saved view.
    w.request = {"id": "g2", "show_genes": ["TFF3"], "focus": "TFF3"}
    w._last_evidence.result(timeout=5)
    assert w._saved_view["landscape"]["view"] == {"target": [1.0, 2.0, 0], "zoom": -3.0}

    w.request = {"id": "back", "restore_view": True}
    w._last_evidence.result(timeout=5)
    # The whole saved view is validated and applied in the browser.
    assert _applied(sent, "landscape")[-1] == {
        "space": "spatial",
        "view": {"target": [1.0, 2.0, 0], "zoom": -3.0},
        "clusters": [],
    }
    assert ls.landscape_state == "spatial"
    assert cgm.highlighted_genes == []
    assert cgm.focused_gene == ""
    assert w.can_restore is False


def test_clicking_clusters_and_views(monkeypatch) -> None:
    w, _ls, cgm, sent = _linked(monkeypatch)
    w.request = {"id": "c1", "show_clusters": ["4", "5"]}
    w._last_evidence.result(timeout=5)
    assert _applied(sent, "landscape")[-1] == {"clusters": ["4", "5"]}

    view = {
        "landscape": {"zoom_to": {"clusters": ["4"]}, "genes": ["MUC2"]},
        "clustergram": {"marker_level": 10, "explode": True},  # unknown keys are dropped
    }
    w.request = {"id": "v1", "apply_view": view}
    w._last_evidence.result(timeout=5)
    assert _applied(sent, "landscape")[-1] == {"zoom_to": {"clusters": ["4"]}, "genes": ["MUC2"]}
    assert cgm.rank_dim == 10
    assert w.error == ""


def test_evidence_clicks_work_while_clerk_is_answering(monkeypatch) -> None:
    w, _ls, _cgm, sent = _linked(monkeypatch)
    w.pending = True  # as if a question were being answered
    w.request = {"id": "g1", "show_genes": ["MUC2"], "focus": "MUC2"}
    w._last_evidence.result(timeout=5)
    assert _applied(sent, "landscape")[-1] == {"genes": ["MUC2"]}


def test_lookup_lines_carry_their_genes(monkeypatch) -> None:
    w, _ls, _cgm, _sent = _linked(monkeypatch)
    w.capture_clustergram = False
    genes = [f"G{i}" for i in range(12)]
    replies = [
        "```celldega-actions\n" + json.dumps({"lookup": {"genes": genes}}) + "\n```",
        "Done.",
    ]
    monkeypatch.setattr(clerk_llm, "ask", lambda q, **kw: replies.pop(0))
    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    action = next(m for m in w.messages if m["role"] == "action")
    assert action["content"].startswith("Looked up 12 genes")
    assert action["genes"] == genes  # the panel lists them on hover


def test_cluster_labels_for_hover(monkeypatch) -> None:
    w, _ls, cgm, _sent = _linked(monkeypatch)
    w.findings = [{"cluster": "4", "label": "Type A"}]
    cgm.manual_col_cat = "cell_type"
    cgm.manual_cat = json.dumps({"col": {"cell_type": {"values": {"5": "Mine"}, "colors": {}}}})
    w._links_for("cluster 4")
    assert w.cluster_labels == {"4": "Type A (Clerk, tentative)", "5": "Mine"}


_GROUPS_STATE = {
    "cols": {
        "names": ["4", "5", "6", "7"],
        "groups": {
            "cut_percent": 40,
            "groups": [
                {"name": "39", "size": 2, "members": ["4", "5"]},
                {"name": "41", "size": 40, "members": ["6", "7"]},  # listed in part
            ],
        },
    }
}


def test_a_cited_dendrogram_group_is_pinned_to_the_cut_clerk_saw() -> None:
    views = {
        "2A": {
            "caption": "Group 39",
            "clustergram": {"dendrogram_group": {"axis": "col", "name": "group 39"}},
        },
        "2B": {
            "clustergram": {"dendrogram_group": {"axis": "col", "name": "41"}, "marker_level": 5}
        },
        "2C": {"clustergram": {"dendrogram_group": {"axis": "row", "name": "7"}}},
        "2D": {"landscape": {"clusters": ["4"]}},
    }
    resolved, problems = clerk_llm.resolve_dendrogram_groups(views, _GROUPS_STATE)
    # Fully listed: selected by its members, at the cut the snapshot was taken at.
    assert resolved["2A"]["clustergram"] == {
        "selection": {"dendrogram": {"axis": "col", "members": ["4", "5"]}},
        "dendrogram": {"col": 40.0},
    }
    # Listed in part: selected by name (at the same cut).
    assert resolved["2B"]["clustergram"] == {
        "marker_level": 5,
        "selection": {"dendrogram": {"axis": "col", "name": "41"}},
        "dendrogram": {"col": 40.0},
    }
    # A group the snapshot doesn't show is dropped, with a note; other views stay.
    assert "2C" not in resolved and resolved["2D"] == views["2D"]
    assert problems == ["view 2C: no row dendrogram group '7' in view"]
    assert clerk_llm.resolve_dendrogram_groups(None, _GROUPS_STATE) == (None, [])


def test_clicking_a_dendrogram_group_view_selects_it(monkeypatch) -> None:
    w, _ls, _cgm, sent = _linked(monkeypatch)
    resolved, _ = clerk_llm.resolve_dendrogram_groups(
        {"2B": {"clustergram": {"dendrogram_group": {"axis": "col", "name": "41"}}}},
        _GROUPS_STATE,
    )
    w.request = {"id": "v2", "apply_view": resolved["2B"]}
    w._last_evidence.result(timeout=5)
    assert w.error == ""
    assert _applied(sent, "clustergram")[-1] == {
        "selection": {"dendrogram": {"axis": "col", "name": "41"}},
        "dendrogram": {"col": 40.0},
    }
    # Selecting a group by name is part of the Clustergram's setter, too.
    with pytest.raises(ValueError, match="members"):
        _cgm.apply_state({"selection": {"dendrogram": {"axis": "col", "name": ""}}})


def test_blocks_with_several_objects_are_merged() -> None:
    """Models sometimes write one object per change; those are read as one."""
    answer = (
        "Labeling.\n```celldega-actions\n"
        '{"clustergram": {"categories": {"values": {"4": "A"}}}}\n'
        '{"clustergram": {"categories": {"values": {"5": "B"}}, "marker_level": 5}}\n'
        "}\n```"
    )
    text, actions, problem = clerk_llm.extract_actions(answer)
    assert text == "Labeling." and problem is None
    assert actions == {
        "clustergram": {"categories": {"values": {"4": "A", "5": "B"}}, "marker_level": 5}
    }
    # Anything else is still refused, with the parser's message.
    _text, actions, problem = clerk_llm.extract_actions(
        '```celldega-actions\n{"clustergram": {}} and more\n```'
    )
    assert actions is None and "Extra data" in problem
