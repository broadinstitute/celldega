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
"""

from __future__ import annotations

import json
import shutil
import subprocess


DEFAULT_TIMEOUT = 180

_SYSTEM_PREAMBLE = (
    "You are Celldega Clerk, an assistant embedded in a spatial-transcriptomics "
    "visualization tool. You help a scientist interpret evidence about a cluster or "
    "region of cells -- proposing cell-type annotations, explaining marker genes, and "
    "answering questions. Reason only from the evidence provided below. Be concise and "
    "concrete; when you propose a cell-type label, give a short rationale grounded in "
    "the markers and any image. If the evidence is insufficient, say so plainly."
)


class ClerkBackendError(RuntimeError):
    """Raised when the ``claude`` CLI is unavailable or returns an error."""


def claude_available() -> bool:
    """Return True if the ``claude`` CLI is on PATH."""
    return shutil.which("claude") is not None


def build_prompt(
    question: str,
    gene_list: list[str] | None = None,
    enrichr_terms: list[dict] | None = None,
    info: str = "",
    has_image: bool = False,
) -> str:
    """Assemble the single-shot prompt from the gathered evidence.

    Args:
        question: The user's free-form question.
        gene_list: Marker / differentially expressed genes for the cluster.
        enrichr_terms: Pre-fetched Enrichr results, each a dict with at least
            ``name`` and (optionally) ``score`` / ``genes`` keys.
        info: Any extra free-text context (dataset, cluster id, notes).
        has_image: Whether a Landscape raster is attached to the message.
    """
    parts: list[str] = [_SYSTEM_PREAMBLE, ""]

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

    if has_image:
        parts += [
            "## Image",
            "A raster screenshot of the Landscape view for this selection is attached.",
            "",
        ]

    parts += ["## Question", question.strip() or "Interpret this cluster."]
    return "\n".join(parts)


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
) -> str:
    """Call the ``claude`` CLI single-shot (no tools) and return the answer text.

    Args:
        prompt: The fully-assembled prompt (see :func:`build_prompt`).
        image_b64: Optional base64 PNG payload (no ``data:`` prefix) to attach as an
            image content block. When provided, the streaming stdin path is used.
        model: Optional model id/alias (e.g. ``"sonnet"``, ``"claude-haiku-4-5"``).
            Empty string inherits the CLI's configured default.
        timeout: Seconds before the subprocess is killed.
    """
    if not claude_available():
        raise ClerkBackendError(
            "The 'claude' CLI was not found on PATH. Install and authenticate Claude "
            "Code once (run 'claude' in a terminal and log in); after that the Clerk "
            "widget works without an open terminal session."
        )

    cmd = ["claude", "-p"]
    if model:
        cmd += ["--model", model]

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
        proc = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClerkBackendError(f"claude timed out after {timeout}s.") from exc
    except OSError as exc:  # pragma: no cover - depends on environment
        raise ClerkBackendError(f"Failed to launch claude: {exc}") from exc

    if proc.returncode != 0:
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
) -> str:
    """Convenience: build the prompt from evidence and run the model in one call."""
    prompt = build_prompt(
        question,
        gene_list=gene_list,
        enrichr_terms=enrichr_terms,
        info=info,
        has_image=bool(image_b64),
    )
    return run_claude(prompt, image_b64=image_b64, model=model, timeout=timeout)
