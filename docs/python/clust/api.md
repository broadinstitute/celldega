# Clust Module API Reference

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
`rank_genes_groups` results for the RANK slider's marker views:

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

## Saving a clustered Matrix (experimental)

`write_zarr()` saves a clustered Matrix, including its dendrograms, views,
colors, attributes, and size matrix, as an AnnData Zarr store. `read_zarr()`
restores it without re-clustering, so it can go straight to a Clustergram:

```python
mat.cluster(view="rank_genes_groups")
mat.write_zarr("pbmc_markers.zarr")

cgm = dega.viz.Clustergram(matrix=dega.clust.Matrix.read_zarr("pbmc_markers.zarr"))
```

The store has the Clustergram's columns as observations and its rows as
variables, so `anndata.read_zarr` opens it too. Values are saved as float32 by
default; pass `dtype=None` to keep the Matrix's own precision. In a browser, the
JavaScript `matrix_from_zarr` renders the same store without Python.

::: celldega.clust
