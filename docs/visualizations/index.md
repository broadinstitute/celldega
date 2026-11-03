# Visualizations

Celldega's interactive views help you explore where cells are, how gene
expression varies, and which biological processes distinguish a group.
Use linked views to move between tissue context, expression patterns, and
gene-set interpretation.

For desktop viewing, try [Celldega-App](../getting-started/desktop-app.md),
with linked Landscape–Clustergram panels, Yearbook cell portraits, and saved
Clustergrams. [Download the latest build](https://github.com/broadinstitute/celldega-app/releases/latest)
or see the [desktop guide and screenshots](../getting-started/desktop-app.md).

!!! tip "Watch a linked-workflow tutorial"
    [Watch the narrated Landscape, Clustergram, and Enrich walkthrough](https://www.youtube.com/watch?v=IjGsIykVIUE)
    to see how the views work together on a Visium HD dataset.
    [Follow along in the notebook](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb).

## Spatial visualizations {#spatial}

Explore cells and neighborhoods in **physical space** (x/y, and sometimes z)
across a tissue section, or compare cells in a low dimensional embedding
landscape (UMAP/XY).

- **[Landscape](landscape.md)** — explore cells, transcripts, images, and
  neighborhoods over tissue, or switch to UMAP and gene-expression XY views.
- **[Yearbook](yearbook.md)** — compare a grid of individual cell portraits
  cropped from the same spatial dataset.
- **[CellCloud](cell-cloud.md)** — explore cell positions in 3D, including
  thick tissue and aligned serial sections.
- **[NeighborhoodCloud](neighborhood-cloud.md)** — explore tissue
  neighborhoods and their cells across slices in 3D.

## Data visualizations {#data}

Compare measured values across cells, clusters, neighborhoods, or samples.

- **[Clustergram](clustergram.md)** — find expression patterns in a clustered
  heatmap or dot plot, with dendrograms and gene/metadata labels.
- **[Composition](composition.md)** — compare category composition, such as
  cell-type proportions, across groups.

## Information visualization {#info}

Interpret the genes that distinguish a selected group.

- **[Enrich](enrich.md)** — explore gene-set enrichment against public
  libraries through Enrichr.

## Linked Visualization

Connect views of the same dataset to explore cell positions, expression
patterns, and gene-set enrichment together.

- **[Landscape–Clustergram–Enrich](landscape-clustergram-enrich.md)** — connect
  tissue or embedding views with expression patterns and gene-set interpretation.
- **[CellCloud–Clustergram](cell-cloud-clustergram.md)** — connect cells in 3D
  with expression patterns across cell groups.

Start with the [Gallery](../gallery/index.md) for interactive examples or the
[Example Notebooks](../examples/index.md) for complete workflows. Each
visualization's guide explains what it shows and how to create it; the
[Python API reference](../python/viz/api.md) covers constructor options and
notebook controls.
