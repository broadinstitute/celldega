# Dataset Module API Reference

The singular `dataset` module contains dataset-level space constructors and
helpers for building `Dataset` objects from cell-level `AnnData` metadata.

`Dataset` is the dataset-level collection object: its `obs` table is the
canonical dataset/sample axis, and derived spaces are stored directly in
`dataset.spaces`. Dataset-specific feature calculation should happen through
methods on this object so the result is attached to the collection that owns
the dataset axis.

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

assert dataset.spaces["population"] is population
```

::: celldega.dataset
