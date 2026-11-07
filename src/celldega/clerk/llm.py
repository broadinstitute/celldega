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
import re
import shutil
import subprocess
import tempfile

from .prompts import ACTIONS_FENCE, FINDINGS_FENCE, SYSTEM_PROMPT, actions_help


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

# The instructions live in prompts.py; re-exported here for convenience.
CLUSTERGRAM_ACTIONS_HELP = actions_help(clustergram=True)

# Most recent conversation turns sent with each question (older turns are dropped).
# 12k characters is roughly 3k tokens.
MAX_HISTORY_TURNS = 12
MAX_HISTORY_CHARS = 12_000


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
            Error entries are skipped; only the most recent turns are kept (see
            :data:`MAX_HISTORY_TURNS` / :data:`MAX_HISTORY_CHARS`).
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
    """
    parts: list[str] = []

    transcript = _format_history(history)
    if transcript:
        parts += ["## Conversation so far", transcript, ""]

    if info:
        parts += ["## Context", info.strip(), ""]

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
            lines.append(
                "Top genes in view: "
                + ", ".join(f"{g['name']} ({g['value']:g})" for g in viewport["genes"])
            )
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
        findings = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return text, None, f"Could not read the recorded findings: {exc}"
    if not isinstance(findings, dict):
        return text, None, "Recorded findings must be a JSON object."
    return text, findings, None


def extract_actions(answer: str) -> tuple[str, dict | None, str | None]:
    """Split an answer into its text and any ``celldega-actions`` block.

    Returns:
        tuple: ``(text, actions, error)``. ``text`` is the answer without the block;
        ``actions`` maps a widget name (e.g. ``"clustergram"``) to its settings, or is
        ``None``; ``error`` describes a malformed block.
    """
    match = _ACTIONS_BLOCK.search(answer or "")
    if not match:
        return (answer or "").strip(), None, None
    text = (answer[: match.start()] + answer[match.end() :]).strip()
    try:
        actions = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return text, None, f"Could not read the requested view change: {exc}"
    if not isinstance(actions, dict) or not all(isinstance(v, dict) for v in actions.values()):
        return text, None, "The requested view change must map widget names to settings."
    return text, actions, None


def _format_history(history: list[dict] | None) -> str:
    """Render recent user/assistant turns as text, newest last, within the caps."""
    labels = {"user": "Scientist", "assistant": "Clerk", "action": "Clerk changed the view"}
    turns = [
        f"{labels[m['role']]}: {str(m.get('content', '')).strip()}"
        for m in (history or [])
        if isinstance(m, dict) and m.get("role") in labels
    ][-MAX_HISTORY_TURNS:]
    # Drop the oldest turns until the transcript fits the character budget.
    while turns and sum(len(t) for t in turns) > MAX_HISTORY_CHARS:
        turns.pop(0)
    return "\n\n".join(turns)


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


def run_claude(
    prompt: str,
    image_b64: str | None = None,
    model: str = "",
    timeout: int = DEFAULT_TIMEOUT,
    effort: str = "",
) -> str:
    """Call the ``claude`` CLI single-shot (no tools) and return the answer text.

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
    """
    if not claude_available():
        raise ClerkBackendError(
            "The 'claude' CLI was not found on PATH. Install and authenticate Claude "
            "Code once (run 'claude' in a terminal and log in); after that the Clerk "
            "widget works without an open terminal session."
        )

    cmd = ["claude", "-p", "--system-prompt", SYSTEM_PROMPT, *ISOLATION_FLAGS]
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

    try:
        # A throwaway working directory keeps the CLI from discovering a project
        # CLAUDE.md or per-project memory from wherever the kernel happens to run.
        with tempfile.TemporaryDirectory(prefix="celldega-clerk-") as workdir:
            proc = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir,
            )
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

    return _extract_result_text(proc.stdout, streaming).strip()


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
) -> str:
    """Build the prompt from evidence (and earlier turns) and run the model in one call."""
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
    )
    return run_claude(prompt, image_b64=image_b64, model=model, timeout=timeout, effort=effort)
