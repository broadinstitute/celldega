"""Analysis notebooks Clerk drafts: the analysis counterpart of Snapshots.

Clerk interprets what the scientist sees; it doesn't run analysis. When a question
needs new analysis, Clerk can draft a Jupyter notebook instead (a ``celldega-notebook``
block in its answer). The notebook is written to disk for the scientist to inspect,
edit and run themselves, or to hand to Claude Code, which runs it in a separate
process with permission to do only that. Its summary comes back to Clerk to interpret.

Nothing here runs a notebook unless :func:`run_with_claude_code` is called, which
the panel does only when the scientist clicks **Run with Claude Code**.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from .prompts import NOTEBOOK_FENCE


_NOTEBOOK_BLOCK = re.compile(
    rf"```{re.escape(NOTEBOOK_FENCE)}[ \t]*\n(.*?)\n?```", re.DOTALL | re.IGNORECASE
)
_CELL_MARK = re.compile(r"^#\s?%%(?P<markdown>\s*\[markdown\])?.*$")
_TITLE = re.compile(r"^\s*title\s*:\s*(?P<title>.+?)\s*$", re.IGNORECASE)

#: Longest a Claude Code run may take (it may re-run a notebook after a small fix).
RUN_TIMEOUT = 3 * 60 * 60


def extract_notebook(answer: str) -> tuple[str, dict | None, str | None]:
    """Split an answer into its text and a drafted notebook, if it has one.

    The block holds an optional ``title:`` line, then cells in Jupytext's percent
    format: ``# %%`` starts a code cell, ``# %% [markdown]`` a text cell whose lines
    start with ``# ``.

    Returns:
        tuple: ``(text, notebook, error)``; ``notebook`` is ``{"title", "cells":
        [{"type": "code"|"markdown", "source"}]}`` or ``None``.
    """
    match = _NOTEBOOK_BLOCK.search(answer or "")
    if not match:
        return (answer or "").strip(), None, None
    text = (answer[: match.start()] + answer[match.end() :]).strip()
    lines = match.group(1).splitlines()
    title = ""
    if lines and (found := _TITLE.match(lines[0])):
        title, lines = found.group("title"), lines[1:]
    cells: list[dict] = []
    kind, body = "code", []

    def flush():
        source = "\n".join(body).strip("\n")
        if kind == "markdown":
            source = "\n".join(re.sub(r"^#\s?", "", line) for line in source.splitlines())
        if source.strip():
            cells.append({"type": kind, "source": source})

    for line in lines:
        mark = _CELL_MARK.match(line)
        if mark:
            flush()
            kind, body = ("markdown" if mark.group("markdown") else "code"), []
        else:
            body.append(line)
    flush()
    if not any(cell["type"] == "code" for cell in cells):
        return text, None, "The drafted notebook has no code cells."
    return text, {"title": title or "Analysis", "cells": cells}, None


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return slug[:48] or "analysis"


def write_notebook(
    notebook: dict,
    folder: str | Path,
    *,
    question: str = "",
    sources: list[str] | None = None,
) -> Path:
    """Write a drafted notebook (from :func:`extract_notebook`) into ``folder``.

    It opens with a note that Clerk drafted it, the question it answers, where its
    data lives, and how to run it; then Clerk's cells, unchanged and unexecuted.
    """
    import nbformat

    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    title = str(notebook.get("title") or "Analysis")
    path = folder / f"{_slug(title)}_{time.strftime('%Y%m%d-%H%M%S')}.ipynb"
    header = [
        f"# {title}",
        "",
        f"*Drafted by Clerk, Celldega's AI assistant, on {time.strftime('%Y-%m-%d %H:%M')}.*",
    ]
    if question:
        header += ["", f"**Question:** {question}"]
    if sources:
        header += ["", "**Data:**", *[f"- {source}" for source in sources]]
    header += [
        "",
        "**Inspect this notebook before running it.** Edit it as you like, run it "
        "yourself, or use **Run with Claude Code** in the Clerk panel. It writes any new "
        "files next to itself and leaves its inputs unchanged.",
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell("\n".join(header))]
    for cell in notebook.get("cells") or []:
        make = (
            nbformat.v4.new_markdown_cell
            if cell.get("type") == "markdown"
            else nbformat.v4.new_code_cell
        )
        nb.cells.append(make(str(cell.get("source") or "")))
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["celldega"] = {"drafted_by": "clerk", "question": question}
    nbformat.write(nb, path)
    return path


def claude_code_command(path: str | Path, *, python: str | None = None) -> list[str]:
    """The ``claude`` command that runs one notebook, allowed to do only that.

    Claude Code may run ``jupyter nbconvert`` on notebooks in the notebook's folder,
    read and edit files there (to fix a small error, and to write the summary), and
    nothing else: other tools and commands are refused, and the user's settings,
    hooks and MCP servers are not loaded.
    """
    path = Path(path).resolve()
    python = python or sys.executable
    folder = path.parent
    summary = path.with_suffix(".summary.md").name
    prompt = (
        "Clerk (Celldega's AI assistant) drafted the Jupyter notebook "
        f"{path.name!r} in the current directory, and the scientist asked you to run "
        "it.\n"
        "1. Run it, saving its outputs in place, with exactly:\n"
        f"   {python} -m jupyter nbconvert --to notebook --execute --inplace "
        f'--ExecutePreprocessor.timeout=1800 "{path.name}"\n'
        "2. If a cell fails because of a small, clear mistake (a typo, a name the error "
        "points to), fix that cell and run the notebook again, at most 3 times. Don't "
        "change what the analysis does, don't install packages, and don't touch files "
        "other than the notebook and the summary.\n"
        f"3. Write {summary!r}: whether it ran, any fixes you made, and the key results "
        "(numbers, top genes, files written), in under 200 words.\n"
        "Reply with that summary."
    )
    # File rules take an absolute path as "//path" ("/path" is relative to settings).
    files = f"/{folder.as_posix()}/**"
    allowed = [
        f"Bash({python} -m jupyter nbconvert:*)",
        f"Read({files})",
        f"Edit({files})",
        f"Write({files})",
        f"NotebookEdit({files})",
    ]
    # In --settings, not --allowedTools: that option splits its value on spaces, which
    # would break the nbconvert rule (and any folder with a space) apart.
    settings = {"permissions": {"allow": allowed, "defaultMode": "dontAsk"}}
    return [
        "claude",
        "-p",
        prompt,
        "--tools",
        "Bash,Read,Edit,Write,NotebookEdit",
        "--settings",
        json.dumps(settings),
        "--permission-mode",
        "dontAsk",
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--no-session-persistence",
    ]


def run_with_claude_code(
    path: str | Path, *, timeout: float = RUN_TIMEOUT, python: str | None = None
) -> dict:
    """Have Claude Code run a notebook in a separate process (blocking).

    Returns:
        dict: ``{"ok", "summary", "log"}``: whether it finished, Claude Code's
        summary (or the error), and the path of the full log.
    """
    from .llm import ISOLATION_ENV

    path = Path(path).resolve()
    if not path.is_file():
        return {"ok": False, "summary": f"No notebook at {path}", "log": ""}
    if shutil.which("claude") is None:
        return {
            "ok": False,
            "summary": "The claude command isn't installed or isn't on PATH.",
            "log": "",
        }
    import os

    log = path.with_suffix(".claude.log")
    command = claude_code_command(path, python=python)
    env = {**os.environ, **ISOLATION_ENV}
    try:
        done = subprocess.run(
            command,
            cwd=path.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "summary": f"Claude Code didn't finish in {timeout:.0f} s.", "log": ""}
    log.write_text(f"$ claude -p ...\n\n{done.stdout}\n\n--- stderr ---\n{done.stderr}")
    summary_file = path.with_suffix(".summary.md")
    summary = (
        summary_file.read_text().strip() if summary_file.is_file() else (done.stdout or "").strip()
    )
    # Claude Code exits normally when it reports being stopped; the notebook's own
    # outputs say whether it actually ran.
    if done.returncode != 0 or not executed(path):
        return {
            "ok": False,
            "summary": summary or (done.stderr or "").strip()[-600:] or "Claude Code failed.",
            "log": str(log),
        }
    return {"ok": True, "summary": summary or "Claude Code finished.", "log": str(log)}


def executed(path: str | Path) -> bool:
    """Whether every code cell of a notebook has been run (has an execution count)."""
    import nbformat

    try:
        nb = nbformat.read(Path(path), as_version=4)
    except Exception:
        return False
    code = [cell for cell in nb.cells if cell.cell_type == "code" and cell.source.strip()]
    return bool(code) and all(cell.get("execution_count") for cell in code)
