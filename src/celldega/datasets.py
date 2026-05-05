"""Dataset-level collection and feature-space constructors."""

from __future__ import annotations

from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.collections import DatasetCollection


__all__ = [
    "calc_dataset_by_pop",
    "dataset_collection_from_adata",
]


def _category_colors(adata: AnnData, category: str) -> dict[str, str]:
    color_key = f"{category}_colors"
    if color_key not in adata.uns:
        return {}

    src_colors = adata.uns[color_key]
    if hasattr(adata.obs[category], "cat"):
        src_categories = list(adata.obs[category].cat.categories.astype(str))
    else:
        src_categories = list(adata.obs[category].unique().astype(str))

    return {
        str(cat): src_colors[i]
        for i, cat in enumerate(src_categories)
        if i < len(src_colors)
    }


def _align_space_to_collection(adata: AnnData, collection: DatasetCollection) -> AnnData:
    target_index = collection.obs.index.astype(str)
    source_index = pd.Index(adata.obs_names.astype(str))

    if list(source_index) == list(target_index):
        return adata

    source_lookup = {name: i for i, name in enumerate(source_index)}
    target_rows = [i for i, name in enumerate(target_index) if name in source_lookup]
    source_rows = [source_lookup[name] for name in target_index if name in source_lookup]

    X = np.zeros((len(target_index), adata.n_vars), dtype=adata.X.dtype)
    if source_rows:
        X[target_rows, :] = np.asarray(adata.X[source_rows, :])

    obs = collection.obs.copy()
    space_obs = adata.obs.copy()
    space_obs.index = source_index
    for col in space_obs.columns:
        values = space_obs[col].reindex(target_index)
        if pd.api.types.is_numeric_dtype(space_obs[col]) or col.startswith("n_"):
            values = values.fillna(0)
        obs[col] = values

    return AnnData(X=X, obs=obs, var=adata.var.copy(), uns=dict(adata.uns))


def calc_dataset_by_pop(
    adata: AnnData,
    dataset_col: str = "sample_id",
    category: str = "leiden",
    output: str = "percentage",
    min_cells: int = 1,
) -> AnnData:
    """Calculate a dataset-by-population feature space from cell metadata.

    Args:
        adata: Cell-level AnnData. ``adata.obs`` must contain ``dataset_col``
            and ``category``.
        dataset_col: Observation column identifying the dataset, sample, tissue
            section, patient, or other dataset-level unit.
        category: Observation column identifying the cell population, cell type,
            cell state, or cluster.
        output: ``"percentage"`` for within-dataset fractions or ``"counts"``
            for raw cell counts.
        min_cells: Minimum number of cells required to keep a dataset row.

    Returns:
        AnnData with datasets as observations and populations as variables.
    """
    if output not in {"percentage", "counts"}:
        raise ValueError("output must be 'percentage' or 'counts'")
    if dataset_col not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{dataset_col}' column")
    if category not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{category}' column")

    dataset_ids = pd.Index(pd.unique(adata.obs[dataset_col].astype(str)), name=dataset_col)
    obs = pd.DataFrame(
        {
            dataset_col: adata.obs[dataset_col].astype(str).values,
            category: adata.obs[category].astype(str).values,
        }
    )

    counts = (
        obs.groupby([dataset_col, category])
        .size()
        .unstack(fill_value=0)
        .pipe(lambda df: df.set_axis(df.columns.astype(str), axis=1))
        .reindex(dataset_ids)
        .fillna(0)
        .astype(int)
    )
    counts = counts[counts.sum(axis=1) >= min_cells]

    if output == "percentage":
        values = counts.div(counts.sum(axis=1), axis=0).fillna(0).values
    else:
        values = counts.values

    dataset_obs = pd.DataFrame(index=counts.index)
    dataset_obs.index.name = dataset_col
    dataset_obs[dataset_col] = dataset_obs.index
    dataset_obs["n_cells"] = counts.sum(axis=1).values

    var = pd.DataFrame(index=counts.columns)
    var.index.name = category
    var[category] = var.index.astype(str)

    adata_pop = AnnData(X=np.asarray(values), obs=dataset_obs, var=var)
    adata_pop.uns["dataset_col"] = dataset_col
    adata_pop.uns["category"] = category
    adata_pop.uns["output"] = output

    color_dict = _category_colors(adata, category)
    if color_dict:
        color_key = f"{category}_colors"
        adata_pop.var["color"] = [color_dict.get(str(c), "#808080") for c in adata_pop.var_names]
        adata_pop.uns[color_key] = [
            color_dict.get(str(c), "#808080") for c in adata_pop.var_names
        ]

    return adata_pop


def dataset_collection_from_adata(
    adata: AnnData,
    dataset_col: str = "sample_id",
    obs_columns: list[str] | None = None,
    population_category: str | None = None,
    population_output: str = "percentage",
    population_key: str = "population",
    min_cells: int = 1,
) -> DatasetCollection:
    """Create a ``DatasetCollection`` from cell-level AnnData metadata.

    This constructor builds the canonical dataset ``obs`` table. When
    ``population_category`` is provided, it also attaches a dataset-by-population
    space under ``population_key``.
    """
    if dataset_col not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{dataset_col}' column")

    dataset_ids = pd.Index(pd.unique(adata.obs[dataset_col].astype(str)), name=dataset_col)
    dataset_obs = pd.DataFrame(index=dataset_ids)
    dataset_obs[dataset_col] = dataset_obs.index

    dataset_labels = adata.obs[dataset_col].astype(str)
    dataset_obs["n_cells"] = (
        dataset_labels.value_counts().reindex(dataset_ids).fillna(0).astype(int)
    )

    for col in obs_columns or []:
        if col == dataset_col:
            continue
        if col not in adata.obs.columns:
            raise ValueError(f"adata.obs missing requested metadata column '{col}'")
        metadata = pd.DataFrame(
            {
                dataset_col: dataset_labels.values,
                col: adata.obs[col].values,
            }
        )
        dataset_obs[col] = metadata.groupby(dataset_col)[col].first().reindex(dataset_ids)

    collection = DatasetCollection(obs=dataset_obs)

    if population_category is not None:
        population = calc_dataset_by_pop(
            adata,
            dataset_col=dataset_col,
            category=population_category,
            output=population_output,
            min_cells=min_cells,
        )
        collection.spaces[population_key] = _align_space_to_collection(population, collection)

    return collection
