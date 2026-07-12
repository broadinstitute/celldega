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


def test_run_claude_text_only(monkeypatch) -> None:
    captured = {}

    def fake_run(cmd, input=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        captured["input"] = input
        return _FakeCompleted(json.dumps({"result": "answer", "is_error": False}))

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    out = clerk_llm.run_claude("hello", model="sonnet")
    assert out == "answer"
    assert captured["cmd"][:2] == ["claude", "-p"]
    assert "--model" in captured["cmd"] and "sonnet" in captured["cmd"]
    assert "--output-format" in captured["cmd"]
    # Text mode passes the prompt as an arg and does not stream.
    assert "hello" in captured["cmd"]
    assert captured["input"] is None
    assert "stream-json" not in captured["cmd"]


def test_run_claude_with_image(monkeypatch) -> None:
    captured = {}
    result_line = json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "result": "Red."}
    )

    def fake_run(cmd, input=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        captured["input"] = input
        return _FakeCompleted(result_line)

    monkeypatch.setattr(clerk_impl.shutil, "which", lambda _n: "/usr/bin/claude")
    monkeypatch.setattr(clerk_impl.subprocess, "run", fake_run)

    out = clerk_llm.run_claude("what color?", image_b64="QUJD")
    assert out == "Red."
    # Streaming multimodal flags.
    assert "--input-format" in captured["cmd"]
    assert "stream-json" in captured["cmd"]
    assert "--verbose" in captured["cmd"]
    # The base64 image rides on stdin inside an image content block.
    msg = json.loads(captured["input"])
    blocks = msg["message"]["content"]
    assert any(b.get("type") == "image" and b["source"]["data"] == "QUJD" for b in blocks)


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

    assert w.pending is False
    assert w.messages[0] == {"role": "user", "content": "annotate"}
    assert w.messages[-1] == {"role": "assistant", "content": "T cell"}


def test_clerk_request_deduplicates(monkeypatch) -> None:
    w = Clerk()
    calls = {"n": 0}

    def fake_ask(question, **kwargs):
        calls["n"] += 1
        return "ok"

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "same", "question": "q"}
    # Re-setting the dict content is a change event but same id -> ignored.
    w.request = {"id": "same", "question": "q", "extra": 1}
    assert calls["n"] == 1


def test_clerk_request_records_error(monkeypatch) -> None:
    w = Clerk()

    def fake_ask(question, **kwargs):
        raise clerk_llm.ClerkBackendError("no cli")

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)

    w.request = {"id": "1", "question": "q"}
    assert w.pending is False
    assert w.error == "no cli"
    assert w.messages[-1]["role"] == "error"
