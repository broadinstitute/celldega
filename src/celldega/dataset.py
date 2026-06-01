"""Dataset-level collection and modality constructors."""

from __future__ import annotations

from typing import Any

from anndata import AnnData
from mudata import MuData
import numpy as np
import pandas as pd

from celldega.collections import CelldegaCollection


__all__ = [
    "DatasetCollection",
    "from_adata",
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

    return {str(cat): src_colors[i] for i, cat in enumerate(src_categories) if i < len(src_colors)}


def _align_mod_to_dataset(adata: AnnData, dataset: CelldegaCollection) -> AnnData:
    target_index = dataset.obs.index.astype(str)
    source_index = pd.Index(adata.obs_names.astype(str))

    if list(source_index) == list(target_index):
        return adata

    source_lookup = {name: i for i, name in enumerate(source_index)}
    target_rows = [i for i, name in enumerate(target_index) if name in source_lookup]
    source_rows = [source_lookup[name] for name in target_index if name in source_lookup]

    X = np.zeros((len(target_index), adata.n_vars), dtype=adata.X.dtype)
    if source_rows:
        X[target_rows, :] = np.asarray(adata.X[source_rows, :])

    obs = dataset.obs.copy()
    space_obs = adata.obs.copy()
    space_obs.index = source_index
    for col in space_obs.columns:
        values = space_obs[col].reindex(target_index)
        if pd.api.types.is_numeric_dtype(space_obs[col]) or col.startswith("n_"):
            values = values.fillna(0)
        obs[col] = values

    return AnnData(X=X, obs=obs, var=adata.var.copy(), uns=dict(adata.uns))


def _resolve_dataset_col(dataset: CelldegaCollection, dataset_col: str | None) -> str:
    if dataset_col is not None:
        return dataset_col
    if "dataset_col" in dataset.uns:
        return str(dataset.uns["dataset_col"])
    if dataset.obs.index.name is not None:
        return str(dataset.obs.index.name)
    if "sample_id" in dataset.obs.columns:
        return "sample_id"
    if "dataset_id" in dataset.obs.columns:
        return "dataset_id"
    raise ValueError("dataset_col must be provided when it cannot be inferred from the dataset")


def _dataset_obs_from_adata(
    adata: AnnData,
    dataset_col: str = "sample_id",
    obs_columns: list[str] | None = None,
) -> pd.DataFrame:
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

    return dataset_obs


class DatasetCollection(CelldegaCollection):
    """Dataset-level collection with convenience modality constructors.

    ``DatasetCollection`` is the dataset-level Celldega collection. Its ``obs``
    table is the canonical dataset/sample axis, and feature constructors attach
    clusterable ``AnnData`` modalities directly to ``self.mod``.
    """

    def __init__(
        self,
        adata: AnnData | None = None,
        dataset_col: str = "sample_id",
        obs_columns: list[str] | None = None,
        obs: pd.DataFrame | None = None,
        mdata: MuData | None = None,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
        mod: dict[str, AnnData] | None = None,
        relations: dict[str, Any] | None = None,
        hierarchies: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
        neighborhood_collections: dict[str, Any] | None = None,
    ) -> None:
        if mdata is not None:
            obs = obs.copy() if obs is not None else None
            dataset_col = str(
                mdata.uns.get("celldega", {}).get(
                    "dataset_col",
                    dataset_col,
                )
            )
        elif obs is None:
            if adata is None:
                raise ValueError("adata is required when obs is not provided")
            obs = _dataset_obs_from_adata(
                adata,
                dataset_col=dataset_col,
                obs_columns=obs_columns,
            )
        else:
            obs = obs.copy()
            if obs.index.name is None:
                obs.index.name = dataset_col

        self.adata = adata
        self.dataset_col = dataset_col
        self.obs_columns = obs_columns or []
        self.source = source
        self.name = name
        self.meta = meta or {}
        self.neighborhood_collections = neighborhood_collections or {}

        collection_provenance = {"source": source} if source is not None else {}
        collection_provenance.update(provenance or {})
        collection_uns = {"dataset_col": dataset_col}
        if name is not None:
            collection_uns["name"] = name
        collection_uns.update(self.meta)
        collection_uns.update(uns or {})

        super().__init__(
            obs=obs,
            mod=mod or {},
            mdata=mdata,
            relations=relations or {},
            hierarchies=hierarchies or {},
            provenance=collection_provenance,
            uns=collection_uns,
            collection_type="dataset",
            obs_entity_type="dataset",
        )

    def construct_population_space(
        self,
        category: str = "leiden",
        key: str = "population",
        output: str = "percentage",
        min_cells: int = 1,
        adata: AnnData | None = None,
    ) -> AnnData:
        """Construct and attach a dataset-by-population modality to ``self.mod``."""
        source_adata = adata if adata is not None else self.adata
        if source_adata is None:
            raise ValueError("adata is required to construct a population space")
        resolved_dataset_col = _resolve_dataset_col(self, self.dataset_col)
        space = _population_space_from_adata(
            source_adata,
            dataset_col=resolved_dataset_col,
            category=category,
            output=output,
            min_cells=min_cells,
        )
        space = _align_mod_to_dataset(space, self)
        return self.add_mod(key, space, entity_type="cell_population")


def _population_space_from_adata(
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
        adata_pop.uns[color_key] = [color_dict.get(str(c), "#808080") for c in adata_pop.var_names]

    return adata_pop


def from_adata(
    adata: AnnData,
    dataset_col: str = "sample_id",
    obs_columns: list[str] | None = None,
    population_category: str | None = None,
    population_output: str = "percentage",
    population_key: str = "population",
    min_cells: int = 1,
    provenance: dict[str, Any] | None = None,
    uns: dict[str, Any] | None = None,
) -> DatasetCollection:
    """Create a ``DatasetCollection`` from cell-level AnnData metadata.

    This constructor builds the canonical dataset ``obs`` table. When
    ``population_category`` is provided, it also attaches a dataset-by-population
    space under ``population_key``.
    """
    dataset = DatasetCollection(
        adata,
        dataset_col=dataset_col,
        obs_columns=obs_columns,
        provenance=provenance or {},
        uns=uns,
    )

    if population_category is not None:
        dataset.construct_population_space(
            category=population_category,
            key=population_key,
            output=population_output,
            min_cells=min_cells,
        )

    return dataset
