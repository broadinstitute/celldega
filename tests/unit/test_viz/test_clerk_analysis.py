"""Analysis notebooks: Clerk drafts them; the scientist or Claude Code runs them."""

import json
import os
from pathlib import Path
import stat
import sys

import pytest


try:
    import nbformat

    from celldega import clerk as clerk_llm
    from celldega.clerk import analysis
    from celldega.viz import Clerk
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)

BLOCK = """Cluster A looks like B cells; a signature score would settle it.

```celldega-notebook
title: B cell signature score
# %% [markdown]
# Score a <cell type> signature across the clusters.
# %%
import scanpy as sc
adata = sc.read_h5ad("<input>.h5ad")
# %%
print(adata)
```"""


def test_a_drafted_notebook_is_split_into_cells():
    text, notebook, problem = analysis.extract_notebook(BLOCK)
    assert problem is None
    assert text == "Cluster A looks like B cells; a signature score would settle it."
    assert notebook["title"] == "B cell signature score"
    assert [c["type"] for c in notebook["cells"]] == ["markdown", "code", "code"]
    assert notebook["cells"][0]["source"] == "Score a <cell type> signature across the clusters."
    assert notebook["cells"][1]["source"].startswith("import scanpy as sc")
    assert analysis.extract_notebook("no block") == ("no block", None, None)
    only_text = "```celldega-notebook\n# %% [markdown]\n# Just words.\n```"
    assert analysis.extract_notebook(only_text)[1:] == (
        None,
        "The drafted notebook has no code cells.",
    )


def test_the_notebook_says_who_drafted_it_and_to_inspect_it(tmp_path):
    _text, notebook, _ = analysis.extract_notebook(BLOCK)
    path = analysis.write_notebook(
        notebook, tmp_path, question="Is cluster A B cells?", sources=["adata: x.h5ad"]
    )
    assert path.parent == tmp_path and path.name.startswith("b_cell_signature_score_")
    nb = nbformat.read(path, as_version=4)
    header = nb.cells[0].source
    assert "Drafted by Clerk" in header and "**Question:** Is cluster A B cells?" in header
    assert "- adata: x.h5ad" in header and "Inspect this notebook before running it" in header
    assert [c.cell_type for c in nb.cells[1:]] == ["markdown", "code", "code"]
    assert all(not c.get("outputs") for c in nb.cells if c.cell_type == "code")
    assert nb.metadata["celldega"]["drafted_by"] == "clerk"


def test_claude_code_may_only_run_the_notebook(tmp_path):
    notebook = tmp_path / "analysis.ipynb"
    command = analysis.claude_code_command(notebook, python="/env/bin/python")
    assert command[:2] == ["claude", "-p"]
    assert "/env/bin/python -m jupyter nbconvert --to notebook --execute --inplace" in command[2]
    settings = json.loads(command[command.index("--settings") + 1])
    files = f"/{tmp_path.resolve().as_posix()}/**"  # "//path": absolute
    assert settings["permissions"]["allow"] == [
        "Bash(/env/bin/python -m jupyter nbconvert:*)",
        f"Read({files})",
        f"Edit({files})",
        f"Write({files})",
        f"NotebookEdit({files})",
    ]
    assert settings["permissions"]["defaultMode"] == "dontAsk"
    assert "--allowedTools" not in command  # it splits rules on spaces
    # Anything else is refused rather than asked; no user settings, hooks or MCP.
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert "--strict-mcp-config" in command and "--no-session-persistence" in command
    assert command[command.index("--setting-sources") + 1] == ""


def test_the_runner_reports_claude_codes_summary(tmp_path, monkeypatch):
    # A stand-in claude: writes the summary file the prompt asks for, then replies.
    # (Whether the notebook ran is read from its outputs, so it is pre-executed here.)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(
        "#!/bin/sh\n"
        'printf "It ran; 3 clusters scored." > analysis.summary.md\n'
        'echo "It ran; 3 clusters scored."\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    notebook = tmp_path / "work" / "analysis.ipynb"
    notebook.parent.mkdir()
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell("print(1)")]
    nbformat.write(nb, notebook)
    # Claude Code exits normally even when it couldn't run the notebook: not ok.
    result = analysis.run_with_claude_code(notebook, python=sys.executable)
    assert not result["ok"] and result["summary"] == "It ran; 3 clusters scored."
    nb.cells[0].execution_count = 1
    nbformat.write(nb, notebook)
    result = analysis.run_with_claude_code(notebook, python=sys.executable)
    assert result["ok"] and result["summary"] == "It ran; 3 clusters scored."
    assert Path(result["log"]).is_file()
    assert analysis.run_with_claude_code(tmp_path / "missing.ipynb")["ok"] is False


def test_clerk_drafts_a_notebook_and_runs_it_only_when_asked(tmp_path, monkeypatch):
    asked = []

    def fake_ask(question, **kwargs):
        asked.append(kwargs)
        return BLOCK

    monkeypatch.setattr(clerk_llm, "ask", fake_ask)
    ran = []
    monkeypatch.setattr(
        analysis,
        "run_with_claude_code",
        lambda path, **kw: ran.append(path) or {"ok": True, "summary": "Scored.", "log": ""},
    )
    w = Clerk()
    w.output_dir = str(tmp_path)
    w.analysis_data = {"adata": "data/cells.h5ad"}
    w.request = {"id": "1", "question": "Is cluster A B cells?"}
    assert w.wait(timeout=5)

    # Clerk was told where the data lives, and drafted (not ran) a notebook.
    assert any(
        "Data for analysis notebooks: adata: data/cells.h5ad" in n for n in asked[0]["notes"]
    )
    (entry,) = w.analyses
    assert entry["status"] == "drafted" and Path(entry["path"]).is_file()
    assert Path(entry["path"]).parent == tmp_path / "analyses"
    line = next(m for m in w.messages if m.get("analysis"))
    assert line["content"] == "Drafted an analysis notebook: B cell signature score"
    assert line["analysis"]["id"] == entry["id"] and not ran

    # The panel's Run with Claude Code button.
    w._on_panel_msg(w, {"event": "run_analysis", "id": entry["id"]}, [])
    for _ in range(100):
        if entry["status"] == "done":
            break
        import time

        time.sleep(0.02)
    assert ran == [entry["path"]] and entry["summary"] == "Scored."
    line = next(m for m in w.messages if m.get("analysis"))
    assert line["analysis"]["status"] == "done"
    # The summary is in the conversation, for Clerk to read with the next question.
    last = w.messages[-1]
    assert last["content"] == "Claude Code ran the analysis notebook B cell signature score"
    assert "Scored." in last["detail"]
    with pytest.raises(ValueError, match="No analysis notebook"):
        w.run_analysis("nope")
    assert json.loads(json.dumps(w.messages))  # still plain data for the panel
