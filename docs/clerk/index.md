# Celldega Clerk

**Celldega Clerk** is an LLM assistant embedded in the Celldega widgets. It doesn't hand
down verdicts — it *gets* state from your other widgets, assembles the evidence, and
*makes a case* for a cell-type label (or answers a question) that **you** rule on. The
name reads as both a *law clerk* (gathers evidence, drafts the reasoning; the principal
decides) and a *bodega clerk* (fetches what you ask for).

It works like the [`Enrich`](../python/viz/api.md) widget, but instead of the Enrichr API
it talks to **Claude** via your local `claude` CLI.

## Requirements

Clerk shells out to the `claude` CLI from the kernel — no API key, no browser calls.

- Install and authenticate **Claude Code** once (run `claude` in a terminal and log in).
  After that, Clerk works without any terminal session open.
- Check availability from Python:

```python
import celldega as dega

dega.clerk.claude_available()   # True if the `claude` CLI is on PATH
```

## Quickstart (standalone)

Ask a question directly, passing whatever evidence you have:

```python
import celldega as dega

answer = dega.clerk.ask(
    "What cell type is this cluster?",
    gene_list=["CD3D", "CD8A", "CD2", "TRAC"],
    info="Cluster 5, Xenium human lung",
)
print(answer)
```

Or use the widget for an interactive chat panel:

```python
clerk = dega.viz.Clerk(gene_list=["CD3D", "CD8A", "CD2", "TRAC"])
clerk
```

Clerk pre-gathers **Enrichr** enrichment terms for the gene list (reusing Celldega's
existing Enrichr integration) and folds them into the prompt as evidence — the model
itself uses no tools, so results are fast and predictable.

Pick a cheaper/faster model for routine annotation:

```python
clerk = dega.viz.Clerk(model="claude-haiku-4-5")   # "" (default) inherits the CLI default
```

## Linking to other widgets

Clerk is **standalone and wide by default**, and you link it to whatever widgets you
have — they can live in other notebook cells. Widgets are modular and swappable; the
usual case is Landscape + Clustergram (optionally Enrich). Link from the constructor:

```python
landscape = dega.viz.Landscape(base_url="...", adata=adata)
cgm       = dega.viz.Clustergram(adata=adata)

clerk = dega.viz.Clerk(landscape=landscape, clustergram=cgm)
clerk   # display the wide Clerk panel wherever you like
```

or after the fact with `link_clerk`:

```python
clerk = dega.viz.Clerk()
dega.viz.link_clerk(clerk, landscape=landscape, clustergram=cgm)
```

Once linked:

- selecting a cluster/gene set in the **Clustergram** flows the genes into
  `clerk.gene_list`;
- the current **Landscape** view is captured as a raster and rides along as image
  evidence — including the exact zoom/pan (see below).

For a simple side-by-side layout of one Landscape + Clerk:

```python
dega.viz.landscape_clerk(landscape, clerk)
```

## Landscape raster capture (a reusable feature)

Clerk needed a screenshot, so `Landscape` gained a general screenshot API. Request a
capture; the base64 PNG (and the exact view state) are written back to traits:

```python
landscape.request_raster()      # asks the browser to snapshot the deck.gl canvas
landscape.raster_png            # base64 PNG (no data: prefix), kept in memory
landscape.raster_view_state     # {"target": [...], "zoom": ..., ...} for reproducibility
```

## CaseFile: durable, savable state

A `CaseFile` is the record of the "case" Clerk builds for one biological entity — keyed
by the **entity id** (e.g. a cluster), not the chat session, so it survives re-clustering
and reloads. It captures the full argument: raw data / provenance, assumptions, evidence,
reasoning (transcript), and conclusions (proposed/final label + accept-edit history), and
serializes to JSON.

```python
# snapshot the current Clerk state into a CaseFile for cluster "5"
cf = clerk.to_casefile(entity_id="5", entity_attr="leiden", dataset="xenium_lung")
cf.propose("CD8+ T cell").accept()      # you rule on the label
cf.save("casefile_5.json")

# later — pick the case back up
cf = dega.clerk.CaseFile.load("casefile_5.json")
clerk.load_casefile(cf)
```

## Roadmap

Clerk is intentionally a light proof-of-concept. Planned, incremental features (with code
sketches in `celldega/clerk/_sketches.py`):

- reuse Enrich's already-computed terms instead of re-querying Enrichr;
- guided one-at-a-time annotation writing labels back to the Clustergram;
- agentic view-fetching (pull Yearbook portraits / Landscape close-ups on demand);
- a `Docket` of open CaseFiles and an interactive HTML report for expert review.

See `celldega/clerk/ROADMAP.md` for the full plan.
