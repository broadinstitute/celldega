"""Clerk and a linked Yearbook: what Clerk sees of it, and the cells it shows there."""

import json

import numpy as np
import pandas as pd
import pytest


try:
    import anndata as ad

    from celldega import clerk as clerk_llm
    from celldega.viz import Clerk, Yearbook, link_clerk
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _adata() -> "ad.AnnData":
    rng = np.random.default_rng(0)
    obs = pd.DataFrame(
        {
            "leiden": pd.Categorical(["1", "2", "10"] * 10),
            "area": np.linspace(10, 100, 30),
        },
        index=[f"cell_{i}" for i in range(30)],
    )
    x = rng.poisson(1, (30, 3)).astype(float)
    x[:, 0] = np.arange(30)  # GENE1 ranks cells by index
    return ad.AnnData(X=x, obs=obs, var=pd.DataFrame(index=["GENE1", "GENE2", "GENE3"]))


def _linked(**clerk_kwargs):
    clerk = Clerk(**clerk_kwargs)
    yearbook = Yearbook(base_url="https://example.org/data", cluster_attr="leiden")
    link_clerk(clerk, yearbook=yearbook)
    return clerk, yearbook


def test_link_clerk_registers_a_yearbook() -> None:
    clerk, yearbook = _linked()
    assert clerk._linked_widgets["yearbook"] is yearbook
    # Linked from the constructor too.
    other = Yearbook(base_url="https://example.org/data")
    assert Clerk(yearbook=other)._linked_widgets["yearbook"] is other


def test_yearbook_action_sets_the_browser_query() -> None:
    clerk, yearbook = _linked()
    changes, _ = clerk._apply_actions(
        {"yearbook": {"cluster": 4, "gene": "GENE1", "max_cells": 5000}}
    )
    assert yearbook.front_end_query == {
        "cluster": {"attr": "leiden", "value": "4"},
        "gene": "GENE1",
        "max_cells": clerk._MAX_YEARBOOK_CELLS,
    }
    assert changes == ["the Yearbook: cluster 4, ranked by GENE1 (up to 200 cells)"]
    # The cluster column of the Yearbook's own query is kept.
    yearbook.front_end_query = {"cluster": {"attr": "cluster", "value": "1"}}
    clerk._apply_actions({"yearbook": {"cluster": "2"}})
    assert yearbook.front_end_query["cluster"] == {"attr": "cluster", "value": "2"}


@pytest.mark.parametrize(
    ("spec", "problem"),
    [
        ({"cells": ["a"]}, "unknown Yearbook setting"),
        ({}, "needs a 'cluster', a 'gene' or a 'select'"),
        ({"select": {}, "gene": "GENE1"}, "not both"),
        ({"select": {"query": {"op": "eq"}}}, "no AnnData"),
    ],
)
def test_yearbook_action_refuses_what_it_cant_do(spec, problem) -> None:
    clerk, yearbook = _linked()
    with pytest.raises(ValueError, match=problem):
        clerk._apply_actions({"yearbook": spec})
    assert yearbook.front_end_query == {}
    with pytest.raises(ValueError, match="no Yearbook is linked"):
        Clerk()._apply_actions({"yearbook": {"gene": "GENE1"}})


def test_yearbook_action_selects_cells_from_the_anndata() -> None:
    clerk, yearbook = _linked(adata=_adata())
    yearbook.front_end_query = {"gene": "GENE2"}
    select = {
        "query": {"op": "eq", "attr": {"type": "obs", "name": "leiden"}, "value": "2"},
        "sampler": {"type": "rank", "attr": {"type": "gene", "name": "GENE1"}, "n": 3},
    }
    changes, _ = clerk._apply_actions({"yearbook": {"select": select}})
    # The highest GENE1 cells of cluster 2, in order; the browser query is cleared.
    assert yearbook.cells == ["cell_28", "cell_25", "cell_22"]
    assert yearbook.front_end_query == {}
    assert yearbook.selection["query"] == select["query"]
    assert yearbook.selection["sampler"]["type"] == "rank"
    assert changes == ["the Yearbook: 3 cells selected from the AnnData (of 10 matching)"]
    # Its cluster column is remembered for the next browser query.
    clerk._apply_actions({"yearbook": {"cluster": "1"}})
    assert yearbook.front_end_query["cluster"] == {"attr": "leiden", "value": "1"}
    yearbook.front_end_query = {"cluster": {"attr": "cluster", "value": "1"}}
    clerk._apply_actions({"yearbook": {"select": select}})
    clerk._apply_actions({"yearbook": {"cluster": "2"}})
    assert yearbook.front_end_query["cluster"] == {"attr": "cluster", "value": "2"}

    with pytest.raises(ValueError, match="the cell selection failed: .*NOPE"):
        clerk._apply_actions(
            {
                "yearbook": {
                    "select": {
                        "query": {**select["query"], "attr": {"type": "gene", "name": "NOPE"}}
                    }
                }
            }
        )
    with pytest.raises(ValueError, match="matched no cells"):
        clerk._apply_actions(
            {"yearbook": {"select": {"query": {**select["query"], "value": "99"}}}}
        )
    # Unchanged by the refused requests.
    assert yearbook.cells == ["cell_28", "cell_25", "cell_22"]


def test_anndata_link_is_read_when_first_needed(tmp_path) -> None:
    path = tmp_path / "cells.h5ad"
    _adata().write_h5ad(path)
    clerk, yearbook = _linked(adata=str(path))
    # Drafted analysis notebooks are told where the data is.
    assert clerk.analysis_data["adata"] == str(path)
    assert clerk._loaded_adata is None
    clerk._apply_actions(
        {
            "yearbook": {
                "select": {
                    "sampler": {"type": "rank", "attr": {"type": "gene", "name": "GENE1"}, "n": 2}
                }
            }
        }
    )
    assert yearbook.cells == ["cell_29", "cell_28"]
    with pytest.raises(ValueError, match=r"\.h5ad or \.zarr"):
        Clerk(adata="cells.csv", yearbook=yearbook)._apply_actions(
            {"yearbook": {"select": {"sampler": 2}}}
        )


def test_prompt_describes_the_yearbook_and_its_anndata() -> None:
    clerk, _ = _linked(adata=_adata())
    described = clerk._describe_selectable()
    assert described.startswith("30 cells x 3 genes (raw counts); genes: GENE1, GENE2, GENE3.")
    # Categories in natural order; numbers as a range.
    assert "- leiden: 3 values (1, 2, 10)" in described
    assert "- area: numbers 10 to 100" in described
    help_text = clerk_llm.actions_help(clustergram=False, yearbook=True, anndata=described)
    assert '{"yearbook": {"cluster": "A"' in help_text and '"select"' in help_text
    assert described in help_text
    # Without an AnnData, only the browser query is offered.
    plain = clerk_llm.actions_help(clustergram=False, yearbook=True)
    assert '"yearbook"' in plain and '"select"' not in plain
    assert '"yearbook"' not in clerk_llm.actions_help(clustergram=False)


def test_yearbook_state_reads_as_text() -> None:
    text = clerk_llm.format_yearbook_state(
        {
            "query": {"cluster": {"attr": "leiden", "value": "4"}, "gene": "GENE1"},
            "cells": [f"c{i}" for i in range(40)],
            "page": 1,
            "selected_cells": ["c3"],
            "display": {"genes": ["GENE1"]},
        },
        max_cells=3,
    )
    assert text.splitlines() == [
        "A grid of single-cell portraits: cells of cluster 4, ranked by GENE1 expression "
        "(highest first); 40 cells, page 2.",
        "Cells: c0, c1, c2, +37",
        "Selected by the scientist: c3",
        "Colored by: GENE1",
    ]
    query = {"op": "eq", "attr": {"type": "obs", "name": "leiden"}, "value": "2"}
    chosen = clerk_llm.format_yearbook_state(
        {"query": {}, "cells": ["c1"], "selection": {"query": query, "sampler": None}}
    )
    assert (
        f"selected from the AnnData with the query {json.dumps(query, separators=(',', ':'))}"
        in chosen
    )


def test_clerk_sees_the_yearbook_with_each_question() -> None:
    clerk, yearbook = _linked(adata=_adata())
    clerk._apply_actions(
        {
            "yearbook": {
                "select": {
                    "sampler": {"type": "rank", "attr": {"type": "gene", "name": "GENE1"}, "n": 2}
                }
            }
        }
    )

    def browser(content, buffers=None):
        if content.get("event") != "capture_snapshot":
            return
        snapshot = {
            "schema": "celldega.view",
            "version": 2,
            "kind": "yearbook",
            "state": {"cells": list(yearbook.cells)},
            "observed_state": {"query": {}, "cells": list(yearbook.cells), "page": 0},
            "image": {"png": "UE5H", "thumb": "dGh1bWI="},
        }
        yearbook._on_snapshot_msg(
            yearbook, {"event": "snapshot", "id": content["id"], "snapshot": snapshot}, []
        )

    yearbook.send = browser
    views = clerk._refresh_views()
    assert views["yearbook_image"] == "UE5H" and views["yearbook_thumb"] == "dGh1bWI="
    assert "Yearbook: 2 cells" in views["summary"]
    # The selection that chose the cells is part of what Clerk sees.
    assert views["yearbook_state"]["selection"]["sampler"]["type"] == "rank"
    assert "cells selected from the AnnData" in clerk_llm.format_yearbook_state(
        views["yearbook_state"]
    )


# ---- a conversation continues in one session, sending only what changed --------
def _fake_browser(yearbook):
    def browser(content, buffers=None):
        if content.get("event") != "capture_snapshot":
            return
        snapshot = {
            "schema": "celldega.view",
            "version": 2,
            "kind": "yearbook",
            "state": {"cells": list(yearbook.cells)},
            "observed_state": {"query": {}, "cells": list(yearbook.cells), "page": 0},
            "image": {"png": "UE5H", "thumb": "dGh1bWI="},
        }
        yearbook._on_snapshot_msg(
            yearbook, {"event": "snapshot", "id": content["id"], "snapshot": snapshot}, []
        )

    return browser


def _fake_cli(monkeypatch, replies=None):
    """Stands in for the claude CLI: records each prompt and its session."""
    calls = []
    replies = iter(replies or [])

    def run_claude(prompt, image_b64=None, session=None, **kwargs):
        calls.append({"prompt": prompt, "session": session, "resumed": session.started})
        session.calls += 1
        session.usage.append({"input_tokens": 10, "output_tokens": 2, "cost_usd": 0.01})
        return next(replies, f"Answer {len(calls)}.")

    monkeypatch.setattr(clerk_llm.llm, "run_claude", run_claude)
    return calls


def _ask(clerk, question, n):
    clerk.request = {"id": str(n), "question": question}
    assert clerk.wait(timeout=5)


def test_later_questions_send_only_the_views_that_changed(monkeypatch) -> None:
    calls = _fake_cli(monkeypatch)
    clerk, yearbook = _linked()
    yearbook.cells = ["c1", "c2"]
    yearbook.send = _fake_browser(yearbook)

    _ask(clerk, "First question?", 1)
    first = calls[-1]
    assert not first["resumed"]
    assert "## Yearbook (what the scientist sees)" in first["prompt"]

    # Nothing changed: the same session, and the Yearbook named as unchanged.
    _ask(clerk, "Second question?", 2)
    second = calls[-1]
    assert second["resumed"] and second["session"] is first["session"]
    assert "Yearbook: as you last saw it" in second["prompt"]
    assert "Cells: c1, c2" not in second["prompt"]
    assert "## Conversation so far" not in second["prompt"]
    assert second["prompt"].endswith("## Question\nSecond question?")
    # The panel says what was resent, and previews only that.
    first_q, second_q = [m for m in clerk.messages if m["role"] == "user"]
    assert first_q["yearbook_image"] and first_q["snapshots"]["yearbook"]
    assert "Yearbook: 2 cells (unchanged)" in second_q["evidence"]
    assert "yearbook_image" not in second_q and "snapshots" not in second_q
    # Each question's token use is its own.
    assert clerk.record[-1]["usage"]["calls"] == 1

    # The Yearbook changed: only it is sent again.
    yearbook.cells = ["c3"]
    _ask(clerk, "Third question?", 3)
    third = calls[-1]
    assert third["session"] is first["session"]
    assert "## Yearbook now (changed since you last saw it)" in third["prompt"]
    assert "Cells: c3" in third["prompt"] and "## Unchanged" not in third["prompt"]


def test_a_conversation_starts_a_new_session_when_it_must(monkeypatch) -> None:
    calls = _fake_cli(monkeypatch)
    clerk, yearbook = _linked()
    yearbook.send = _fake_browser(yearbook)
    clerk.max_session_questions = 2

    for n in range(1, 4):
        _ask(clerk, f"Question {n}?", n)
    # The third question starts afresh, with everything and the conversation so far.
    assert [c["resumed"] for c in calls] == [False, True, False]
    assert "## Conversation so far" in calls[-1]["prompt"]

    # New context reaches Clerk in a new session's first message.
    clerk.context_info = "New context."
    _ask(clerk, "Question 4?", 4)
    assert not calls[-1]["resumed"] and "New context." in calls[-1]["prompt"]

    # Off: every question starts a new session.
    clerk.continue_conversation = False
    _ask(clerk, "Question 5?", 5)
    _ask(clerk, "Question 6?", 6)
    assert [c["resumed"] for c in calls[-2:]] == [False, False]
    assert clerk._conversation is None


def test_reopening_a_conversation_ends_the_session(monkeypatch, tmp_path) -> None:
    calls = _fake_cli(monkeypatch)
    clerk, yearbook = _linked()
    yearbook.send = _fake_browser(yearbook)
    _ask(clerk, "Question 1?", 1)
    session = clerk._conversation["session"]
    saved = clerk.save_conversation(tmp_path / "chat.json")

    closed = []
    monkeypatch.setattr(session, "close", lambda: closed.append(True))
    clerk.load_conversation(saved)
    assert closed and clerk._conversation is None
    _ask(clerk, "Question 2?", 2)
    assert not calls[-1]["resumed"] and "## Conversation so far" in calls[-1]["prompt"]


def test_what_happened_between_questions_reaches_clerk(monkeypatch) -> None:
    calls = _fake_cli(monkeypatch)
    clerk, yearbook = _linked()
    yearbook.send = _fake_browser(yearbook)
    _ask(clerk, "Question 1?", 1)
    clerk._append({"role": "action", "content": "Labeled Clustergram columns 1 and 2."})
    _ask(clerk, "Question 2?", 2)
    assert (
        "## Since your last answer\nClerk did: Labeled Clustergram columns 1 and 2."
        in (calls[-1]["prompt"])
    )


def test_views_clerk_changes_appear_in_the_conversation(monkeypatch) -> None:
    block = '```celldega-actions\n{"yearbook": {"cluster": "2"}, "continue": true}\n```'
    _fake_cli(monkeypatch, [block, "Here they are."])
    clerk, yearbook = _linked()
    yearbook.send = _fake_browser(yearbook)
    _ask(clerk, "Show me cluster 2's cells.", 1)
    (view,) = [m for m in clerk.messages if m["role"] == "view"]
    assert view["content"] == "the Yearbook: cluster 2 (up to 60 cells)"
    assert view["yearbook_image"] == "dGh1bWI="
    assert view["snapshots"]["yearbook"]["kind"] == "yearbook"
    # Only what Clerk changed: no Landscape or Clustergram preview.
    assert "image" not in view and "clustergram_image" not in view
    # Not part of what Clerk reads back as history.
    assert "Clerk showed" not in clerk_llm.llm._format_history(clerk.messages)
