"""Dataset-level collection and feature-space constructors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anndata import AnnData, read_h5ad
import numpy as np
import pandas as pd

from celldega.collections import CelldegaCollection, HierarchyResult


__all__ = [
    "Dataset",
    "calc_dataset_by_pop",
    "construct_population_space",
    "from_adata",
    "read",
]

_CELLDEGA_DATASET_ENCODING = "celldega.dataset"
_CELLDEGA_DATASET_VERSION = "0.1.0"
_MANIFEST_KEY = "_celldega_manifest"
_SPACES_KEY = "_celldega_spaces"
_RELATIONS_KEY = "_celldega_relations"
_HIERARCHIES_KEY = "_celldega_hierarchies"
_METADATA_KEY = "_celldega_metadata"


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


def _align_space_to_dataset(adata: AnnData, dataset: CelldegaCollection) -> AnnData:
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
    raise ValueError(
        "dataset_col must be provided when it cannot be inferred from the dataset"
    )


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


def _hierarchy_to_mapping(hierarchy: HierarchyResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": hierarchy.id,
        "input_kind": hierarchy.input_kind,
        "input_key": hierarchy.input_key,
        "method": hierarchy.method,
        "params": hierarchy.params,
        "preprocessing": hierarchy.preprocessing,
        "provenance": hierarchy.provenance,
        "uns": hierarchy.uns,
    }
    if hierarchy.labels is not None:
        payload["labels"] = hierarchy.labels.rename("label").to_frame()
    if hierarchy.leaf_order is not None:
        payload["leaf_order"] = hierarchy.leaf_order
    if hierarchy.linkage_matrix is not None:
        payload["linkage_matrix"] = np.asarray(hierarchy.linkage_matrix)
    if hierarchy.graph_key is not None:
        payload["graph_key"] = hierarchy.graph_key
    return payload


def _hierarchies_to_mapping(
    hierarchies: dict[str, HierarchyResult],
) -> dict[str, dict[str, Any]]:
    return {key: _hierarchy_to_mapping(value) for key, value in hierarchies.items()}


def _hierarchy_from_mapping(payload: dict[str, Any]) -> HierarchyResult:
    labels = payload.get("labels")
    if isinstance(labels, pd.DataFrame):
        labels = labels.iloc[:, 0]
    elif labels is not None and not isinstance(labels, pd.Series):
        labels = pd.Series(labels)

    leaf_order = payload.get("leaf_order")
    if leaf_order is not None and not isinstance(leaf_order, list):
        leaf_order = list(leaf_order)

    return HierarchyResult(
        id=str(payload["id"]),
        input_kind=str(payload["input_kind"]),
        input_key=str(payload["input_key"]),
        method=str(payload["method"]),
        params=dict(payload.get("params", {})),
        preprocessing=dict(payload.get("preprocessing", {})),
        labels=labels,
        leaf_order=leaf_order,
        linkage_matrix=payload.get("linkage_matrix"),
        graph_key=payload.get("graph_key"),
        provenance=dict(payload.get("provenance", {})),
        uns=dict(payload.get("uns", {})),
    )


def _hierarchies_from_mapping(payload: dict[str, Any]) -> dict[str, HierarchyResult]:
    return {key: _hierarchy_from_mapping(dict(value)) for key, value in payload.items()}


class Dataset(CelldegaCollection):
    """Dataset-level collection with convenience space constructors.

    ``Dataset`` is the dataset-level Celldega collection. Its ``obs`` table is
    the canonical dataset/sample axis, and feature constructors attach aligned
    ``AnnData`` spaces directly to ``self.spaces``.
    """

    def __init__(
        self,
        adata: AnnData | None = None,
        dataset_col: str = "sample_id",
        obs_columns: list[str] | None = None,
        obs: pd.DataFrame | None = None,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
        spaces: dict[str, AnnData] | None = None,
        relations: dict[str, Any] | None = None,
        hierarchies: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        uns: dict[str, Any] | None = None,
        neighborhood_collections: dict[str, Any] | None = None,
    ) -> None:
        if obs is None:
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
        self.collection_type = "dataset"
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
            spaces=spaces or {},
            relations=relations or {},
            hierarchies=hierarchies or {},
            provenance=collection_provenance,
            uns=collection_uns,
        )

    def construct_population_space(
        self,
        category: str = "leiden",
        key: str = "population",
        output: str = "percentage",
        min_cells: int = 1,
        adata: AnnData | None = None,
    ) -> AnnData:
        """Construct and attach a dataset-by-population space to ``self.spaces``."""
        source_adata = adata if adata is not None else self.adata
        if source_adata is None:
            raise ValueError("adata is required to construct a population space")
        return construct_population_space(
            self,
            source_adata,
            dataset_col=self.dataset_col,
            category=category,
            key=key,
            output=output,
            min_cells=min_cells,
        )

    def write(
        self,
        filename: str | Path,
        *,
        convert_strings_to_categoricals: bool = True,
        compression: str | None = None,
        compression_opts: Any | None = None,
        as_dense: tuple[str, ...] = (),
    ) -> None:
        """Write this dataset object to a Celldega H5AD file.

        The root H5AD object stores the dataset-level ``obs`` table. Celldega
        stores named spaces, relations, and metadata in reserved ``uns`` keys so
        the file remains readable by ``anndata.read_h5ad`` while
        ``dega.dataset.read`` can reconstruct the full ``Dataset``.
        """
        if self.neighborhood_collections:
            raise NotImplementedError(
                "Dataset.write does not yet serialize linked neighborhood collections"
            )

        root = AnnData(
            X=np.empty((len(self.obs), 0), dtype=np.float32),
            obs=self.obs.copy(),
            var=pd.DataFrame(index=pd.Index([], name="feature")),
            uns={
                _MANIFEST_KEY: {
                    "encoding_type": _CELLDEGA_DATASET_ENCODING,
                    "encoding_version": _CELLDEGA_DATASET_VERSION,
                    "dataset_col": self.dataset_col,
                    "collection_type": self.collection_type,
                    "space_keys": list(self.spaces),
                    "relation_keys": list(self.relations),
                    "hierarchy_keys": list(self.hierarchies),
                },
                _SPACES_KEY: self.spaces,
                _RELATIONS_KEY: self.relations,
                _HIERARCHIES_KEY: _hierarchies_to_mapping(self.hierarchies),
                _METADATA_KEY: {
                    "provenance": self.provenance,
                    "uns": self.uns,
                },
            },
        )
        if convert_strings_to_categoricals:
            root.strings_to_categoricals()
            for space in self.spaces.values():
                space.strings_to_categoricals()
        root.write(
            filename,
            compression=compression,
            compression_opts=compression_opts,
            as_dense=as_dense,
        )


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


def construct_population_space(
    dataset: CelldegaCollection,
    adata: AnnData,
    dataset_col: str | None = None,
    category: str = "leiden",
    key: str = "population",
    output: str = "percentage",
    min_cells: int = 1,
) -> AnnData:
    """Construct and attach a dataset-by-population space to a dataset object.

    Args:
        dataset: Dataset object whose ``obs.index`` defines the dataset row axis.
        adata: Cell-level AnnData. ``adata.obs`` must contain ``dataset_col``
            and ``category``.
        dataset_col: Observation column identifying dataset-level units. When
            omitted, the function tries ``dataset.uns["dataset_col"]``, the
            dataset index name, and common columns such as ``"sample_id"``.
        category: Observation column identifying the cell population, cell type,
            cell state, or cluster.
        key: Space key in ``dataset.spaces``.
        output: ``"percentage"`` for within-dataset fractions or ``"counts"``
            for raw cell counts.
        min_cells: Minimum number of cells required to keep a dataset row before
            alignment back to the full dataset.

    Returns:
        The aligned AnnData stored at ``dataset.spaces[key]``.
    """
    resolved_dataset_col = _resolve_dataset_col(dataset, dataset_col)
    space = calc_dataset_by_pop(
        adata,
        dataset_col=resolved_dataset_col,
        category=category,
        output=output,
        min_cells=min_cells,
    )
    space = _align_space_to_dataset(space, dataset)
    dataset.spaces[key] = space
    return space


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
) -> Dataset:
    """Create a ``Dataset`` from cell-level AnnData metadata.

    This constructor builds the canonical dataset ``obs`` table. When
    ``population_category`` is provided, it also attaches a dataset-by-population
    space under ``population_key``.
    """
    dataset = Dataset(
        adata,
        dataset_col=dataset_col,
        obs_columns=obs_columns,
        provenance=provenance or {},
        uns=uns,
    )

    if population_category is not None:
        construct_population_space(
            dataset,
            adata,
            dataset_col=dataset_col,
            category=population_category,
            key=population_key,
            output=population_output,
            min_cells=min_cells,
        )

    return dataset


def read(filename: str | Path) -> Dataset:
    """Read a Celldega dataset H5AD file written by ``Dataset.write``."""
    root = read_h5ad(filename)
    manifest = dict(root.uns.get(_MANIFEST_KEY, {}))
    encoding_type = manifest.get("encoding_type")
    if encoding_type != _CELLDEGA_DATASET_ENCODING:
        raise ValueError(
            f"{filename!s} is not a Celldega dataset H5AD file "
            f"(encoding_type={encoding_type!r})"
        )

    metadata = dict(root.uns.get(_METADATA_KEY, {}))
    return Dataset(
        adata=None,
        obs=root.obs.copy(),
        dataset_col=str(manifest.get("dataset_col", root.obs.index.name or "sample_id")),
        spaces=dict(root.uns.get(_SPACES_KEY, {})),
        relations=dict(root.uns.get(_RELATIONS_KEY, {})),
        hierarchies=_hierarchies_from_mapping(dict(root.uns.get(_HIERARCHIES_KEY, {}))),
        provenance=dict(metadata.get("provenance", {})),
        uns=dict(metadata.get("uns", {})),
    )
