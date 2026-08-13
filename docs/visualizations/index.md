# Visualizations

Celldega ships interactive visualizations, grouped into three kinds:

## Spatial

Render directly in geographic (x/y, and sometimes z) space over a tissue
section, using deck.gl for GPU-accelerated rendering of large point/polygon
datasets.

- **[Landscape](landscape.md)** — the main spatial view: cells, transcripts,
  images, and neighborhoods over a tissue section.
- **[Yearbook](yearbook.md)** — a grid of per-cell spatial "portraits" cropped
  from the same underlying LandscapeFiles.
- **[CellCloud](cell-cloud.md)** — a 3D orbit-camera view of cell centroids,
  for thick tissue or multi-slice alignments.
- **[NeighborhoodCloud](neighborhood-cloud.md)** — a 3D orbit-camera view of
  precomputed tissue neighborhoods.

## Data

Render a dataset's values directly, independent of spatial position.

- **[Clustergram](clustergram.md)** — a hierarchically clustered heatmap
  (dendrograms, reorderable rows/columns) over a matrix (e.g. genes by cells
  or genes by clusters).
- **[Composition](composition.md)** — a `Clustergram` variant comparing
  category composition (e.g. cell-type proportions) across groups.

## Info

Summarize or look up information about a gene list rather than rendering a
dataset's cells or matrix directly.

- **[Enrich](enrich.md)** — gene set enrichment analysis against public
  libraries (via the [Enrichr](https://maayanlab.cloud/Enrichr/) API).

!!! note
    Screenshots and example videos for each visualization are coming soon.
    For now, each page below documents what the visualization shows and how
    to create it; see the [Example Notebooks](../examples/index.md) and
    [Gallery](../gallery/index.md) for runnable demos.
