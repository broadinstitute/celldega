# Neighborhood Module API Reference

`alpha_shape` returns Shapely geometry and `calc_gradient` returns a GeoDataFrame.
Neither requires a `NeighborhoodCollection`. With coordinates in microns:

```python
footprint = dega.nbhd.alpha_shape(adata.obsm["spatial"][seed_mask], inv_alpha=40)
rings = dega.nbhd.calc_gradient(
    footprint, direction="both", bin_width=25, max_dist=200,
    clip_reference=adata,
)
```

Spatially join cell centroids to the bands, then store counts or proportions in
an AnnData with bands as observations and cell types as variables. Multiple
footprints are unioned before buffering; cells exactly on shared boundaries
should be assigned once using an explicit tie-breaking rule.

::: celldega.nbhd
