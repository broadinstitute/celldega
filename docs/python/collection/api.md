# CelldegaCollection API Reference

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
Higher-order collections do not embed lower-level source objects such as
single-cell AnnData. Source data can be linked through lightweight metadata in
`collection.uns["sources"]` and recorded in modality provenance.

Observation relations should live canonically in `mdata.obsp`. This is the
right native location for graph-like or distance-like observation pairs. When a
workflow needs to treat a square relation matrix as `AnnData.X` for heatmap or
Matrix-style clustering, materialize it as a modality:

```python
relation_mod = collection.add_relation_modality("similarity")
assert collection.mod["similarity_relation"] is relation_mod
```

## Dataset

`dega.dataset.DatasetCollection` observations are datasets, samples, tissue
sections, patients, or other dataset-level units. Dataset-level feature spaces
are MuData modalities such as `population`, `expression`, `image`, `clinical`,
and `joint`.

Use `dega.dataset.DatasetCollection(...).calc_dataset_by_pop(...)` to calculate
and attach a dataset-level population modality:

```python
import celldega as dega

dset = dega.dataset.DatasetCollection(
    adata,
    dataset_col="sample_id",
)
dset.calc_dataset_by_pop(adata, category="cell_type")
population = dset.mod["population"]

assert population.var["entity_type"].iloc[0] == "cell_population"
```

Collections write through MuData:

```python
dset.write("dataset.h5mu")
loaded = dega.dataset.DatasetCollection.read("dataset.h5mu")
```

## Hierarchies

`HierarchyResult` is a convenience wrapper for adding serializable hierarchy
metadata to `mdata.uns["celldega"]["hierarchies"]`. Hierarchies point to the
MuData source they came from, such as `input_mod="population"` or
`input_relation="similarity"`.

Hierarchical biclustering can store both axes:

```python
import numpy as np

dset.add_hierarchy(
    dega.HierarchyResult(
        id="mod:population__hierarchical",
        input_mod="population",
        method="hierarchical",
        axis="bicluster",
        obs_leaf_order=["sample_1", "sample_2"],
        obs_linkage_matrix=np.array([[0, 1, 0.3, 2]]),
        var_leaf_order=["B cell", "T cell"],
        var_linkage_matrix=np.array([[0, 1, 0.5, 2]]),
    )
)
```

Linkage payloads are stored as plain SciPy-compatible `(n - 1, 4)` arrays under
`obs_linkage` and `var_linkage`. Flat cluster assignments, such as Leiden
labels, should usually live as columns in `collection.obs` or in the relevant
modality `var` table. Method metadata for those labels can live in
`collection.uns` or `collection.provenance`.

## NeighborhoodCollection

`NeighborhoodCollection` observations are neighborhoods or spatial regions such
as hex tiles, alpha-shape regions, manual regions, or gradient rings.

Recommended modalities include `gene`, `population`, `image`, `morphology`,
`gradient`, and `joint`.

Recommended relations include `adjacency`, `bordering`, `overlap`, `distance`,
`gene_knn`, `population_knn`, and `image_knn`. Use `bordering` for
shared-boundary relationships.

`NeighborhoodCollection` can be constructed directly from a neighborhood
GeoDataFrame. Cell-level AnnData is passed only to calculations that need it:

```python
nbhd = dega.nbhd.NeighborhoodCollection(
    gdf=gdf_hex,
    nbhd_type="hextile",
)
nbhd.calc_nbhd_by_pop(adata, category="cell_type")
population = nbhd.mod["population"]

assert nbhd.mod["population"] is population
```

The legacy `NBHD` helper still owns a `NeighborhoodCollection` under
`nbhd.collection` and attaches feature modalities and sparse relations with
methods such as `construct_gene_space`, `calc_nbhd_by_pop`,
`construct_overlap_relation`, and `construct_bordering_relation`.

Geometry is kept as a live `GeoDataFrame` on `NeighborhoodCollection.geometry`
for now. Durable geometry storage can be added later with WKB columns or
GeoParquet sidecars keyed by `obs_names`.

::: celldega.collection
