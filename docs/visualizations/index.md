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
| 1 | View and image | **SPATIAL**, **UMAP**, and **XY** switch between tissue, embedding, and two-gene views (UMAP appears when the data include an embedding). **IMG** shows or hides the image; each channel button toggles that channel, and its slider sets the channel's brightness. |
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
