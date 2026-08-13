# Clustergram

`Clustergram` is a hierarchically clustered heatmap for a matrix (e.g. genes
by cells, or genes by clusters) — the data-visualization counterpart to the
spatial views, for inspecting expression patterns directly rather than their
tissue location.

## What it shows

- A **matrix view**: rows and columns rendered as a dot-matrix (dot size/color
  encodes value) or a filled tile, toggled with the `TILE: prop/unit` and
  composition `prop/counts` controls.
- **Dendrograms** on both axes, with sliders to change the linkage-distance
  cutoff used to cut the tree into clusters.
- **Reorder controls** for both axes (`clust`, `sum`, `var`, `ini`) to
  resort rows/columns by clustering order, summed value, variance, or the
  original input order.
- Category bar graphs shown alongside a dendrogram when its cut point is
  clicked.

For comparing category composition (e.g. cell-type proportions) across
groups instead of a general heatmap, see [Composition](composition.md), a
`Clustergram` variant purpose-built for that comparison.

## Usage

`Clustergram` is built from a clustered `celldega.clust.Matrix`:

```python
import celldega as dega

mat = dega.clust.Matrix(adata, filter_genes=5000)
mat.cluster()

cgm = dega.viz.Clustergram(matrix=mat)
cgm
```

`Clustergram` can also be linked to a spatial view (`Landscape`, `CellCloud`,
or `NeighborhoodCloud`) so that selecting rows/columns highlights the
corresponding cells spatially — see
[`dega.viz.spatial_clustergram`](../python/viz/api.md).
For the full constructor options (including the more efficient
`parquet_data` path via
[`Matrix.export_viz_parquet`](../python/clust/api.md#celldega.clust.matrix.Matrix.export_viz_parquet)),
see the [Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
