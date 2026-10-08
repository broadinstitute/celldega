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

For a `SetCollection` signature, the main expression matrix and a same-shaped
size channel can be selected without creating a second signature modality:

```python
mat = dega.clust.Matrix(
    collection=setc,
    color_by="expression",
    size_by_layer="fraction_expressing",
)
mat.norm("row", by="zscore")
mat.cluster(view="rank_genes_groups", levels=[1, 3, 5, 10, 25, 50])
```

`cluster()` is the canonical clustering method and returns `self` for chaining.
It accepts one optional `view`; the full matrix remains available when reduced
views are precomputed. Use `cut_tree()` to turn either dendrogram into flat
labels, providing exactly one of `n_clusters` or `threshold`.

The older `clust()`, `views=`, `dot_plot`, `dot_mat`, `set_dot_matrix()`, and
`to_cluster()` interfaces are deprecated compatibility aliases. New code should
use `cluster()`, `view=`, `size_by_layer` / `size_matrix` /
`set_size_matrix()`, and `cut_tree()`.

::: celldega.clust
