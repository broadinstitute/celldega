# Landscape

`Landscape` is Celldega's main spatial visualization: an interactive,
deck.gl-powered view of a tissue section that scales to datasets with
hundreds of millions of transcripts by loading data as vector tiles instead
of all at once.

## What it shows

- **Image**: the underlying microscopy image (e.g. H&E, DAPI), rendered as a
  zoomable tile pyramid, with per-channel visibility/contrast controls.
- **CELL**: cell segmentation boundaries, colored by cluster/category (e.g. a
  `leiden` column from an `AnnData`) or by gene expression, with a size
  slider.
- **TRX**: individual transcript locations, colored by gene, with a size
  slider.
- **NBHD**: tissue neighborhoods (alpha-shape or hextile regions), toggled
  on/off with their own opacity control.
- A **gene search** box and a bar graph that summarizes the currently visible
  cells by category or gene, updated as you pan/zoom.
- Support for **multiple datasets** via a dropdown selector.

For 3D, orbit-camera views of a dataset (thick tissue, multi-slice
alignments, or precomputed neighborhoods), see
[CellCloud](cell-cloud.md) and [NeighborhoodCloud](neighborhood-cloud.md),
which replace `Landscape`'s older `technology="point-cloud"` /
`"neighborhood-cloud"` modes.

## Usage

```python
import celldega as dega

landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    adata=adata,
    ini_zoom=-5,
)
landscape
```

`Landscape` can also be linked to a `Clustergram` so that selections in one
update the other — see [`dega.viz.spatial_clustergram`](../python/viz/api.md).

## Cell attributes and population selection

Pass the observation columns you want to explore through `cell_attr`. The
**CELL** dropdown switches the active color attribute; `color_by` chooses its
initial value and can also be changed from Python. Keep `cluster_attr` set to
the attribute used by a linked Clustergram's columns.

```python
landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    adata=adata,
    cluster_attr="leiden",
    cell_attr=["leiden", "cell_type", "total_counts", "cell_area"],
    color_by="leiden",
)
landscape.color_by = "total_counts"
```

Categorical attributes use population bars that update with the viewport.
Click a bar to select a category; Shift-click bars to add or remove categories.
Shift-clicking cells or their outlines supports the same category selection.
Numerical attributes use a continuous color legend with a fixed global range;
missing and non-finite values are gray, and zero remains a valid value. Gene
expression coloring remains available through gene search and linked widgets.

See the [linked pancreas notebook](../examples/brief_notebooks/Scatter_Pancreas_Linked.ipynb)
for Scatter gates and Clustergram selections highlighted in Landscape.

For the full list of constructor arguments (multi-dataset support, point-cloud
options, `AnnData` integration, etc.), see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
