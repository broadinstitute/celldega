# Neighborhood Module API Reference

Neighborhoods are `GeoDataFrame`s with one row per neighborhood and an id
column (`name` by default, falling back to `neighborhood_id` / `nbhd_id`). They
come from alpha shapes, hextiles, gradient rings, or your own polygons, and are
summarized against cell-level `AnnData` or `MuData` into new neighborhood-level
`AnnData` objects:

```python
import celldega as dega

gdf_hex = dega.nbhd.generate_hextile(adata, diameter=100)

# neighborhoods x genes (mean expression of the cells inside each hexagon)
adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_hex, "cell", adata)

# neighborhoods x cell types (proportions)
adata_nbp = dega.nbhd.calc_nbhd_by_pop(adata, gdf_hex, category="leiden")

# neighborhoods x neighborhoods relations
adata_overlap = dega.nbhd.calc_nbhd_overlap(gdf_alpha, metric="iou")

# every result is ready for a Clustergram
mat = dega.clust.Matrix(adata_nbp)
```

With a `MuData` (e.g. RNA + protein), `calc_nbhd_by_gene` aggregates every
modality and returns a `MuData` of neighborhood-level modalities; pass
`modality=` to aggregate just one. Any object exposing `to_geodataframe()` can
stand in for the neighborhood `GeoDataFrame`.

`alpha_shape` returns Shapely geometry and `calc_gradient` returns a
`GeoDataFrame` of rings. With coordinates in microns:

```python
footprint = dega.nbhd.alpha_shape(adata.obsm["spatial"][seed_mask], inv_alpha=40)
rings = dega.nbhd.calc_gradient(
    footprint, direction="both", bin_width=25, max_dist=200,
    clip_reference=adata,
)
adata_rings = dega.nbhd.calc_nbhd_by_pop(adata, rings, category="leiden", min_cells=1)
```

Multiple footprints are unioned before buffering. Cells are assigned to rings
with a `within` spatial join, so a cell lying exactly on a ring boundary is not
counted in either ring.

::: celldega.nbhd
