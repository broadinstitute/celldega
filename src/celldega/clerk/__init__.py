"""Clerk AI -- AI-assisted interpretation of clusters and regions.

This is the *backend* module (analysis, prompt building, data structures). The paired
visualization lives at :class:`celldega.viz.Clerk`. Keeping the two separate mirrors the
rest of the library: ``dega.clerk`` does the reasoning/data work, ``dega.viz.Clerk``
renders it.

Clerk talks to Claude via the local ``claude`` CLI (kernel-side, no API key). It reasons
from evidence that Celldega gathers -- the linked views' state, a Landscape screenshot,
lookups it asks for, and free-text context. Each question is one CLI session: follow-up
rounds resume it, so the conversation so far is read from the API's cache.

Example::

    import celldega as dega

    answer = dega.clerk.ask(
        "What cell type is this?",
        gene_list=["CD3D", "CD8A", "CD2"],
        info="Cluster 5, Xenium lung",
    )
"""

from . import lookups
from .engine import run_turn
from .llm import (
    CLUSTERGRAM_ACTIONS_HELP,
    DEFAULT_TIMEOUT,
    EFFORT_LEVELS,
    LOGIN_HELP,
    ClerkBackendError,
    Session,
    ask,
    build_follow_up,
    build_prompt,
    claude_auth_status,
    claude_available,
    extract_actions,
    extract_findings,
    extract_views,
    follow_up,
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
    "ClerkBackendError",
    "Session",
    "actions_help",
    "ask",
    "build_follow_up",
    "build_prompt",
    "claude_auth_status",
    "claude_available",
    "extract_actions",
    "extract_findings",
    "extract_views",
    "follow_up",
    "format_clustergram_state",
    "format_enrich_state",
    "format_landscape_state",
    "lookups",
    "run_claude",
    "run_turn",
]
