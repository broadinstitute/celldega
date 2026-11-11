"""Clerk's case record, written out: what was asked, what Clerk did, and how to redo it.

A law clerk who brings evidence also says where it came from and how to check it.
:func:`write_report` turns a Clerk conversation record into files you can keep:

- ``report.html``: the conversation as one self-contained page. Each screenshot sits
  under code to replay supported settings; Clerk's work and evidence are collapsed.
- ``report.ipynb``: the same as a notebook, so the reproduction code can be re-run
  against your own widgets.
- ``record.json`` plus ``images/``: everything, machine-readable.
- ``findings.csv``: the cell types Clerk proposed.

Widget-independent: the record is plain JSON-like data (see ``Clerk.record``).
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
import pprint
import re
import time
from typing import Any


REPORT_VERSION = 1

# Width the screenshots are shown at in the report (the PNG keeps its full size).
IMAGE_WIDTH = 640


def _code(variable: str, settings: dict) -> str:
    text = pprint.pformat(settings, width=80, sort_dicts=False)
    return f"{variable}.apply_state({text})"


def reproduction_code(step: dict, names: dict | None = None) -> str:
    """Python that replays supported settings with ``apply_state`` (a partial restore)."""
    names = {"landscape": "landscape", "clustergram": "cgm", **(names or {})}
    lines = []
    for kind in ("landscape", "clustergram"):
        snapshot = (step.get("snapshots") or {}).get(kind)
        if snapshot:
            text = pprint.pformat(snapshot, width=80, sort_dicts=False)
            lines.append(f"{names[kind]}.restore_snapshot({text})")
        elif step.get(kind):
            lines.append(_code(names[kind], step[kind]))
    return "\n".join(lines) or "# (no view state was captured)"


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in str(text).splitlines())


def _fold(summary: str, body: str, open_: bool = False) -> str:
    """A collapsible Markdown section (blank lines keep the body rendered as Markdown)."""
    flag = " open" if open_ else ""
    return f"<details{flag}><summary>{html.escape(summary)}</summary>\n\n{body}\n\n</details>"


def split_evidence(text: str) -> tuple[str, str, str]:
    """``(answer, evidence, closing)``: the same split the panel shows (see clerk_turns.js)."""
    line_re = re.compile(
        r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?evidence(?:\*\*|__)?\s*"
        r"(?::\s*(?:\*\*|__)?|(?:\*\*|__)?\s*$)\s*(.*)$",
        re.IGNORECASE,
    )
    item_re = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
    lines = str(text).split("\n")
    at = next((i for i, line in enumerate(lines) if line_re.match(line)), -1)
    if at < 0:
        return str(text), "", ""
    first = line_re.match(lines[at]).group(1).strip()
    rest = lines[at + 1 :]
    last_item = max((i for i, line in enumerate(rest) if item_re.match(line)), default=-1)
    end = len(rest)
    if last_item >= 0:
        end = last_item + 1
        while end < len(rest) and re.match(r"^\s+\S", rest[end]):
            end += 1
    evidence = "\n".join([first, *rest[:end]]).strip()
    if not evidence:
        return str(text), "", ""
    return "\n".join(lines[:at]).strip(), evidence, "\n".join(rest[end:]).strip()


def _figure_anchor(number: int, view_id: str) -> str:
    return f"q{number}-fig-{re.sub(r'[^A-Za-z0-9_-]', '-', str(view_id))}"


def _anchor_view_links(text: str, number: int, views: dict) -> str:
    """Point ``[Fig 1A](view:1A)`` links at the figure below the answer."""

    def replace(match):
        label, view_id = match.group(1), match.group(2)
        if view_id not in views:
            return label
        return f"[{label}](#{_figure_anchor(number, view_id)})"

    return re.sub(r"\[([^\]]+)\]\(view:([A-Za-z0-9_.-]{1,32})\)", replace, str(text))


def _capture_cell(nbformat, step: dict, names: dict | None) -> Any:
    cell = nbformat.v4.new_code_cell(reproduction_code(step, names))
    cell.metadata["clerk"] = {"capture": step.get("text", "")}
    for key, what in (("image", "Landscape"), ("clustergram_image", "Clustergram")):
        if step.get(key):
            cell.outputs.append(
                nbformat.v4.new_output(
                    "display_data",
                    data={
                        "image/png": step[key],
                        "text/plain": f"<{what} view: {step.get('text', '')}>",
                    },
                    metadata={"image/png": {"width": IMAGE_WIDTH}},
                )
            )
    return cell


def _work_markdown(steps: list[dict]) -> str:
    parts = []
    for step in steps:
        kind = step.get("kind")
        if kind == "action":
            parts.append(f"- ↻ {step.get('text', '')}")
        elif kind == "lookups":
            parts.append(_fold("Lookup results", f"```text\n{step.get('text', '')}\n```"))
        elif kind == "answer":
            parts.append(_quote(step.get("text", "")))
        elif kind == "error":
            parts.append(f"- **Error:** {step.get('text', '')}")
        elif kind == "pause":
            parts.append(f"- _{step.get('text', '')}_")
    return "\n\n".join(parts)


def _findings_markdown(findings: list[dict]) -> str:
    if not findings:
        return "_No cell types were recorded._"
    rows = [
        "| Cluster | Cell type | Confidence | Markers | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in findings:
        cells = [
            f.get("cluster", ""),
            f.get("label", ""),
            f.get("confidence", ""),
            ", ".join(f.get("markers") or []),
            f.get("notes", ""),
        ]
        rows.append("| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |")
    return "\n".join(rows)


def _usage_text(usage: dict | None) -> str:
    """`` · 3 model calls · 41k tokens (35k from cache) · ~$0.06`` for a question."""
    if not usage or not usage.get("calls"):
        return ""
    read = int(usage.get("cache_read_input_tokens") or 0)
    total = (
        int(usage.get("input_tokens") or 0)
        + int(usage.get("cache_creation_input_tokens") or 0)
        + read
        + int(usage.get("output_tokens") or 0)
    )
    calls = usage["calls"]
    text = f" · {calls} model call{'s' if calls != 1 else ''} · {total / 1000:.0f}k tokens"
    if read:
        text += f" ({read / 1000:.0f}k from cache)"
    if usage.get("cost_usd"):
        text += f" · ~${usage['cost_usd']:.3f} est."
    return text


def summarize(record: list[dict], findings: list[dict], title: str = "") -> str:
    """A Markdown summary of a Clerk conversation, for a later briefing.

    Each question with Clerk's final answer (evidence included), plus the latest cell
    type per cluster. Screenshots, lookup results and interim replies are left out.
    """
    lines = [f"### {title}" if title else "### Earlier Clerk session", ""]
    for number, entry in enumerate(record, start=1):
        answers = [s for s in entry.get("steps") or [] if s.get("kind") == "answer"]
        asked = f" ({entry['asked']})" if entry.get("asked") else ""
        lines += [f"**Q{number}{asked}:** {entry.get('question', '')}", ""]
        if answers:
            lines += [f"**Clerk:** {answers[-1].get('text', '').strip()}", ""]
    latest: dict[str, dict] = {}
    for finding in findings:
        latest[str(finding.get("cluster"))] = finding
    if latest:
        lines += [
            "**Recorded cell types (tentative):**",
            "",
            _findings_markdown(list(latest.values())),
        ]
    return "\n".join(lines).strip()


def build_notebook(
    record: list[dict],
    findings: list[dict],
    meta: dict | None = None,
    names: dict | None = None,
):
    """The conversation as a notebook: questions, screenshots under their code, answers.

    Args:
        record: ``Clerk.record`` (one entry per question).
        findings: ``Clerk.findings``.
        meta: Session details shown at the top (dataset context, widgets, versions).
        names: Variable names used in the reproduction code, e.g.
            ``{"landscape": "ls", "clustergram": "cgm"}``.
    """
    import nbformat

    meta = dict(meta or {})
    title = str(meta.get("title") or "Clerk report")
    cells = []
    header = [
        f"# {html.escape(title)}",
        "",
        f"Exported {meta.get('exported') or time.strftime('%Y-%m-%d %H:%M:%S')}"
        + (f" · Celldega {meta['celldega']}" if meta.get("celldega") else ""),
    ]
    if meta.get("context"):
        header += ["", f"**Context:** {meta['context']}"]
    if meta.get("widgets"):
        header += ["", "**Linked views:** " + ", ".join(meta["widgets"])]
    if meta.get("briefing"):
        sources = ", ".join(meta.get("briefing_sources") or []) or "text set directly"
        header += [
            "",
            _fold(f"Briefing: Clerk was given earlier work ({sources})", meta["briefing"]),
        ]
    header += [
        "",
        "Each screenshot is shown under code to replay supported settings with the "
        "widgets' `restore_snapshot` API (or `apply_state` for older records): load the "
        "same data in your linked widgets (named "
        f"`{(names or {}).get('landscape', 'landscape')}` and "
        f"`{(names or {}).get('clustergram', 'cgm')}` here). Clerk's lookups and "
        "interim replies are under *Work*; the evidence behind each answer is under "
        "*Evidence*. This is a partial restore: gates, edited neighborhood geometry, "
        "custom non-manual palettes and cross-widget links are not restored. "
        "Cited views have replay code but are not "
        "rendered on export. Cell types are tentative until you accept them.",
    ]
    cells.append(nbformat.v4.new_markdown_cell("\n".join(header)))

    for number, entry in enumerate(record, start=1):
        steps = entry.get("steps") or []
        model = " · ".join(
            x for x in (entry.get("model") or "default model", entry.get("effort")) if x
        )
        lines = [
            f"## {number}. {entry.get('question', '')}",
            "",
            f"<small>Asked {entry.get('asked', '')} · {model}"
            + (
                " · sent with: " + ", ".join(html.escape(s) for s in entry["sent_with"])
                if entry.get("sent_with")
                else ""
            )
            + _usage_text(entry.get("usage"))
            + "</small>",
        ]
        cells.append(nbformat.v4.new_markdown_cell("\n".join(lines)))

        answers = [i for i, s in enumerate(steps) if s.get("kind") == "answer"]
        final = answers[-1] if answers else None
        captures = [s for s in steps if s.get("kind") == "capture"]
        work = [
            s
            for i, s in enumerate(steps)
            if s.get("kind") in ("action", "lookups", "answer", "error", "pause") and i != final
        ]
        if captures:
            cells.append(_capture_cell(nbformat, captures[0], names))
        if work:
            cells.append(
                nbformat.v4.new_markdown_cell(
                    _fold(
                        f"Work · {len(work)} step{'s' if len(work) != 1 else ''}",
                        _work_markdown(work),
                    )
                )
            )
        for step in captures[1:]:
            cells.append(nbformat.v4.new_markdown_cell(f"**View after:** {step.get('text', '')}"))
            cells.append(_capture_cell(nbformat, step, names))
        if final is not None:
            views = steps[final].get("views") or {}
            text = _anchor_view_links(steps[final].get("text", ""), number, views)
            main, evidence, closing = split_evidence(text)
            body = ["**Clerk:**", "", main]
            if evidence:
                body += ["", _fold("Evidence", evidence)]
            if closing:
                body += ["", closing]
            cells.append(nbformat.v4.new_markdown_cell("\n".join(body)))
            # Views Clerk cited: in the live panel they're links that apply the view;
            # here each is a numbered figure with the code that recreates it.
            for view_id, view in views.items():
                caption = view.get("caption") or ""
                cells.append(
                    nbformat.v4.new_markdown_cell(
                        f'<a id="{_figure_anchor(number, view_id)}"></a>'
                        f"**Fig {view_id}.** {caption}"
                    )
                )
                cells.append(nbformat.v4.new_code_cell(reproduction_code(view, names)))
        recorded = [c for s in steps if s.get("kind") == "findings" for c in s["cell_types"]]
        if recorded:
            cells.append(
                nbformat.v4.new_markdown_cell(
                    "**Recorded cell types:**\n\n" + _findings_markdown(recorded)
                )
            )

    latest: dict[str, dict] = {}
    for finding in findings:
        latest[str(finding.get("cluster"))] = finding
    cells.append(
        nbformat.v4.new_markdown_cell(
            "## Cell types (latest per cluster)\n\n"
            + _findings_markdown(list(latest.values()))
            + "\n\nWrite them to an AnnData with "
            '`clerk.write_cell_types(adata, groupby="leiden")`.'
        )
    )
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata["clerk_report"] = {"version": REPORT_VERSION, **meta}
    return notebook


def notebook_to_html(notebook) -> str:
    """A self-contained HTML page (images embedded) from a report notebook."""
    from nbconvert import HTMLExporter

    exporter = HTMLExporter()
    exporter.exclude_input_prompt = True
    exporter.exclude_output_prompt = True
    title = notebook.metadata.get("clerk_report", {}).get("title") or "Clerk report"
    body, _resources = exporter.from_notebook_node(
        notebook, resources={"metadata": {"name": title}}
    )
    return body


def record_with_images(questions: list[dict], folder: Path | None) -> list[dict]:
    """A record read from ``record.json``, with its ``images/`` files back inline.

    The reverse of how :func:`write_report` stores screenshots; image paths that can't
    be read (or with no ``folder``) are dropped.
    """
    out = []
    for entry in questions or []:
        steps = []
        for step in entry.get("steps") or []:
            step = dict(step)
            for key in ("image", "clustergram_image"):
                value = step.get(key)
                if isinstance(value, str) and value.startswith("images/"):
                    path = Path(folder) / value if folder is not None else None
                    if path is not None and path.is_file():
                        step[key] = base64.b64encode(path.read_bytes()).decode()
                    else:
                        step.pop(key)
            steps.append(step)
        out.append({**entry, "steps": steps})
    return out


def _record_without_images(record: list[dict], folder: Path) -> list[dict]:
    """The record with screenshots written to ``images/`` and referenced by path."""
    images = folder / "images"
    out = []
    for number, entry in enumerate(record, start=1):
        steps = []
        shot = 0
        for step in entry.get("steps") or []:
            step = dict(step)
            if step.get("image") or step.get("clustergram_image"):
                shot += 1
            for key, suffix in (("image", ""), ("clustergram_image", "_clustergram")):
                # A record reopened from another report may already point at a file.
                if step.get(key) and not str(step[key]).startswith("images/"):
                    images.mkdir(parents=True, exist_ok=True)
                    name = f"q{number}_{shot}{suffix}.png"
                    (images / name).write_bytes(base64.b64decode(step[key]))
                    step[key] = f"images/{name}"
            steps.append(step)
        out.append({**entry, "steps": steps})
    return out


def write_report(
    folder: str | Path,
    record: list[dict],
    findings: list[dict],
    meta: dict | None = None,
    *,
    names: dict | None = None,
    html_report: bool = True,
    messages: list[dict] | None = None,
) -> dict[str, Path]:
    """Write the report files into ``folder`` (created if needed).

    ``messages`` (the Clerk panel's conversation) go into ``record.json`` too, so
    ``Clerk.load_conversation`` can reopen the report as it was shown.

    Returns:
        dict: The paths written, by kind (``html``, ``notebook``, ``record``,
        ``findings``).
    """
    import pandas as pd

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"exported": time.strftime("%Y-%m-%d %H:%M:%S"), **(meta or {})}
    written: dict[str, Path] = {}

    payload = {
        "version": REPORT_VERSION,
        "meta": meta,
        "questions": _record_without_images(record, folder),
        "findings": findings,
    }
    if messages is not None:
        payload["messages"] = messages
    written["record"] = folder / "record.json"
    written["record"].write_text(json.dumps(payload, indent=2, default=str))

    columns = ["cluster", "label", "confidence", "markers", "notes", "question", "recorded"]
    frame = pd.DataFrame(
        [{**f, "markers": ", ".join(f.get("markers") or [])} for f in findings], columns=columns
    )
    written["findings"] = folder / "findings.csv"
    frame.to_csv(written["findings"], index=False)

    try:
        import nbformat
    except ImportError:  # optional: the JSON record and findings are still written
        return written
    notebook = build_notebook(record, findings, meta, names)
    written["notebook"] = folder / "report.ipynb"
    nbformat.write(notebook, written["notebook"])
    if html_report:
        try:
            page = notebook_to_html(notebook)
        except ImportError:
            return written
        written["html"] = folder / "report.html"
        written["html"].write_text(page, encoding="utf-8")
    return written
