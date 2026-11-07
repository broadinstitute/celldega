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

Reasoning effort is a separate setting (`"low"`, `"medium"`, `"high"`, `"xhigh"`,
`"max"`): higher effort is slower and uses more tokens. Both have pickers next to the
**Ask** button, or set them from Python:

```python
clerk.model = "opus"
clerk.effort = "high"
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

Clerk only sees the widgets you link. In the conversation, each question shows the
Landscape screenshot it was sent with and a "Sent with" line listing the rest, so you can
see exactly what Clerk received. If a linked widget doesn't reply (for example, it isn't
displayed), Clerk is told so and says it rather than guessing.

With a linked **Enrich** panel, each question carries the enrichment results on screen:
the library, input genes and their source, the top terms with combined score, adjusted
p-value, odds ratio and overlapping genes, the selected term, and the Enrichr link.
Clerk then stops running its own Enrichr query.

With a linked **Clustergram**, each question also carries a snapshot of what the
Clustergram shows: the clusters and genes on screen (with their attributes, such as
`leiden`, `cell_type` or `leiden_marker`), each axis's order, the marker level (DIM
slider), the dendrogram groups at the current cut, the selection, and a capped table of
values and dot sizes for what's on screen. Genes you name in a question, or that Clerk
named in its previous answer, are added to that table when the Clustergram has them, so
"check MUC2 and TFF3 across clusters" works even if they're off screen. Choose what it
describes with
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

## How Clerk answers

Clerk is instructed to be brief (the answer first, then a few bullets of deciding
evidence) and conservative: before naming a cell type it checks each relevant cluster's
top ~25 ranked markers, canonical markers for the candidate type and its alternatives,
and enrichment in more than one library, and it states a confidence. It starts from
morphology and anatomy, treats the sample's diagnosis (e.g. "colorectal cancer") as a
description of the whole sample rather than of the region in view, and does not call a
region abnormal without evidence specific to that. The instructions are in
`celldega/clerk/prompts.py` (`dega.clerk.SYSTEM_PROMPT`).

## Lookups

While answering, Clerk can look things up without changing anything you see; each lookup
appears in the conversation as a "↻" line:

- **Ranked markers**: a cluster's top-N up-regulated genes (`rank_genes_groups`) with
  their value and dot size, whatever the DIM slider shows. The Matrix sends each
  cluster's ranked markers to the Clustergram front end for this.
- **Genes**: specific genes' values and dot sizes across all clusters.
- **Enrichr**: a cluster's top markers, or any gene list, against Enrichr libraries
  (`CellMarker_2024` and `PanglaoDB_Augmented_2021` by default). This calls the Enrichr
  web service directly; the Enrich panel is not changed.
- **PubMed**: literature searches through NCBI's public E-utilities (titles and abstract
  excerpts); Clerk cites PMIDs as links.

From Python, `cgm.request_state(markers={"clusters": ["4"], "n": 25})` reads the same
ranked markers, and `dega.clerk.lookups.enrichr(...)` / `dega.clerk.lookups.pubmed(...)`
run the web lookups.

## Recording cell types

When Clerk proposes cell types, it records them ("↻ Recorded tentative cell types: 4 →
Goblet cells (high), …"). Get them as a table or write them to an AnnData (cell-level, or
the cluster-level signature AnnData behind a Clustergram):

```python
clerk.findings_df()          # cluster, label, confidence, markers, notes, question, time
clerk.write_cell_types(adata, groupby="leiden", key="clerk_cell_type")
```

`write_cell_types` only adds a column (pass `overwrite=True` to replace one), fills
clusters without a proposal with `Unassigned`, and records the labels used in
`adata.uns["clerk_cell_types"]`.

## Letting Clerk change the views

Clerk can show you its evidence: highlight the clusters it is discussing in the
Landscape, color it by genes, zoom to a cluster, or move the Clustergram's DIM slider.
It uses the same setters you can call yourself (`landscape.apply_state`,
`cgm.apply_state`; see the [Landscape](../visualizations/landscape/index.md) and
[Clustergram](../visualizations/clustergram.md) pages), and each change appears in the
conversation as a "↻ Changed …" line. Cell types Clerk records are also written to the
Clustergram's manual column category (`clerk.label_clustergram = False` turns this
off); labels you set yourself are never overwritten.

Reading and changing are separate. Clerk can look up any gene in the Clustergram (values
and dot sizes across clusters) without changing what you see, even genes hidden by the
DIM slider or off screen; the browser holds the whole matrix, and DIM, crop and zoom only
filter what's displayed. Such lookups appear as "↻ Looked up EPCAM, PTPRC in the
Clustergram (view unchanged)".

Clerk can also change the linked Clustergram when you ask or when seeing it helps, for
example "show more marker genes" moves the DIM slider. It makes the change, looks at the updated view, and
continues its answer; the change appears in the conversation as a line such as
"↻ Changed the Clustergram: DIM -> 10 markers per cluster". Clerk makes at most
`clerk.max_action_rounds` (default 2) changes per question.

The same changes are available from Python:

```python
cgm.apply_state({"marker_level": 10})         # DIM slider; "all" for every row
cgm.apply_state({"mode": "dotplot", "size": "unit"})
cgm.apply_state({"focus_gene": "MUC2"})        # zoom to a gene, like the search box
```

More controls (order, dendrogram cut, crop, selection, zoom) will follow, so that every
control in the widgets can be driven from code or by Clerk.

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
