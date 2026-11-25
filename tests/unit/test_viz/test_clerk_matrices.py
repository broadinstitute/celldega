"""Clerk with a Clustergram of several matrices (``Clustergram(matrix={name: Matrix})``)."""

import json

import numpy as np
import pandas as pd

from tests.unit.test_viz.snapshot_helpers import snapshot_browser


CLUSTERS = [str(i) for i in range(5)]
GENES = [f"GENE{i}" for i in range(60)]


def _expression(name="expr_clerk"):
    from celldega.clust import Matrix

    rng = np.random.default_rng(0)
    data = pd.DataFrame(rng.random((len(GENES), len(CLUSTERS))), index=GENES, columns=CLUSTERS)
    matrix = Matrix(data, name=name, description="Mean expression per cluster.")
    matrix.set_size_matrix(data / 2)
    matrix._marker_ranks = pd.DataFrame(
        {
            "group": [c for c in CLUSTERS for _ in range(3)],
            "names": [GENES[3 * i + k] for i in range(len(CLUSTERS)) for k in range(3)],
            "rank": [k for _ in CLUSTERS for k in range(3)],
        }
    )
    matrix.cluster()
    return matrix


def _enrichment(name="nhood_clerk"):
    from celldega.clust import Matrix

    rng = np.random.default_rng(1)
    z = rng.normal(scale=5, size=(5, 5))
    data = pd.DataFrame((z + z.T) / 2, index=CLUSTERS, columns=CLUSTERS)
    matrix = Matrix(
        data,
        row_entity="cluster",
        col_entity="cluster",
        name=name,
        description="Squidpy neighborhood enrichment z-scores; positive: neighbors more often.",
    )
    matrix.cluster()
    return matrix


def _clustergram(**kwargs):
    from celldega.viz import Clustergram

    return Clustergram(
        matrix={"Gene expression": _expression(), "Neighborhood enrichment": _enrichment()},
        **kwargs,
    )


def _answer_states(monkeypatch, cgm, state):
    """Answer this Clustergram's state requests like a browser would."""

    def render(content):
        if content.get("event") == "get_state":
            answer = {**state, "options": content.get("options")}
            cgm._on_state_msg(cgm, {"event": "state", "id": content["id"], "state": answer}, [])

    monkeypatch.setattr(cgm, "send", snapshot_browser(cgm, render))


def _browser_state(matrix, rows, cols, **extra):
    return {
        "kind": "clustergram",
        "matrix": matrix,
        "rows": {"selection_mode": "viewport", "names": list(rows), "total": len(rows)},
        "cols": {"selection_mode": "viewport", "names": list(cols), "total": len(cols)},
        "values": {"values": [[1.0] * len(cols) for _ in rows]},
        **extra,
    }


def test_matrix_state_summarizes_a_matrix_not_on_screen() -> None:
    from celldega.clerk.matrices import matrix_state

    small = matrix_state(
        _enrichment("nhood_small"),
        "Neighborhood enrichment",
        labels={"cell_type": {"1": "Podocyte"}},
    )
    assert small["matrix"] == "Neighborhood enrichment"
    assert small["description"].startswith("Squidpy")
    # A small matrix is listed whole, in dendrogram order, with its groups.
    assert sorted(small["rows"]["names"]) == CLUSTERS
    assert len(small["values"]["values"]) == len(CLUSTERS)
    assert small["cols"]["groups"]["groups"]
    assert small["rows"]["attributes"][0]["values"][small["rows"]["names"].index("1")] == "Podocyte"

    # A big one lists only the rows asked about.
    big = matrix_state(_expression("expr_big"), "Gene expression", extra_rows=["GENE7", "nope"])
    assert big["rows"]["names"] == ["GENE7"]
    assert big["rows"]["groups"] is None
    assert len(big["values"]["sizes"][0]) == len(CLUSTERS)


def test_question_lists_the_matrices_and_summarizes_the_one_off_screen(monkeypatch) -> None:
    from celldega import clerk as clerk_llm
    from celldega.viz import Clerk

    cgm = _clustergram(name="clerk_multi_1")
    clerk = Clerk(clustergram=cgm)
    clerk.snapshot_timeout = 5
    _answer_states(
        monkeypatch, cgm, _browser_state("Gene expression", ["GENE1", "GENE2"], CLUSTERS)
    )
    seen = {}

    def fake_ask(question, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)
    clerk.request = {"id": "1", "question": "Which clusters are next to cluster 2?"}
    assert clerk.wait(timeout=5)

    matrices = {m["name"]: m for m in seen["matrices"]}
    assert matrices["Gene expression"]["on_screen"] is True
    assert matrices["Neighborhood enrichment"]["description"].startswith("Squidpy")
    assert (matrices["Neighborhood enrichment"]["rows"], matrices["Gene expression"]["rows"]) == (
        5,
        60,
    )
    summary = seen["matrix_states"]["Neighborhood enrichment"]
    assert sorted(summary["cols"]["names"]) == CLUSTERS
    assert any(
        line.startswith("Clustergram matrix 'Neighborhood enrichment': 5 rows x 5 columns")
        for line in clerk.record[-1]["sent_with"]
    )
    # The help names the matrices Clerk can switch to.
    assert '"Neighborhood enrichment"' in seen["actions_help"]


def test_marker_lookups_read_the_matrix_with_markers_when_it_is_off_screen(monkeypatch) -> None:
    from celldega.viz import Clerk

    cgm = _clustergram(name="clerk_multi_2", active_matrix="Neighborhood enrichment")
    clerk = Clerk(clustergram=cgm)
    clerk.snapshot_timeout = 5
    _answer_states(
        monkeypatch,
        cgm,
        _browser_state(
            "Neighborhood enrichment",
            CLUSTERS,
            CLUSTERS,
            marker_ranking=False,
            cluster_markers=[{"cluster": "1", "found": False, "genes": []}],
        ),
    )
    views = clerk._refresh_views("q", markers={"clusters": ["1"], "n": 2})
    markers = views["clustergram_state"]["cluster_markers"]
    assert markers[0]["found"] is True
    assert [g["name"] for g in markers[0]["genes"]] == ["GENE3", "GENE4"]
    assert markers[0]["genes"][0]["size"] is not None
    assert any("come from the matrix 'Gene expression'" in note for note in views["notes"])
    # The expression matrix, off screen, lists the genes asked about.
    views = clerk._refresh_views("Is GENE5 high in cluster 1?")
    assert views["matrix_states"]["Gene expression"]["rows"]["names"] == ["GENE5"]


def test_prompt_shows_the_matrices_with_descriptions() -> None:
    from celldega.clerk import llm
    from celldega.clerk.matrices import matrix_state

    matrices = [
        {"name": "Gene expression", "description": "Mean expression.", "on_screen": True},
        {"name": "Neighborhood enrichment", "description": "z-scores.", "rows": 5, "cols": 5},
    ]
    summary = matrix_state(_enrichment("nhood_prompt"), "Neighborhood enrichment")
    prompt = llm.build_prompt(
        "q",
        clustergram_state=_browser_state("Gene expression", ["GENE1"], CLUSTERS),
        matrices=matrices,
        matrix_states={"Neighborhood enrichment": summary},
    )
    assert "## Clustergram matrices" in prompt
    assert "- 'Neighborhood enrichment' (not on screen, summarized below; 5 rows x 5" in prompt
    assert "## Clustergram (what the scientist sees): matrix 'Gene expression'" in prompt
    assert "## Clustergram matrix 'Neighborhood enrichment' (not on screen)" in prompt
    # One matrix: no list.
    assert llm.format_matrices(matrices[:1]) == ""

    nxt = llm.build_next_question(
        "q", matrices=matrices, matrix_states={"Neighborhood enrichment": summary}
    )
    assert "## Clustergram matrices" in nxt
    follow_up = llm.build_follow_up(matrix_states={"Neighborhood enrichment": summary})
    assert "## Clustergram matrix 'Neighborhood enrichment' (not on screen), now" in follow_up


def test_views_naming_another_matrix_use_its_groups() -> None:
    from celldega.clerk.llm import resolve_dendrogram_groups
    from celldega.clerk.matrices import matrix_state

    summary = matrix_state(_enrichment("nhood_groups"), "Neighborhood enrichment")
    group = summary["cols"]["groups"]["groups"][0]
    views = {
        "1A": {
            "caption": "c",
            "clustergram": {
                "matrix": "Neighborhood enrichment",
                "dendrogram_group": {"axis": "col", "name": group["name"]},
            },
        }
    }
    resolved, problems = resolve_dendrogram_groups(
        views,
        _browser_state("Gene expression", ["GENE1"], CLUSTERS),
        {"Neighborhood enrichment": summary},
    )
    assert problems == []
    settings = resolved["1A"]["clustergram"]
    assert settings["matrix"] == "Neighborhood enrichment"
    assert settings["selection"]["dendrogram"] == {"axis": "col", "members": group["members"]}


def test_continuing_session_sends_only_changed_matrices() -> None:
    from celldega.viz.widget import _changed_views, _summary_view, _unchanged_views, _views_since

    a = _browser_state("Gene expression", ["0"], ["0"])
    b = _browser_state("Gene expression", ["1"], ["1"])
    listed = [{"name": "Gene expression", "on_screen": True}]
    sent = {"clustergram_state": a, "matrix_states": {"x": a, "y": a}, "matrices": listed}
    call = {"clustergram_state": a, "matrix_states": {"x": a, "y": b}, "matrices": listed}
    assert _unchanged_views(sent, call) == ["Clustergram", "Clustergram matrix 'x'"]
    since = _views_since(sent, call)
    assert since["matrix_states"] == {"y": b}
    assert "matrices" not in since
    moved = [{"name": "Gene expression", "on_screen": False}]
    assert _views_since(sent, {**call, "matrices": moved})["matrices"] == moved
    views = {"clustergram_state": a, "matrix_states": {"x": b, "y": b}}
    assert _changed_views(call, views, "")["matrix_states"] == {"x": b}
    assert _summary_view("Clustergram matrix 'y': 5 rows x 5 columns") == "Clustergram matrix 'y'"
    assert _summary_view("Clustergram: 4 rows") == "Clustergram"


def test_saved_case_lists_every_matrix(tmp_path) -> None:
    from celldega.viz import Clerk

    clerk = Clerk(clustergram=_clustergram(name="clerk_multi_3"))
    clerk.messages = [{"role": "user", "content": "q"}]
    saved = json.loads(clerk.save_conversation(tmp_path / "case.json").read_text())
    source = saved["sources"]["clustergram"]
    assert [m["name"] for m in source["matrices"]] == ["Gene expression", "Neighborhood enrichment"]
    assert source["active_matrix"] == "Gene expression"
