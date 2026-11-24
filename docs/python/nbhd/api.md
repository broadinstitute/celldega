# Neighborhood Module API Reference

## Motivation

Tissue is organized above the single cell: functional tissue units such as
glomeruli or islets, cellular niches, and the regions around a structure. Many
questions are about these regions rather than their cells. What cell types make
up each one? What do its cells express? Which regions overlap or border each
other, and how does composition change with distance from a structure?

Neighborhoods capture these regions as polygons together with the cells inside
them. Like other entities above the single cell, a neighborhood is described in
several feature spaces at once: its cell-type composition, its expression, and
its spatial relations to other neighborhoods. Neither the neighborhoods nor
these spaces come off the instrument. The `nbhd` module builds neighborhoods
from cells, calculates their feature spaces, and keeps them together in a
`NeighborhoodCollection`.

## Demo notebooks

- [Find niches with hexagonal neighborhoods](../../examples/brief_notebooks/NeighborhoodCollection_Hextile_Niches.ipynb):
  a simulated tissue's hexagons, clustered by composition into niches.
- [Pancreas islet gradients](../../examples/brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb):
  rings around real islets, with their composition and expression, stored in a
  NeighborhoodCollection.

**Tutorial:** [Atera breast cancer neighborhoods](../../examples/tutorial_notebooks/Atera_Breast_Cancer_Neighborhood_Exploration.ipynb)
compares hextile niches and alpha shapes.

## NeighborhoodCollection

A `NeighborhoodCollection` holds a set of neighborhoods and everything
calculated for them, with one observation per neighborhood:

| Part | Accessor | Holds |
| --- | --- | --- |
| Geometry | `nc.gdf` | A `GeoDataFrame` of the neighborhood polygons |
| Observations | `nc.obs` | Per-neighborhood annotations, such as area and centroid |
| Feature spaces | `nc.mod[name]` | One `AnnData` per space, such as `population` (neighborhoods × cell types) or `gene` (neighborhoods × genes) |
| Relations | `nc.relations[name]` | Neighborhood × neighborhood matrices, such as overlap or bordering |
| Type | `nc.nbhd_type` | How the neighborhoods were made, such as `"alpha_shape"`, `"hextile"` or `"gradient"` |

The collection stores data and doesn't calculate anything itself. Pass it to
the `nbhd` functions wherever they take a neighborhood `GeoDataFrame`, then
store what they return. Like Celldega's other collections, it is a thin wrapper
around MuData; see [Collections](../collection/api.md) for the shared model.

```python
import celldega as dega

gdf_alpha = dega.nbhd.alpha_shape_cell_clusters(adata, cat="leiden", alphas=[150])
gdf_alpha = dega.nbhd.filter_alpha_shapes(gdf_alpha, alpha=150)
nc = dega.nbhd.NeighborhoodCollection(gdf=gdf_alpha, nbhd_type="alpha_shape")

pop = dega.nbhd.calc_nbhd_by_pop(adata, nc, category="leiden", min_cells=5)
nc.subset(pop.obs_names)             # optional: drop neighborhoods below min_cells
nc.add_mod("population", pop)
nc.add_mod("gene", dega.nbhd.calc_nbhd_by_gene(nc, adata=adata))
nc.add_relation("overlap", dega.nbhd.calc_nbhd_overlap(nc, metric="iou"))

trx = dega.nbhd.read_transcripts(data_dir)
nc.obs = nc.obs.join(dega.nbhd.calc_nbhd_transcript_assignment(nc, trx))

# Cluster the neighborhoods by their composition (the population modality).
mat = dega.clust.Matrix(mdata=nc, color_by="population")
```

You can also use the `nbhd` functions without a collection: each takes a plain
`GeoDataFrame` and returns plain `AnnData`.

## Building neighborhoods

A neighborhood is a row of a `GeoDataFrame` with a polygon and an id column
(`name` by default, falling back to `neighborhood_id` / `nbhd_id`).

| Neighborhoods | Function |
| --- | --- |
| Concave hulls around each cluster's cells | `alpha_shape_cell_clusters`, then `filter_alpha_shapes` to keep one alpha; `alpha_shape` for a single set of points |
| The same, for each serial section of a 3D stack | `alpha_shape_cell_clusters_by_slice` |
| A regular hexagonal grid | `generate_hextile` |
| Niches: hexagons merged by clustering their contents | `hextile_niche` |
| Rings inward and outward from a region | `calc_gradient` |
| Regions drawn by hand on a Landscape | `landscape.nbhd` |
| Your own polygons | Any `GeoDataFrame` with an id column |

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

## Calculating feature spaces

Each function summarizes neighborhoods against cell-level `AnnData` or `MuData`
and returns a neighborhood-level `AnnData` that clusters in a Clustergram:

| Feature space | Function |
| --- | --- |
| Cell-type composition (neighborhoods × cell types) | `calc_nbhd_by_pop` |
| Expression (neighborhoods × genes or proteins) | `calc_nbhd_by_gene` |
| Image intensity statistics per channel | `calc_img_zonal_stats` |
| Transcript counts and the share assigned to cells | `calc_nbhd_transcript_assignment` |
| Overlap between neighborhoods (neighborhoods × neighborhoods) | `calc_nbhd_overlap` |
| Shared borders between neighborhoods (neighborhoods × neighborhoods) | `calc_nbhd_bordering` |

```python
gdf_hex = dega.nbhd.generate_hextile(adata, diameter=100)

# neighborhoods x genes (mean expression of the cells inside each hexagon)
adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_hex, "cell", adata)

# neighborhoods x cell types (proportions)
adata_nbp = dega.nbhd.calc_nbhd_by_pop(adata, gdf_hex, category="leiden")

# every result is ready for a Clustergram
mat = dega.clust.Matrix(adata_nbp)
```

With a `MuData` (e.g. RNA + protein), `calc_nbhd_by_gene` aggregates every
modality and returns a `MuData` of neighborhood-level modalities; pass
`modality=` to aggregate just one. In the `calc_nbhd_*` functions and
`calc_gradient`, any object exposing `to_geodataframe()` can stand in for the
neighborhood `GeoDataFrame`.

## API

::: celldega.nbhd
