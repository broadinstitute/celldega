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

For the full list of constructor arguments (multi-dataset support, point-cloud
options, `AnnData` integration, etc.), see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
