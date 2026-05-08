# Collection Schema API Reference

Celldega collection schemas define lightweight containers for aligned
dataset-level and neighborhood-level data. The collection classes document the
expected in-memory shape; [`datasets`](../datasets/api.md) helpers and `NBHD`
methods can populate spaces and relations into those containers.

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

Use [`calc_dataset_by_pop`](../datasets/api.md#celldega.datasets.calc_dataset_by_pop)
to construct the first dataset-level space:

```python
import celldega as dega

population = dega.calc_dataset_by_pop(
    adata,
    dataset_col="sample_id",
    category="cell_type",
)
datasets = dega.dataset_collection_from_adata(
    adata,
    dataset_col="sample_id",
    population_category="cell_type",
)
```

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

`NBHD` now owns a `NeighborhoodCollection` under `nbhd.collection` and attaches
feature spaces and sparse relations with methods such as
`construct_gene_space`, `construct_population_space`,
`construct_image_space`, `construct_overlap_relation`, and
`construct_bordering_relation`.

::: celldega.collections
