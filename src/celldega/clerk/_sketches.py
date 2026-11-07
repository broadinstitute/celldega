"""SKETCHES -- not wired up. Scaffolding for the next Clerk features.

These are intentionally unimplemented stubs (they raise ``NotImplementedError``) that
capture the *intended* signatures and behavior for the roadmap items in ``ROADMAP.md``.
They are NOT imported by the package; promote a sketch to a real module/function when we
build that step. Keeping them here means the design is legible and reviewable without
committing to full implementations up front.

Clerk builds a "case" by getting (and later setting) state across the workspace widgets:
Landscape + Clustergram + Enrich + Yearbook.
"""

from __future__ import annotations


# --- Enrich -> Clerk evidence sharing --------------------------------------
def enrich_terms_from_widget(enrich) -> list[dict]:
    """Read Enrich's *already-computed* enrichment terms so Clerk needn't re-query Enrichr.

    Requires Enrich to expose its last results (e.g. a synced ``last_results`` trait:
    ``[{"name", "score", "genes"}, ...]``). Then ``landscape_yearbook_clustergram_clerk``
    would prefer these over Clerk's own Enrichr fetch. Widgets making each other better.
    """
    raise NotImplementedError("Sketch: expose Enrich results as a trait, then map them.")


# --- Guided one-at-a-time annotation (Clerk SETS Clustergram) --------------
def apply_label_to_clustergram(cgm, entity_id: str, label: str, attr: str = "manual_cat"):
    """Write an accepted cell-type label for one cluster into the Clustergram.

    Reuses the existing manual-category machinery: ``Clustergram.manual_cat`` is a JSON
    string keyed by column/entity. Parse it, set ``{entity_id: label}`` under ``attr``,
    and reassign so the frontend re-renders. This is the write-back for the guided loop
    (propose -> human accept/edit -> Clustergram updates), one entity at a time.
    """
    raise NotImplementedError("Sketch: json-load manual_cat, set entity->label, reassign.")


# --- Agentic view-fetching (Clerk SETS Yearbook / Landscape) ---------------
def request_yearbook_portraits(yearbook, cluster_attr: str, cluster_value: str):
    """Drive a Yearbook to show portraits for a cluster, to gather visual evidence.

    Sets ``yearbook.front_end_query = {"cluster": {"attr": cluster_attr,
    "value": cluster_value}}`` (see ``landscape_yearbook``). A later step captures the
    Yearbook raster back into the CaseFile as additional evidence.
    """
    raise NotImplementedError("Sketch: set yearbook.front_end_query for the cluster.")


def restore_landscape_view(landscape, view_state: dict) -> None:
    """Restore a saved Landscape view state (zoom/pan) to reproduce a figure.

    The inverse of raster capture: push ``view_state`` (recorded in
    ``CaseFile.provenance['landscape_view_state']``) back onto the Landscape so a saved
    case renders the exact same view.
    """
    raise NotImplementedError("Sketch: set landscape initial view / view_state trait.")


# --- Docket: a worklist/collection of CaseFiles ----------------------------
class Docket:
    """A collection of open ``CaseFile`` objects across clusters (a clerk's docket).

    Keyed by ``entity_id`` so re-clustering/reloads stay coherent. JSON-serializable like
    ``CaseFile`` (a list/dict of CaseFile dicts). Would offer: ``add``, ``get``,
    ``open`` (status == "open"), ``accepted``, ``save``, ``load``, and iteration for the
    guided annotation loop.
    """

    def __init__(self, casefiles=None):
        raise NotImplementedError("Sketch: dict[entity_id -> CaseFile] + save/load.")


# --- Interactive HTML report ------------------------------------------------
def casefiles_to_html(casefiles, path) -> None:
    """Render CaseFiles into a self-contained interactive HTML report.

    Bundles per-case: the static raster, the reasoning transcript, the proposed/final
    label, and the JSON state that produced the views (``dega.select`` selection for
    Yearbook, Landscape ``view_state``) so views can re-hydrate interactively. Intended
    as the methods-section / expert-review artifact.
    """
    raise NotImplementedError("Sketch: template CaseFile dicts + embedded state JSON.")


# --- Full workspace layout (all four widgets + Clerk below) ----------------
def workspace(landscape, cgm, enrich, yearbook, clerk):
    """Compose the full workspace: Landscape + Clustergram + Enrich + Yearbook, with a
    wide Clerk bar below acting as the reasoning hub.

    Would reuse the existing linking helpers (``landscape_clustergram`` with ``enrich``,
    ``landscape_yearbook``) and wire every widget's state into Clerk (genes from
    Clustergram, terms from Enrich, raster+view from Landscape, portraits from Yearbook).
    Promote from sketch once the arrangement settles.
    """
    raise NotImplementedError("Sketch: link the four widgets, feed all state to Clerk.")
