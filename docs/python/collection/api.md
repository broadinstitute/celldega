# CelldegaCollection API Reference

`CelldegaCollection` is the base class of Celldega's collections: the
data structures for biological entities above the level of a single cell.
[SetCollection](../set/api.md), [NeighborhoodCollection](../nbhd/api.md) and
[DatasetCollection](../dataset/api.md) are built on it.

## Motivation

Spatial biology asks questions about entities that sit above the single cell:

- **Sets of cells**, such as clusters, spatial domains or manual annotations.
- **Neighborhoods**, such as functional tissue units or the region around a
  structure.
- **Datasets**, such as the samples of a cohort.

Each of these entities is described in several feature spaces at once. A
dataset can be described by its cell-type population, or by the expression
signature of one population, such as its B cells. A neighborhood can be
described by its cell-type composition, its expression, or how it overlaps
other neighborhoods. A set of cells can be described by its gene or protein
signature, its composition, or its overlap with sets from another clustering.
Each space can be clustered on its own and compared with the others.

For single cells, both the observations and their features come off the
instrument. For higher-level entities, neither does: the entities have to be
constructed from cell-level data, and each feature space has to be calculated.

Celldega organizes these entities and their spaces with a data structure,
`CelldegaCollection`. One collection holds one kind of entity as its
observations, and each feature space calculated for them as a modality:

| Collection | One observation is | Example feature spaces |
| --- | --- | --- |
| `SetCollection` | a set of cells (a cluster, domain or annotation) | membership (which cells), expression or protein signature, cell-type composition, overlap with other sets |
| `NeighborhoodCollection` | a neighborhood, with its geometry | cell-type composition, expression, overlap or bordering relations |
| `DatasetCollection` | a sample or dataset | cell-type population, the expression signature of one population |

```python
import celldega as dega

# One row per sample, with patient metadata carried over from the cells.
dset = dega.DatasetCollection(adata, dataset_col="sample_id", obs_columns=["patient_id"])

# The same samples in two feature spaces.
dset.calc_population(adata, category="cell_type")                  # cell-type population space
dset.calc_signature(adata, category="cell_type", value="B cells")  # B cell expression signature space

dset.mod["population"]          # samples x cell types
dset.mod["b_cells_signature"]   # samples x genes, from each sample's B cells

# Compare the samples' cell-type composition as stacked bars.
dega.viz.Composition(dset, group_attrs=["patient_id"])
```

## Demo notebooks

Each runs in a minute on simulated data:

- [Compare samples in two feature spaces](../../examples/brief_notebooks/DatasetCollection_Feature_Spaces.ipynb):
  a DatasetCollection's samples by cell-type composition, in a Composition view,
  and by their B cells' expression, in a Clustergram.
- [Compare two clusterings](../../examples/brief_notebooks/SetCollection_Compare_Clusterings.ipynb): a
  SetCollection's overlap between clusterings shows matches, merges and splits.
- [Set signatures as a dot plot](../../examples/brief_notebooks/SetCollection_Signatures.ipynb): each set's
  expression and fraction expressing in one Clustergram.
- [Find niches with hexagonal neighborhoods](../../examples/brief_notebooks/NeighborhoodCollection_Hextile_Niches.ipynb):
  a NeighborhoodCollection of hexagons clustered by composition into niches.

**Tutorial:** [pancreas islet gradients](../../examples/brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb)
stores rings around real islets, with their composition and expression, in a
NeighborhoodCollection.

## A thin wrapper around MuData

A collection is a thin wrapper around one `MuData` object (`collection.mdata`).
Each feature space is an ordinary `AnnData` modality over the collection's
shared observations, so anything that reads AnnData or MuData can use it, and a
collection saves to and reads from `.h5mu`.

A collection doesn't store copies of the cell-level data it summarizes. It
stays linked to it through shared IDs instead:

- A `SetCollection`'s `membership` modality is a sparse `sets x cells` matrix
  that names the cells in each set.
- A `DatasetCollection`'s observations are the values of the cell-level
  `dataset_col`.
- A `source=` descriptor given when a collection is built, such as the path of
  the cell-level file, is recorded in the collection's provenance
  (`collection.provenance["source"]`).

Celldega adds a small convention on top of MuData: the entity type of the
observations and of each modality's features, provenance, geometry, and
metadata for linking views.

## Core model

The core accessors are aliases for attributes of the underlying `MuData`, not
separate storage:

| Concept | Accessor | Is exactly |
|---|---|---|
| Observations (the entities) | `collection.obs` | `collection.mdata.obs` |
| Feature spaces | `collection.mod[name]` | `collection.mdata.mod[name]` |
| Observation relations | `collection.relations[name]` | `collection.mdata.obsp[name]` |
| Celldega metadata | `collection.uns` | `collection.mdata.uns["celldega"]` |

`collection.relations` **is** `collection.mdata.obsp`, the same object.
`relations` is Celldega's name for MuData's observation-pairwise store, used for
relations between entities such as set-to-set overlap. They live on the shared
observation axis because they belong to the entities, not to one feature space.
Feature-by-feature relations belong in a modality's `varp`.

Each modality's `X` is its clusterable matrix, and its `var` table describes
that modality's features. The observation entity type is stored in
`collection.uns["obs_entity_type"]`, and each modality's feature entity type in
`collection.mod[name].var["entity_type"]`.

To cluster a square relation as a matrix, for example in a Clustergram, copy it
into a modality:

```python
# Make a modality from a stored relation...
collection.add_relation_modality("overlap")

# ...and use it like any other feature space.
collection.mod["overlap_relation"]
```

## API

::: celldega.collection
