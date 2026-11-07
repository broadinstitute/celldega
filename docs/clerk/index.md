# Celldega Clerk

**Celldega Clerk** is an LLM assistant embedded in the Celldega widgets. It doesn't hand
down verdicts — it *gets* state from your other widgets, assembles the evidence, and
*makes a case* for a cell-type label (or answers a question) that **you** rule on. The
name reads as both a *law clerk* (gathers evidence, drafts the reasoning; the principal
decides) and a *bodega clerk* (fetches what you ask for).

It works like the [`Enrich`](../python/viz/api.md) widget, but instead of the Enrichr API
it talks to **Claude** via your local `claude` CLI.

## Requirements and logging in

Clerk sends your questions to Claude through the `claude` command-line tool (Claude
Code), running on the same machine as your kernel and using your own Claude account. You
need:

- **Claude Code installed** on the machine running the kernel; see the
  [setup guide](https://code.claude.com/docs/en/setup).
- **A Claude plan that includes Claude Code** (Pro or higher), or an Anthropic Console
  account billed per use. The free plan doesn't include Claude Code.

Log in once:

1. Open a terminal on the machine running the kernel (JupyterLab: *File → New →
   Terminal*; VS Code: *Terminal → New Terminal*).
2. Run `claude auth login` (add `--console` to use a Console account instead of a Claude
   plan).
3. Sign in on the page that opens. If no browser opens, open the link it prints, sign in,
   and paste the code it shows back into the terminal.

The CLI remembers the login (in the macOS keychain, or its own credentials file on
Linux), so no terminal needs to stay open afterwards. Celldega never sees or stores it.
If the kernel runs on a remote server (e.g. JupyterHub), log in from a terminal on that
server.

Check from Python, without calling the model:

```python
import celldega as dega

dega.clerk.claude_auth_status()
# {'logged_in': True, 'auth_method': 'claude.ai', 'subscription_type': 'pro'}
```

If you ask a question while logged out, Clerk replies with these instructions instead of
the CLI's raw error.

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

Each question also carries the recent conversation (the last 12 turns, about 3k tokens at
most), so follow-up questions keep their context. Questions run in the background: the
notebook stays usable while Clerk thinks.

Every call is isolated from your own Claude Code setup: Clerk uses its own system prompt,
no tools or MCP servers, none of your settings or hooks, and a throwaway working
directory, so no project `CLAUDE.md` or memory is picked up. Only the CLI login is
shared.

Pick a model by alias (`"opus"`, `"sonnet"`, `"haiku"`) or full id; a smaller model is
cheaper and faster for routine questions:

```python
clerk = dega.viz.Clerk(model="haiku")   # "" (default) inherits the CLI default
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
- each time you ask a question, the current **Landscape** view is captured and sent
  as image evidence, including the exact zoom/pan (see below). Pan and zoom, then ask
  "what's in this field of view?"

With a linked **Clustergram**, each question also carries a snapshot of what the
Clustergram shows: the clusters and genes on screen (with their attributes, such as
`leiden`, `cell_type` or `leiden_marker`), each axis's order, the marker level (DIM
slider), the dendrogram groups at the current cut, the selection, and a capped table of
values and dot sizes for what's on screen. Choose what it describes with
`clerk.clustergram_options`, e.g. `{"rows": "ranked", "max_rows": 25}` for the top of the
current order instead of what's on screen.

The same snapshot is available on its own:

```python
cgm.request_state()                       # rows/cols on screen
cgm.request_state(rows="ranked", cols=["4", "5"], max_rows=25)
# ...in a later cell, once the browser has replied:
cgm.latest_state                          # plain dict; never saved into the notebook
```

In JavaScript (e.g. a web app embedding Celldega), the Clustergram instance returned by
`matrix_viz` exposes the same snapshot synchronously as `matrix.get_state(options)`.

For a simple side-by-side layout of one Landscape + Clerk:

```python
dega.viz.landscape_clerk(landscape, clerk)
```

## Landscape raster capture (a reusable feature)

Clerk needed a screenshot, so `Landscape` gained a general screenshot API. Request a
capture; when the browser replies, the image and the exact view state are set on the
widget (in memory only — captures are never saved into the notebook):

```python
landscape.request_raster()      # asks the browser to snapshot the current view
# ...in a later cell, once the browser has replied:
landscape.raster_png            # base64 PNG (no data: prefix), longest side <= 1024 px
landscape.raster_thumb          # small preview
landscape.raster_view_state     # {"target": [...], "zoom": ..., ...} for reproducibility
```

The reply arrives asynchronously, so read these in a later cell or `observe` them; a
cell that requests a capture can't wait for it.

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
