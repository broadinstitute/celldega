# CelldegaCollection API Reference

A Celldega collection is the base Class that is used to build Celldega's dataset-level ([DatasetCollection](../dataset/api.md)) and neighborhood-level ([NeighborhoodCollection](../nbhd/api.md)) data structures. Celldega collections are typed MuData profiles. AnnData is the unit of a
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
| Canonical observations | `collection.obs` |
| Feature spaces | `collection.mod[name]` |
| Observation relations | `collection.relations[name]` |
| Celldega metadata | `collection.uns` |
| Hierarchy registry | `collection.uns["celldega"]["hierarchies"]` |

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
# make a new modality from a pre-existing relationship obsp
collection.add_relation_modality("similarity")

# view new modality
collection.mod["similarity_relation"]
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

## API

::: celldega.collection
