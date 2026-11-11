# Clerk

!!! note "Experimental"
    Clerk is a proof of concept: its features and API may change between releases.

**Clerk** is Celldega's AI tool for exploring and interpreting its visualizations. It
isn't a separate service or an MCP server. It's a set of prompts, actions and light
interface components that let Anthropic's **Claude** read and drive the visualizations
you link to it (a Landscape, Clustergram or Enrich panel) and consult outside tools:
Enrichr for gene-set enrichment and PubMed for the literature.

Clerk gathers the evidence (marker genes, enrichment, literature, the tissue image) and
makes a case for a cell-type label, or answers your question, that **you** rule on. The
name reads as both a *law clerk* (gathers evidence and drafts the reasoning; you decide)
and a *bodega clerk* (fetches what you ask for).

Genes, clusters and cited views can be clicked to inspect the evidence in your widgets.
The conversation can be exported with screenshots, observed evidence and supported
replay settings. Full view restoration is not implemented yet. Clerk runs through your
own Claude account, using the `claude` command-line tool on the machine running your
notebook.

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

Each question also carries the recent conversation, so follow-up questions keep their
context: the last `clerk.history_questions` questions (default 10) with Clerk's replies
and actions, within `clerk.history_chars` characters (default 40,000, about 10k
tokens). It's sent once per question, so a longer memory costs little; screenshots and
lookup results from earlier questions aren't included, only the text. Questions run in
the background: the notebook stays usable while Clerk thinks.

## What Clerk knows

Clerk only knows what each question sends it, so you can tell where an answer came from:

- its instructions (`dega.clerk.SYSTEM_PROMPT`), whose examples use placeholders
  (cluster "A", GENE1) rather than real tissues or genes, so they can't hint at an
  answer;
- the evidence gathered for the question (the linked views, your gene list and
  context, and the lookups Clerk asks for);
- the recent conversation in this panel (see `history_questions` above). A new `Clerk`
  starts with none;
- a briefing, if you load one (below).

### Briefings: starting from earlier work

To give Clerk earlier conclusions to build on, load a briefing. It goes with every
question under "Earlier work", introduced as claims to check rather than evidence, and
the panel shows a "Briefing: …" line so it's always clear what Clerk was told:

```python
clerk.load_briefing("clerk_files/report_20261107-101500")  # an exported report folder
clerk.load_briefing("case1/record.json", "notes.md")     # several sources
clerk.load_briefing(other_clerk, append=True)            # another panel's conversation
clerk.load_briefing("celldega_files/screenshots")        # manual saved views
clerk.load_briefing("clerk_files/screenshots", append=True) # Clerk's saved views
clerk.briefing = "Cluster 7 looked mixed last time."     # or plain text
clerk.briefing = ""                                      # clear it
```

A record is summarized as each question with Clerk's final answer and the latest cell
types; screenshots and lookup results are left out. Exported reports show the briefing
Clerk was given. To carry over the visible conversation itself instead, copy it:
`clerk.messages = other_clerk.messages`.

Every call is isolated from your own Claude Code setup: Clerk uses its own system
prompt, no tools or MCP servers, none of your settings or hooks, the CLI's switches
that turn off memory and `CLAUDE.md` files, and a throwaway working directory. Nothing
from your other Claude Code sessions, memory or projects reaches it; only the CLI login
is shared. The CLI itself adds your account's email address and today's date to each
call.

The model's general training knowledge is the one thing you can't switch off. It may
know public datasets and papers, so for a fair test of Clerk's reasoning use
unpublished data, or leave dataset names out of `context_info`.

## Efficiency

Each question is one CLI session. The first call sends the evidence; each follow-up
round (after a lookup or a view change Clerk asked to see) resumes the session and
sends only what is new: the lookup results, any view that changed, and a screenshot
only if the view moved. The API caches the conversation so far, so a follow-up round
re-reads it at about a tenth of the price; in a test with a 34k-token prompt, a
follow-up cost $0.008 instead of $0.12. The CLI saves the session's transcript so it
can be resumed, and Clerk deletes it when the question is done.

Token use per question (and the CLI's cost estimate, which is notional on a Claude
plan) is recorded in `clerk.record[i]["usage"]` and shown in exported reports.

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

### Sidecar or wide

To lay Clerk out with the views, linked, pass it to `spatial_clustergram`. By default it
becomes a **sidecar**: a narrow column at the end of the row, the row's height, the way
an Enrich panel sits beside the Clustergram. `clerk_layout="wide"` puts it full width
under the row instead.

```python
dega.viz.spatial_clustergram(landscape, cgm, clerk=True)                 # sidecar
dega.viz.spatial_clustergram(landscape, cgm, enrich=True, clerk=True)    # with Enrich
dega.viz.spatial_clustergram(landscape, cgm, clerk=clerk, clerk_layout="wide")
```

`clerk=True` creates a Clerk (pass its options as `clerk_kwargs`), or pass one you made.
A sidecar sizes itself: it takes the room the row leaves, between 240 and 300 px, and
the Landscape, Clustergram and Enrich keep their full widths. A row wider than the
notebook scrolls sideways, with room under it for the scrollbar. A Clerk with its own
`width` keeps it. When the panel is narrow, the question box takes its own line, with
the model and effort pickers below.

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

Clerk is instructed to be very brief: the answer in a sentence or two, then an optional
**Evidence** list of at most five bullets, which the panel shows collapsed. It is also
conservative: before naming a cell type it checks each relevant cluster's top ~25 ranked
markers, canonical markers for the candidate type and its alternatives, and enrichment
in more than one library, and it states a confidence. It starts from morphology and
anatomy, treats the sample's diagnosis (e.g. "colorectal cancer") as a description of
the whole sample rather than of the region in view, does not call a region abnormal
without evidence specific to that, and says when a canonical marker isn't in the panel
(unmeasured is not absent). The instructions are in `celldega/clerk/prompts.py`
(`dega.clerk.SYSTEM_PROMPT`).

## The conversation panel

Each question is a collapsible turn:

- the question, with the Landscape screenshot and a "Sent with" line;
- **Work · N steps** (collapsed): the lookups and view changes Clerk made and any interim
  replies; open while Clerk is working;
- Clerk's answer, with its **Evidence** collapsed;
- Enrichr results, each folded under a title such as "Enrichr · Cluster 4 upregulated";
- what Clerk recorded or changed alongside the answer (one short ↻ line each, with the
  details, such as each cluster's cell type, in the turn's Evidence), and any errors.

Genes selected in the linked views still go with your next question. Enrichr results
appear in the conversation alongside Clerk's answer.

If the answer ends with a yes/no question ("Check cluster 7's top 25 markers?"),
**Yes** and **No** buttons answer it. **Expand** / **Collapse** open or close every turn,
work log and evidence section at once (handy before searching the page), and the panel
remembers the ones you opened or closed. **Write report** saves the conversation as a report
(see [Taking the record with you](#taking-the-record-with-you)).

## Evidence you can click

Everything Clerk cites can be replayed in the linked widgets, right away and even while
it's still answering:

- **Conversation images**: **Show this view** below a screenshot restores the
  Landscape and any Clustergram view captured with it. You can navigate elsewhere
  and use this link to revisit the image's state. **Back to your view** returns to
  where you were before following the link. These links are kept when saving and
  reopening the conversation; older images without a saved state have no link.
- **Genes** (blue, dotted underline): hover for the UniProt name and description, as in
  the other widgets; click to color the Landscape by the gene, mark it in the
  Clustergram (blue row label) and zoom the Clustergram to it. Shift-click adds or
  removes genes, to compare several; clicking the only gene shown again returns to
  cluster colors.
- **Clusters** ("cluster 4", "clusters 4, 5 and 12"): hover for the label you or Clerk
  gave it; click to highlight it in the Landscape, shift-click to add more.
- **Gene lists** in Clerk's work log ("Looked up 16 genes"): hover to list them, click
  to show them in the Landscape (up to 20).
- **Cited views** ("[Fig 1A]"): for a point that needs a particular view (a zoom, genes
  together, a marker level, a dendrogram group), Clerk defines the view and links it
  like a figure. Hover for its caption and what it shows; click to apply it to the
  Landscape and Clustergram. Nothing changes until you click. Genes and clusters named
  inside a cited view's link are still links of their own.
- **Dendrogram groups**: when Clerk discusses a group ("group 39"), it can cite a view
  that selects it again. The view keeps the dendrogram cut the group was seen at, so the
  group's name and members still match when you click it later.

Before the first link, Clerk saves the supported Landscape and Clustergram settings.
**Back to your view** reapplies them, including Clustergram pan/zoom, crop and order,
and Landscape layers, channels and sliders. See the remaining
[replay limitations](../../javascript/viz-api.md#replaying-supported-settings). In an exported
report, each cited view becomes a numbered figure under the answer with the
`apply_state` code that applies its settings, and the "[Fig 1A]" link jumps to it.
Cited views do not yet get their own rendered images on export.

Back now validates the saved view's data fingerprint and waits for browser completion.
If a dataset has changed or restoration fails, Clerk keeps the saved view for retry.
Within the same session it checks loaded data without re-downloading remote assets.
Conversation captures include portable snapshot envelopes, so reports can use
`restore_snapshot` when reopening evidence on compatible, freshly constructed widgets.
The [host contract](hosting.md) describes the widget-independent loop and celldega-app
integration points.

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

### Enrichr results in the conversation

Enrichr results are drawn in the conversation, under the answer, like the Enrich panel
and folded under a title ("Cluster 4 upregulated", "6 selected genes"): a library picker,
a scrolling bar graph of the top 20 terms by combined score, a paragraph of the genes
tested, and a **View full results on Enrichr** link to the same list on the Enrichr
website. Hover a bar for its statistics; click it to color the paragraph as Enrich does
(the term's genes blue, the rest dark gray) and show the term's genes on the Landscape
and Clustergram, and click again to clear. Picking another library asks Enrichr from
the browser. Genes in the paragraph work like Clerk's other gene links. This covers both
Clerk's own Enrichr lookups and the panel's Enrichr results for the selected genes,
shown once per gene list. The model reads the top 8 terms as text, with the Enrichr
link, which it can cite; the drawing is for you.

## Recording cell types

When Clerk proposes cell types (for example when you ask what a cluster might be), it
records them, together with the marker genes it relied on: "↻ Recorded tentative cell
types for 3 clusters", with each cluster's cell type in the turn's Evidence. With a
Clustergram linked, Clerk then asks **Label these clusters in the Clustergram
(cell_type)?**; **Label** makes the cell types tentative column labels (in the manual
column category, or `clerk_cell_type` if none is set up) and marks the marker genes with
their cell type on the rows (the manual row category, or `clerk_marker`), in the same
color as the column. If you asked Clerk to label the clusters, it labels them right
away. Labels you set yourself are never overwritten, and when Clerk relabels a cluster
it clears the marks it made for the old label. `clerk.label_clustergram = True` always
labels right away, and `False` never labels.

Get the cell types as a table or write them to an AnnData (cell-level, or the
cluster-level signature AnnData behind a Clustergram):

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
`cgm.apply_state`; see the [Landscape](../landscape/index.md) and
[Clustergram](../clustergram.md) pages), and each change appears in the
conversation as a "↻ Changed …" line. Cell types Clerk records can also be written to
the Clustergram's manual column category, when you accept its offer to (see
[Recording cell types](#recording-cell-types)); labels you set yourself are never
overwritten.

Reading and changing are separate. Clerk can look up any gene in the Clustergram (values
and dot sizes across clusters) without changing what you see, even genes hidden by the
DIM slider or off screen; the browser holds the whole matrix, and DIM, crop and zoom only
filter what's displayed. Such lookups appear as "↻ Looked up EPCAM, PTPRC in the
Clustergram (view unchanged)".

Clerk cites views rather than changing them (see above), and changes the linked views
directly only when you ask it to show something now, for example "show more marker
genes" moves the DIM slider. A view change ends Clerk's
reply, unless Clerk asked to look at the result and continue (`"continue": true` in its
actions); lookups always continue with their results. Lookup results add up over a
question, so Clerk remembers what it already checked, and an action identical to the
previous one is not repeated.

Each lookup or change is one round, and Clerk makes at most `clerk.max_action_rounds`
(default 6) per question. At that point it pauses with a **Continue** button rather
than stopping: click it to let Clerk carry on with a fresh budget, or ask something
else.

The same changes are available from Python:

```python
cgm.apply_state({"marker_level": 10})         # DIM slider; "all" for every row
cgm.apply_state({"mode": "dotplot", "size": "unit"})
cgm.apply_state({"focus_gene": "MUC2"})        # zoom to a gene, like the search box
cgm.apply_state({"order": {"row": "rank"}, "crop": {"col": ["4", "5"]}})
cgm.apply_state({"view": {"target": [250, 250], "zoom": [1, 2]}})
landscape.apply_state({"layers": {"image": True, "cells": False}})
```

Landscape also exposes image channels, layer sliders and the image source selector.
See [Viz API](../../javascript/viz-api.md) for the complete shapes. Dendrogram cut and
linked selections remain future controls.

For a simple side-by-side layout of one Landscape + Clerk:

```python
dega.viz.landscape_clerk(landscape, clerk)
```

## Landscape raster capture (a reusable feature)

Clerk needed to see the view, so `Landscape` gained a general raster capture: the
image alone, the first of the [three capture levels](../../javascript/saved-views.md#terms-and-scope)
(raster, saved view, screenshot). Request a capture; when the browser replies, the
image and the exact view state are set on the widget (in memory only — captures are
never saved into the notebook):

```python
landscape.request_raster()      # asks the browser to capture the current view
# ...in a later cell, once the browser has replied:
landscape.raster_png            # base64 PNG (no data: prefix), longest side <= 1024 px
landscape.raster_thumb          # small preview
landscape.raster_view_state     # {"target": [...], "zoom": ..., ...} for reproducibility
```

The reply arrives asynchronously, so read these in a later cell or `observe` them; a
cell that requests a capture can't wait for it.

## Screenshots

Ask Clerk to save evidence ("save a screenshot of this for the report") and it takes a
[screenshot with provenance](../index.md#screenshots) of the linked views,
after any change it makes for it, with its own description. They're written to
`clerk_files/screenshots/` (or `clerk.screenshot_dir`), marked as made by Clerk, listed
in `clerk.screenshots`, and recorded in the conversation. Manual exports from
**PIC** or `widget.screenshot()` default to `celldega_files/screenshots/`. Either
folder can be loaded as a briefing or configured to use a shared location.

## Taking the record with you

Clerk writes exported reports to `clerk_files/report_<time>/` and screenshots to
`clerk_files/screenshots/`; change the parent folder with `clerk.output_dir`.
Manual visualization exports use `celldega_files/screenshots/` and the widget's
`screenshot_dir`. Both default output directories are ignored by Git.

A law clerk who brings evidence also says how it was found and how to check it.
`clerk.export()` (or the panel's **Write report** button) writes the conversation to a folder.
The button opens an optional **Report name** field. The name becomes the report's
heading and its folder name, followed by a timestamp. Leave it blank to use
`report_<time>`.

```python
clerk.export("hcrc_clerk")                               # default: clerk_files/report_<time>
clerk.export("hcrc_clerk", adata=adata, groupby="leiden")  # also annotate an AnnData
clerk.export(title="Kidney exploration")                 # named report under clerk_files/
```

- `report.html`: the whole conversation as one self-contained page with static images.
  Each Landscape and Clustergram screenshot sits under code to replay its supported
  settings on widgets with the same data loaded, e.g.
  `landscape.apply_state({"space": "spatial", "view": {...}, "clusters": ["4"]})` and
  `cgm.apply_state({"marker_level": 25})`; Clerk's work and evidence are collapsed.
- `report.ipynb`: the same as a notebook, to re-run the reproduction code against your
  own widgets.
- `record.json` and `images/`: every question with its model, effort, what was sent,
  each step (lookups and their results, view changes, replies), each capture's observed
  evidence (`observations`), available widget sources and partial replay settings.
- `findings.csv`: the cell types Clerk proposed.
- With `adata=` and `groupby=`: the latest cell types written into
  `adata.obs["clerk_cell_type"]` (a column Clerk wrote earlier is replaced) and
  `cell_types.csv`; add `write_h5ad=True` to save the AnnData too.

The record is also available as `clerk.record` (a list of dicts, one per question). The
HTML needs `nbconvert`; without it the other files are still written.

### Saving and reopening a conversation

The panel's **Save** button (or `clerk.save_conversation()`) saves the conversation to
reopen later, the way PIC saves a view. It writes one JSON file to
`clerk_files/conversations/`, holding:

- the messages, with their gene, cluster and view links and Enrichr results;
- the record of each question, with the replay settings of its captures;
- Clerk's proposed cell types and the context;
- links to the data the linked widgets show.

Each question's screenshot preview is kept, but full-size captures are left out to keep
the file light; **Write report** keeps those.

**Open** (or `clerk.load_conversation(path)`) puts a saved conversation back in the
panel, replacing the current one. It also opens an exported report folder.

```python
saved = clerk.save_conversation(title="kidney walkthrough")
# ...later, in a notebook with the same data linked:
clerk.load_conversation(saved)          # or the panel's Open button
```

Reading a saved conversation needs no Claude, so it shows what a session looked like:
click through the genes, clusters and cited views (`[Fig 1A]`) and they change the linked
widgets, as they did when Clerk answered. The links need the same data loaded in those
widgets. A new question continues the conversation, with the loaded one as its history.

## Saved views, evidence and reports

The Viz API preserves an interactive observation as a versioned saved view. A saved
view becomes an **evidence artifact** when Clerk cites it to support or contradict a
claim. The report collects those artifacts with questions, lookups, reasoning and
findings; that organization belongs to Clerk, not the visualization API.

Use `clerk.export(...)` and `clerk.load_briefing(...)` to save and reuse this record.
Manual exports use the same underlying saved-view contract without constructing a
Clerk. See [portable saved views](../../javascript/saved-views.md).

## Roadmap

Planned next steps include a one-click "label my clusters" pass (evidence gathered by
code, one model call), counting the cell types in view at mid zoom without loading
transcripts, Yearbook portraits on request, and running Clerk on the Claude Agent SDK
so lookups are real tools. See `celldega/clerk/ROADMAP.md` for the full plan.
