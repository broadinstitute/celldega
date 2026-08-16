# CellCloud

`CellCloud` is a 3D, orbit-camera spatial view of cell centroids — for
inspecting a dataset's overall shape (thick tissue, multi-slice alignments)
rather than the tile-based 2D detail `Landscape` is optimized for. It
replaces `Landscape`'s older `technology="point-cloud"` mode.

## What it shows

- Cell **centroids** in 3D, colored by cluster/category or gene expression,
  rendered as a rotatable/orbit-able point cloud rather than tiled polygons.
- The same **CELL** color/size controls as `Landscape`, minus the
  tile-specific image and transcript layers (there's no underlying image
  pyramid or per-transcript layer in this view).
- Support for **named alignment variants** — e.g. previewing a candidate
  slice alignment by pointing at `cell_metadata_<alignment>.parquet` instead
  of rebuilding DegaFiles.

## Usage

```python
import celldega as dega

cell_cloud = dega.viz.CellCloud(
    base_url="https://your-landscape-files-url",
    adata=adata,
    rotation_x=90,
)
cell_cloud
```

Build the underlying point-cloud DegaFiles with
[`celldega.align.write_alignment_point_cloud`](../python/align/api.md).
`CellCloud` can also be linked to a `Clustergram`, exactly like `Landscape`
— see [`dega.viz.spatial_clustergram`](../python/viz/api.md).

For the full list of constructor arguments, see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
