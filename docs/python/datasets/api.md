# Datasets Module API Reference

The `datasets` module contains dataset-level space constructors and helpers for
building `DatasetCollection` objects from cell-level `AnnData` metadata.

Use this module for dataset, sample, tissue section, patient, or cohort-level
feature spaces. For example, `calc_dataset_by_pop` creates a
dataset-by-population `AnnData` matrix aligned by dataset/sample ID, and
`dataset_collection_from_adata` creates a `DatasetCollection` with optional
spaces attached.

```python
import celldega as dega

population = dega.datasets.calc_dataset_by_pop(
    adata,
    dataset_col="sample_id",
    category="cell_type",
)

datasets = dega.datasets.dataset_collection_from_adata(
    adata,
    dataset_col="sample_id",
    obs_columns=["patient_id", "condition"],
    population_category="cell_type",
)
```

::: celldega.datasets
