"""Celldega Clerk -- LLM-assisted interpretation of clusters and regions.

This is the *backend* module (analysis, prompt building, data structures). The paired
visualization lives at :class:`celldega.viz.Clerk`. Keeping the two separate mirrors the
rest of the library: ``dega.clerk`` does the reasoning/data work, ``dega.viz.Clerk``
renders it.

Clerk talks to Claude via the local ``claude`` CLI (kernel-side, no API key). It reasons
single-shot from evidence that Celldega pre-gathers -- a gene list, Enrichr terms, a
captured Landscape raster, and free-text context.

Example::

    import celldega as dega

    answer = dega.clerk.ask(
        "What cell type is this?",
        gene_list=["CD3D", "CD8A", "CD2"],
        info="Cluster 5, Xenium lung",
    )
"""

from . import lookups
from .casefile import CaseFile
from .llm import (
    CLUSTERGRAM_ACTIONS_HELP,
    DEFAULT_TIMEOUT,
    EFFORT_LEVELS,
    LOGIN_HELP,
    ClerkBackendError,
    ask,
    build_prompt,
    claude_auth_status,
    claude_available,
    extract_actions,
    extract_findings,
    format_clustergram_state,
    format_enrich_state,
    format_landscape_state,
    run_claude,
)
from .prompts import SYSTEM_PROMPT, actions_help


__all__ = [
    "CLUSTERGRAM_ACTIONS_HELP",
    "DEFAULT_TIMEOUT",
    "EFFORT_LEVELS",
    "LOGIN_HELP",
    "SYSTEM_PROMPT",
    "CaseFile",
    "ClerkBackendError",
    "actions_help",
    "ask",
    "build_prompt",
    "claude_auth_status",
    "claude_available",
    "extract_actions",
    "extract_findings",
    "format_clustergram_state",
    "format_enrich_state",
    "format_landscape_state",
    "lookups",
    "run_claude",
]
