# Clustergram

`Clustergram` uses **hierarchical bi-clustering** to organize both axes of a
high-dimensional matrix: genes/features by their expression patterns, and
cells, clusters, neighborhoods, or samples by their similarity. The heatmap
or dot plot makes these relationships visible alongside dendrograms.

For single-cell expression, a common workflow starts by identifying cell
groups with tools such as
[Scanpy's Leiden clustering](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.leiden.html).
Celldega can summarize expression within those groups, then hierarchically
cluster the genes and groups to explore marker programs and relationships
between cell populations.

## What it shows

- A **heatmap or dot plot** of matrix values, with gene and metadata labels.
- **Row and column dendrograms** for exploring groups of similar features
  and observations.
- **Ordering controls** for clustering order (`clust`), summed value (`sum`),
  variance (`var`), or original order (`ini`).
- **Precomputed views** that focus on marker genes or highly ranked features.
- Linked selections that color or highlight cells in a Landscape and send
  gene sets to Enrich.

For stacked cell-type proportions across groups, use
[Composition](composition.md).

## Usage

This example assumes that `adata.X` already contains prepared expression
values. Filtering and normalization are explicit:

```python
import celldega as dega

mat = dega.clust.Matrix(adata)
mat.filter("row", by="var", num=min(5000, adata.n_vars))
mat.norm("row", by="zscore")
mat.cluster()

cgm = dega.viz.Clustergram(matrix=mat)
cgm
```

Row z-scoring emphasizes each gene's relative expression across the columns.
For large single-cell datasets, summarize cells into groups as below before
hierarchically clustering the columns.

## Controls

- **COL / ROW ordering** changes the display order on each axis.
- **Dendrogram sliders** change the cut height used to define groups. A
  temporary tree preview and blue cut indicator show which branches merge;
  release the slider or press Escape to dismiss the preview.
- **DIM** appears when the Matrix has precomputed views. Its readout shows
  the ranking used: **RANK**, **VAR**, **SUM**, or **MEAN**.
- **TILE prop/unit**, available for dot plots, switches between proportional
  sizes and full-size tiles while retaining expression coloring.

## Advanced usage

### A marker-gene dot plot after Leiden clustering

Assume that `adata.obs["leiden"]` holds the first-round cell labels and
`adata.X` contains nonnegative, log-normalized expression, before cell-level
z-scoring. This example requires `celldega[scanpy]`.

```python
import scanpy as sc
import celldega as dega

# Rank markers using the same expression values that will be summarized.
sc.tl.rank_genes_groups(adata, groupby="leiden", use_raw=False)

# Columns become Leiden groups; rows remain genes.
markers = dega.clust.Matrix(adata, groupby="leiden")
markers.filter_by_size(0.05)
markers.norm("row", by="zscore")
markers.cluster(
    view="rank_genes_groups",
    levels=[1, 3, 5, 10, 25],
)

dotplot = dega.viz.Clustergram(matrix=markers, rank_dim=5)
dotplot
```

Before row z-scoring, the color matrix is each group's mean expression.
Dot size is the fraction of its cells with expression greater than zero.
`filter_by_size(0.05)` keeps genes detected in at least 5% of cells in at least
one group; row z-scoring changes the color values while preserving those
fractions. A Matrix carrying size values opens as a dot plot automatically.

Matrix reuses matching `rank_genes_groups` results. Alternatively, pass
`rank_genes_groups=True` when constructing the Matrix to calculate missing
rankings. See Scanpy's
[marker-ranking documentation](https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.rank_genes_groups.html)
and [aggregation documentation](https://scanpy.readthedocs.io/en/stable/generated/scanpy.get.aggregate.html)
for the underlying operations.

### Generate views at different feature resolutions

`cluster(view=..., levels=...)` keeps the full matrix and precomputes
smaller feature sets. Each set is independently clustered on both axes, so
the column order can change as different gene programs come into focus.

| `view` | How rows are chosen | Meaning of a level |
| --- | --- | --- |
| `"rank_genes_groups"` | Union of each group's top-ranked marker genes | Markers per group |
| `"var"` | Highest row variance | Total rows |
| `"sum"` | Highest row sum | Total rows |
| `"mean"` | Highest row mean | Total rows |

In the dot-plot example, level 5 means up to five markers per Leiden group.
Shared markers are counted once, so the total displayed rows may be less
than `5 × number of groups`. The DIM slider switches among the computed
levels and **all**, which restores the full matrix.

Metric views also work without marker rankings, including bulk and other
high-dimensional data. For example, compare the most variable genes across
Leiden-group means:

```python
variable = dega.clust.Matrix(
    adata,
    groupby="leiden",
    rank_genes_groups=False,
)
variable.cluster(view="var", levels=[100, 500, 1000])

heatmap = dega.viz.Clustergram(
    matrix=variable,
    viz_mode="heatmap",
    rank_dim=500,
)
heatmap
```

Metric rankings use the Matrix's current values. Use un-z-scored normalized
values for variance views: row z-scoring makes row variances equal.
Choose levels smaller than the feature count. Levels that select the whole
matrix, too few rows, or duplicate another feature set are omitted.

One Matrix stores one view family at a time. Build separate Matrices to compare
marker-ranked and variance-ranked views. `rank_dim` chooses the initial level;
it does not compute a new view. The browser switches among precomputed levels.

### Save the clustered views

```python
markers.write_zarr("marker_dotplot.zarr")
restored = dega.clust.Matrix.read_zarr("marker_dotplot.zarr")
reopened = dega.viz.Clustergram(matrix=restored, rank_dim=5)
```

The store preserves values, optional dot sizes, metadata, dendrograms,
precomputed views, colors, and marker rankings. See
[Matrix storage](../python/clust/api.md#saving-matrix-inputs-and-clustered-objects)
for what is saved before and after clustering, and
[File Formats](../getting-started/file_formats.md#anndata-zarr-before-and-after-matrix-clustering)
for the AnnData Zarr schema and JavaScript readers.

## Linked views and examples

Link a Clustergram to a Landscape, CellCloud, or NeighborhoodCloud with
[`dega.viz.spatial_clustergram`](../python/viz/api.md). Gene clicks color cells
by expression, and group selections highlight their corresponding cells.

The [Chromium PBMC tutorial](../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)
demonstrates marker dot plots and saved Matrix stores. The
[Visium HD tutorial](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb)
demonstrates linked Landscape, Clustergram, and Enrich views.

For constructor options, see the [Viz API](../python/viz/api.md).
Source: [Matrix clustering and views](https://github.com/broadinstitute/celldega/blob/main/src/celldega/clust/matrix.py),
[Clustergram widget](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/widget.py),
and [browser view controls](https://github.com/broadinstitute/celldega/blob/main/js/ui/ui_containers.js).
