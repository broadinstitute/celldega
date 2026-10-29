"""Dataset-level collection and modality constructors."""

from __future__ import annotations

from typing import Any

from anndata import AnnData
from mudata import MuData
import numpy as np
import pandas as pd

from celldega.collection import CelldegaCollection


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
    missing_rows = np.isnan(normalized).all(axis=1)
    library_size = normalized.sum(axis=1)
    valid = (library_size > 0) & ~missing_rows
    normalized[(~valid) & ~missing_rows, :] = 0
    if valid.any():
        normalized[valid, :] = normalized[valid, :] / library_size[valid, None] * 1_000_000
    if norm == "log1p_cpm":
        normalized = np.log1p(normalized)
    normalized[missing_rows, :] = np.nan
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
    dataset_ids: pd.Index | None = None,
    missing_datasets: str = "nan",
) -> AnnData:
    if dataset_col not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{dataset_col}' column")
    if category not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{category}' column")
    if aggregate not in {"sum", "mean"}:
        raise ValueError("aggregate must be 'sum' or 'mean'")
    if missing_datasets not in {"nan", "raise"}:
        raise ValueError("missing_datasets must be 'nan' or 'raise'")

    if dataset_ids is None:
        dataset_ids = pd.Index(pd.unique(adata.obs[dataset_col].astype(str)), name=dataset_col)
    else:
        dataset_ids = pd.Index(dataset_ids.astype(str), name=dataset_col)

    raw_category_values = adata.obs[category]
    category_values = raw_category_values.astype(str)
    selected = category_values == str(value)
    if not selected.any():
        available = sorted(raw_category_values.dropna().astype(str).unique())
        preview = ", ".join(repr(item) for item in available[:10]) or "<none>"
        suffix = "" if len(available) <= 10 else f", ... ({len(available)} total)"
        if missing_datasets == "raise":
            raise ValueError(
                f"No cells found where adata.obs['{category}'] == {value!r}. "
                f"Available values: {preview}{suffix}"
            )

        obs = pd.DataFrame(index=dataset_ids)
        obs[dataset_col] = obs.index.astype(str)
        obs["cell_count"] = 0
        var = adata.var.copy()
        var.index = adata.var_names.astype(str)
        if "gene" not in var.columns:
            var["gene"] = var.index.astype(str)
        return AnnData(
            X=np.full((len(dataset_ids), adata.n_vars), np.nan, dtype=float),
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
                "missing_datasets": missing_datasets,
                "available_values": available,
            },
        )

    target = adata[selected.to_numpy(), :]
    matrix = _matrix_from_adata(target, layer)
    dataset_labels = target.obs[dataset_col].astype(str).to_numpy()
    counts_by_dataset = (
        pd.Series(dataset_labels).value_counts().reindex(dataset_ids).fillna(0).astype(int)
    )

    missing_ids = counts_by_dataset[counts_by_dataset < min_cells].index
    if len(missing_ids) and missing_datasets == "raise":
        preview = ", ".join(map(str, missing_ids[:10]))
        suffix = "" if len(missing_ids) <= 10 else f", ... ({len(missing_ids)} total)"
        raise ValueError(
            f"Some datasets have fewer than {min_cells} cells where "
            f"adata.obs['{category}'] == {value!r}: {preview}{suffix}"
        )

    values = np.full((len(dataset_ids), target.n_vars), np.nan, dtype=float)
    for row_idx, dataset_id in enumerate(dataset_ids):
        mask = dataset_labels == dataset_id
        count = int(mask.sum())
        if count < min_cells:
            continue

        group = matrix[mask, :]
        vector = group.sum(axis=0) if aggregate == "sum" else group.mean(axis=0)
        values[row_idx, :] = _as_1d(vector)
    values = _normalize_rows(values, normalization)

    obs = pd.DataFrame(index=dataset_ids)
    obs[dataset_col] = obs.index.astype(str)
    obs["cell_count"] = counts_by_dataset.values

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
            "missing_datasets": missing_datasets,
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
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
    ) -> None:
        """Build a dataset-level collection.

        The dataset/sample observation axis is established one of three ways:
        from a pre-built ``mdata`` (``dataset_col`` recovered from its metadata),
        from an explicit ``obs`` table, or — most commonly — by **binning
        cell-level ``adata`` over ``dataset_col``** (one row per unique dataset,
        with an ``n_cells`` count and the first value of each ``obs_columns``).

        Args:
            adata: Cell-level ``AnnData`` to derive the dataset axis from
                (required when neither ``obs`` nor ``mdata`` is given).
            dataset_col: ``adata.obs`` column identifying the dataset/sample/
                patient unit; becomes the collection's observation index.
            obs_columns: Per-dataset metadata columns to carry over from
                ``adata.obs`` (first value per dataset).
            obs: Pre-built dataset observation table (alternative to ``adata``).
            mdata: Pre-built ``MuData`` to wrap (e.g. from ``read``).
            source: Source descriptor recorded in provenance and
                ``uns["sources"]["cells"]``.
            name: Optional collection name (stored in metadata).
            meta: Extra metadata merged into ``uns["celldega"]``.
            mod: Feature-space modalities to attach up front.
            relations: Square dataset-by-dataset matrices for ``mdata.obsp``.
            provenance: Free-form provenance metadata.
            uns: Extra Celldega metadata.

        Raises:
            ValueError: If ``adata`` is missing when ``obs``/``mdata`` are absent.
        """
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
            provenance=collection_provenance,
            uns=collection_uns,
            collection_type="dataset",
            obs_entity_type="dataset",
        )

    def calc_population(
        self,
        adata: AnnData,
        category: str = "leiden",
        modality_name: str = "population",
        output: str = "proportion",
        min_cells: int = 1,
        dataset_col: str | None = None,
    ) -> None:
        """Calculate a dataset-by-population modality and attach it to ``self.mod``.

        For each dataset, counts cells per ``category`` value and stores the
        result as a dataset (rows) by population (columns) feature matrix.

        Args:
            adata: Cell-level ``AnnData`` containing ``dataset_col`` and
                ``category`` in ``obs``.
            category: ``obs`` column naming the population/cell-type/cluster.
            modality_name: Key for the modality in ``self.mod``.
            output: ``"proportion"`` (within-dataset fractions) or ``"counts"``.
            min_cells: Minimum cells for a dataset row to be kept.
            dataset_col: Override the collection's dataset column; defaults to
                ``self.dataset_col``.

        Returns:
            ``None`` — the modality is attached to ``self.mod[modality_name]``.
        """
        _calc_dataset_by_pop(
            self,
            adata=adata,
            dataset_col=dataset_col,
            category=category,
            modality_name=modality_name,
            output=output,
            min_cells=min_cells,
        )

    def calc_signature(
        self,
        adata: AnnData,
        category: str,
        value: Any,
        modality_name: str | None = None,
        layer: str | None = None,
        aggregate: str = "sum",
        normalization: str | None = "log1p_cpm",
        min_cells: int = 1,
        missing_datasets: str = "nan",
        dataset_col: str | None = None,
        var_entity_type: str = "gene",
    ) -> None:
        """Calculate and attach a dataset-by-feature signature for one category value.

        Selects the cells where ``adata.obs[category] == value`` and aggregates
        their expression per dataset into a dataset (rows) by gene (columns)
        signature modality (a pseudobulk profile for that one population).

        Args:
            adata: Cell-level ``AnnData`` with ``dataset_col``, ``category``, and
                an expression matrix (``X`` or ``layer``).
            category: ``obs`` column to select on (e.g. ``"cell_type"``).
            value: The ``category`` value whose cells form the signature (e.g.
                ``"CD8 T"``).
            modality_name: Key for the modality; defaults to
                ``f"{slug(value)}_signature"``.
            layer: ``adata`` layer to aggregate; ``None`` uses ``adata.X``.
            aggregate: ``"sum"`` or ``"mean"`` across the selected cells.
            normalization: ``None``, ``"cpm"``, or ``"log1p_cpm"`` applied per
                dataset row.
            min_cells: Minimum selected cells for a dataset to get a real row.
            missing_datasets: ``"nan"`` keeps the full observation axis and marks
                datasets below ``min_cells`` (or with no selected cells) as
                ``NaN`` rows; ``"raise"`` rejects them instead.
            dataset_col: Override the collection's dataset column.
            var_entity_type: Entity type written to the modality's
                ``var["entity_type"]`` (default ``"gene"``).

        Returns:
            ``None`` — the modality is attached to ``self.mod``.
        """
        resolved_dataset_col = _resolve_dataset_col(self, dataset_col or self.dataset_col)
        modality = _category_signature_from_adata(
            adata,
            dataset_col=resolved_dataset_col,
            category=category,
            value=value,
            layer=layer,
            aggregate=aggregate,
            normalization=normalization,
            min_cells=min_cells,
            dataset_ids=self.obs.index,
            missing_datasets=missing_datasets,
        )
        self.add_mod(
            modality_name or f"{_slug(value)}_signature",
            modality,
            var_entity_type=var_entity_type,
        )


def _population_modality_from_adata(
    adata: AnnData,
    dataset_col: str = "sample_id",
    category: str = "leiden",
    output: str = "proportion",
    min_cells: int = 1,
) -> AnnData:
    """Calculate a dataset-by-population modality from cell metadata.

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
    modality_name: str = "population",
) -> None:
    """Calculate a dataset-by-population modality.

    The result is attached to ``dataset.mod[modality_name]`` and the function
    returns ``None``.
    """
    resolved_dataset_col = _resolve_dataset_col(dataset, dataset_col or dataset.dataset_col)
    modality = _population_modality_from_adata(
        adata,
        dataset_col=resolved_dataset_col,
        category=category,
        output=output,
        min_cells=min_cells,
    )
    dataset.add_mod(modality_name, modality, var_entity_type="cell_population")
