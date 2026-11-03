# Landscape

`Landscape` displays spatial tissue data and **low dimensional embedding
landscapes**: UMAP embeddings and gene-expression XY plots. Spatial
Landscapes read DegaFiles, loading images, cell boundaries, and transcripts
as tiles. Single-cell Landscapes can read AnnData Zarr directly, fetching
expression one gene at a time in the browser.

See [File Formats](../getting-started/file_formats.md) for the storage layouts and
the division of work between Python and JavaScript.

## What it shows

- **Image**: the underlying microscopy image (e.g. H&E, DAPI), rendered as a
  zoomable tile pyramid, with per-channel visibility/contrast controls.
- **CELL**: cell centroids and, for spatial data, segmentation boundaries,
  colored by cluster/category (e.g. `obs["leiden"]`) or gene expression.
  The CELL slider controls centroid size; zero hides the centroids.
- **TRX**: individual transcript locations, colored by gene, with a size
  slider.
- **NBHD**: supplied neighborhoods or polygons drawn in spatial, UMAP, or
  XY coordinates, with controls for visibility and editing.
- A **gene search** box and a bar graph that summarizes the currently visible
  cells by category or gene, updated as you pan/zoom.
- Support for **multiple datasets** via a dropdown selector.

For 3D, orbit-camera views of a dataset (thick tissue, multi-slice
alignments, or precomputed neighborhoods), see
[CellCloud](cell-cloud.md) and [NeighborhoodCloud](neighborhood-cloud.md),
which replace `Landscape`'s older `technology="point-cloud"` /
`"neighborhood-cloud"` modes.

## Usage

### Spatial DegaFiles

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

### Single-cell AnnData Zarr

Prepare a CSC copy of a sparse expression layer so the browser can read
individual genes efficiently. The example uses raw counts:

```python
import zarr

adata.layers["counts_csc"] = adata.layers["counts"].tocsc()
adata.write_zarr("cells.zarr")
zarr.consolidate_metadata("cells.zarr")

landscape = dega.viz.Landscape(
    zarr_url="cells.zarr",
    zarr_layer="counts_csc",
    cluster_attr="cell_type",
    cell_attr=["cell_type", "sample_id"],
    nbhd_edit=True,
)
```

`zarr_url` accepts an HTTP(S) URL or a local store under the working
directory, which Python serves over HTTP. The browser loads metadata and
`obsm["X_umap"]` from the store, then reads requested genes with Zarrita.
This path defaults to `technology="Chromium"`. Dense or CSR expression
needs a CSC copy; `zarr_layer` selects it explicitly.

Optional `adata` supplies overriding cell metadata, cluster colors, and
UMAP positions; its cell IDs must match the store. Passing `adata` alone
does not supply the browser's expression data: use `base_url` or `zarr_url`.
See [AnnData Zarr storage](../getting-started/file_formats.md#anndata-zarr-for-a-single-cell-landscape)
for gene statistics, layer discovery, and format details.

### Add aligned H&E to spatial DegaFiles

After preparing a spatial dataset, add an H&E image using
`dega.pre.add_aligned_he("data/DegaFiles", "sample_he.ome.tif",
alignment="sample_he_imagealignment.csv")`. Reload Landscape to use the
Fluorescence/H&E selector; cells and transcripts share the same reference
coordinates on both backgrounds. An image already on the reference grid
does not need an alignment argument. See
[Add aligned H&E to DegaFiles](../python/aligned_he.md) for requirements
and the example notebook.

## Low dimensional embedding landscapes: UMAP and XY

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
polygons matching the current coordinate space are rendered. A fingerprint
of ordered cell IDs and coordinates/expression keeps saved gates tied to their
original data even if a local server URL changes. New names are
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
cell centers inside the viewport, as the spatial view does when zoomed in.
Points are sized in embedding units, so they grow as you zoom in. To send a
region's cells to Python (`get_selected_cells()`), draw an NBHD polygon around
them.

The gene bars follow the viewport too, and the **TRX** button shows what they
hold:

- **Blue**, every cell in view: the whole-dataset gene statistics.
- **Purple**, zoomed in: genes estimated from cell-type signatures (below).
- **Gray**, zoomed in without matching signatures: the whole-dataset genes.

For AnnData Zarr without `var["mean"]`, the whole-dataset ranking uses
detection fraction instead of mean expression.

TRX is an indicator in UMAP/XY; clicking it does not fetch expression or change
the estimate. Spatial TRX controls still show and hide transcripts.

To estimate expression in the viewport, give Landscape each cell type's mean
expression, as an AnnData with cell types as `obs_names` and genes as
`var_names`. Use `layers["counts"]` for mean raw counts per cell when the
Landscape colors cells from raw counts. An optional `log1p` layer can hold
mean log-normalized expression for z-scored Clustergram views. For a
cell-level AnnData with raw counts in `layers["counts"]` and log1p in `X`,
compute these means and pass them as `adata_sig`; they are sent with the widget:

```python
import scanpy as sc

signature = sc.get.aggregate(adata, by="cell_type", func="mean", layer="counts")
signature.layers["counts"] = signature.layers.pop("mean")
signature.layers["log1p"] = sc.get.aggregate(adata, by="cell_type", func="mean").layers["mean"]
signature.uns["viewport_signature"] = {
    "groupby": "cell_type",
    "layers": {"counts": "mean counts per cell", "log1p": "mean log1p counts per 10,000"},
}

landscape = dega.viz.Landscape(
    zarr_url="cells.zarr",
    cluster_attr="cell_type",
    adata_sig=signature,
    nbhd_edit=True,
)
```

Larger signatures (tens of MB, e.g. hundreds of cell types × the whole
transcriptome) are better saved as a separate AnnData Zarr and read by the
browser from `gene_signature_url`:

```python
import json
import zarr

signature.uns["viewport_signature"] = json.dumps(signature.uns["viewport_signature"])
signature.write_zarr("cell_type_signatures.zarr")
zarr.consolidate_metadata("cell_type_signatures.zarr")

landscape = dega.viz.Landscape(
    zarr_url="cells.zarr",
    cluster_attr="cell_type",
    gene_signature_url="cell_type_signatures.zarr",
)
```

Spatial DegaFiles need neither: their UMAP/XY views use `df_sig.parquet`, each
default cluster's mean counts per cell, while the Landscape shows those clusters.

Means must be finite and nonnegative. Signature Zarr stores require a dense
matrix; `adata_sig` also accepts sparse means, which Python converts to dense
values for transport. The estimate reads
`viewport_signature["layer"]` when set, else `layers["counts"]`, else `X`; other
units (e.g. mean log1p) work too, and are named in TRX's tooltip. Match the
layer to the expression that colors the cells (the Zarr store's `zarr_layer`).
When a dataset mixes UMI counts with read counts (e.g. 10x and Smart-seq2),
store library-size-normalized, log1p expression in the Zarr layer, as CELLxGENE
Explorer shows, and read the signatures' `log1p` layer
(`"layer": "log1p"`): raw read counts can be hundreds of times larger than UMI
counts and would set every gene's color scale. `groupby`
names the cell attribute the labels come from (default: `cluster_attr`). The estimated gene bars show
`sum(visible cell-type count × cell-type mean) / visible cell count` for up to
200 highest estimated genes. These composition estimates do not capture
variation within a cell type. Every visible cell must have a matching signature;
otherwise the gene bars keep the whole dataset (TRX gray) and TRX's tooltip
reports the coverage. No per-cell expression is
downloaded when the viewport changes. Gene coloring and XY axes still read
actual cell expression.

For exact expression of every gene, or a Clustergram, draw an NBHD and use the
matching cell-level AnnData in Python:

```python
selected = landscape.get_selected_cells(adata)
if selected.n_obs:
    mat = dega.clust.Matrix(selected)
    mat.filter("row", by="var", num=min(500, selected.n_vars))
    mat.cluster()
    cgm = dega.viz.Clustergram(matrix=mat)
```

For constructor arguments and Python selection methods, see the
[Viz Module API reference](../python/viz/api.md#landscape-data-sources-and-controls).
For independent browser rendering, see the
[JavaScript API](../javascript/api.md#visualizations-without-python-landscape-clustergram-and-link_models).

## Source code

- [Python Landscape widget](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/widget.py):
  constructor, AnnData metadata, signatures, and selection/neighborhood methods.
- [Browser initialization](https://github.com/broadinstitute/celldega/blob/main/js/celldega.js)
  and [Landscape renderer](https://github.com/broadinstitute/celldega/blob/main/js/viz/landscape_ist.js).
- [AnnData Zarr reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/anndata_zarr.js):
  metadata and CSC gene slices.
- [UMAP/XY layouts](https://github.com/broadinstitute/celldega/blob/main/js/umap/expression_scatter.js)
  and [neighborhood coordinate spaces](https://github.com/broadinstitute/celldega/blob/main/js/umap/embedding_gates.js).
- [Viewport summaries](https://github.com/broadinstitute/celldega/blob/main/js/umap/viewport_summary.js)
  and [signature readers](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/gene_signatures.js).
