# Dataset Module API Reference

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

dset = dega.dataset.DatasetCollection(
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

dset.calc_signature(
    adata,
    category="cell_type",
    value="CD8 T",
    modality_name="cd8_t_expression",
    missing_datasets="nan",
)

cd8_t_expression = dset.mod["cd8_t_expression"]

dset.write("dataset.h5mu")
loaded = dega.dataset.DatasetCollection.read("dataset.h5mu")
```

::: celldega.dataset
