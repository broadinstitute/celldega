# Collection Schema API Reference

Celldega collection schemas define lightweight containers for aligned
dataset-level and neighborhood-level data.

## Motivation

`AnnData` is excellent for one observation-by-variable matrix plus annotations.
Celldega workflows often need a stable biological row axis with several aligned
feature spaces, pairwise relations, clustering results, geometry, and
provenance. For example, the same datasets may have population fractions,
expression summaries, image features, clinical annotations, and similarity
graphs. Keeping those as unrelated `AnnData` objects makes it easy for row order
or metadata to drift.

The collection schema is a coordination layer around those objects. It does not
replace `AnnData`; spaces inside a collection are still `AnnData` matrices.
Instead, a collection defines one canonical `obs` table and stores aligned
spaces, relations, hierarchy results, and metadata around that axis.

[`dataset`](../dataset/api.md) helpers and `NBHD` methods can populate spaces
and relations into these containers.

## Core Model

| Concept | Meaning |
|---|---|
| `obs` | Canonical observation table and row axis. |
| `spaces` | Named observation-by-feature `AnnData` matrices aligned to `obs`. |
| `relations` | Named observation-by-observation sparse matrices. |
| `hierarchies` | Clustering or tree results uniquely tied to a space or relation. |
| `provenance` | Free-form metadata describing where the collection came from. |
| `uns` | Free-form collection metadata. |

## Dataset

`dega.dataset.Dataset` observations are datasets, samples, tissue sections,
patients, or other dataset-level units. A `Dataset` is the object that stores
the dataset-level `obs`, spaces, relations, provenance, and linked
neighborhood-level collections.

Recommended spaces include `population`, `expression`, `image`, `neighborhood`,
`clinical`, and `joint`.

Recommended relations include `similarity`, `distance`, `matched_pair`,
`patient_pairing`, `population_knn`, `expression_knn`, and
`neighborhood_knn`.

Use `dega.dataset.Dataset(...).construct_population_space(...)` to construct
and attach a dataset-level population space:

```python
import celldega as dega

dataset = dega.dataset.Dataset(
    adata,
    dataset_col="sample_id",
)
population = dataset.construct_population_space(category="cell_type")
assert dataset.spaces["population"] is population
```

## Hierarchies

`HierarchyResult` stores clustering state for a specific input using
`input_kind` and `input_key`, such as `space:population` or
`relation:similarity`. Hierarchical biclustering can store both the observation
axis and the feature/entity axis through the `obs_*` and `entity_*` fields.

Flat cluster assignments, such as Leiden labels, should usually live as columns
in the collection `obs` table. Method metadata for those labels can live in
`uns` or `provenance`.

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
