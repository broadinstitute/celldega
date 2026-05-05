# Collection Schema API Reference

Celldega collection schemas define lightweight containers for aligned
dataset-level and neighborhood-level data. These classes document the expected
in-memory shape only. They do not run neighborhood computations, validate
alignment, or read and write files.

## Core Model

| Concept | Meaning |
|---|---|
| `obs` | Canonical observation table and row axis. |
| `spaces` | Named observation-by-feature `AnnData` matrices aligned to `obs`. |
| `relations` | Named observation-by-observation sparse matrices. |
| `hierarchies` | Clustering or tree results derived from a space or relation. |
| `provenance` | Free-form metadata describing where the collection came from. |
| `uns` | Free-form collection metadata. |

## DatasetCollection

`DatasetCollection` observations are datasets, samples, tissue sections,
patients, or other dataset-level units.

Recommended spaces include `population`, `expression`, `image`, `neighborhood`,
`clinical`, and `joint`.

Recommended relations include `similarity`, `distance`, `matched_pair`,
`patient_pairing`, `population_knn`, `expression_knn`, and
`neighborhood_knn`.

## NeighborhoodCollection

`NeighborhoodCollection` observations are neighborhoods or spatial regions such
as hex tiles, alpha-shape regions, manual regions, or gradient rings.

Recommended spaces include `gene`, `population`, `image`, `morphology`,
`gradient`, and `joint`.

Recommended relations include `adjacency`, `bordering`, `overlap`, `distance`,
`gene_knn`, `population_knn`, and `image_knn`. Use `bordering` for
shared-boundary relationships.

Recommended memberships include `cell_to_neighborhood`,
`transcript_to_neighborhood`, `spot_to_neighborhood`, and
`pixel_to_neighborhood`.

::: celldega.collections
