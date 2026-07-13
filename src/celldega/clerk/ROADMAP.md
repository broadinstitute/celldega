# Celldega Clerk — roadmap

Clerk is the reasoning companion for the Celldega widgets. It doesn't hand down verdicts;
it *gets* state from the other widgets, assembles the evidence, and *makes a case* for a
label that the scientist rules on. The assembled case is a `CaseFile`.

This document tracks what's built (the POC) and what's sketched for later, so we can grow
it in small, reviewable steps. Two guiding principles:

1. **Widgets make each other better.** Every Clerk capability should land as a reusable
   Celldega API. Clerk needed a screenshot → `Landscape` gained `request_raster()` /
   `captureRaster()` (a general screenshot feature).
2. **Human-in-the-loop.** Clerk assembles and proposes; the scientist accepts/edits.

## Built (v1 POC)

- `dega.clerk` backend module: `ask` / `build_prompt` / `run_claude` / `claude_available`
  talking to the local `claude` CLI (kernel-side, no API key), single-shot, no tools.
  Text and inline-image (stream-json on stdin) modes.
- `dega.viz.Clerk` widget: free-form chat UI; evidence strip (gene chips + raster
  thumbnail); pre-gathers Enrichr terms via the existing Enrichr API.
- `Landscape` raster capture: `request_raster()` → `raster_png` (+ `raster_view_state`
  with the exact zoom/pan for reproducibility). `preserveDrawingBuffer` enabled on deck.
- `dega.clerk.CaseFile`: durable, JSON-serializable per-entity record — raw data /
  provenance, assumptions, evidence, reasoning (transcript), conclusions (label +
  accept/edit history). Keyed by **entity id**, not chat session. `save`/`load`.
- Linking helpers: `landscape_clerk` (portrait, single Landscape), `clustergram_clerk`,
  `landscape_yearbook_clustergram_clerk` (trio + wide Clerk bar below).
- `Clerk.to_casefile()` / `Clerk.load_casefile()` to snapshot/resume state.

## The vision: Clerk as a get/set hub across the widgets

Clerk builds the case by reading (and later writing) state across the full workspace
(Landscape + Clustergram + Enrich + Yearbook), with Clerk as a wide bar below.

| Widget      | Clerk GETS (evidence)                                   | Clerk SETS (actions)                                   |
|-------------|---------------------------------------------------------|--------------------------------------------------------|
| Clustergram | selected genes (DE / markers) for a cluster             | write proposed label to `manual_cat` (guided loop)     |
| Enrich      | already-computed enrichment terms (don't re-query)      | set `gene_list` to run enrichment for a selection      |
| Landscape   | raster PNG + view state (zoom/pan) as image evidence    | restore a saved `view_state` to reproduce a figure     |
| Yearbook    | representative-cell portraits / `dega.select` selection | drive `front_end_query` to pull portraits on demand    |

## Sketched (see `_sketches.py`) — build incrementally

- **Enrich → Clerk evidence sharing.** Read Enrich's computed terms instead of Clerk
  re-fetching Enrichr. Needs Enrich to expose its last results as a trait.
- **Guided one-at-a-time annotation.** Clerk proposes a label per cluster; accept/edit
  writes to `Clustergram.manual_cat` (the existing manual-category API).
- **Agentic view-fetching.** Clerk requests Yearbook portraits / Landscape close-ups when
  it needs more visual evidence, folding the returned rasters back into the CaseFile.
- **Docket.** A worklist/collection of open CaseFiles across clusters.
- **Interactive HTML report.** Render CaseFiles to a self-contained report bundling static
  rasters AND the JSON state (`dega.select` selection, Landscape view state) so views can
  re-hydrate. An expert reviews it to curate the cell typing.
- **Full workspace helper.** `Landscape + Clustergram + Enrich + Yearbook` linked, with a
  wide Clerk bar below (promote once the layout settles).
- **Stateful save/load of the whole session** (Docket of CaseFiles), beyond per-CaseFile
  JSON.

## CaseFile philosophy

A `CaseFile` is a **human-readable store of results and decisions**, not a serialization
of AI/model state. It holds the evidence, the reasoning as readable prose, and the
human's ruling -- the curated artifact an expert reviews and cites. It deliberately keeps
Claude/model internal state out (no session ids, raw `stream-json`, token scratchpad, or
conversation-resume blobs). Resuming a Claude conversation, if ever needed, is a separate
ephemeral concern. This keeps CaseFiles durable and reviewable even as the backend model
changes.

## Notes for building

- Cross-widget coordination is orchestrated in Python via `observe` (widgets can't call
  each other's JS). See existing helpers in `celldega/viz/__init__.py`.
- Keep the `claude` call single-shot / no-tools for predictability; Celldega pre-gathers
  evidence. Agentic tool use is a deliberate, later step.
- The `claude` CLI must be installed + authenticated once; no terminal session need be
  open while Clerk runs.
