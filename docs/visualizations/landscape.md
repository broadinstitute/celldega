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
UMAP's second coordinate increases upward, matching the usual AnnData/Scanpy
orientation. XY's expression Y axis also increases upward.

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
XY retain their scaled display coordinates, with Y increasing downward in
the stored geometry. UMAP records `axes.y.reversed=True` because increasing
`X_umap[:, 1]` is displayed upward. Matching saved UMAP polygons from the
previous orientation migrate automatically; cell IDs remain unchanged.
Filter to the appropriate space before
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

## Viewport cell types and estimated expression

Panning or zooming in UMAP or XY updates the cell-type bars with counts of all
cell centers inside the viewport. **Select cells in view** sends those cell IDs
to `get_selected_cells()` for Python analysis or a cell-level Clustergram.
It does not dim the view. NBHD polygons remain an option for a custom boundary.
Without a signature store, the gene bars retain the labeled whole-dataset
summary.

To estimate gene expression locally, supply a separate signature AnnData Zarr:

```python
import json
import scanpy as sc
import zarr

# adata.X should contain the expression you want to summarize, before z-scoring.
signature = sc.get.aggregate(adata, by="cell_type", func="mean")
signature.X = signature.layers["mean"]
signature.uns["viewport_signature"] = json.dumps({
    "groupby": "cell_type",
    "units": "mean log1p counts per 10,000",  # match your preprocessing
})
signature.write_zarr("cell_type_signatures.zarr")
zarr.consolidate_metadata("cell_type_signatures.zarr")

landscape = dega.viz.Landscape(
    zarr_url="cells.zarr",
    cluster_attr="cell_type",
    gene_signature_url="cell_type_signatures.zarr",
    nbhd_edit=True,
)
```

The signature store has cell-type labels as `obs_names`, gene names as
`var_names`, and a dense, finite, nonnegative `X`. The **Estimated genes** bars
show `sum(visible cell-type count × cell-type mean) / visible cell count`, using
the signature's units and up to 200 highest estimated genes. These composition
estimates do not capture variation within a cell type. Every visible cell must
have a matching signature; otherwise the panel reports the coverage instead.
No per-cell expression is downloaded when the viewport changes. Gene coloring
and XY axes still read actual cell expression.

For exact expression or a Clustergram, select a viewport or NBHD and use the
matching cell-level AnnData in Python:

```python
selected = landscape.get_selected_cells(adata)
if selected.n_obs:
    mat = dega.clust.Matrix(selected)
    mat.filter("row", by="var", num=min(500, selected.n_vars))
    mat.cluster()
    cgm = dega.viz.Clustergram(matrix=mat)
```

For the full list of constructor arguments (multi-dataset support, point-cloud
options, `AnnData` integration, etc.), see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
