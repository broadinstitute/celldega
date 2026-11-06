# From Scanpy & Squidpy

If you already analyze single-cell or spatial data with
[Scanpy](https://scanpy.readthedocs.io/) and
[Squidpy](https://squidpy.readthedocs.io/), Celldega picks up where your
notebook leaves off. It reads the same AnnData: your clusters, colors, UMAP, and
expression. You explore them interactively, then bring selections and
annotations back into the AnnData for the next step of your analysis.

## What Celldega reads from your AnnData

| AnnData | Used for |
| --- | --- |
| `obs_names` | Cell IDs. For spatial data they must match the DegaFiles' cell IDs. |
| `obs["leiden"]`, or any categorical column | Cell colors and the CELL bars, chosen with `cluster_attr` |
| `uns["leiden_colors"]` | The cluster palette, as Scanpy stores it; a palette is generated if absent |
| Other `obs` columns | Extra cell attributes for tooltips and queries, chosen with `cell_attr` |
| `obsm["X_umap"]` | The UMAP view |
| `obsm["spatial"]` | Cell positions for neighborhood analysis and 3D CellClouds; a spatial Landscape takes positions from its DegaFiles |
| `X` or a layer | Expression for Clustergram summaries; a single-cell Landscape reads a CSC layer from AnnData Zarr |
| `var_names` | Gene names; human gene symbols also get UniProt descriptions |

## Choose a route

```text
 Is your data spatial?
   │
   ├─ Yes, and you have the instrument output (Xenium, MERSCOPE, Visium HD)
   │     └─► make DegaFiles, then Landscape(base_url=..., adata=adata)
   │
   ├─ Yes, but you only have an AnnData with obsm["spatial"]
   │     └─► write a point cloud, then CellCloud(zarr_url=...)
   │
   └─ No: single-cell RNA-seq
         └─► save AnnData Zarr with a CSC layer, then Landscape(zarr_url=...)
```

- **Spatial, with instrument output.** DegaFiles hold the images, cell
  boundaries, and transcripts that make a spatial Landscape, and your AnnData
  supplies the clusters, colors, and UMAP. Follow
  [Visualize Your Own Data](your-data.md).
- **Spatial, AnnData only.** Without the images and transcripts, a
  [CellCloud](../visualizations/cell-cloud.md) shows the cells as points,
  colored by cluster or gene. 2D coordinates work as a flat section:

    ```python
    dega.pre.write_point_cloud_zarr(adata, "cells.zarr", cluster_key="leiden")
    dega.viz.CellCloud(zarr_url="cells.zarr", cluster_attr="leiden")
    ```

- **Single-cell.** No preprocessing beyond a CSC copy of the expression. See
  [Single-cell Landscapes](../visualizations/landscape/index.md#single-cell-landscapes):

    ```python
    adata.layers["counts_csc"] = adata.layers["counts"].tocsc()
    adata.write_zarr("cells.zarr")
    dega.viz.Landscape(zarr_url="cells.zarr", zarr_layer="counts_csc", cluster_attr="leiden")
    ```

## Scanpy and Squidpy plots, interactively

| In Scanpy or Squidpy | In Celldega |
| --- | --- |
| `sc.pl.umap(adata, color="leiden")` | The Landscape's **UMAP** view, with clusters you can select |
| `sc.pl.umap(adata, color="CD3E")` | Gene search, or click a gene's bar; several genes are combined |
| `sq.pl.spatial_scatter(adata, color="leiden")` | The spatial Landscape: the same cells over the tissue image, down to transcripts |
| `sc.pl.rank_genes_groups_dotplot(adata)` | `Matrix(adata, groupby="leiden")` and a dot-plot Clustergram, with views at several numbers of markers |
| `sc.pl.matrixplot(adata, markers, groupby="leiden")` | A Clustergram heatmap: `Clustergram(matrix=mat, viz_mode="heatmap")` |
| `sc.tl.dendrogram(adata, groupby="leiden")` | Hierarchical clustering of both the groups and the genes |
| `sq.gr.nhood_enrichment(adata, cluster_key="leiden")` | A Clustergram of the enrichment z-scores (below) |
| Enrichment with gseapy or Enrichr | Enrich, linked to Clustergram selections |

For example, to explore Squidpy's neighborhood enrichment as a Clustergram:

```python
import pandas as pd
import squidpy as sq
import celldega as dega

sq.gr.nhood_enrichment(adata, cluster_key="leiden")
clusters = adata.obs["leiden"].cat.categories
zscore = pd.DataFrame(
    adata.uns["leiden_nhood_enrichment"]["zscore"], index=clusters, columns=clusters
)

mat = dega.clust.Matrix(zscore)
mat.cluster()
dega.viz.Clustergram(matrix=mat)
```

The [Scanpy–Squidpy Xenium pancreas tutorial](../examples/tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb)
links this Clustergram to a Landscape.

## Bring results back into your AnnData

The widgets share their state with Python, so what you select and draw becomes
part of your analysis:

```python
# Cells in the selected clusters or a drawn neighborhood
adata.obs["selected"] = adata.obs_names.isin(landscape.selected_cells)
subset = landscape.get_selected_cells(adata)

# Drawn neighborhoods, as a GeoDataFrame
landscape.nbhd

# Cells checked for review in a Yearbook
adata.obs["reviewed"] = adata.obs_names.isin(yearbook.selected_cells)

# Genes selected in a Clustergram, and clusters labeled in its category editor
cgm.selected_genes
cgm.manual_cat
```

See each visualization's "Python-backed interactions" section, for example
[Landscape](../visualizations/landscape/index.md#widget-python-backed-interactions)
and [Clustergram](../visualizations/clustergram.md#widget-python-backed-interactions).

## Plain objects or Collections

Celldega's analysis functions work on the objects you already use: AnnData,
pandas DataFrames, and GeoPandas GeoDataFrames. For example, summarize the cell
types in drawn neighborhoods and cluster the neighborhoods by composition.
Celldega is also developing **Collection** classes that keep related results
together, such as a neighborhood's geometry, its composition, its expression,
and which neighborhoods border each other. Both approaches give the same
results; use whichever fits your analysis.

=== "Plain objects"

    ```python
    gdf_nbhd = landscape.nbhd  # a GeoDataFrame

    composition = dega.nbhd.calc_nbhd_by_pop(adata, gdf_nbhd, category="leiden")  # AnnData
    expression = dega.nbhd.calc_nbhd_by_gene(gdf_nbhd, by="cell", adata=adata)  # AnnData

    mat = dega.clust.Matrix(composition)
    mat.cluster()
    dega.viz.Clustergram(matrix=mat)
    ```

=== "NeighborhoodCollection"

    ```python
    nc = dega.nbhd.NeighborhoodCollection(gdf=landscape.nbhd, nbhd_type="drawn")
    nc.add_mod("population", dega.nbhd.calc_nbhd_by_pop(adata, nc, category="leiden"))
    nc.add_mod("gene", dega.nbhd.calc_nbhd_by_gene(nc, by="cell", adata=adata))
    nc.add_relation("bordering", dega.nbhd.calc_nbhd_bordering(nc, metric="binary"))

    nc.mdata  # a MuData: one observation per neighborhood, one modality per summary

    mat = dega.clust.Matrix(nc.mod["population"])
    mat.cluster()
    dega.viz.Clustergram(matrix=mat)
    ```

The [pancreas islet gradients example](../examples/brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb)
uses both, and the [collection API](../python/collection/api.md) describes the
storage model.

## Common pitfalls

- **Cell IDs don't match.** Spatial readers such as `spatialdata_io.xenium()`
  can leave `obs_names` as `0, 1, 2, ...`. Set
  `adata.obs_names = adata.obs["cell_id"].astype(str)` so that cells match the
  DegaFiles; unmatched cells are drawn in a fallback color.
- **Scaled expression in dot plots.** After `sc.pp.scale`, values can be
  negative, so "fraction expressing" (values greater than zero) is no longer
  meaningful. Build `Matrix(adata, groupby=...)` from normalized, log-transformed
  expression, and z-score rows in the Matrix instead.
- **Dense or CSR expression in AnnData Zarr.** A single-cell Landscape reads one
  gene at a time from a CSC matrix; save a CSC copy, such as
  `adata.layers["counts_csc"]`.
- **Remote notebooks and `localhost`.** A local file server runs where the
  kernel runs. On a remote kernel, use a URL your browser can reach, or host the
  data; see [Usage](usage/index.md#3-view-the-prepared-data-locally).
- **Google Colab.** Link widgets with `ipywidgets.jslink` and display them in an
  `HBox`, as in the [Quick Start](index.md#2-explore-a-public-xenium-dataset).
