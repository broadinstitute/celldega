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


def _source_payload(source: str | dict[str, Any], dataset_col: str) -> dict[str, Any]:
    payload = dict(source) if isinstance(source, dict) else {"uri": str(source)}
    payload.setdefault("obs_entity_type", "cell")
    payload.setdefault("source_obs_key", dataset_col)
    payload.setdefault("collection_obs_key", dataset_col)
    return payload


def _slug(value: Any) -> str:
    text = str(value).strip().lower()
    chars = [char if char.isalnum() else "_" for char in text]
    slug = "_".join(part for part in "".join(chars).split("_") if part)
    return slug or "category"


def _matrix_from_adata(adata: AnnData, layer: str | None) -> Any:
    if layer is None:
        return adata.X
    if layer not in adata.layers:
        raise ValueError(f"adata.layers missing requested layer '{layer}'")
    return adata.layers[layer]


def _as_1d(values: Any) -> np.ndarray:
    return np.asarray(values).ravel()


def _normalize_rows(values: np.ndarray, normalization: str | None) -> np.ndarray:
    if normalization is None:
        return values

    norm = normalization.lower().replace("-", "_").replace(" ", "_")
    if norm in {"none", "raw"}:
        return values
    if norm not in {"cpm", "log1p_cpm"}:
        raise ValueError("normalization must be None, 'cpm', or 'log1p_cpm'")

    normalized = values.astype(float, copy=True)
    library_size = normalized.sum(axis=1)
    valid = library_size > 0
    normalized[~valid, :] = 0
    if valid.any():
        normalized[valid, :] = normalized[valid, :] / library_size[valid, None] * 1_000_000
    if norm == "log1p_cpm":
        normalized = np.log1p(normalized)
    return normalized


def _category_signature_from_adata(
    adata: AnnData,
    dataset_col: str,
    category: str,
    value: Any,
    layer: str | None = None,
    aggregate: str = "sum",
    normalization: str | None = "log1p_cpm",
    min_cells: int = 1,
) -> AnnData:
    if dataset_col not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{dataset_col}' column")
    if category not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{category}' column")
    if aggregate not in {"sum", "mean"}:
        raise ValueError("aggregate must be 'sum' or 'mean'")

    category_values = adata.obs[category].astype(str)
    selected = category_values == str(value)
    if not selected.any():
        raise ValueError(f"No cells found where adata.obs['{category}'] == {value!r}")

    target = adata[selected.to_numpy(), :]
    matrix = _matrix_from_adata(target, layer)
    dataset_labels = target.obs[dataset_col].astype(str).to_numpy()
    dataset_ids = pd.Index(pd.unique(dataset_labels), name=dataset_col)

    kept_ids: list[str] = []
    vectors: list[np.ndarray] = []
    n_cells: list[int] = []
    for dataset_id in dataset_ids:
        mask = dataset_labels == dataset_id
        count = int(mask.sum())
        if count < min_cells:
            continue

        group = matrix[mask, :]
        vector = group.sum(axis=0) if aggregate == "sum" else group.mean(axis=0)
        kept_ids.append(str(dataset_id))
        vectors.append(_as_1d(vector))
        n_cells.append(count)

    values = np.vstack(vectors) if vectors else np.zeros((0, target.n_vars), dtype=float)
    values = _normalize_rows(values, normalization)

    obs = pd.DataFrame(index=pd.Index(kept_ids, name=dataset_col))
    obs[dataset_col] = obs.index.astype(str)
    obs["cell_count"] = n_cells

    var = target.var.copy()
    var.index = target.var_names.astype(str)
    if "gene" not in var.columns:
        var["gene"] = var.index.astype(str)

    return AnnData(
        X=values,
        obs=obs,
        var=var,
        uns={
            "feature_type": "dataset_signature",
            "dataset_col": dataset_col,
            "category": category,
            "value": str(value),
            "layer": layer,
            "aggregate": aggregate,
            "normalization": normalization,
        },
    )


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
        if source is not None:
            collection_uns.setdefault("sources", {})
            collection_uns["sources"].setdefault("cells", _source_payload(source, dataset_col))

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

    def calc_dataset_by_pop(
        self,
        adata: AnnData,
        category: str = "leiden",
        key: str = "population",
        output: str = "proportion",
        min_cells: int = 1,
        dataset_col: str | None = None,
    ) -> None:
        """Calculate and attach a dataset-by-population modality to ``self.mod``."""
        _calc_dataset_by_pop(
            self,
            adata=adata,
            dataset_col=dataset_col,
            category=category,
            key=key,
            output=output,
            min_cells=min_cells,
        )

    def calc_dataset_signature(
        self,
        adata: AnnData,
        category: str,
        value: Any,
        key: str | None = None,
        layer: str | None = None,
        aggregate: str = "sum",
        normalization: str | None = "log1p_cpm",
        min_cells: int = 1,
        dataset_col: str | None = None,
        var_entity_type: str = "gene",
    ) -> None:
        """Calculate and attach a dataset-by-feature signature for one category value."""
        resolved_dataset_col = _resolve_dataset_col(self, dataset_col or self.dataset_col)
        space = _category_signature_from_adata(
            adata,
            dataset_col=resolved_dataset_col,
            category=category,
            value=value,
            layer=layer,
            aggregate=aggregate,
            normalization=normalization,
            min_cells=min_cells,
        )
        space = _align_mod_to_dataset(space, self)
        self.add_mod(
            key or f"{_slug(value)}_signature",
            space,
            var_entity_type=var_entity_type,
        )


def _population_space_from_adata(
    adata: AnnData,
    dataset_col: str = "sample_id",
    category: str = "leiden",
    output: str = "proportion",
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
        output: ``"proportion"`` for within-dataset fractions or ``"counts"``
            for raw cell counts.
        min_cells: Minimum number of cells required to keep a dataset row.

    Returns:
        AnnData with datasets as observations and populations as variables.
    """
    if output not in {"proportion", "counts"}:
        raise ValueError("output must be 'proportion' or 'counts'")
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

    if output == "proportion":
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


def _calc_dataset_by_pop(
    dataset: DatasetCollection,
    adata: AnnData,
    dataset_col: str | None = None,
    category: str = "leiden",
    output: str = "proportion",
    min_cells: int = 1,
    key: str = "population",
) -> None:
    """Calculate a dataset-by-population feature space.

    The result is attached to ``dataset.mod[key]`` and the function returns
    ``None``.
    """
    resolved_dataset_col = _resolve_dataset_col(dataset, dataset_col or dataset.dataset_col)
    space = _population_space_from_adata(
        adata,
        dataset_col=resolved_dataset_col,
        category=category,
        output=output,
        min_cells=min_cells,
    )
    space = _align_mod_to_dataset(space, dataset)
    dataset.add_mod(key, space, var_entity_type="cell_population")
