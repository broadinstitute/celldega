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

## Spatial, UMAP, and gene-expression views

**XY** plots two genes' expression for every cell, with **LIN** and **LOG**
(`log1p`) scaling. It is available for spatial and non-spatial datasets with
gene expression, even without a UMAP. The X/Y gene inputs replace the image
controls while XY is active; **SPATIAL** restores the tissue view and image
controls. **UMAP** is shown only when an embedding is supplied.

XY uses the same expression reader as gene coloring: spatial datasets read
DegaFiles, and non-spatial datasets can read DegaFiles or AnnData Zarr.

```python
landscape.set_xy("CD3D", "MS4A1", scale="log1p")
landscape.landscape_state = "spatial"  # or "umap" when available
```

With `nbhd_edit=True`, drawn neighborhoods belong to the view in which they
were created. An XY neighborhood also records its genes and scale. Only
polygons matching the current coordinate space are rendered. New names are
unique across spaces (for example, `nbhd_spatial_1`, `nbhd_umap_1`, and
`nbhd_xy_1`); the editor also checks custom names for duplicates.

`landscape.nbhd` contains neighborhoods from **all** spaces, as does
`landscape.nbhd_polygons`. Both include `space`, `coordinate_space`, geometry,
and `x`/`y` vertex rings; drawn neighborhoods also include `cell_ids` and
`cell_count`. Spatial geometry uses native tissue coordinates, while UMAP and
XY retain their embedding coordinates. Filter to the appropriate space before
calculating physical areas or distances:

```python
tissue_nbhds = landscape.nbhd.loc[landscape.nbhd["space"] == "spatial"]
landscape.save_nbhds("neighborhoods.geojson")
landscape.load_nbhds("neighborhoods.geojson")
landscape.select_nbhd("nbhd_xy_1")  # restores its axes and selects its cells
```

You can also pass `nbhd=landscape.nbhd` into another Landscape of the same
dataset. Spatial polygons are transformed for the tissue image; embedding
polygons retain their saved coordinate-space metadata and render only in the
matching view.

For the full list of constructor arguments (multi-dataset support, point-cloud
options, `AnnData` integration, etc.), see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
