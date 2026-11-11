"""Talk to Claude via the local ``claude`` CLI (kernel-side, no API key).

The Clerk widget runs in the browser (JS) but the ``claude`` CLI is only reachable from
the kernel, so all inference happens here in Python. We shell out to the CLI rather than
using an API key -- this reuses the user's existing Claude Code authentication. The user
only needs the ``claude`` CLI installed and logged in once; no terminal session has to be
open while Clerk runs.

Two invocation modes (see :func:`run_claude`):

* text-only -- ``claude -p "<prompt>" --output-format json``; the answer is the
  ``result`` field of the emitted JSON object.
* with an image -- ``claude -p --input-format stream-json --output-format stream-json
  --verbose``; a single JSONL user message (with a base64 ``image`` content block) is
  written to stdin, and the answer is the ``result`` field of the final
  ``{"type": "result", ...}`` line. Nothing is written to disk.

Reasoning is single-shot with no tools: Celldega pre-gathers the evidence (gene list,
Enrichr terms, the Landscape raster, free-text context) and bundles it into one prompt.

Every call is isolated from the user's Claude Code setup (see :data:`ISOLATION_FLAGS`):
Clerk's own system prompt replaces Claude Code's, no tools or MCP servers are available,
the user's settings and hooks are not loaded, nothing is saved as a session, and the CLI
runs in a throwaway working directory so no project ``CLAUDE.md`` or memory is picked up.
Only the CLI's login is shared.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from .prompts import ACTIONS_FENCE, FINDINGS_FENCE, SYSTEM_PROMPT, VIEWS_FENCE, actions_help


DEFAULT_TIMEOUT = 180

# Reasoning effort levels the `claude` CLI accepts (``--effort``).
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# Flags that keep each call independent of the user's Claude Code configuration. Clerk's
# system prompt is passed separately via ``--system-prompt``.
ISOLATION_FLAGS = (
    "--tools",
    "",  # no built-in tools
    "--strict-mcp-config",  # ignore the user's MCP servers (none are passed)
    "--no-session-persistence",  # don't save Clerk calls as resumable sessions
    "--setting-sources",
    "",  # skip user/project/local settings, including hooks
)
# A Session (one question and its follow-up rounds) is saved while it is open so it
# can be resumed, then deleted (Session.close).
SESSION_ISOLATION_FLAGS = tuple(f for f in ISOLATION_FLAGS if f != "--no-session-persistence")

# Belt and braces on top of the throwaway working directory: the CLI's switches that
# turn off memory and CLAUDE.md loading. (The CLI still adds the account's email and
# today's date to the context; nothing about earlier work or data.)
ISOLATION_ENV = {
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
}

# The instructions live in prompts.py; re-exported here for convenience.
CLUSTERGRAM_ACTIONS_HELP = actions_help(clustergram=True)

# How much of the conversation goes with each question: the last N questions (each
# with Clerk's replies and actions), within a character budget. 40k characters is
# about 10k tokens. Sent once per question (follow-up rounds resume the session), so a
# longer memory costs little. Clerk sets these per panel (history_questions /
# history_chars).
MAX_HISTORY_QUESTIONS = 10
MAX_HISTORY_CHARS = 40_000
# Cap on a briefing (earlier work the scientist shares with Clerk), in characters.
MAX_BRIEFING_CHARS = 60_000


class ClerkBackendError(RuntimeError):
    """Raised when the ``claude`` CLI is unavailable or returns an error."""


LOGIN_HELP = (
    "Clerk needs you to log in to Claude once on this machine: open a terminal where "
    "the kernel runs and run `claude auth login`, then sign in through the page it "
    "opens (or the link it prints). The CLI remembers the login; Celldega never sees "
    "or stores it. Check with `dega.clerk.claude_auth_status()`."
)


def claude_available() -> bool:
    """Return True if the ``claude`` CLI is on PATH."""
    return shutil.which("claude") is not None


def claude_auth_status(timeout: float = 15) -> dict:
    """Report whether the local ``claude`` CLI is logged in, without a model call.

    Runs ``claude auth status --json``. Account details such as the email address and
    organization are deliberately dropped so they don't end up in notebook output.

    Args:
        timeout: Seconds before the check gives up.

    Returns:
        dict: ``logged_in`` (bool), plus ``auth_method`` and ``subscription_type`` when
        the CLI reports them, or ``error`` when the check itself failed.
    """
    if not claude_available():
        return {
            "logged_in": False,
            "error": "The 'claude' CLI was not found on PATH. Install Claude Code first.",
        }
    try:
        proc = subprocess.run(
            ["claude", "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"logged_in": False, "error": f"Could not check the login status: {exc}"}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        detail = (proc.stderr or proc.stdout or "").strip()
        return {"logged_in": False, "error": detail or "Unrecognized 'claude auth status' output."}
    return {
        "logged_in": bool(data.get("loggedIn")),
        "auth_method": data.get("authMethod") or "",
        "subscription_type": data.get("subscriptionType") or "",
    }


def build_prompt(
    question: str,
    gene_list: list[str] | None = None,
    enrichr_terms: list[dict] | None = None,
    info: str = "",
    has_image: bool = False,
    history: list[dict] | None = None,
    clustergram_state: dict | None = None,
    notes: list[str] | None = None,
    enrich_state: dict | None = None,
    actions_help: str | None = None,
    lookups: list[str] | None = None,
    landscape_state: dict | None = None,
    neighborhoods: list[dict] | None = None,
    briefing: str = "",
    history_questions: int | None = None,
    history_chars: int | None = None,
) -> str:
    """Assemble the prompt for one question from the gathered evidence.

    Args:
        question: The user's free-form question.
        gene_list: Marker / differentially expressed genes for the cluster.
        enrichr_terms: Pre-fetched Enrichr results, each a dict with at least
            ``name`` and (optionally) ``score`` / ``genes`` keys.
        info: Any extra free-text context (dataset, cluster id, notes).
        has_image: Whether a Landscape raster is attached to the message.
        history: Earlier turns, ``[{"role": "user" | "assistant", "content": ...}]``.
            Error entries are skipped; only the most recent questions are kept (see
            ``history_questions`` / ``history_chars``).
        clustergram_state: A Clustergram snapshot (``Clustergram.latest_state``) of
            what the scientist is looking at; see :func:`format_clustergram_state`.
        notes: Short notes about the evidence, e.g. that a linked view didn't reply.
        enrich_state: An Enrich snapshot (``Enrich.latest_state``) of the enrichment
            results on screen; see :func:`format_enrich_state`.

        actions_help: How Clerk may change the linked views (e.g.
            :data:`CLUSTERGRAM_ACTIONS_HELP`); omitted when nothing can be changed.
        lookups: Results of lookups Clerk asked for (markers, Enrichr, PubMed).
        landscape_state: A Landscape snapshot (``Landscape.latest_state``).
        neighborhoods: Drawn neighborhoods (``Landscape.neighborhood_summary()``).
        briefing: Earlier work the scientist chose to share (Markdown), e.g. from an
            exported Clerk record; capped at :data:`MAX_BRIEFING_CHARS`.
        history_questions: How many recent questions of ``history`` to include
            (default :data:`MAX_HISTORY_QUESTIONS`).
        history_chars: Character budget for ``history`` (default
            :data:`MAX_HISTORY_CHARS`).
    """
    parts: list[str] = []

    transcript = _format_history(history, history_questions, history_chars)
    if transcript:
        parts += ["## Conversation so far", transcript, ""]

    if info:
        parts += ["## Context", info.strip(), ""]

    if briefing and briefing.strip():
        text = briefing.strip()
        if len(text) > MAX_BRIEFING_CHARS:
            text = text[:MAX_BRIEFING_CHARS] + "\n\n[briefing truncated]"
        parts += [
            "## Earlier work (shared by the scientist)",
            "Conclusions from earlier sessions. Treat them as claims to check against "
            "the evidence below, not as evidence; say when you rely on them.",
            "",
            text,
            "",
        ]

    if gene_list:
        parts += [
            "## Marker / DE genes",
            ", ".join(str(g) for g in gene_list),
            "",
        ]

    if enrichr_terms:
        lines = []
        for t in enrichr_terms:
            name = t.get("name") if isinstance(t, dict) else str(t)
            if not name:
                continue
            score = t.get("score") if isinstance(t, dict) else None
            genes = t.get("genes") if isinstance(t, dict) else None
            suffix = ""
            if score is not None:
                suffix += f" (score {float(score):.2f})"
            if genes:
                overlap = ", ".join(str(g) for g in genes[:8])
                suffix += f" [{overlap}]"
            lines.append(f"- {name}{suffix}")
        if lines:
            parts += ["## Enrichr enrichment (top terms)", *lines, ""]

    landscape_text = format_landscape_state(landscape_state, neighborhoods)
    if landscape_text:
        parts += ["## Landscape (what the scientist sees)", landscape_text, ""]

    clustergram_text = format_clustergram_state(clustergram_state)
    if clustergram_text:
        parts += ["## Clustergram (what the scientist sees)", clustergram_text, ""]

    enrich_text = format_enrich_state(enrich_state)
    if enrich_text:
        parts += ["## Enrich: enrichment results on screen", enrich_text, ""]

    if has_image:
        parts += [
            "## Image",
            "A screenshot of the current Landscape view is attached.",
            "",
        ]

    if notes:
        parts += ["## Evidence notes", *(f"- {note}" for note in notes), ""]

    if lookups:
        parts += ["## Lookup results", *lookups, ""]

    if actions_help:
        parts += ["## Looking things up and changing views", actions_help, ""]

    parts += ["## Question", question.strip() or "Interpret this cluster."]
    return "\n".join(parts)


_SELECTION_MODES = {
    "viewport": "on screen",
    "ranked": "top of the current order",
    "names": "requested",
}


def _annotated(names: list[str], attributes: list[dict]) -> list[str]:
    """``name [attr=value, ...]`` for each item, skipping empty or redundant values."""
    out = []
    for i, name in enumerate(names):
        notes = []
        for attr in attributes:
            values = attr.get("values") or []
            value = values[i] if i < len(values) else None
            if value in (None, "", "NA", "nan") or str(value) == str(name):
                continue
            notes.append(f"{attr.get('name')}={value}")
        out.append(f"{name} [{', '.join(notes)}]" if notes else str(name))
    return out


def format_clustergram_state(
    state: dict | None, *, max_value_rows: int = 25, max_value_cols: int = 20
) -> str:
    """Render a Clustergram snapshot (``Clustergram.latest_state``) as compact text.

    Lists the visible rows and columns with their attributes, the order, marker level,
    dendrogram groups and selection, plus a capped table of values (and dot sizes).
    Returns ``""`` for an empty snapshot.
    """
    if not state:
        return ""
    lines: list[str] = []

    for axis_key, label in (("cols", "Columns"), ("rows", "Rows")):
        axis = state.get(axis_key) or {}
        names = [str(n) for n in axis.get("names") or []]
        if not names:
            continue
        mode = _SELECTION_MODES.get(axis.get("selection_mode"), "selected")
        order = (axis.get("order") or {}).get("label") or "unknown"
        count = f"{axis.get('total', len(names))} {mode}"
        if axis.get("displayed") is not None and axis.get("count") is not None:
            count += f" of {axis['displayed']} shown ({axis['count']} total)"
        more = f", +{axis['total'] - len(names)} more not listed" if axis.get("truncated") else ""
        lines.append(f"{label} ({count}; order: {order}{more}):")
        lines.append("  " + "; ".join(_annotated(names, axis.get("attributes") or [])))
        if axis.get("added"):
            lines.append(
                f"{label} added because they were asked about (may be off screen): "
                + ", ".join(str(n) for n in axis["added"])
            )
        if axis.get("missing"):
            lines.append(
                f"Asked about but not in the Clustergram {label.lower()}: "
                + ", ".join(str(n) for n in axis["missing"])
            )

        groups = axis.get("groups") or {}
        if groups.get("groups"):
            cut = groups.get("cut_percent")
            rendered = [
                f"{g['name']} ({g.get('size', len(g.get('members', [])))}): "
                + ", ".join(g.get("members") or [])
                for g in groups["groups"]
            ]
            head = f"{label} dendrogram groups" + (f" at {cut}% cut" if cut is not None else "")
            lines.append(f"{head}: " + " | ".join(rendered))

    level = state.get("marker_level")
    if level:
        current = level.get("current")
        unit = "markers per cluster" if level.get("unit") == "per_cluster" else "rows"
        shown = f"top {current} {unit}" if current is not None else "all rows"
        lines.append(f"Marker level (DIM slider): {shown}; levels: {level.get('levels')}")
    cluster_markers = state.get("cluster_markers")
    if cluster_markers:
        lines.append(
            "Ranked markers by cluster (rank_genes_groups, best first; value/dot size in "
            "that cluster):"
        )
        for entry in cluster_markers:
            if not entry.get("found"):
                lines.append(f"  {entry.get('cluster')}: no ranked markers")
                continue
            genes = []
            for gene in entry.get("genes") or []:
                value = gene.get("value")
                text = f"{gene['name']} {value:.2f}" if value is not None else str(gene["name"])
                if gene.get("size") is not None:
                    text += f"/{gene['size']:.2f}"
                genes.append(text)
            lines.append(f"  {entry.get('cluster')}: " + ", ".join(genes))
    elif state.get("marker_ranking"):
        lines.append("Ranked markers per cluster are available (lookup.markers).")
    display = state.get("display") or {}
    if display.get("mode"):
        mode = display["mode"] + (f", {display['size'].upper()}" if display.get("size") else "")
        focus = f"; zoomed to {display['focused_row']}" if display.get("focused_row") else ""
        lines.append(f"Display: {mode}{focus}")

    selection = state.get("selection") or {}
    click = selection.get("click")
    if click and click.get("type"):
        lines.append(f"Last click: {click['type']} {click.get('value')}")
    for key, label in (
        ("selected_genes", "Selected genes"),
        ("enrich_term_genes", "Genes in the selected Enrich term"),
    ):
        if selection.get(key):
            lines.append(f"{label}: " + ", ".join(selection[key]))
    group = selection.get("dendro_group")
    if group and group.get("members"):
        lines.append(
            f"Selected dendrogram group ({group.get('axis')} {group.get('name')}): "
            + ", ".join(group["members"])
        )

    block = state.get("values") or {}
    values = block.get("values") or []
    rows_state = state.get("rows") or {}
    all_rows = [str(n) for n in rows_state.get("names") or []]
    col_names = [str(n) for n in (state.get("cols") or {}).get("names") or []][:max_value_cols]
    # Rows asked about always make the table; fill the rest from the selection.
    added = {str(n) for n in rows_state.get("added") or []}
    added_idx = [i for i, n in enumerate(all_rows) if n in added][:max_value_rows]
    other_idx = [i for i, n in enumerate(all_rows) if n not in added]
    row_idx = sorted(other_idx[: max(0, max_value_rows - len(added_idx))] + added_idx)
    if values and row_idx and col_names:
        sizes = block.get("sizes")

        def cell(i, j):
            value = values[i][j] if i < len(values) and j < len(values[i]) else None
            text = "." if value is None else f"{value:.2f}"
            if sizes:
                size = sizes[i][j] if i < len(sizes) and j < len(sizes[i]) else None
                text += "" if size is None else f"/{size:.2f}"
            return text

        caption = "Values as displayed (often row z-scores)"
        if sizes:
            caption += " / dot size (often fraction of cells expressing)"
        lines.append(f"{caption}, rows x columns:")
        lines.append("\t".join(["", *col_names]))
        lines.extend(
            "\t".join([all_rows[i], *(cell(i, j) for j in range(len(col_names)))]) for i in row_idx
        )

    return "\n".join(lines)


def format_landscape_state(state: dict | None, neighborhoods: list[dict] | None = None) -> str:
    """Render a Landscape snapshot (``Landscape.latest_state``) and drawn neighborhoods
    (``Landscape.neighborhood_summary()``) as compact text."""
    lines: list[str] = []
    if state:
        view = state.get("view_state") or {}
        target = view.get("target")
        camera = (
            f"; camera at ({target[0]}, {target[1]}), zoom {view.get('zoom')}"
            if target and len(target) >= 2
            else ""
        )
        lines.append(f"Space: {state.get('space') or 'unknown'}{camera}")
        color_by = state.get("color_by")
        if color_by and color_by != "cluster":
            lines.append(f"Cells colored by gene expression: {color_by}")
        elif state.get("selected_clusters"):
            lines.append("Highlighted clusters: " + ", ".join(state["selected_clusters"]))
        else:
            lines.append("Cells colored by cluster; nothing selected")
        viewport = state.get("viewport") or {}
        if viewport.get("clusters"):
            lines.append(
                "Cells in view by cluster: "
                + ", ".join(f"{c['name']} ({c['value']:g})" for c in viewport["clusters"])
            )
        if viewport.get("genes"):
            summary = viewport.get("gene_summary") or {}
            mode = summary.get("mode")
            caption = {
                "estimate": "Estimated genes in view from cell-type means",
                "dataset": "Whole-dataset genes (not specific to this field of view)",
                "whole": "Whole-dataset genes (all cells are in view)",
                "unavailable": "Gene bars (current viewport summary unavailable)",
            }.get(mode, "Gene bars (scope and method not recorded)")
            if summary.get("units"):
                caption += f" [{summary['units']}]"
            lines.append(
                caption
                + ": "
                + ", ".join(f"{g['name']} ({g['value']:g})" for g in viewport["genes"])
            )
            if summary.get("status"):
                lines.append(str(summary["status"]))
    for nbhd in neighborhoods or []:
        mix = ", ".join(
            f"{c['name']} {round(100 * c['fraction'])}%" for c in nbhd.get("clusters") or []
        )
        lines.append(
            f"Drawn neighborhood {nbhd.get('name') or '(unnamed)'} ({nbhd.get('space')}): "
            f"{nbhd.get('n_cells', 0)} cells" + (f"; clusters {mix}" if mix else "")
        )
    return "\n".join(lines)


def format_enrich_state(state: dict | None, *, max_genes: int = 12) -> str:
    """Render an Enrich snapshot (``Enrich.latest_state``) as compact text.

    Returns ``""`` when there is nothing to report (no gene list).
    """
    if not state or not (state.get("gene_list") or state.get("terms")):
        return ""
    lines: list[str] = []
    genes = [str(g) for g in state.get("gene_list") or []]
    n_genes = state.get("n_genes") or len(genes)
    source = f", from {state['source_label']}" if state.get("source_label") else ""
    shown = ", ".join(genes[:40]) + (f", +{n_genes - 40} more" if n_genes > 40 else "")
    lines.append(f"Library: {state.get('library') or 'unknown'}")
    lines.append(f"Input genes ({n_genes}{source}): {shown}")
    if state.get("loading"):
        lines.append(
            "(Enrichment was still loading; the terms below may be for the previous list.)"
        )

    def stat(value, label):
        return f"{label} {value:.3g}" if isinstance(value, int | float) else None

    for rank, term in enumerate(state.get("terms") or [], start=1):
        stats = [
            s
            for s in (
                stat(term.get("score"), "combined score"),
                stat(term.get("adjusted_p"), "adj. p"),
                stat(term.get("odds_ratio"), "odds ratio"),
            )
            if s
        ]
        overlap = [str(g) for g in term.get("genes") or []]
        more = f", +{len(overlap) - max_genes}" if len(overlap) > max_genes else ""
        lines.append(
            f"{rank}. {term.get('name')} ({'; '.join(stats)}): "
            + ", ".join(overlap[:max_genes])
            + more
        )
    selected = state.get("selected_term")
    if selected and selected != "Select Term":
        lines.append(
            f"Selected term: {selected}; its genes: "
            + ", ".join(str(g) for g in state.get("term_genes") or [])
        )
    if state.get("link"):
        lines.append(f"Full results: {state['link']}")
    return "\n".join(lines)


_ACTIONS_BLOCK = re.compile(
    rf"```{re.escape(ACTIONS_FENCE)}[ \t]*\n(.*?)\n?```", re.DOTALL | re.IGNORECASE
)
_FINDINGS_BLOCK = re.compile(
    rf"```{re.escape(FINDINGS_FENCE)}[ \t]*\n(.*?)\n?```", re.DOTALL | re.IGNORECASE
)
_VIEWS_BLOCK = re.compile(
    rf"```{re.escape(VIEWS_FENCE)}[ \t]*\n(.*?)\n?```", re.DOTALL | re.IGNORECASE
)
# Settings a cited view may use, per widget (the apply_state keys, minus edits).
VIEW_KEYS = {
    "landscape": (
        "clusters",
        "genes",
        "view",
        "zoom_to",
        "reset_view",
        "space",
        "layers",
        "channels",
        "sliders",
        "image_source",
    ),
    "clustergram": (
        "marker_level",
        "mode",
        "size",
        "focus_gene",
        "view",
        "order",
        "crop",
        "dendrogram_group",
    ),
}
#: Settings a view holds once :func:`resolve_dendrogram_groups` has expanded a
#: ``dendrogram_group`` (the cut it was seen at, and that group selected).
RESOLVED_VIEW_KEYS = {"clustergram": ("dendrogram", "selection")}
MAX_VIEWS = 12


def resolve_dendrogram_groups(
    views: dict | None, clustergram_state: dict | None
) -> tuple[dict | None, list[str]]:
    """Pin each view's ``dendrogram_group`` to the Clustergram state Clerk saw.

    Clerk names a group as listed in the Clustergram snapshot, e.g.
    ``{"dendrogram_group": {"axis": "col", "name": "39"}}``. Group names depend on
    the dendrogram cut, so the view keeps that cut and selects the group by its
    members (by name when the snapshot lists only some of them). Groups the
    snapshot doesn't show are dropped from the view and reported.

    Returns:
        tuple: ``(views, problems)``.
    """
    if not views:
        return views, []
    problems: list[str] = []
    resolved = {}
    for view_id, view in views.items():
        settings = (view or {}).get("clustergram")
        if not isinstance(settings, dict) or "dendrogram_group" not in settings:
            resolved[view_id] = view
            continue
        settings = dict(settings)
        spec = settings.pop("dendrogram_group")
        axis = str((spec or {}).get("axis") or "col") if isinstance(spec, dict) else ""
        name = str((spec or {}).get("name") or "") if isinstance(spec, dict) else ""
        name = re.sub(r"^\s*group\s+", "", name, flags=re.IGNORECASE).strip()
        key = {"col": "cols", "row": "rows"}.get(axis)
        groups = ((clustergram_state or {}).get(key) or {}).get("groups") or {} if key else {}
        group = next((g for g in groups.get("groups") or [] if str(g.get("name")) == name), None)
        if group is None:
            problems.append(f"view {view_id}: no {axis or '?'} dendrogram group {name!r} in view")
        else:
            members = [str(m) for m in group.get("members") or []]
            complete = members and len(members) >= int(group.get("size") or len(members))
            selection = dict(settings.get("selection") or {})
            selection["dendrogram"] = (
                {"axis": axis, "members": members} if complete else {"axis": axis, "name": name}
            )
            settings["selection"] = selection
            if groups.get("cut_percent") is not None:
                settings["dendrogram"] = {
                    **(settings.get("dendrogram") or {}),
                    axis: float(groups["cut_percent"]),
                }
        view = {**view, "clustergram": settings}
        if not settings:
            view.pop("clustergram")
        if any(widget in view for widget in VIEW_KEYS):
            resolved[view_id] = view
    return resolved or None, problems


_VIEW_ID = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")


def _merge_into(target: dict, extra: dict) -> dict:
    """Merge ``extra`` into ``target``, recursing into dicts both have."""
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_into(target[key], value)
        else:
            target[key] = value
    return target


def _load_block(text: str):
    """The JSON in a fenced block, tolerating what models sometimes write.

    Several objects one after another (e.g. one per cluster) are merged into one;
    stray closing brackets after the last object are ignored. Anything else raises
    the original :class:`json.JSONDecodeError`.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as first:
        decoder = json.JSONDecoder()
        objects, i, n = [], 0, len(text)
        while True:
            while i < n and text[i] in " \t\r\n,":
                i += 1
            if i >= n or not text[i:].strip(" \t\r\n}]"):
                break
            try:
                value, i = decoder.raw_decode(text, i)
            except json.JSONDecodeError:
                raise first from None
            objects.append(value)
        if not objects or not all(isinstance(o, dict) for o in objects):
            raise first from None
        merged: dict = {}
        for value in objects:
            _merge_into(merged, value)
        return merged


def extract_findings(answer: str) -> tuple[str, dict | None, str | None]:
    """Split an answer into its text and any ``celldega-findings`` block.

    Returns:
        tuple: ``(text, findings, error)``; ``findings`` is the parsed JSON object
        (e.g. ``{"cell_types": [...]}``) or ``None``.
    """
    match = _FINDINGS_BLOCK.search(answer or "")
    if not match:
        return (answer or "").strip(), None, None
    text = (answer[: match.start()] + answer[match.end() :]).strip()
    try:
        findings = _load_block(match.group(1))
    except json.JSONDecodeError as exc:
        return text, None, f"Could not read the recorded findings: {exc}"
    if not isinstance(findings, dict):
        return text, None, "Recorded findings must be a JSON object."
    return text, findings, None


def extract_views(answer: str) -> tuple[str, dict | None, str | None]:
    """Split an answer into its text and any ``celldega-views`` block.

    A view is what Clerk wants to show for a point it makes: ``{"caption": ...,
    "landscape": {...}, "clustergram": {...}}`` with ``apply_state`` settings (see
    :data:`VIEW_KEYS`). The answer cites it as ``[Fig 1A](view:1A)``; nothing changes
    until the scientist clicks. Invalid views are dropped and reported.

    Returns:
        tuple: ``(text, views, error)``; ``views`` maps view ids to views, or is
        ``None``.
    """
    match = _VIEWS_BLOCK.search(answer or "")
    if not match:
        return (answer or "").strip(), None, None
    text = (answer[: match.start()] + answer[match.end() :]).strip()
    try:
        raw = _load_block(match.group(1))
    except json.JSONDecodeError as exc:
        return text, None, f"Could not read the cited views: {exc}"
    if not isinstance(raw, dict):
        return text, None, "Cited views must be a JSON object of view ids."
    views, problems = {}, []
    for view_id, view in list(raw.items())[:MAX_VIEWS]:
        view_id = str(view_id)
        if not _VIEW_ID.match(view_id) or not isinstance(view, dict):
            problems.append(f"{view_id!r} is not a valid view")
            continue
        clean: dict = {"caption": str(view.get("caption") or "")}
        for widget, keys in VIEW_KEYS.items():
            settings = view.get(widget)
            if settings is None:
                continue
            unknown = sorted(set(settings) - set(keys)) if isinstance(settings, dict) else None
            if unknown is None or unknown:
                problems.append(f"view {view_id}: unknown {widget} setting(s) {unknown}")
                clean = {}
                break
            clean[widget] = settings
        if clean and any(widget in clean for widget in VIEW_KEYS):
            views[view_id] = clean
        elif clean:
            problems.append(f"view {view_id} changes nothing")
    error = "Some cited views were dropped: " + "; ".join(problems) if problems else None
    return text, views or None, error


def extract_actions(answer: str) -> tuple[str, dict | None, str | None]:
    """Split an answer into its text and any ``celldega-actions`` block.

    Returns:
        tuple: ``(text, actions, error)``. ``text`` is the answer without the block;
        ``actions`` maps a widget name (e.g. ``"clustergram"``) to its settings, plus
        an optional ``"continue": true``, or is ``None``; ``error`` describes a
        malformed block.
    """
    match = _ACTIONS_BLOCK.search(answer or "")
    if not match:
        return (answer or "").strip(), None, None
    text = (answer[: match.start()] + answer[match.end() :]).strip()
    try:
        actions = _load_block(match.group(1))
    except json.JSONDecodeError as exc:
        return text, None, f"Could not read the requested view change: {exc}"
    # Widget names map to settings; "continue" (bool) asks to see the result.
    if not isinstance(actions, dict) or not all(
        isinstance(v, bool) if k == "continue" else isinstance(v, dict) for k, v in actions.items()
    ):
        return text, None, "The requested view change must map widget names to settings."
    return text, actions, None


def _format_history(
    history: list[dict] | None,
    max_questions: int | None = None,
    max_chars: int | None = None,
) -> str:
    """Render the recent conversation as text, newest last, within the caps.

    Keeps the last ``max_questions`` questions with Clerk's replies and actions, then
    drops the oldest lines until it fits ``max_chars`` (defaults:
    :data:`MAX_HISTORY_QUESTIONS`, :data:`MAX_HISTORY_CHARS`).
    """
    max_questions = MAX_HISTORY_QUESTIONS if max_questions is None else max_questions
    max_chars = MAX_HISTORY_CHARS if max_chars is None else max_chars
    labels = {"user": "Scientist", "assistant": "Clerk", "action": "Clerk did"}
    groups: list[list[str]] = []
    for m in history or []:
        if not isinstance(m, dict) or m.get("role") not in labels:
            continue
        if m["role"] == "user" or not groups:
            groups.append([])
        groups[-1].append(f"{labels[m['role']]}: {str(m.get('content', '')).strip()}")
    lines = [line for group in groups[-max_questions:] for line in group] if max_questions else []
    # Drop the oldest lines until the transcript fits the character budget.
    while lines and sum(len(t) for t in lines) > max_chars:
        lines.pop(0)
    return "\n\n".join(lines)


def _extract_result_text(stdout: str, streaming: bool) -> str:
    """Pull the answer text out of the CLI's JSON output."""
    if streaming:
        # stream-json emits one JSON object per line; the final success object holds
        # the full result.
        result = ""
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "result":
                if obj.get("is_error"):
                    raise ClerkBackendError(obj.get("result") or "claude reported an error")
                result = obj.get("result", result)
        if not result:
            raise ClerkBackendError("No result found in claude stream output.")
        return result

    obj = json.loads(stdout)
    if obj.get("is_error"):
        raise ClerkBackendError(obj.get("result") or "claude reported an error")
    return obj.get("result", "")


def _claude_projects_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"


class Session:
    """One CLI conversation: a question and its follow-up rounds.

    The first call starts it (``--session-id``) with the full prompt; each later call
    resumes it (``--resume``) and sends only what is new (lookup results, views that
    changed). The API caches the conversation so far, so a follow-up round re-reads it
    at about a tenth of the price instead of paying for all of it again; in a test, a
    follow-up round on a 34k-token prompt cost $0.008 instead of $0.12.

    The CLI saves the transcript (under ``~/.claude/projects``) so it can be resumed;
    :meth:`close` deletes it and the working directory. Transcripts left behind by a
    crashed kernel are removed the next time a Session starts.
    """

    # Transcripts of Clerk sessions older than this are assumed abandoned.
    STALE_SECONDS = 3600

    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.workdir = tempfile.mkdtemp(prefix="celldega-clerk-")
        self.calls = 0
        self.usage: list[dict] = []
        _remove_stale_sessions(self.STALE_SECONDS)

    @property
    def started(self) -> bool:
        return self.calls > 0

    def totals(self) -> dict:
        """Tokens and the CLI's cost estimate summed over the calls so far."""
        keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        out = {k: sum(int(u.get(k) or 0) for u in self.usage) for k in keys}
        out["output_tokens"] = sum(int(u.get("output_tokens") or 0) for u in self.usage)
        out["cost_usd"] = round(sum(float(u.get("cost_usd") or 0) for u in self.usage), 5)
        out["calls"] = len(self.usage)
        return out

    def close(self) -> None:
        """Delete the saved transcript and the working directory."""
        shutil.rmtree(self.workdir, ignore_errors=True)
        projects = _claude_projects_dir()
        for path in projects.glob(f"*/{self.id}.jsonl"):
            path.unlink(missing_ok=True)
        for path in projects.glob(f"*/{self.id}"):
            shutil.rmtree(path, ignore_errors=True)
        own = projects / re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(self.workdir))
        shutil.rmtree(own, ignore_errors=True)


def _remove_stale_sessions(max_age: float) -> None:
    """Delete transcripts of Clerk sessions that were never closed (e.g. a crash)."""
    cutoff = time.time() - max_age
    for path in _claude_projects_dir().glob("*celldega-clerk-*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def build_follow_up(
    notes: list[str] | None = None,
    lookups: list[str] | None = None,
    clustergram_state: dict | None = None,
    landscape_state: dict | None = None,
    neighborhoods: list[dict] | None = None,
    enrich_state: dict | None = None,
    has_image: bool = False,
) -> str:
    """The message for a follow-up round: only what is new since the last message."""
    parts: list[str] = []
    landscape_text = format_landscape_state(landscape_state, neighborhoods)
    if landscape_text:
        parts += ["## Landscape now", landscape_text, ""]
    clustergram_text = format_clustergram_state(clustergram_state)
    if clustergram_text:
        parts += ["## Clustergram now", clustergram_text, ""]
    enrich_text = format_enrich_state(enrich_state)
    if enrich_text:
        parts += ["## Enrich now", enrich_text, ""]
    if has_image:
        parts += ["## Image", "A new screenshot of the Landscape view is attached.", ""]
    if notes:
        parts += ["## Notes", *(f"- {note}" for note in notes), ""]
    if lookups:
        parts += ["## Lookup results", *lookups, ""]
    parts += [
        "Continue answering the scientist's question with this. Don't repeat what you "
        "already said or request anything you already did."
    ]
    return "\n".join(parts)


def run_claude(
    prompt: str,
    image_b64: str | None = None,
    model: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    effort: str = "",
    session: Session | None = None,
) -> str:
    """Call the ``claude`` CLI (no tools) and return the answer text.

    Args:
        prompt: The fully-assembled prompt (see :func:`build_prompt`).
        image_b64: Optional base64 PNG payload (no ``data:`` prefix) to attach as an
            image content block. When provided, the streaming stdin path is used.
        model: Optional model alias or id (e.g. ``"opus"``, ``"sonnet"``, ``"haiku"``).
            Empty string inherits the CLI's configured default.
        timeout: Seconds before the subprocess is killed.
        effort: Reasoning effort (``"low"``, ``"medium"``, ``"high"``, ``"xhigh"``,
            ``"max"``); empty inherits the CLI default. Higher effort is slower and
            uses more tokens.
        session: Optional :class:`Session`. Without one the call is single-shot and
            nothing is saved; with one, the first call starts the session and later
            calls resume it.
    """
    if not claude_available():
        raise ClerkBackendError(
            "The 'claude' CLI was not found on PATH. Install and authenticate Claude "
            "Code once (run 'claude' in a terminal and log in); after that the Clerk "
            "widget works without an open terminal session."
        )

    if session is None:
        cmd = ["claude", "-p", "--system-prompt", SYSTEM_PROMPT, *ISOLATION_FLAGS]
    else:
        cmd = ["claude", "-p", "--system-prompt", SYSTEM_PROMPT, *SESSION_ISOLATION_FLAGS]
        cmd += ["--resume" if session.started else "--session-id", session.id]
    if model:
        cmd += ["--model", model]
    if effort:
        if effort not in EFFORT_LEVELS:
            raise ClerkBackendError(f"effort must be one of {list(EFFORT_LEVELS)}, not {effort!r}")
        cmd += ["--effort", effort]

    stdin_data: str | None = None
    if image_b64:
        # Multimodal: stream-json in requires stream-json out + --verbose.
        cmd += [
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        user_msg = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        }
        stdin_data = json.dumps(user_msg) + "\n"
        streaming = True
    else:
        cmd += [prompt, "--output-format", "json"]
        streaming = False

    def _run(workdir: str):
        return subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
            env={**os.environ, **ISOLATION_ENV},
        )

    try:
        # A throwaway working directory keeps the CLI from discovering a project
        # CLAUDE.md or per-project memory from wherever the kernel happens to run.
        if session is not None:
            proc = _run(session.workdir)
        else:
            with tempfile.TemporaryDirectory(prefix="celldega-clerk-") as workdir:
                proc = _run(workdir)
    except subprocess.TimeoutExpired as exc:
        raise ClerkBackendError(f"claude timed out after {timeout}s.") from exc
    except OSError as exc:  # pragma: no cover - depends on environment
        raise ClerkBackendError(f"Failed to launch claude: {exc}") from exc

    if proc.returncode != 0:
        # The most common first-run failure: explain how to log in rather than echoing
        # the CLI's raw error.
        if not claude_auth_status().get("logged_in"):
            raise ClerkBackendError(LOGIN_HELP)
        detail = (proc.stderr or proc.stdout or "").strip()
        raise ClerkBackendError(f"claude exited with code {proc.returncode}: {detail}")

    text = _extract_result_text(proc.stdout, streaming).strip()
    if session is not None:
        session.calls += 1
        session.usage.append(_extract_usage(proc.stdout))
    return text


def _extract_usage(stdout: str) -> dict:
    """Token counts and the CLI's cost estimate from its JSON output (best effort)."""
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("type", "result") == "result":
            usage = dict(obj.get("usage") or {})
            usage["cost_usd"] = obj.get("total_cost_usd")
            return usage
    return {}


def ask(
    question: str,
    gene_list: list[str] | None = None,
    enrichr_terms: list[dict] | None = None,
    info: str = "",
    image_b64: str | None = None,
    model: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    effort: str = "",
    history: list[dict] | None = None,
    clustergram_state: dict | None = None,
    notes: list[str] | None = None,
    enrich_state: dict | None = None,
    actions_help: str | None = None,
    lookups: list[str] | None = None,
    landscape_state: dict | None = None,
    neighborhoods: list[dict] | None = None,
    session: Session | None = None,
    briefing: str = "",
    history_questions: int | None = None,
    history_chars: int | None = None,
) -> str:
    """Build the prompt from evidence (and earlier turns) and run the model.

    With a :class:`Session`, this starts it; continue with :func:`follow_up`.
    """
    prompt = build_prompt(
        question,
        gene_list=gene_list,
        enrichr_terms=enrichr_terms,
        info=info,
        has_image=bool(image_b64),
        history=history,
        clustergram_state=clustergram_state,
        notes=notes,
        enrich_state=enrich_state,
        actions_help=actions_help,
        lookups=lookups,
        landscape_state=landscape_state,
        neighborhoods=neighborhoods,
        briefing=briefing,
        history_questions=history_questions,
        history_chars=history_chars,
    )
    return run_claude(
        prompt, image_b64=image_b64, model=model, timeout=timeout, effort=effort, session=session
    )


def follow_up(
    session: Session,
    *,
    notes: list[str] | None = None,
    lookups: list[str] | None = None,
    clustergram_state: dict | None = None,
    landscape_state: dict | None = None,
    neighborhoods: list[dict] | None = None,
    enrich_state: dict | None = None,
    image_b64: str | None = None,
    model: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    effort: str = "",
) -> str:
    """Continue a started :class:`Session` with only what is new (see :func:`build_follow_up`)."""
    if not session.started:
        raise ValueError("start the session with ask(..., session=session) first")
    prompt = build_follow_up(
        notes=notes,
        lookups=lookups,
        clustergram_state=clustergram_state,
        landscape_state=landscape_state,
        neighborhoods=neighborhoods,
        enrich_state=enrich_state,
        has_image=bool(image_b64),
    )
    return run_claude(
        prompt, image_b64=image_b64, model=model, timeout=timeout, effort=effort, session=session
    )
