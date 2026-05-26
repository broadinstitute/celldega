# Dataset Module API Reference

The singular `dataset` module contains dataset-level modality constructors and
helpers for building MuData-backed `Dataset` objects from cell-level `AnnData`
metadata.

`Dataset` is the dataset-level collection object: its `obs` table is the
canonical dataset/sample axis, and derived feature spaces are stored directly as
MuData modalities in `dataset.mod`. Dataset-specific feature calculation should
happen through methods on this object so the result is attached to the
collection that owns the dataset axis.

```python
import celldega as dega

dataset = dega.dataset.Dataset(
    adata,
    dataset_col="sample_id",
    obs_columns=["patient_id", "condition"],
)

population = dataset.construct_population_space(
    category="cell_type",
    output="percentage",
)

assert dataset.mod["population"] is population

dataset.write("dataset.h5mu")
loaded = dega.dataset.Dataset.read("dataset.h5mu")
```

::: celldega.dataset
