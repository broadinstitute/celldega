"""Tests for the Clerk widget and its ``clerk_llm`` backend."""

import json

import pytest


try:
    from celldega import clerk as clerk_llm  # backend module: dega.clerk
    from celldega.clerk import llm as clerk_impl  # low-level (subprocess/shutil live here)
    from celldega.viz import Clerk
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


# ---- build_prompt ---------------------------------------------------------
def test_build_prompt_includes_evidence() -> None:
    prompt = clerk_llm.build_prompt(
        "What cell type is this?",
        gene_list=["CD3D", "CD8A"],
        enrichr_terms=[{"name": "T cells", "score": 12.5, "genes": ["CD3D"]}],
        info="Cluster 5, Xenium lung",
        has_image=True,
    )
    assert "What cell type is this?" in prompt
    assert "CD3D" in prompt and "CD8A" in prompt
    assert "T cells" in prompt
    assert "Cluster 5, Xenium lung" in prompt
    assert "image" in prompt.lower()


def test_build_prompt_minimal() -> None:
    prompt = clerk_llm.build_prompt("hi")
    assert "hi" in prompt
    # No evidence sections when nothing is provided.
    assert "Marker / DE genes" not in prompt
    assert "Enrichr" not in prompt
    assert "Conversation so far" not in prompt


def test_build_prompt_includes_history() -> None:
    history = [
        {"role": "user", "content": "What is cluster 4?"},
        {"role": "assistant", "content": "Likely goblet cells (MUC2)."},
        {"role": "error", "content": "timed out"},
    ]
    prompt = clerk_llm.build_prompt("Why the stripes?", history=history)
    assert "Conversation so far" in prompt
    assert "Scientist: What is cluster 4?" in prompt
    assert "Clerk: Likely goblet cells (MUC2)." in prompt
    # Errors are not part of the conversation; the new question comes last.
    assert "timed out" not in prompt
    assert prompt.rstrip().endswith("Why the stripes?")


def test_build_prompt_caps_history(monkeypatch) -> None:
    monkeypatch.setattr(clerk_impl, "MAX_HISTORY_TURNS", 2)
    history = [{"role": "user", "content": f"turn {i}"} for i in range(5)]
    prompt = clerk_llm.build_prompt("q", history=history)
    assert "turn 4" in prompt and "turn 3" in prompt
    assert "turn 2" not in prompt

    monkeypatch.setattr(clerk_impl, "MAX_HISTORY_TURNS", 10)
    monkeypatch.setattr(clerk_impl, "MAX_HISTORY_CHARS", 30)
    history = [{"role": "user", "content": "x" * 20}, {"role": "user", "content": "newest"}]
    prompt = clerk_llm.build_prompt("q", history=history)
    assert "newest" in prompt and "x" * 20 not in prompt


# ---- result extraction ----------------------------------------------------
def test_extract_result_text_json() -> None:
    out = json.dumps({"result": "It is a T cell.", "is_error": False})
    assert clerk_impl._extract_result_text(out, streaming=False) == "It is a T cell."


def test_extract_result_text_stream() -> None:
    lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "assistant", "message": {"content": []}}),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Red."}),
    ]
    assert clerk_impl._extract_result_text("\n".join(lines), streaming=True) == "Red."


def test_extract_result_text_error() -> None:
    out = json.dumps({"result": "boom", "is_error": True})
    with pytest.raises(clerk_llm.ClerkBackendError):
        clerk_impl._extract_result_text(out, streaming=False)


# ---- run_claude argv / stdin (subprocess mocked) --------------------------
class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _assert_isolated(cmd: list[str], cwd) -> None:
    """Every call uses Clerk's system prompt, no tools/MCP/settings, and a temp cwd."""
    assert cmd[cmd.index("--system-prompt") + 1] == clerk_impl.SYSTEM_PROMPT
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in cmd
    assert "--no-session-persistence" in cmd
    assert cwd and "celldega-clerk-" in str(cwd)


def test_run_claude_text_only(monkeypatch) -> None:
    captured = {}

    def fake_run(cmd, input=None, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = input
        captured["cwd"] = kwargs.get("cwd")
        return _FakeCompleted(json.dumps({"result": "answer", "is_error": False}))

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    out = clerk_llm.run_claude("hello", model="sonnet")
    assert out == "answer"
    assert captured["cmd"][:2] == ["claude", "-p"]
    assert "--model" in captured["cmd"] and "sonnet" in captured["cmd"]
    assert "--output-format" in captured["cmd"]
    _assert_isolated(captured["cmd"], captured["cwd"])
    # Text mode passes the prompt as an arg and does not stream.
    assert "hello" in captured["cmd"]
    assert captured["input"] is None
    assert "stream-json" not in captured["cmd"]


def test_run_claude_with_image(monkeypatch) -> None:
    captured = {}
    result_line = json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "result": "Red."}
    )

    def fake_run(cmd, input=None, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = input
        captured["cwd"] = kwargs.get("cwd")
        return _FakeCompleted(result_line)

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    out = clerk_llm.run_claude("what color?", image_b64="QUJD")
    assert out == "Red."
    # Streaming multimodal flags.
    assert "--input-format" in captured["cmd"]
    assert "stream-json" in captured["cmd"]
    assert "--verbose" in captured["cmd"]
    _assert_isolated(captured["cmd"], captured["cwd"])
    # The base64 image rides on stdin inside an image content block.
    msg = json.loads(captured["input"])
    blocks = msg["message"]["content"]
    assert any(b.get("type") == "image" and b["source"]["data"] == "QUJD" for b in blocks)


def test_claude_auth_status_drops_account_details(monkeypatch) -> None:
    status = {
        "loggedIn": True,
        "authMethod": "claude.ai",
        "subscriptionType": "pro",
        "email": "someone@example.org",
        "orgName": "Some Lab",
    }

    def fake_run(cmd, **kwargs):
        assert cmd == ["claude", "auth", "status", "--json"]
        return _FakeCompleted(json.dumps(status))

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    out = clerk_llm.claude_auth_status()
    assert out == {"logged_in": True, "auth_method": "claude.ai", "subscription_type": "pro"}


def test_claude_auth_status_without_cli_or_bad_output(monkeypatch) -> None:
    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: None)
    assert clerk_llm.claude_auth_status()["logged_in"] is False

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(
        clerk_impl.subprocess, "run", lambda cmd, **kw: _FakeCompleted("not json", 1, "boom")
    )
    out = clerk_llm.claude_auth_status()
    assert out["logged_in"] is False and out["error"] == "boom"


def test_run_claude_logged_out_explains_login(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["claude", "auth", "status"]:
            return _FakeCompleted(json.dumps({"loggedIn": False}))
        return _FakeCompleted("", 1, "Invalid API key · Please run /login")

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    with pytest.raises(clerk_llm.ClerkBackendError, match="claude auth login"):
        clerk_llm.run_claude("hi")


def test_run_claude_other_failure_keeps_cli_error(monkeypatch) -> None:
    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["claude", "auth", "status"]:
            return _FakeCompleted(json.dumps({"loggedIn": True}))
        return _FakeCompleted("", 1, "model not found")

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    with pytest.raises(clerk_llm.ClerkBackendError, match="model not found"):
        clerk_llm.run_claude("hi")


def test_run_claude_missing_cli(monkeypatch) -> None:
    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: None)
    with pytest.raises(clerk_llm.ClerkBackendError):
        clerk_llm.run_claude("hi")


# ---- Clerk widget ---------------------------------------------------------
def test_clerk_defaults() -> None:
    w = Clerk()
    assert w.component == "Clerk"
    assert w.gene_list == []
    assert w.messages == []
    assert w.pending is False
    assert w.model == ""


def test_clerk_request_triggers_ask(monkeypatch) -> None:
    w = Clerk(gene_list=["CD3D"])

    def fake_ask(question, **kwargs):
        assert question == "annotate"
        assert kwargs["gene_list"] == ["CD3D"]
        return "T cell"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "annotate", "gene_list": ["CD3D"]}
    assert w.wait(timeout=5)

    assert w.pending is False
    # The question records what was sent with it.
    assert w.messages[0] == {
        "role": "user",
        "content": "annotate",
        "evidence": ["1 selected genes"],
    }
    assert w.messages[-1] == {"role": "assistant", "content": "T cell"}


def test_clerk_request_runs_in_background(monkeypatch) -> None:
    import threading

    release = threading.Event()
    w = Clerk()

    def slow_ask(question, **kwargs):
        release.wait(5)
        return "done"

    monkeypatch.setattr(clerk_llm, "ask", slow_ask)

    w.request = {"id": "1", "question": "q"}
    # The observer returned while the model call is still running.
    assert w.pending is True
    assert w.messages == [{"role": "user", "content": "q"}]

    # A second question while busy is refused rather than queued.
    w.request = {"id": "2", "question": "another"}
    assert "still answering" in w.error

    release.set()
    assert w.wait(timeout=5)
    assert w.pending is False
    assert w.messages[-1] == {"role": "assistant", "content": "done"}


def test_clerk_sends_conversation_history(monkeypatch) -> None:
    w = Clerk()
    seen = []

    def fake_ask(question, **kwargs):
        seen.append(kwargs["history"])
        return f"answer to {question}"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "first"}
    w.wait(timeout=5)
    w.request = {"id": "2", "question": "second"}
    w.wait(timeout=5)

    assert seen[0] == []
    assert seen[1] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer to first"},
    ]


def test_clerk_request_deduplicates(monkeypatch) -> None:
    w = Clerk()
    calls = {"n": 0}

    def fake_ask(question, **kwargs):
        calls["n"] += 1
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "same", "question": "q"}
    w.wait(timeout=5)
    # Re-setting the dict content is a change event but same id -> ignored.
    w.request = {"id": "same", "question": "q", "extra": 1}
    w.wait(timeout=5)
    assert calls["n"] == 1


def test_clerk_request_records_error(monkeypatch) -> None:
    w = Clerk()

    def fake_ask(question, **kwargs):
        raise clerk_llm.ClerkBackendError("no cli")

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    assert w.pending is False
    assert w.error == "no cli"
    assert w.messages[-1]["role"] == "error"


def test_clerk_request_records_unexpected_error(monkeypatch) -> None:
    w = Clerk()

    def fake_ask(question, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    assert w.pending is False
    assert "boom" in w.error
    assert w.messages[-1]["role"] == "error"


# ---- images: full image Python-side only, preview synced -------------------
def test_clerk_image_is_not_synced() -> None:
    w = Clerk()
    assert w.trait_metadata("image_b64", "sync") is None
    assert w.trait_metadata("image_thumb_b64", "sync") is True

    w.image_thumb_b64 = "VEhVTUI="
    w.image_b64 = "RlVMTA=="
    assert w.has_image is True
    w.image_b64 = ""
    assert w.has_image is False
    assert w.image_thumb_b64 == ""


def _landscape():
    import warnings

    from celldega.viz import Landscape

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # no transform file: identity is fine
        return Landscape()


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


_STATE = {
    "kind": "clustergram",
    "rows": {
        "selection_mode": "viewport",
        "names": ["MUC2", "TFF3"],
        "total": 30,
        "truncated": True,
        "displayed": 45,
        "count": 18000,
        "order": {"name": "clust", "label": "clustered"},
        "attributes": [{"name": "leiden_marker", "type": "categorical", "values": ["4", "4"]}],
        "groups": {
            "cut_percent": 50,
            "groups": [{"name": "1", "size": 2, "members": ["MUC2", "TFF3"]}],
        },
    },
    "cols": {
        "selection_mode": "viewport",
        "names": ["4", "5"],
        "total": 2,
        "truncated": False,
        "displayed": 15,
        "count": 15,
        "order": {"name": "rank", "label": "sum"},
        "attributes": [
            {"name": "leiden", "type": "categorical", "values": ["4", "5"]},
            {"name": "cell_type", "type": "categorical", "values": ["Goblet", None]},
        ],
    },
    "marker_level": {"current": 3, "unit": "per_cluster", "levels": [1, 2, 3, 5]},
    "selection": {
        "click": {"type": "col_label", "value": "4"},
        "selected_genes": ["MUC2"],
        "enrich_term_genes": ["muc2"],
        "dendro_group": None,
    },
    "values": {"values": [[2.1, -0.4], [1.8, None]], "sizes": [[0.9, 0.1], [0.8, None]]},
}


def test_format_clustergram_state_is_compact_and_complete() -> None:
    text = clerk_llm.format_clustergram_state(_STATE)
    # Columns with their attributes; redundant (leiden == name) and empty values skipped.
    assert "4 [cell_type=Goblet]; 5" in text
    assert "order: sum" in text
    # Rows: on-screen count, the rest summarized, attributes, and dendrogram groups.
    assert "30 on screen of 45 shown (18000 total)" in text and "+28 more" in text
    assert "MUC2 [leiden_marker=4]" in text
    assert "Rows dendrogram groups at 50% cut: 1 (2): MUC2, TFF3" in text
    assert "top 3 markers per cluster" in text
    assert "Selected genes: MUC2" in text
    # Values / dot sizes table, with missing cells marked.
    assert "MUC2\t2.10/0.90\t-0.40/0.10" in text
    assert "TFF3\t1.80/0.80\t." in text
    assert clerk_llm.format_clustergram_state({}) == ""


def test_build_prompt_includes_clustergram_state() -> None:
    prompt = clerk_llm.build_prompt("q", clustergram_state=_STATE)
    assert "## Clustergram (what the scientist sees)" in prompt
    assert "MUC2" in prompt


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


def test_clerk_sends_clustergram_state_with_question(monkeypatch) -> None:
    cgm = _clustergram()
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 5

    def fake_send(content):
        if content.get("event") == "get_state":
            state = {"kind": "clustergram", "options": content["options"]}
            cgm._on_state_msg(cgm, {"event": "state", "id": content["id"], "state": state}, [])

    monkeypatch.setattr(cgm, "send", fake_send)
    seen = {}

    def fake_ask(question, **kwargs):
        seen["state"] = kwargs["clustergram_state"]
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "what am I looking at?"}
    assert w.wait(timeout=5)
    assert seen["state"]["kind"] == "clustergram"
    assert seen["state"]["options"]["rows"] == "viewport"


def test_clerk_skips_clustergram_state_that_does_not_arrive(monkeypatch) -> None:
    cgm = _clustergram()
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 0.05
    monkeypatch.setattr(cgm, "send", lambda content: None)  # no browser
    seen = {}

    def fake_ask(question, **kwargs):
        seen["state"] = kwargs["clustergram_state"]
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    assert seen["state"] is None


def test_clerk_captures_fresh_view_before_asking(monkeypatch) -> None:
    ls = _landscape()
    w = Clerk(landscape=ls, capture_on_select=False)
    w.snapshot_timeout = 5

    # Simulate the browser: answer each capture request with a new image.
    def fake_send(content):
        if content.get("event") == "capture_raster":
            req_id = content["id"]
            ls._on_custom_msg(
                ls,
                {
                    "event": "raster",
                    "id": req_id,
                    "png": f"IMG{req_id}",
                    "thumb": f"TH{req_id}",
                    "view_state": {"zoom": req_id},
                },
                [],
            )

    monkeypatch.setattr(ls, "send", fake_send)
    seen = {}

    def fake_ask(question, **kwargs):
        seen["image"] = kwargs["image_b64"]
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "what's in view?"}
    assert w.wait(timeout=5)

    # The question carried the capture taken when it was asked, with its preview.
    assert seen["image"] == f"IMG{ls.raster_capture_id}"
    assert w.image_thumb_b64 == f"TH{ls.raster_capture_id}"
    assert w.image_view_state == {"zoom": ls.raster_capture_id}
    # ...and the conversation shows that screenshot under the question.
    assert w.messages[0]["image"] == f"TH{ls.raster_capture_id}"
    assert w.messages[0]["evidence"] == ["Landscape view"]


# ---- Enrich, gene mentions, evidence notes ---------------------------------
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


def test_format_enrich_state() -> None:
    text = clerk_llm.format_enrich_state(_ENRICH_STATE)
    assert "Library: CellMarker_2024" in text
    assert "Input genes (3, from Clustergram row crop): MUC2, TFF3, SPINK4" in text
    assert "1. Goblet Cell Colon Human (combined score 812; adj. p 1.2e-06" in text
    assert "Selected term: Goblet Cell Colon Human; its genes: MUC2, TFF3" in text
    assert clerk_llm.format_enrich_state({"gene_list": [], "terms": []}) == ""

    prompt = clerk_llm.build_prompt("q", enrich_state=_ENRICH_STATE, notes=["view missing"])
    assert "## Enrich: enrichment results on screen" in prompt
    assert "## Evidence notes\n- view missing" in prompt


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


def test_clerk_reads_linked_enrich_instead_of_fetching(monkeypatch) -> None:
    from celldega.viz import Enrich

    en = Enrich()
    w = Clerk(enrich=en)
    assert w.fetch_enrichr is False
    w.snapshot_timeout = 5

    def fake_send(content):
        if content.get("event") == "get_state":
            en._on_state_msg(
                en, {"event": "state", "id": content["id"], "state": _ENRICH_STATE}, []
            )

    monkeypatch.setattr(en, "send", fake_send)
    seen = {}

    def fake_ask(question, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "what do these terms say?"}
    assert w.wait(timeout=5)
    assert seen["enrich_state"]["terms"][0]["name"] == "Goblet Cell Colon Human"
    assert w.messages[0]["evidence"] == ["Enrich: 1 CellMarker_2024 terms"]


def test_mentioned_rows_matching() -> None:
    cgm = _clustergram()
    cgm.row_names = ["MUC2", "TFF3", "SET", "Fezf2"]
    w = Clerk(clustergram=cgm)

    found = w._mentioned_rows(["Check MUC2 and tff3, then muc2 again.", "Fezf2 and set"])
    # Exact matches, and case-insensitive ones for words with a digit (tff3, muc2)
    # or in capitals. Plain English ("set") is skipped even though SET is a gene.
    assert found == ["MUC2", "TFF3", "Fezf2"]
    # Trailing punctuation is not part of the symbol.
    assert w._mentioned_rows(["Look at SET."]) == ["SET"]
    assert w._mentioned_rows(["nothing relevant here"]) == []


def test_clerk_adds_genes_from_question_and_last_answer(monkeypatch) -> None:
    cgm = _clustergram()
    cgm.row_names = ["MUC2", "TFF3", "EPCAM", "PTPRC"]
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 5
    w.messages = [
        {"role": "user", "content": "what is this?"},
        {"role": "assistant", "content": "Check EPCAM and PTPRC."},
    ]
    requested = {}

    def fake_send(content):
        if content.get("event") == "get_state":
            requested.update(content["options"])
            cgm._on_state_msg(
                cgm, {"event": "state", "id": content["id"], "state": {"kind": "x"}}, []
            )

    monkeypatch.setattr(cgm, "send", fake_send)
    monkeypatch.setattr(clerk_llm, "ask", lambda question, **kwargs: "ok")

    w.request = {"id": "1", "question": "Can you check MUC2 and those markers?"}
    assert w.wait(timeout=5)
    assert requested["extra_rows"] == ["MUC2", "EPCAM", "PTPRC"]


def test_clerk_notes_views_that_do_not_reply(monkeypatch) -> None:
    cgm = _clustergram()
    w = Clerk(clustergram=cgm)
    w.snapshot_timeout = 0.05
    monkeypatch.setattr(cgm, "send", lambda content: None)  # not displayed
    seen = {}

    def fake_ask(question, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "q"}
    assert w.wait(timeout=5)
    assert any("Clustergram is linked but did not return" in n for n in seen["notes"])
    assert w.messages[0]["evidence"] == ["Clustergram: no snapshot"]

    alone = Clerk(name="alone")
    monkeypatch.setattr(clerk_llm, "ask", fake_ask)
    alone.request = {"id": "1", "question": "q"}
    assert alone.wait(timeout=5)
    assert any("No Landscape, Clustergram or Enrich" in n for n in seen["notes"])
