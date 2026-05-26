# Collection Schema API Reference

Celldega collections are typed MuData profiles. AnnData is the unit of a
feature space; MuData is the unit of a multimodal Celldega collection.

## Motivation

AnnData is an excellent representation for one observation-by-feature matrix
plus aligned annotations, graphs, and metadata. Celldega collections need
several independently clusterable feature spaces over the same biological
observation axis: genes, populations, image features, morphology features,
clinical variables, and derived joint spaces.

MuData provides that collection layer by storing each feature space as its own
AnnData modality while preserving shared observation metadata. Celldega adds a
thin schema convention on top for biological entity typing, hierarchy results,
provenance, geometry, and view-linking metadata.

## Core Model

| Concept | Storage |
|---|---|
| Canonical observations | `collection.mdata.obs` / `collection.obs` |
| Feature spaces | `collection.mdata.mod[name]` / `collection.mod[name]` |
| Observation relations | `collection.mdata.obsp[name]` / `collection.relations[name]` |
| Celldega metadata | `collection.mdata.uns["celldega"]` / `collection.uns` |
| Hierarchy registry | `collection.mdata.uns["celldega"]["hierarchies"]` |

Each modality is a normal AnnData object. Its `X` is the clusterable matrix and
its `var` table describes the local feature/entity axis. Celldega stores the
global row entity type in `mdata.uns["celldega"]["obs_entity_type"]` and stores
modality-local entity types in `mdata.mod[name].var["entity_type"]`.

## Dataset

`dega.dataset.Dataset` observations are datasets, samples, tissue sections,
patients, or other dataset-level units. Dataset-level feature spaces are MuData
modalities such as `population`, `expression`, `image`, `clinical`, and
`joint`.

Use `dega.dataset.Dataset(...).construct_population_space(...)` to construct
and attach a dataset-level population modality:

```python
import celldega as dega

dataset = dega.dataset.Dataset(
    adata,
    dataset_col="sample_id",
)
population = dataset.construct_population_space(category="cell_type")

assert dataset.mod["population"] is population
assert dataset.mod["population"].var["entity_type"].iloc[0] == "cell_population"
```

Collections write through MuData:

```python
dataset.write("dataset.h5mu")
loaded = dega.dataset.Dataset.read("dataset.h5mu")
```

## Hierarchies

`HierarchyResult` is a convenience wrapper for adding serializable hierarchy
metadata to `mdata.uns["celldega"]["hierarchies"]`. Hierarchies point to the
MuData source they came from, such as `input_mod="population"` or
`input_relation="similarity"`.

Hierarchical biclustering can store both axes:

```python
dataset.add_hierarchy(
    dega.HierarchyResult(
        id="mod:population__hierarchical",
        input_mod="population",
        method="hierarchical",
        axis="bicluster",
        obs_leaf_order=["sample_1", "sample_2"],
        var_leaf_order=["B cell", "T cell"],
    )
)
```

Flat cluster assignments, such as Leiden labels, should usually live as columns
in `collection.obs`. Method metadata for those labels can live in
`collection.uns` or `collection.provenance`.

## NeighborhoodCollection

`NeighborhoodCollection` observations are neighborhoods or spatial regions such
as hex tiles, alpha-shape regions, manual regions, or gradient rings.

Recommended modalities include `gene`, `population`, `image`, `morphology`,
`gradient`, and `joint`.

Recommended relations include `adjacency`, `bordering`, `overlap`, `distance`,
`gene_knn`, `population_knn`, and `image_knn`. Use `bordering` for
shared-boundary relationships.

`NBHD` owns a `NeighborhoodCollection` under `nbhd.collection` and attaches
feature modalities and sparse relations with methods such as
`construct_gene_space`, `construct_population_space`, `construct_image_space`,
`construct_overlap_relation`, and `construct_bordering_relation`.

Geometry is kept as a live `GeoDataFrame` on `NeighborhoodCollection.geometry`
for now. Durable geometry storage can be added later with WKB columns or
GeoParquet sidecars keyed by `obs_names`.

::: celldega.collections
