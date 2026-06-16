# CelldegaCollection API Reference

A CelldegaCollection is the base Class that is used to build Celldega's dataset-level ([DatasetCollection](../dataset/api.md)) and neighborhood-level ([NeighborhoodCollection](../nbhd/api.md)) data structures. Celldega collections are typed MuData profiles. AnnData is the unit of a
feature space; MuData is the unit of a multimodal Celldega collection.

## Motivation

Celldega defines new biological entities — datasets, neighborhoods, and more in
the future — which requires both *constructing* the entity and *calculating* its
feature spaces, neither of which is free for entities above the single-cell
level. For single-cell gene expression and spatial data, both come straight off
the instrument; for higher-order entities, `DatasetCollection` and
`NeighborhoodCollection` construct the observation axis and attach the feature
modalities themselves.

AnnData is an excellent representation for one observation-by-feature matrix
plus aligned annotations, graphs, and metadata. Celldega collections need
several independently clusterable feature spaces over the same biological
observation axis: genes, populations, image features, morphology features,
clinical variables, and derived joint spaces.

MuData provides that collection layer by storing each feature space as its own
AnnData modality while preserving shared observation metadata. Celldega adds a
thin schema convention on top for biological entity typing, provenance,
geometry, and view-linking metadata.

## Core Model

| Concept | Storage |
|---|---|
| Canonical observations | `collection.obs` |
| Feature spaces | `collection.mod[name]` |
| Observation relations | `collection.relations[name]` |
| Celldega metadata | `collection.uns` |

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
# make a new modality from a pre-existing relationship
collection.add_relation_modality("similarity")

# view new modality
collection.mod["similarity_relation"]
```

## API

::: celldega.collection
