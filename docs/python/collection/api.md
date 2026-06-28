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

A `CelldegaCollection` is a thin wrapper over a `MuData` (`collection.mdata`).
Its core accessors are convenience aliases that proxy directly to attributes of
the underlying `MuData` — they are not separate storage:

| Concept | Accessor | Is exactly |
|---|---|---|
| Canonical observations | `collection.obs` | `collection.mdata.obs` |
| Feature spaces | `collection.mod[name]` | `collection.mdata.mod[name]` |
| Observation relations | `collection.relations[name]` | `collection.mdata.obsp[name]` |
| Celldega metadata | `collection.uns` | `collection.mdata.uns["celldega"]` |

In particular, `collection.relations` **is** `collection.mdata.obsp` (the same
object): `collection.relations["x"] is collection.mdata.obsp["x"]`. The
`relations` name is just Celldega vocabulary for MuData's `obsp` ("observation
pairwise") store — use whichever you prefer. Relations live in `obsp` (the
shared, collection-level observation axis) rather than inside a single
modality's `obsp` because they are modality-independent properties of the
observations themselves; feature-by-feature relations belong in a modality's
`varp`.

Each modality is a normal AnnData object. Its `X` is the clusterable matrix and
its `var` table describes the local feature/entity axis. Celldega stores the
global row entity type in `mdata.uns["celldega"]["obs_entity_type"]` and stores
modality-local entity types in `mdata.mod[name].var["entity_type"]`.
Higher-order collections do not embed lower-level source objects such as
single-cell AnnData. Source data can be linked through lightweight metadata in
`collection.uns["sources"]` and recorded in modality provenance.

`obsp` is the right native location for graph-like or distance-like observation
pairs. When a workflow needs to treat a square relation matrix as `AnnData.X`
for heatmap or Matrix-style clustering, materialize it as a modality:

```python
# make a new modality from a pre-existing relationship
collection.add_relation_modality("similarity")

# view new modality
collection.mod["similarity_relation"]
```

## API

::: celldega.collection
