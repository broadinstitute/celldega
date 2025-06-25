"""Utility functions for Matrix operations."""

from typing import Any
import warnings

import numpy as np
import pandas as pd

from .constants import CONFIG, ERRORS, METRIC_FUNCTIONS


def get_data_hash(data: pd.DataFrame | None) -> int:
    """Fast hash computation for cache invalidation."""
    if data is None:
        return 0

    shape_hash = hash(data.shape)
    if data.size > CONFIG["large_matrix_threshold"]:
        # Sample-based hash for large matrices
        sample_size = min(CONFIG["sample_hash_size"], data.shape[0])
        sample_data = data.iloc[:sample_size, : min(10, data.shape[1])]
        content_hash = hash(sample_data.values.tobytes())
    else:
        content_hash = hash(data.values.tobytes())

    return hash((shape_hash, content_hash))


def validate_metadata(df: pd.DataFrame, meta_col: pd.DataFrame, meta_row: pd.DataFrame) -> None:
    """Validate metadata alignment with data."""
    missing_cols = set(df.columns) - set(meta_col.index)
    missing_rows = set(df.index) - set(meta_row.index)

    if missing_cols:
        raise ValueError(ERRORS["missing_metadata"].format("Column", list(missing_cols)[:5]))
    if missing_rows:
        raise ValueError(ERRORS["missing_metadata"].format("Row", list(missing_rows)[:5]))


def validate_metadata_types(meta_col: pd.DataFrame, meta_row: pd.DataFrame) -> None:
    """Check for mixed data types in metadata."""
    for df_name, meta_df in [("meta_col", meta_col), ("meta_row", meta_row)]:
        for col in meta_df.columns:
            dtypes = meta_df[col].dropna().apply(type).unique()
            if len(dtypes) > 1:
                warnings.warn(f"Mixed data types in {df_name}['{col}'].", UserWarning, stacklevel=2)


def compute_metric(data: pd.DataFrame | np.ndarray, metric: str, axis: int = 1) -> np.ndarray:
    """Compute specified metric along axis."""
    if metric not in METRIC_FUNCTIONS:
        raise ValueError(ERRORS["invalid_filter"].format(metric, list(METRIC_FUNCTIONS.keys())))

    if isinstance(data, pd.DataFrame):
        return getattr(data, METRIC_FUNCTIONS[metric])(axis=axis).values

    # Handle numpy array cases
    if metric == "sum":
        return np.sum(data, axis=axis)
    if metric == "var":
        return np.var(data, axis=axis)
    if metric == "mean":
        return np.mean(data, axis=axis)
    if metric == "median":
        return np.median(data, axis=axis)
    raise ValueError(f"Unsupported metric: {metric}")


def fast_cosine_distance(data: np.ndarray) -> np.ndarray:
    """Optimized cosine distance computation."""
    norms = np.linalg.norm(data, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized_data = data / norms

    similarity_matrix = np.dot(normalized_data, normalized_data.T)
    distance_matrix = 1 - similarity_matrix

    # Extract upper triangle
    n = distance_matrix.shape[0]
    indices = np.triu_indices(n, k=1)
    return distance_matrix[indices]


def zscore_normalize_inplace(data: np.ndarray, axis: int = 0) -> np.ndarray:
    """Memory-efficient in-place z-score normalization."""
    means = np.mean(data, axis=axis, keepdims=True)
    stds = np.std(data, axis=axis, keepdims=True)

    zero_std_mask = stds == 0
    if zero_std_mask.any():
        warnings.warn(
            f"Found {zero_std_mask.sum()} constant features. "
            "Replacing zero std with small value to avoid inf/NaN.",
            UserWarning,
            stacklevel=2,
        )
        stds[zero_std_mask] = 1e-10

    data -= means
    data /= stds
    return data


def create_node_info_base(n_nodes: int, linkage_data: list[Any]) -> dict[str, Any]:
    """Create base node info structure."""
    linkage_array = np.array(linkage_data) if linkage_data else np.array([]).reshape(0, 4)

    return {
        "ini": list(range(n_nodes, 0, -1)),
        "clust": list(range(n_nodes)),
        "rank": list(range(n_nodes)),
        "Y": linkage_array,
    }


def add_categories_to_node_info(
    node_info: dict[str, Any], nodes: list[str], meta_df: pd.DataFrame, cats: list[str]
) -> None:
    """Add category information to node info."""
    if not cats or meta_df.empty:
        return

    valid_cats = [cat for cat in cats if cat in meta_df.columns]
    if not valid_cats:
        return

    try:
        cat_data = meta_df.reindex(nodes)[valid_cats].fillna("Unknown").astype(str)
        for idx, cat_name in enumerate(valid_cats):
            node_info[f"cat-{idx}"] = cat_data[cat_name].tolist()
    except Exception:
        pass  # Skip failed category processing
