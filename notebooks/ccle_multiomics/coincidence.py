"""Cross-assay nearest-neighbor coincidence and marker-selected stacking."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from anndata import AnnData
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform

from celldega.dataset import DatasetCollection

from .prepare import apply_modality_colors, inherit_annotation_colors


def _shared_index(values_by_modality: Mapping[str, pd.DataFrame]) -> pd.Index:
    """Validate and return one ordered model axis shared by every assay."""
    if len(values_by_modality) < 2:
        raise ValueError("nearest-neighbor coincidence needs at least two modalities")
    first = next(iter(values_by_modality.values())).index.astype(str)
    if first.has_duplicates:
        raise ValueError("model identifiers must be unique")
    for modality, values in values_by_modality.items():
        index = values.index.astype(str)
        if not first.equals(index):
            raise ValueError(
                f"{modality!r} does not use the same ordered models; subset and reorder explicitly first"
            )
    return pd.Index(first, name="ModelID")


def _neighbor_adjacency(values: pd.DataFrame, n_neighbors: int) -> np.ndarray:
    """Return an undirected local-neighborhood graph from Euclidean distances."""
    n_models = len(values)
    if not 1 <= n_neighbors < n_models:
        raise ValueError("n_neighbors must be between 1 and n_models - 1")
    distances = squareform(pdist(values.to_numpy(dtype=np.float64, copy=False), metric="euclidean"))
    np.fill_diagonal(distances, np.inf)
    nearest = np.argpartition(distances, kth=n_neighbors - 1, axis=1)[:, :n_neighbors]
    adjacency = np.zeros((n_models, n_models), dtype=np.uint8)
    adjacency[np.arange(n_models)[:, None], nearest] = 1
    # "A is near B" is sufficient evidence for the pair; requiring reciprocal
    # rank would make local densities dominate the result.
    adjacency = np.maximum(adjacency, adjacency.T)
    np.fill_diagonal(adjacency, 0)
    return adjacency


def nearest_neighbor_coincidence(
    values_by_modality: Mapping[str, pd.DataFrame],
    *,
    n_neighbors: int,
    min_modalities: int = 2,
    n_permutations: int = 250,
    random_state: int = 0,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """Find model pairs that recur as local neighbors across assay spaces.

    The observed score is the number of unordered model pairs that are
    neighbors in at least ``min_modalities`` assays. The empirical null keeps
    each assay's neighborhood graph intact but independently permutes model
    labels for every non-anchor assay. It therefore asks whether the same cell
    lines coincide more often than expected from their assay-specific local
    graph structure alone.
    """
    model_ids = _shared_index(values_by_modality)
    modalities = list(values_by_modality)
    if not 2 <= min_modalities <= len(modalities):
        raise ValueError("min_modalities must be between 2 and the number of modalities")
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")

    adjacency_arrays = {
        modality: _neighbor_adjacency(values, n_neighbors) for modality, values in values_by_modality.items()
    }
    coincidence = np.zeros((len(model_ids), len(model_ids)), dtype=np.uint8)
    for adjacency in adjacency_arrays.values():
        coincidence += adjacency
    np.fill_diagonal(coincidence, 0)

    upper = np.triu_indices(len(model_ids), k=1)
    observed_score = int(np.count_nonzero(coincidence[upper] >= min_modalities))
    rng = np.random.default_rng(random_state)
    null_scores = np.empty(n_permutations, dtype=np.int32)
    anchor = adjacency_arrays[modalities[0]]
    for iteration in range(n_permutations):
        shuffled = anchor.copy()
        for modality in modalities[1:]:
            permutation = rng.permutation(len(model_ids))
            shuffled += adjacency_arrays[modality][permutation][:, permutation]
        null_scores[iteration] = np.count_nonzero(shuffled[upper] >= min_modalities)

    null_mean = float(null_scores.mean())
    null_std = float(null_scores.std(ddof=1))
    summary = pd.DataFrame(
        [
            {
                "n_models": len(model_ids),
                "modalities": ", ".join(modalities),
                "n_neighbors_per_assay": n_neighbors,
                "min_coincident_modalities": min_modalities,
                "n_permutations": n_permutations,
                "observed_coincident_pairs": observed_score,
                "null_mean_coincident_pairs": null_mean,
                "null_std_coincident_pairs": null_std,
                "z_score": (observed_score - null_mean) / null_std if null_std else np.nan,
                "empirical_p_value": (1 + np.count_nonzero(null_scores >= observed_score))
                / (n_permutations + 1),
            }
        ]
    )
    null = pd.DataFrame({"permutation": np.arange(1, n_permutations + 1), "coincident_pairs": null_scores})
    adjacency_frames = {
        modality: pd.DataFrame(adjacency, index=model_ids, columns=model_ids)
        for modality, adjacency in adjacency_arrays.items()
    }
    coincidence_frame = pd.DataFrame(coincidence, index=model_ids, columns=model_ids)
    return coincidence_frame, adjacency_frames, summary, null


def coincident_pair_table(
    coincidence: pd.DataFrame,
    adjacency_by_modality: Mapping[str, pd.DataFrame],
    *,
    min_modalities: int = 2,
) -> pd.DataFrame:
    """Return unordered recurring pairs with the assays supporting each edge."""
    ids = coincidence.index.astype(str)
    upper = np.triu_indices(len(ids), k=1)
    counts = coincidence.to_numpy()[upper]
    keep = counts >= min_modalities
    table = pd.DataFrame(
        {
            "ModelID_1": ids.to_numpy()[upper[0][keep]],
            "ModelID_2": ids.to_numpy()[upper[1][keep]],
            "n_coincident_modalities": counts[keep],
        }
    )
    for modality, adjacency in adjacency_by_modality.items():
        table[f"{modality}_neighbors"] = adjacency.to_numpy()[upper][keep].astype(bool)
    return table.sort_values(
        ["n_coincident_modalities", "ModelID_1", "ModelID_2"], ascending=[False, True, True]
    ).reset_index(drop=True)


def select_ranked_features(
    markers: pd.DataFrame,
    *,
    top_n_per_group: int = 15,
    max_features: int = 120,
    adjusted_p_value: float = 0.05,
) -> pd.DataFrame:
    """Choose a capped, provenance-preserving union of group marker features."""
    needed = {"group", "rank", "names", "scores", "pvals_adj"}
    missing = needed.difference(markers.columns)
    if missing:
        raise KeyError(f"marker table lacks required columns: {sorted(missing)}")
    candidates = markers.loc[
        (markers["rank"] <= top_n_per_group) & (markers["pvals_adj"] <= adjusted_p_value)
    ].copy()
    if candidates.empty:
        raise ValueError("no marker features passed the requested rank and adjusted-p-value filters")
    candidates["abs_score"] = candidates["scores"].abs()
    candidates = candidates.sort_values(
        ["rank", "pvals_adj", "abs_score", "names"], ascending=[True, True, False, True]
    )
    selected = candidates.drop_duplicates("names", keep="first").head(max_features).copy()
    selected = selected.rename(columns={"names": "feature_id", "group": "marker_group"})
    return selected.drop(columns="abs_score").reset_index(drop=True)


def stack_selected_features(
    collection: DatasetCollection,
    selections: Mapping[str, pd.DataFrame],
    model_ids: Sequence[str] | pd.Index,
) -> AnnData:
    """Stack rank-selected assay features and retain assay/marker provenance."""
    models = pd.Index(model_ids, dtype="string", name="ModelID")
    if models.has_duplicates:
        raise ValueError("model_ids must be unique")
    arrays: list[np.ndarray] = []
    feature_tables: list[pd.DataFrame] = []
    for modality, selection in selections.items():
        if modality not in collection.mod:
            raise KeyError(f"unknown modality: {modality}")
        if "feature_id" not in selection:
            raise KeyError(f"selection for {modality!r} lacks 'feature_id'")
        feature_ids = pd.Index(selection["feature_id"].astype(str))
        if feature_ids.has_duplicates:
            raise ValueError(f"selection for {modality!r} contains duplicate features")
        adata = collection.mod[modality]
        missing_models = models.difference(pd.Index(adata.obs_names.astype(str)))
        missing_features = feature_ids.difference(pd.Index(adata.var_names.astype(str)))
        if len(missing_models) or len(missing_features):
            raise ValueError(
                f"{modality!r} lacks {len(missing_models)} models or {len(missing_features)} selected features"
            )
        subset = adata[models, feature_ids].copy()
        values = subset.X.toarray() if hasattr(subset.X, "toarray") else np.asarray(subset.X)
        arrays.append(values.astype(np.float32, copy=False))
        metadata = selection.set_index("feature_id").reindex(feature_ids).drop(columns="modality", errors="ignore").copy()
        metadata.insert(0, "modality", modality)
        metadata.insert(0, "original_feature_id", feature_ids)
        metadata.index = [f"{modality}:{feature}" for feature in feature_ids]
        feature_tables.append(metadata)

    stacked = AnnData(
        X=np.hstack(arrays).astype(np.float32, copy=False),
        obs=collection.mod[next(iter(selections))].obs.reindex(models).copy(),
        var=pd.concat(feature_tables),
    )
    inherit_annotation_colors(stacked, collection.mod[next(iter(selections))])
    return apply_modality_colors(stacked)
