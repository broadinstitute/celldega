"""Independent unsupervised clustering and marker ranking for each CCLE assay."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import warnings

from anndata import AnnData
import numpy as np
import pandas as pd
import scanpy as sc

from celldega.clust import Matrix
from celldega.dataset import DatasetCollection

from .prepare import apply_modality_colors, inherit_annotation_colors


@dataclass(frozen=True)
class HierarchicalConfig:
    """Configuration for the primary Ward Clustergram analysis."""

    n_top_features: int = 2_000
    n_meta_clusters: int = 8


def _values(adata: AnnData) -> np.ndarray:
    values = adata.X.toarray() if hasattr(adata.X, "toarray") else np.asarray(adata.X)
    if not np.isfinite(values).all():
        raise ValueError("resolve missing values explicitly before clustering")
    return values.astype(np.float64, copy=False)


def _variable_mask(values: np.ndarray, n_top_features: int) -> np.ndarray:
    variance = values.var(axis=0)
    usable = np.isfinite(variance) & (variance > 0)
    if usable.sum() < 2:
        raise ValueError("fewer than two variable features remain")
    if n_top_features >= usable.sum():
        return usable
    selected = np.argpartition(variance, -n_top_features)[-n_top_features:]
    mask = np.zeros(values.shape[1], dtype=bool)
    mask[selected] = True
    return mask & usable


def _clustergram_input(adata: AnnData, col_attributes: tuple[str, ...]) -> AnnData:
    """Avoid passing unrelated mixed-type model metadata into a Matrix view."""
    display = adata.copy()
    visible = [key for key in col_attributes if key in display.obs]
    display.obs = display.obs.loc[:, visible].copy()
    for key in visible:
        values = display.obs[key].astype("string").fillna("unknown").astype(str)
        if isinstance(display.obs[key].dtype, pd.CategoricalDtype):
            categories = display.obs[key].cat.categories.astype(str).tolist()
            if "unknown" not in categories:
                categories.append("unknown")
            display.obs[key] = pd.Categorical(values, categories=categories)
        else:
            display.obs[key] = values
    return display


def hierarchical_clustergram(
    adata: AnnData,
    config: HierarchicalConfig | None = None,
    *,
    col_attributes: tuple[str, ...] = (
        "OncotreeLineage",
        "OncotreePrimaryDisease",
        "OncotreeSubtype",
    ),
) -> tuple[AnnData, Matrix]:
    """Build the primary Ward Clustergram and cut its own column dendrogram.

    The returned Matrix is the clustering authority.  The flat labels attached
    to the AnnData are cut from that exact Ward dendrogram, rather than from a
    separately computed tree.  The full dendrogram remains available for
    interactive exploration; ``n_meta_clusters`` only selects one marker view.
    """
    config = config or HierarchicalConfig()
    if adata.n_obs < 3:
        raise ValueError("at least three cell lines are needed for clustering")
    result = adata.copy()
    mask = _variable_mask(_values(result), config.n_top_features)
    result.var["used_for_hierarchical_clustering"] = mask
    discovery = _clustergram_input(result[:, mask], col_attributes)
    selected_col_attributes = [key for key in col_attributes if key in discovery.obs]
    matrix = Matrix(discovery, col_attr=selected_col_attributes, row_attr=["modality"])
    matrix.norm("row", by="zscore")
    matrix.cluster(dist_type="euclidean", linkage_type="ward")
    key = f"hierarchical_k{config.n_meta_clusters}"
    labels = matrix.cut_tree(axis="col", n_clusters=config.n_meta_clusters).astype(str)
    result.obs[key] = pd.Categorical(labels.reindex(result.obs_names))
    result.uns["hierarchical_clustergram"] = {
        "cluster_key": key,
        "config": asdict(config),
        "matrix_features": int(discovery.n_vars),
        "normalization": "feature z-score for Ward dendrogram and display",
        "distance": "euclidean",
        "linkage": "ward",
    }
    return result, matrix


def rank_cluster_markers(adata: AnnData, groupby: str, *, key_added: str | None = None) -> pd.DataFrame:
    """Rank markers and add source-scale median effects to Scanpy statistics.

    Wilcoxon rank-sum is used for the test.  The returned median difference is
    more meaningful than generic log-fold changes for these three continuous,
    differently normalized assays.
    """
    if groupby not in adata.obs:
        raise KeyError(f"{groupby!r} is not in adata.obs")
    if adata.obs[groupby].isna().any():
        raise ValueError(f"{groupby!r} contains missing labels")
    groups = adata.obs[groupby].astype("category")
    if groups.nunique() < 2:
        raise ValueError("marker ranking needs at least two groups")
    key = key_added or f"rank_genes_groups__{groupby}"
    # Scanpy also materializes a generic log-fold-change column. These source
    # scales can contain negative values, so that field is neither stable nor
    # scientifically comparable across assays; retain Wilcoxon statistics and
    # calculate explicit median effects below instead.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="invalid value encountered in log2", category=RuntimeWarning)
        warnings.filterwarnings("ignore", message="invalid value encountered in divide", category=RuntimeWarning)
        sc.tl.rank_genes_groups(
            adata,
            groupby=groupby,
            method="wilcoxon",
            tie_correct=True,
            use_raw=False,
            key_added=key,
        )
    values, features = _values(adata), pd.Index(adata.var_names.astype(str))
    tables: list[pd.DataFrame] = []
    for group in groups.cat.categories:
        ranked = sc.get.rank_genes_groups_df(adata, group=str(group), key=key)
        ranked = ranked.drop(columns=["logfoldchanges"], errors="ignore")
        in_group = np.asarray(groups == group)
        effects = pd.DataFrame(
            {
                "names": features,
                "median_delta": np.median(values[in_group], axis=0) - np.median(values[~in_group], axis=0),
                "median_group": np.median(values[in_group], axis=0),
            }
        )
        ranked = ranked.merge(effects, on="names", how="left", validate="one_to_one")
        ranked.insert(0, "group", str(group))
        ranked.insert(1, "rank", np.arange(1, len(ranked) + 1))
        tables.append(ranked)
    markers = pd.concat(tables, ignore_index=True)
    markers.attrs["rank_genes_groups_key"] = key
    markers.attrs["median_delta"] = "median(group) - median(all other groups), original assay scale"
    return markers


def marker_clustergram(
    adata: AnnData,
    *,
    levels: tuple[int, ...] = (5, 10, 20),
    col_attributes: tuple[str, ...] = (
        "OncotreeLineage",
        "OncotreePrimaryDisease",
        "OncotreeSubtype",
    ),
) -> Matrix:
    """Create a marker-slider Clustergram from a previously ranked tree cut.

    This preserves the selected discovery features used for the base Ward tree,
    attaches the Scanpy ranks, and precomputes the displayed top-marker views.
    Each slider level selects top markers per dendrogram-derived meta-cluster.
    """
    if "rank_genes_groups" not in adata.uns:
        raise ValueError("run rank_cluster_markers(..., key_added='rank_genes_groups') first")
    if "used_for_hierarchical_clustering" not in adata.var:
        raise ValueError("run hierarchical_clustergram first")
    visual = _clustergram_input(
        adata[:, adata.var["used_for_hierarchical_clustering"].to_numpy()],
        col_attributes,
    )
    attributes = [key for key in col_attributes if key in visual.obs]
    matrix = Matrix(visual, col_attr=attributes, row_attr=["modality"])
    matrix.norm("row", by="zscore")
    matrix.cluster(
        dist_type="euclidean",
        linkage_type="ward",
        view="rank_genes_groups",
        levels=list(levels),
    )
    return matrix


def gene_modules_from_clustergram(matrix: Matrix, n_modules: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cut the gene-side tree and score each co-varying module per model.

    Scores are means of feature z-scores already used by the Clustergram. They
    are descriptive program activities, not independently fitted latent factors.
    """
    labels = matrix.cut_tree(axis="row", n_clusters=n_modules).astype(str)
    membership = pd.DataFrame(
        {"feature_id": labels.index.astype(str), "gene_module": labels.to_numpy()}
    )
    values = matrix.data.copy()
    values["gene_module"] = labels.reindex(values.index).to_numpy()
    scores = values.groupby("gene_module", sort=True).mean().T
    scores.index.name = "ModelID"
    return membership, scores


def representative_module_features(
    matrix: Matrix,
    membership: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    """Rank genes by correlation with the mean profile of their row-tree module."""
    required = {"feature_id", "gene_module"}
    if missing := required.difference(membership.columns):
        raise KeyError(f"membership lacks required columns: {sorted(missing)}")
    rows: list[pd.DataFrame] = []
    for module, frame in membership.groupby("gene_module", observed=True):
        feature_ids = pd.Index(frame["feature_id"].astype(str))
        profiles = matrix.data.reindex(feature_ids).T
        activity = scores.loc[profiles.index, str(module)]
        correlation = profiles.corrwith(activity)
        table = pd.DataFrame(
            {
                "gene_module": str(module),
                "feature_id": correlation.index.astype(str),
                "module_correlation": correlation.to_numpy(),
            }
        ).sort_values("module_correlation", ascending=False, na_position="last")
        table["rank_within_module"] = range(1, len(table) + 1)
        rows.append(table)
    return pd.concat(rows, ignore_index=True)


def stack_modalities(
    collection: DatasetCollection,
    modalities: tuple[str, ...],
    model_ids: pd.Index,
    *,
    n_top_features: int | dict[str, int] = 1_000,
) -> AnnData:
    """Create a matched, feature-stacked AnnData for a multimodal Clustergram.

    Each modality first selects variable features on the requested shared cohort.
    `Matrix.norm("row", by="zscore")` then gives every displayed feature equal
    weight, while `var["modality"]` preserves the assay category in the row
    annotations.  The function never imputes a missing assay: callers supply
    the explicit matched `model_ids` cohort.
    """
    if not modalities:
        raise ValueError("at least one modality is required")
    unknown = sorted(set(modalities).difference(collection.mod))
    if unknown:
        raise KeyError(f"unknown modalities: {unknown}; available: {list(collection.mod)}")
    models = pd.Index(model_ids.astype(str), name="ModelID")
    if models.has_duplicates:
        raise ValueError("model_ids must be unique")

    arrays: list[np.ndarray] = []
    feature_tables: list[pd.DataFrame] = []
    for modality in modalities:
        adata = collection.mod[modality]
        absent = models.difference(pd.Index(adata.obs_names.astype(str)))
        if len(absent):
            raise ValueError(f"{modality} is missing {len(absent)} requested models")
        selected = adata[models].copy()
        count = n_top_features.get(modality, selected.n_vars) if isinstance(n_top_features, dict) else n_top_features
        mask = _variable_mask(_values(selected), count)
        arrays.append(_values(selected)[:, mask])
        feature_ids = selected.var_names[mask].astype(str)
        feature_tables.append(
            pd.DataFrame(
                {
                    "feature_id": feature_ids,
                    "original_feature_id": feature_ids,
                    "modality": modality,
                },
                index=[f"{modality}:{feature}" for feature in feature_ids],
            )
        )

    obs = collection.mod[modalities[0]].obs.reindex(models).copy()
    stacked = AnnData(
        X=np.hstack(arrays).astype(np.float32, copy=False),
        obs=obs,
        var=pd.concat(feature_tables),
    )
    inherit_annotation_colors(stacked, collection.mod[modalities[0]])
    return apply_modality_colors(stacked)


def marker_jaccard(
    markers: pd.DataFrame,
    group_columns: list[str],
    *,
    top_n: int = 20,
) -> pd.DataFrame:
    """Compare marker sets across independently discovered groups."""
    needed = {*group_columns, "names", "rank"}
    missing = needed.difference(markers.columns)
    if missing:
        raise KeyError(f"marker table lacks required columns: {sorted(missing)}")
    groups: dict[tuple[object, ...], set[str]] = {}
    for key, frame in markers.loc[markers["rank"] <= top_n].groupby(group_columns, observed=True):
        normalized = key if isinstance(key, tuple) else (key,)
        groups[normalized] = set(frame["names"].astype(str))
    rows: list[dict[str, object]] = []
    keys = list(groups)
    for index, left in enumerate(keys):
        for right in keys[index + 1 :]:
            union = groups[left] | groups[right]
            if not union:
                continue
            row: dict[str, object] = {
                "jaccard": len(groups[left] & groups[right]) / len(union),
                "n_shared": len(groups[left] & groups[right]),
                "shared_markers": ", ".join(sorted(groups[left] & groups[right])),
            }
            row.update({f"left_{name}": value for name, value in zip(group_columns, left, strict=True)})
            row.update({f"right_{name}": value for name, value in zip(group_columns, right, strict=True)})
            rows.append(row)
    columns = [
        "jaccard",
        "n_shared",
        "shared_markers",
        *[f"{side}_{name}" for side in ("left", "right") for name in group_columns],
    ]
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["jaccard", "n_shared"], ascending=False
    ).reset_index(drop=True)


def annotation_table(adata: AnnData, cluster_key: str, annotation: str) -> pd.DataFrame:
    """Describe a discovered cluster without using annotation in clustering."""
    if cluster_key not in adata.obs or annotation not in adata.obs:
        raise KeyError(f"need {cluster_key!r} and {annotation!r} in adata.obs")
    return pd.crosstab(adata.obs[cluster_key], adata.obs[annotation], normalize="index")
