# Dataset Module API Reference

## Motivation

Studies compare samples, patients and cohorts, not only cells. A sample can be
described by its cell-type composition, or by the expression signature of one
of its populations, such as its B cells, and samples can group differently in
each space: two samples with the same composition can differ in what their B
cells express. Neither the sample-level observations nor these feature spaces
come off the instrument; they have to be built from cell-level data.

`DatasetCollection` makes the samples the observations, carries their metadata
(such as patient and condition), and stores each feature space calculated for
them as a modality, so the spaces can be clustered and compared side by side.
Like Celldega's other collections, it is a thin wrapper around MuData; see
[Collections](../collection/api.md) for the shared model, and
[Compare samples in two feature spaces](../../examples/brief_notebooks/DatasetCollection_Feature_Spaces.ipynb)
for a brief example with a Composition view.

## Overview

The `dataset` module contains dataset-level modality constructors and
helpers for building MuData-backed `DatasetCollection` objects from cell-level
`AnnData` metadata.

`DatasetCollection` is the dataset-level collection object: its `obs` table is
the canonical dataset/sample axis, and derived feature spaces are stored
directly as MuData modalities in `dset.mod`. Dataset-specific feature
calculation should happen through methods on this object so the result is
attached to the collection that owns the dataset axis. Cell-level AnnData is
used as an input to constructors and calculations, but it is not stored on the
dataset-level collection.

```python
import celldega as dega

dset = dega.DatasetCollection(
    adata,
    dataset_col="sample_id",
    obs_columns=["patient_id", "condition"],
)

dset.calc_population(
    adata,
    category="cell_type",
    output="proportion",
)

population = dset.mod["population"]

# Compare the samples' composition as stacked bars.
dega.viz.Composition(dset, group_attrs=["condition"])

dset.calc_signature(
    adata,
    category="cell_type",
    value="CD8 T",
    modality_name="cd8_t_expression",
    missing_datasets="nan",
)

cd8_t_expression = dset.mod["cd8_t_expression"]

dset.write("dataset.h5mu")
loaded = dega.DatasetCollection.read("dataset.h5mu")
```

::: celldega.dataset
