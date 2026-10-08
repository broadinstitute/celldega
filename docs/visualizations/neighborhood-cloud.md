# NeighborhoodCloud

`NeighborhoodCloud` is a 3D, orbit-camera view of precomputed tissue
neighborhoods — one alpha-shape polygon per cluster/slice, so it stays cheap
to display regardless of dataset size. It replaces `Landscape`'s older
`technology="neighborhood-cloud"` mode.

## What it shows

- **Neighborhood polygons**: one alpha-shape region per (cluster, slice),
  rendered in 3D with the same orbit camera as `CellCloud`.
- **On-demand cell detail**: real cell centroids load in only when a
  neighborhood is selected, instead of being loaded up front.
- A **slice** control for stepping through multi-slice datasets.

Note: the 2D neighborhood *drawing* editor (used to hand-draw a region on a
tissue section) is a `Landscape` feature and is intentionally not part of
`NeighborhoodCloud`, which only visualizes neighborhoods that already exist.

## Usage

```python
import celldega as dega

nbhd_cloud = dega.viz.NeighborhoodCloud(
    base_url="https://your-landscape-files-url",
    adata=adata,
)
nbhd_cloud
```

Build the underlying neighborhood-cloud DegaFiles with
[`celldega.align.write_nbhd_cloud`](../python/align/api.md) (or
[`celldega.pre.write_nbhd_cloud_dataset`](../python/pre/api.md)).
`NeighborhoodCloud` can also be linked to a `Clustergram`, exactly like
`Landscape` — see [`dega.viz.spatial_clustergram`](../python/viz/api.md).

For the full list of constructor arguments, see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
