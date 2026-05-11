# Dataset Module API Reference

The singular `dataset` module contains dataset-level space constructors and
helpers for building `Dataset` objects from cell-level `AnnData` metadata.

`Dataset` is the dataset-level collection object: its `obs` table is the
canonical dataset/sample axis, and derived spaces are stored directly in
`dataset.spaces`. `calc_dataset_by_pop` remains a low-level calculator that
returns a standalone dataset-by-population `AnnData`.

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

dataset.write("dataset.h5ad")
loaded = dega.dataset.read("dataset.h5ad")
```

## H5AD Storage

`Dataset.write("dataset.h5ad")` writes a Celldega-flavored H5AD file:

- The root H5AD object stores the dataset-level `obs` table.
- `dataset.spaces` are stored as named `AnnData` objects in reserved `uns` keys.
- `dataset.relations`, `dataset.provenance`, and collection metadata are stored
  alongside those spaces.

The file remains readable with `anndata.read_h5ad`, while
`dega.dataset.read("dataset.h5ad")` reconstructs the full `Dataset` object.

::: celldega.dataset
