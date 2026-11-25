"""Captions: a paragraph under a figure whose links change the figure.

``caption(text, views, landscape=..., clustergram=...)`` is a Clerk panel in caption
mode: no conversation and no AI, just Markdown in which gene names, "cluster N" and
``[text](view:ID)`` are links. Clicking one shows it in the linked widgets (colors
the cells by the gene, highlights the cluster, or opens the view or Snapshot), in the
browser, so captions work in saved notebooks and web pages too.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


#: What a caption's view may set, per widget (Clerk's cited-view settings).
def _view_keys() -> dict:
    from ..clerk.llm import VIEW_KEYS

    return VIEW_KEYS


def caption_view(view: Any) -> dict:
    """One caption view: Clerk-style settings, or a Snapshot (a saved view).

    Accepts ``{"caption": ..., "landscape": {...}, "clustergram": {...}}``, a
    captured snapshot dictionary (with ``"kind"``), a :class:`~celldega.viz.Snapshot`
    card, or ``{"snapshot": {kind: snapshot}}``.
    """
    from .snapshot_widget import Snapshot

    if isinstance(view, Snapshot):
        record = dict(view.view or {})
        if not record.get("kind"):
            raise ValueError("this Snapshot has no saved view to open")
        return {"caption": view.name or "", "snapshot": {record["kind"]: record}}
    if not isinstance(view, Mapping):
        raise TypeError("a caption view is a dict of settings or a Snapshot")
    view = dict(view)
    if view.get("kind") and view.get("state") is not None:
        return {"caption": view.get("description") or "", "snapshot": {view["kind"]: view}}
    if "snapshot" in view:
        snapshots = view["snapshot"]
        if not isinstance(snapshots, Mapping) or not snapshots:
            raise ValueError('"snapshot" must be {kind: saved view}')
        return {"caption": str(view.get("caption") or ""), "snapshot": dict(snapshots)}
    keys = _view_keys()
    unknown = sorted(set(view) - {"caption", *keys})
    if unknown:
        raise ValueError(f"unknown caption view setting(s): {unknown}")
    out: dict[str, Any] = {"caption": str(view.get("caption") or "")}
    for widget, allowed in keys.items():
        settings = view.get(widget)
        if settings is None:
            continue
        if not isinstance(settings, Mapping):
            raise ValueError(f"{widget} settings must be a dict")
        bad = sorted(set(settings) - set(allowed) - {"selection", "dendrogram"})
        if bad:
            raise ValueError(f"unknown {widget} setting(s): {bad}")
        out[widget] = dict(settings)
    return out


def caption(
    text: str,
    views: Mapping[str, Any] | None = None,
    *,
    landscape: Any = None,
    clustergram: Any = None,
    yearbook: Any = None,
    width: int = 0,
):
    """A caption under a figure: Markdown whose links show things in the figure.

    Gene names and "cluster N" in ``text`` become links, as in Clerk's answers, and
    ``[text](view:ID)`` links one of ``views``: settings to apply (e.g. ``{"landscape":
    {"zoom_to": {"clusters": ["16"]}}, "clustergram": {"matrix": "Neighborhood
    enrichment"}}``) or a Snapshot to open. No AI is involved.

    Args:
        text: The caption, in Markdown.
        views: ``{ID: view}`` (see :func:`caption_view`).
        landscape: The Landscape its links change.
        clustergram: The Clustergram its links change.
        yearbook: The Yearbook its links change.
        width: Width in pixels; ``0`` (default) fills the notebook's width.

    Returns:
        Clerk: A Clerk panel in caption mode; display it under the figure.

    Example::

        dega.viz.caption(
            "Cluster 20 cells express PODXL and NPHS2; they [sit with the podocytes "
            "of cluster 16](view:glom) in every glomerulus.",
            {"glom": {"landscape": {"zoom_to": {"clusters": ["16"]}, "clusters": ["16", "20"]},
                      "clustergram": {"matrix": "Neighborhood enrichment"}}},
            landscape=landscape, clustergram=cgm,
        )
    """
    from .widget import Clerk

    normalized = {str(key): caption_view(view) for key, view in (views or {}).items()}
    return Clerk(
        mode="caption",
        caption=str(text),
        caption_views=normalized,
        landscape=landscape,
        clustergram=clustergram,
        yearbook=yearbook,
        width=width,
    )
