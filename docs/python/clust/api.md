# Clust Module API Reference

For complete workflows, see the
[Chromium PBMC notebook](../../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)
and [Atera breast cancer notebook](../../examples/tutorial_notebooks/Atera_Breast_Cancer_Landscape-Clustergram.ipynb).
The [Clustergram guide](../../visualizations/clustergram.md#advanced-usage)
explains marker dot plots and precomputed views.

`Matrix` preserves supplied values during construction. For general standalone
datasets, filtering and normalization are explicit operations, so the data
transformations remain visible in the notebook:

```python
import celldega as dega

mat = dega.clust.Matrix(adata)
mat.filter("row", by="var", num=5000)
mat.norm("col", by="total")
mat.norm("row", by="zscore")
mat.cluster()
```

For a marker-gene dot plot, pass a cell-level `AnnData` with `groupby`. Matrix
aggregates the cells with `scanpy.get.aggregate` (mean expression drives
color, the fraction of cells expressing drives dot size) and reuses scanpy's
`rank_genes_groups` results for the DIM slider's marker views:

```python
import scanpy as sc

sc.tl.rank_genes_groups(adata, groupby="leiden")
mat = dega.clust.Matrix(adata, groupby="leiden")
mat.norm("row", by="zscore")
mat.cluster(view="rank_genes_groups", levels=[1, 3, 5, 10, 25, 50])
cgm = dega.viz.Clustergram(matrix=mat)
```

Pass `rank_genes_groups=True` (or a dict of `sc.tl.rank_genes_groups` keyword
arguments) to compute the ranks on the fly, and `layer=` to aggregate a layer
instead of `X`. The same `groupby` path works for samples or any other cell
grouping.

With whole-transcriptome data, consider dropping genes that almost no cells
detect before the row z-score. The z-score measures how specific a gene is to
a cluster, not how many cells express it, so a gene detected in a single cell
of a single cluster gets the same top value as a real marker and can crowd the
full-gene view. `filter_by_size()` keeps rows whose size (here, the fraction
of cells expressing) reaches a threshold in at least one column:

```python
mat = dega.clust.Matrix(adata, groupby="leiden")
mat.filter_by_size(0.05)  # detected in at least 5% of some cluster's cells
mat.norm("row", by="zscore")
```

Precomputed modalities in a `MuData` can drive color and size directly:

```python
mat = dega.clust.Matrix(mdata=mdata, color_by="expression", size_by="fraction")
```

`cluster()` is the canonical clustering method and returns `self` for chaining.
It accepts one optional `view`; the full matrix remains available when reduced
views are precomputed. Use `cut_tree()` to turn either dendrogram into flat
labels, providing exactly one of `n_clusters` or `threshold`.

The older `clust()`, `views=`, `dot_plot`, `dot_mat`, `set_dot_matrix()`, and
`to_cluster()` interfaces are deprecated compatibility aliases. New code should
use `cluster()`, `view=`, `size_by_layer` / `size_matrix` /
`set_size_matrix()`, and `cut_tree()`.

## Saving Matrix inputs and clustered objects

### Before clustering

Save the analysis AnnData to preserve its values, metadata, layers, and
analysis annotations, then construct a Matrix after loading:

```python
import anndata as ad

adata.write_zarr("matrix_input.zarr")
mat = dega.clust.Matrix(ad.read_zarr("matrix_input.zarr"))
```

`mat.to_adata().write_zarr("matrix_values.zarr")` also saves an unclustered
Matrix's current values and row/column metadata. This conversion does not
include its size matrix, colors, axis entities, marker rankings, or
clustering/view state. Keep the input AnnData if those analysis inputs need
to be preserved.

### After clustering (experimental)

Call `cluster()` before `write_zarr()` to save the complete clustered Matrix:

```python
mat.cluster()
mat.write_zarr("clustered_matrix.zarr")

restored = dega.clust.Matrix.read_zarr("clustered_matrix.zarr")
cgm = dega.viz.Clustergram(matrix=restored)
```

The store preserves:

- Values and the optional dot-size matrix.
- Row and column metadata.
- Dendrogram orders and linkages.
- Precomputed views.
- Colors, visualization settings, axis entities, and marker rankings when present.

`read_zarr()` restores these without reclustering or repeating normalization.
It requires a store written with the clustered Matrix schema; for an
ordinary AnnData store use `Matrix(anndata.read_zarr(...))` instead.
`to_clustered_adata()` and `from_clustered_adata()` provide the complete
conversion in memory.

The store has the Clustergram's columns as observations and its rows as
variables. Values are saved as float32 by default; `dtype=None` keeps their
existing precision. `zarr_format=3` is the default; version 2 is also supported.
`Matrix.read_zarr()` can read local or HTTP(S) stores, loading the saved matrix
into memory.

In a browser, `clustergram(el, {url})` or `matrix_from_zarr(el, {url})` renders
the same clustered store without Python; `network_from_zarr(url)` returns its
network. See [File Formats](../../getting-started/file_formats.md#anndata-zarr-before-and-after-matrix-clustering)
for the AnnData schema and [JavaScript API](../../javascript/api.md) for rendering.

Source: [Matrix conversions and persistence](https://github.com/broadinstitute/celldega/blob/main/src/celldega/clust/matrix.py)
and [browser Matrix reader](https://github.com/broadinstitute/celldega/blob/main/js/read_zarr/network_from_zarr.js).

::: celldega.clust
