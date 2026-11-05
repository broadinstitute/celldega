# CellCloud–Clustergram

Link a [CellCloud](cell-cloud.md) and [Clustergram](clustergram.md) to compare
3D cell organization with gene-expression patterns. This is useful for thick
tissue or aligned serial sections, where rotating the cell cloud reveals
relationships across slices.

CellCloud shows cell positions in physical space. Clustergram compares
expression across cell groups; its selections update the 3D view.

<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;">
    <iframe src="https://www.youtube.com/embed/a9fSskh1A1g" title="Broad-Allen developing mouse brain E15.5 in 3D, a CellCloud linked to a Clustergram" loading="lazy" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe>
</div>

*The Broad–Allen developing mouse brain: 3.8 million cells from 43 aligned
Xenium sections in a CellCloud. Explore it in the
[3D gallery](../gallery/gallery_broad_allen_mouse_brain_3d.md), or link it to a
Clustergram in the
[visualization notebook](../examples/tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb).*

## What you can explore

- Select a cell group and inspect its distribution across the 3D dataset.
- Click a gene to see where expressing cells occur while rotating or zooming.
- Compare the expression relationships in the Clustergram with the physical
  arrangement of the corresponding cells.

## Before you start

Use point-cloud DegaFiles containing 3D cell positions and a matching
cell-level AnnData, `adata`. Its `obs_names` must match the DegaFiles cell IDs;
`adata.obs["leiden"]` supplies the cell-group labels used by both views.

The example assumes prepared, nonnegative expression in `adata.X` and uses
`celldega[scanpy]` to summarize cells by group. Replace `"leiden"` in both
`groupby` and `cluster_attr` to use a different cell annotation.

See the [CellCloud guide](cell-cloud.md) for point-cloud preparation and
[File Formats](../getting-started/file_formats.md#point-cloud-degafiles) for
the layout.

## Usage

Build the expression summary from the cells shown in the cloud:

```python
import celldega as dega

mat = dega.clust.Matrix(adata, groupby="leiden")
mat.filter("row", by="var", num=min(500, adata.n_vars))
mat.norm("row", by="zscore")
mat.cluster()

cell_cloud = dega.viz.CellCloud(
    base_url="https://your-data-host/point_cloud_files",
    adata=adata,
    cluster_attr="leiden",
    use_adata_3d_centroids=False,
)
cgm = dega.viz.Clustergram(matrix=mat, name="cloud_clusters")

linked = dega.viz.spatial_clustergram(cell_cloud, cgm)
linked
```

Replace `base_url` with your point-cloud DegaFiles URL.
`use_adata_3d_centroids=False` uses the saved 3D positions from DegaFiles
while AnnData supplies the cell annotations.
The Clustergram has genes as rows and cell groups as columns. Dot color
shows row-z-scored mean expression and dot size shows the fraction of cells
expressing each gene.

Use [Clustergram advanced usage](clustergram.md#advanced-usage) to prepare
marker-ranked views or restore a previously saved Matrix instead.

## Try the linked selections

1. **Rotate and zoom the CellCloud.** Inspect the overall shape of the tissue
   or aligned sections.
2. **Select a cell group in the Clustergram.** Its corresponding cells are
   highlighted in 3D.
3. **Click a gene in the Clustergram.** CellCloud colors cells by expression,
   while you continue to rotate and zoom.
4. **Change the Clustergram's feature view.** Explore a different set of genes
   when the Matrix includes precomputed views.

To add gene-set interpretation, pass `enrich=True` to the same helper:

```python
linked_with_enrich = dega.viz.spatial_clustergram(
    cell_cloud, cgm, enrich=True
)
linked_with_enrich
```

See [Landscape–Clustergram–Enrich](landscape-clustergram-enrich.md) for
the enrichment interactions shared by these linked layouts.

## Examples and reference

- [3D developing mouse brain gallery](../gallery/gallery_broad_allen_mouse_brain_3d.md):
  explore a CellCloud interactively.
- [Thick-tissue MERFISH notebook](../examples/brief_notebooks/Landscape-3D_thick_MERFISH.ipynb):
  an example 3D dataset.
- [Python linking API](../python/viz/api.md#celldega.viz.spatial_clustergram):
  linking and layout options.

Source: [linking helpers](https://github.com/broadinstitute/celldega/blob/main/src/celldega/viz/__init__.py).
