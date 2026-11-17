# Visualizations

Celldega's interactive views help you explore where cells are, how gene
expression varies, and which biological processes distinguish a group.
Use linked views to move between tissue context, expression patterns, and
gene-set interpretation.

For desktop viewing, try [Celldega-App](../getting-started/desktop-app.md),
with linked Landscape–Clustergram panels, Yearbook cell portraits, and saved
Clustergrams. [Download the latest build](https://github.com/broadinstitute/celldega-app/releases/latest)
or see the [desktop guide and screenshots](../getting-started/desktop-app.md).

## Video tutorial

This narrated walkthrough links a Landscape, Clustergram, and Enrich to explore
a Visium HD human colorectal cancer dataset. Follow along in the
[Visium HD Human CRC Landscape-Clustergram-Enrich](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb)
notebook.

<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;">
    <iframe src="https://www.youtube.com/embed/IjGsIykVIUE" title="Landscape, Clustergram, and Enrich tutorial in Celldega" loading="lazy" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe>
</div>

## Spatial visualizations {#spatial}

Explore cells and neighborhoods in **physical space** (x/y, and sometimes z)
across a tissue section, or compare cells in a low dimensional embedding
landscape (UMAP/XY).

- **[Landscape](landscape/index.md)**: Where are cell types in the tissue, and
  which cells express a gene? Explore cells, transcripts, images, and
  neighborhoods over tissue, or switch to UMAP and gene-expression XY views.
- **[Yearbook](yearbook.md)**: What do individual cells look like? Compare a
  grid of cell portraits, each centered on one cell from the same spatial
  dataset, and mark cells for review.
- **[CellCloud](cell-cloud.md)**: How are cells arranged in 3D? Explore thick
  tissue and aligned serial sections.
- **[NeighborhoodCloud](neighborhood-cloud.md)**: How do tissue neighborhoods
  extend across slices? Explore neighborhoods and their cells in 3D.

## Data visualizations {#data}

Compare measured values across cells, clusters, neighborhoods, or samples.

- **[Clustergram](clustergram.md)**: Which genes distinguish each cell group,
  and which groups are most alike? Find expression patterns in a clustered
  heatmap or dot plot, with dendrograms and gene/metadata labels.
- **[Composition](composition.md)**: How do cell-type proportions differ
  across samples, regions, or neighborhoods?

## Information visualization {#info}

Interpret the genes that distinguish a selected group.

- **[Enrich](enrich.md)**: Which biological processes or cell types are
  associated with a set of genes? Explore gene-set enrichment against public
  libraries through Enrichr.

## Linked Visualization

Connect views of the same dataset to explore cell positions, expression
patterns, and gene-set enrichment together.

- **[Landscape–Clustergram–Enrich](landscape-clustergram-enrich.md)**: connect
  tissue or embedding views with expression patterns and gene-set interpretation.
- **[CellCloud–Clustergram](cell-cloud-clustergram.md)**: connect cells in 3D
  with expression patterns across cell groups.

Start with the [Gallery](../gallery/index.md) for interactive examples or the
[Example Notebooks](../examples/index.md) for complete workflows. Each
visualization's guide explains what it shows and how to create it; the
[Python API reference](../python/viz/api.md) covers constructor options and
notebook controls.

## The control panel

Landscape, Yearbook, CellCloud, and NeighborhoodCloud share a control panel above
the view. Clustergram, Composition, and Enrich have their own panels, described on
their pages.

[![Landscape control panel above a kidney tissue view, with numbered callouts](../assets/img/visualizations/index/control_panel.webp)](../assets/img/visualizations/index/control_panel.webp)

*The Landscape control panel over a whole-transcriptome kidney section, showing
glomeruli and tubules. Cells are colored by cluster over the DAPI, boundary, and
RNA image channels.*

| | Control | What it does |
| --- | --- | --- |
| 1 | View and image | The view menu switches between tissue (**SPATIAL**), embedding (**UMAP**, when the data include one), and two-gene (**XY**) views: it shows the current view, and its **▾** lists the others. **IMG** shows or hides the image; each channel button toggles that channel, and its slider sets the channel's brightness. **SNAP** saves a [Snapshot with a memo](#snapshots), and **PINS** shows [pinned Snapshots](#pins-points-of-interest) on the tissue (it appears when there are pins). |
| 2 | **CELL** | Shows or hides the cells; the slider sets their size. The bars rank cell clusters by count: click a bar to select that cluster, and shift-click to add more. |
| 3 | **TRX** | Transcripts and gene expression. Zoomed in, TRX shows or hides individual transcripts and the slider sets their size; zoomed out, the slider sets how strongly cells are colored by a selected gene. The bars rank genes: click one to color cells by its expression. |
| 4 | **NBHD** | Neighborhoods: shows supplied tissue regions, or lets you draw your own. Appears only when neighborhoods are supplied or drawing is turned on. |
| 5 | Gene search | Type one or more gene names, separated by commas, to color cells by expression; clear the box to return to cluster colors. The box below describes the selected gene, from UniProt. |
| 6 | Celldega logo | Opens this visualization's documentation page. |
| 7 | The view | Scroll to zoom, drag to pan, hover over cells and transcripts for details, and click a cell to select its cluster. |

Conventions shared across visualizations:

- **Blue** button text means on; **gray** means off. A faded button is not
  available at the current zoom.
- Scrolling over a Landscape, CellCloud, or Clustergram zooms it instead of
  scrolling the page. Move the pointer off the visualization to scroll the page.
- Hovering shows details in a tooltip, without changing the selection;
  clicking selects. For genes, hovering shows a brief UniProt description and
  clicking shows it in the gene information box.
- The **Celldega logo** in every control panel links to that visualization's
  page in this documentation.

## Two ways to use a visualization

Each visualization, such as a Landscape or a Clustergram, runs in your web
browser. You can use it in two ways:

```text
 Notebook widget (Jupyter or marimo)      JavaScript on a web page
┌────────────────────────────────────┐   ┌────────────────────────────────────┐
│ Python kernel                      │   │ Gallery, standalone web page,      │
│   AnnData, Matrix, your analysis   │   │ or notebook report (no Python)     │
│     │ options        ▲ selections, │   │                                    │
│     ▼ and data       │ drawings    │   │                                    │
│ Browser                            │   │ Browser                            │
│   Landscape ◄─link─► Clustergram   │   │   Landscape ◄─link─► Clustergram   │
└────────────────────────────────────┘   └────────────────────────────────────┘
                   ▲                                        ▲
                   └───────────────────┬────────────────────┘
                                       │
           prepared data (DegaFiles or AnnData Zarr), read over HTTP
```

- **As a notebook widget with a Python back-end.** Create the visualization
  from your analysis in Jupyter or [marimo](https://marimo.io/). The Python
  back-end makes the widget stateful: selections, drawn neighborhoods, and
  annotations are available to your analysis, and Python can update the view.
  Links between widgets, such as a Clustergram click coloring a Landscape, run in
  the browser through the widget framework (`jslink`).

  You can also embed visualizations in notebook **reports**: static HTML pages
  made from pre-executed notebooks saved with their widget state. The
  visualizations and their links stay interactive in the report, without a
  running kernel. The [Example Notebooks](../examples/index.md) on this site are
  shown this way.
- **As JavaScript on a web page, without Python.** The [Gallery](../gallery/index.md)
  pages, standalone pages built with the [JavaScript API](../javascript/index.md),
  and notebook reports all run the same visualizations in the browser. Every
  interaction and browser link works; there is no Python back-end to receive
  selections or annotations.

Each visualization's page describes its interactions, which are the same in
both cases, and then what the widget's Python back-end adds.

## Reading and driving visualizations from code

Every visualization can be read and changed from code as well as by clicking: getters
report what it shows, setters change it as its controls would, and exporters capture it
as an image. The same keys work in Python (`widget.request_state()`,
`widget.apply_state()`, `widget.snapshot()`) and JavaScript; see the
[Viz API](../javascript/viz-api.md).

## Snapshots {#snapshots}

<span id="screenshots"></span>

**Snapshot** is Celldega's name for a captured visualization that combines three parts:

- **Screenshot**: a raster image of what the visualization showed at capture time.
- **Memo**: a description of what you noticed and why it matters, supplied through
  `description`.
- **Reproducibility metadata**: the data source and identity, supported view settings,
  observed state, author, capture time and renderer version needed to interpret the
  observation and revisit its view.

The screenshot is the visual component of a Snapshot. The complete artifact keeps
that image together with its explanation and context. Like **Landscape**, **Snapshot**
names a specific Celldega concept. Its goal is to **preserve an interactive observation
as reproducible visual evidence**.

Think of a Snapshot as a postcard: a picture of a place in your data, with an
explanation of why it matters and a way to return. The in-memory capture and its PNG
export are both Snapshots. Python saves a PNG and a human-readable Markdown companion:

- `<name>.png`: the image, with your description, who made it and when, the Celldega version, each
  widget's saved view (`snapshot`, with its replay settings in `snapshot.state`), its
  observed state (`observed_state`), what was in view (cell counts per cluster, top
  genes), and the data it came from (dataset name, base URL or AnnData Zarr URL,
  AnnData shape, the Matrix's source) embedded in its metadata;
- `<name>.md`: the description, the image, provenance and code to reopen the view.

The PNG alone carries the saved view; the Markdown companion is for readers and is
not needed for replay.

### Why Snapshots: annotating what you find

Celldega already lets you annotate a dataset's molecular side: label clusters with
cell types, group genes, and draw neighborhoods around regions of tissue. Much of
what you notice while exploring is a particular view, though: a ring of cells around
a structure, two genes that meet at a boundary, an odd patch at one zoom level. A
drawn region doesn't capture that well, and an ordinary screenshot loses it: the
image keeps no record of the dataset, the settings, or how to get back to it.

Snapshots are annotations of that kind. Each one keeps the view's spatial evidence,
your explanation, and the settings to reopen it, inside the PNG itself, so the context
travels with the image. You can take them yourself with **SNAP**, and
[Clerk](clerk/index.md) takes them while it explores. Put together, they make
something you can share instead of a narrated screen recording:

- a notebook of free text and Snapshot cards, each card linked to a live
  visualization so clicking it opens that view;
- a Landscape with [pins](#pins-points-of-interest) marking points of interest, each
  pin opening the Snapshot behind it.

The spatial evidence then sits beside the molecular annotations, such as cell type
labels and marker genes, in a form a collaborator can open and check.

The idea isn't limited to tissue. Pins also go on a UMAP, so a single-cell dataset
(an AnnData Zarr in a Landscape) can be an annotated embedding. Snapshots of a
Clustergram or a Yearbook have no map to pin to, but make the same cards: a heatmap
view, or a page of cells, with your notes and a link back.

The saved view records what data it shows (cell, gene and cluster names, or a
Clustergram's row and column names). Image and state are captured together.
`widget.restore_snapshot(...)` checks the schema, data identity and canvas size
before changing the view; see [Portable Snapshots](../javascript/saved-views.md)
for reopening exports and declaring an exact data revision.

Records are marked `restoration: "partial"`. They preserve the image and provenance,
and `from_png` can load a recorded source into a fresh widget, but not every control
is restored. See
[replay coverage and limitations](../javascript/viz-api.md#replaying-supported-settings).

Save one from a widget's control panel with **SNAP**: it captures the view, then asks
for a name and a memo of what you're looking at and why it's interesting. Or
from Python, on a Landscape, Clustergram, Yearbook, CellCloud or NeighborhoodCloud. In a web
page without a notebook kernel, SNAP downloads a PNG with the replay state and
description embedded:

```python
landscape.snapshot(
    name="Glomerulus",
    description="Podocyte-like cells ring each glomerulus; the ring breaks where ...",
    path="figures/",            # a folder, or a file like "figures/fig2a.png"
)
# A linked row (or several widgets) becomes one image, side by side:
dega.viz.snapshot(linked, description="...", path="figures/fig2.png")
```

The image arrives from the browser after the cell finishes, so the call's output shows
"Capturing…" and then a preview with the saved path. Without a path, Snapshots go to
`celldega_files/snapshots/` (or `widget.snapshot_dir`). This export directory can be
kept out of version control or shared as a collection of evidence. Areas the
visualization leaves empty are white, so the image looks the same in light and dark
viewers; pass `background="black"` (any CSS color) or `background=None` for
transparency.

The PNG records links, not data: a widget's `base_url` or `zarr_url`, and a Matrix's
Zarr source when it was opened with `Matrix.read_zarr`, plus constructor options. An
object passed in memory, such as `adata=adata` or a Matrix built in the notebook, has
no path to record (`read_h5ad` keeps none). The PNG stores its shape and marks it as
needed again when reopening. The whole record is typically a few KB.

Record what Python can't see, such as the AnnData file a widget was made from, once per
widget; it's added to every Snapshot of it, including SNAP ones. This is a note for
readers: reopening still needs the object passed back.

```python
landscape.snapshot_metadata = {"adata": "data/kidney.h5ad", "notebook": "review.ipynb"}
```

Reopen the image as an interactive visualization:

```python
view = dega.viz.from_png("figures/fig2a.png")
display(view)
# In a later cell: None while pending, else applied/apply_error.
view.get_apply_result(view.apply_request_id)
```

The original data must still be available. Supply `matrix=mat` or `adata=adata`
when the original view used an in-memory object; constructor options can point to
a relocated source. For a composite Snapshot, `panel=1` opens the second widget.
Use `widget.restore_png(path)` to restore into a widget that already has its data.
See [Portable Snapshots](../javascript/saved-views.md#reopen-a-png-as-an-interactive-visualization)
for browser usage, validation and restoration limits.

Inspect the embedded record with `dega.viz.load_snapshot(path)` and discover a
folder's PNG records with `dega.viz.load_snapshots(folder)`. A folder of Snapshots
works as a scrapbook of what you found along the way, reusable by people and
application agents: [Clerk](clerk/index.md) can read it as a briefing or add
its own.

### Postcards in a notebook

Saving with **SNAP** or `widget.snapshot(name="...")` also adds the capture to the
viewer's `snap` dictionary. Names are preserved exactly; repeated names receive
` (2)`, ` (3)`, etc. Use `list(landscape.snap)` to see them. The collection is local
to that Python instance; the PNG and Markdown files persist on disk.

After the capture finishes, display a postcard in a later notebook cell:

```python
from celldega.viz import Snapshot

Snapshot(landscape=landscape, snapshot="Glomerulus")
```

The card shows a static PNG, its name and memo. **Snapshot metadata** expands the
provenance and replay settings. The blue **Show this view** link restores the linked
viewer and reports any failure. Several cards can point to the same viewer; place
them between Markdown cells to explain an analysis step by step.

```python
# A file is also usable after restarting the kernel; link the newly displayed viewer.
Snapshot("figures/glomerulus.png", landscape=landscape)
Snapshot(clustergram=cgm, snapshot="Markers")
Snapshot(yearbook=yb, snapshot="Interesting cells")

# An unlinked postcard, including an ordinary PNG with your own caption:
Snapshot("figures/overview.png", name="Overview", description="Start here.")
# Or the in-memory image and state from request_snapshot():
Snapshot(landscape.latest_snapshot, landscape=landscape)
```

Cards embed their PNG and text in notebook widget state and do not load the dataset
or visualization renderer. Save notebook widget state to keep them when sharing a
notebook. Navigation needs a live kernel and the linked viewer displayed. Ordinary
PNGs have no replay metadata, so they show no navigation link. For a composite PNG,
`panel=1` chooses the second viewer's state; the card still displays the composite.

Navigation accepts a different viewer size by default (`allow_resize=False` requires
the original size), but always checks data identity. Yearbook Snapshots preserve the
actual ordered cells, page, zoom, checked cells, colors and supported layer controls;
the grid layout must match. The original data must remain available.

### Pins: points of interest

Snapshots can also annotate the tissue itself, like pins on a map of places you've
been, each with a photo and a postcard about it. Give a Landscape a collection of
Snapshots and each one becomes a pin at the center of its view. **PINS** shows or
hides them; hovering a pin shows its Snapshot's name and memo, and clicking it opens
its view. Where drawn neighborhoods outline regions, pins mark points of interest
with whatever explanation you write, for your future self or a collaborator.

```python
poi = dega.viz.Snapshots(landscape.snap)          # the Snapshots you saved with SNAP
poi = dega.viz.Snapshots("celldega_files/snapshots")  # or every Snapshot PNG in a folder
poi = dega.viz.Snapshots(["glomerulus.png", "medulla.png"])  # or chosen files

landscape.pins = poi
landscape.show_pins = True  # or press PINS

# Pins can also be pre-loaded when the Landscape is created:
landscape = dega.viz.Landscape(base_url=..., snapshots=poi, show_pins=True)
```

`Snapshots` is a small named collection (`poi.names()`, `poi["Glomerulus"]`,
`poi.add(path, name=...)`, and `poi.card("Glomerulus", landscape=landscape)` for a
postcard chosen by name). While shown, the pins are also listed by name in place of
the image controls; click one to open its view. Snapshots of other data than the
Landscape's are skipped, with a warning. A pin sits in the space its Snapshot shows,
the tissue or the UMAP, and appears while the Landscape shows that space; the list
names them all and marks those in the other space, which opening switches to. XY
Snapshots aren't pinned (their axes depend on the genes chosen), and Clustergram and
Yearbook Snapshots are shown as cards instead. Pins live in
the widget's state, so opening one works in a saved notebook or static page without a
kernel. In JavaScript, pass `pins` (or `pin_data`) and `show_pins` to
`celldega.landscape(el, {...})`: each pin is `{name, description, target: [x, y],
space, snapshot}`, with `space` `"spatial"` (the default) or `"umap"`.

The former `screenshot()`, `load_screenshot()`, `load_screenshots()`,
`screenshot_dir` and `screenshot_metadata` spellings remain compatibility aliases.
