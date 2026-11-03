# Landscape–Clustergram–Enrich

Link a [Landscape](landscape.md), [Clustergram](clustergram.md), and
[Enrich](enrich.md) to move between cell positions, expression patterns,
and the biological functions associated with a gene set.

Landscape provides the tissue or UMAP/XY context. Clustergram organizes
expression across genes and cell groups. Enrich helps interpret a selected
group of genes through gene-set enrichment.

## What you can explore

- Locate the cells expressing a gene selected in the Clustergram.
- Select a cell group in the Clustergram and inspect its distribution
  in tissue or an embedding.
- Select a gene group, explore its enriched terms, and focus on individual
  genes across the linked views.

## Before you start

Use a cell-level AnnData, `adata`, with prepared, nonnegative expression in
`adata.X` and cell labels in `adata.obs["leiden"]`. Its `obs_names` must match
the cell IDs in the Landscape's DegaFiles.

The example summarizes cells into Leiden groups using `celldega[scanpy]`.
Use the same grouping for Matrix's `groupby` and Landscape's `cluster_attr`.
For a different annotation, replace `"leiden"` with its column name in both
places. See [installation](../getting-started/installation.md) for the optional
Scanpy dependency.

## Usage

Prepare a clustered expression summary, then create and link the views:

```python
import celldega as dega

mat = dega.clust.Matrix(adata, groupby="leiden")
mat.filter("row", by="var", num=min(500, adata.n_vars))
mat.norm("row", by="zscore")
mat.cluster()

landscape = dega.viz.Landscape(
    base_url="https://your-data-host/DegaFiles",
    adata=adata,
    cluster_attr="leiden",
)
cgm = dega.viz.Clustergram(matrix=mat, name="landscape_clusters")

linked = dega.viz.spatial_clustergram(landscape, cgm, enrich=True)
linked
```

Replace `base_url` with your hosted DegaFiles URL. The Matrix has genes as
rows and Leiden groups as columns. Its color values are row-z-scored group
means; dot sizes are the fraction of cells expressing each gene.
See [Clustergram advanced usage](clustergram.md#advanced-usage) for marker
ranking, different feature views, and saving the clustered Matrix.

`spatial_clustergram` places the views side by side.
`enrich=True` creates Enrich and connects it to the other two widgets.

## Try the linked selections

1. **Click a gene in the Clustergram.** Landscape colors cells by that
   gene's expression, so you can inspect its location in tissue or UMAP/XY.
2. **Select a cell group in the Clustergram.** Landscape highlights the
   corresponding cells using the shared cell annotation.
3. **Select a gene group with the row dendrogram.** Enrich updates its
   gene-set query and shows enriched terms from the selected library.
4. **Select an enriched term.** Its associated genes are highlighted in the
   Clustergram.
5. **Click a gene in Enrich.** The Clustergram focuses that gene and Landscape
   colors cells by its expression.

A focused gene and the enrichment gene set are kept separate: inspecting one
gene does not replace the multi-gene enrichment query. Use the
[Enrich guide](enrich.md) for library selection and result interpretation.

## Examples and reference

- [Visium HD notebook](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb):
  a complete spatial Landscape–Clustergram–Enrich workflow.
- [Narrated walkthrough](../getting-started/index.md#video-tutorial):
  watch the linked spatial workflow.
- [Chromium PBMC notebook](../examples/tutorial_notebooks/Scanpy_Chromium.ipynb):
  single-cell UMAP Landscapes linked to Clustergrams and enrichment.
- [Python linking API](../python/viz/api.md#celldega.viz.spatial_clustergram):
  layout and enrichment options.
- [CellCloud–Clustergram](cell-cloud-clustergram.md):
  the same linking approach for cells in 3D.

Source: [linking helpers](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/__init__.py).
