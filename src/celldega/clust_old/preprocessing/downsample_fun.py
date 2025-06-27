"""
Downsampling utilities for high-dimensional clustering data.

This module provides K-means based downsampling functionality for reducing
the dimensionality of datasets while preserving cluster structure and metadata.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans


# Separator string for category formatting
CATEGORY_SEPARATOR = ": "


def main(
    net: Any,
    df: pd.DataFrame | None = None,
    ds_type: str = "kmeans",
    axis: str = "row",
    num_samples: int = 100,
    random_state: int = 1000,
    ds_name: str = "Downsample",
    ds_cluster_name: str = "cluster",
) -> pd.Series | None:
    """
    Downsample matrix rows or columns using K-means clustering.

    Args:
        net: Network object containing the data and metadata
        df: Optional DataFrame to downsample (uses net.export_df() if None)
        ds_type: Downsampling algorithm type (currently only "kmeans" supported)
        axis: Axis to downsample ("row" or "col")
        num_samples: Target number of clusters/samples
        random_state: Random seed for reproducibility
        ds_name: Name for the downsampling operation
        ds_cluster_name: Prefix for cluster names

    Returns:
        Series mapping original labels to cluster assignments, or None if metadata exists

    Raises:
        ValueError: If parameters are invalid or insufficient data available
    """
    if num_samples <= 0:
        raise ValueError("num_samples must be positive")
    if axis not in {"row", "col"}:
        raise ValueError(f"Invalid axis '{axis}'. Must be 'row' or 'col'.")

    input_df = df if df is not None else net.export_df()

    available = input_df.shape[0 if axis == "row" else 1]
    if num_samples > available:
        raise ValueError(f"Requested {num_samples} samples but only {available} {axis}s available")

    net.ds_name = ds_name

    # Core processing - optimized single pass
    ds_df, cluster_assignments = _process_downsample(
        net, input_df, num_samples, axis, random_state, ds_cluster_name
    )

    # Generate results efficiently
    original_labels = input_df.index if axis == "row" else input_df.columns
    cluster_series = pd.Series(
        [f"{ds_cluster_name}-{x + 1}" for x in cluster_assignments], index=original_labels
    )

    # Update network in-place
    _finalize_network(net, ds_df, axis, ds_name, cluster_series)

    return None if net.meta_cat else cluster_series


def _process_downsample(
    net: Any,
    df: pd.DataFrame,
    num_samples: int,
    axis: str,
    random_state: int,
    cluster_name: str,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Execute complete downsampling pipeline with minimal data copying."""

    # Prepare data matrices - single data access
    is_row_axis = axis == "row"
    X = df.values if is_row_axis else df.values.T
    target_labels = df.index.tolist() if is_row_axis else df.columns.tolist()
    other_labels = df.columns.tolist() if is_row_axis else df.index.tolist()

    # Add metadata if needed - single conditional check
    if net.meta_cat:
        meta_cats = getattr(net, f"{axis}_cats", None)
        if meta_cats:
            meta_source = getattr(net, f"meta_{axis}")
            target_labels = [
                tuple([label] + [f"{cat}: {meta_source.loc[label, cat]}" for cat in meta_cats])
                for label in target_labels
            ]

    # Clustering with optimized retry - minimized iterations
    centers, assignments = _cluster_with_validation(X, num_samples, random_state)

    # Generate metadata efficiently
    cluster_labels = _build_cluster_labels(
        assignments, target_labels, centers.shape[0], cluster_name
    )

    # Create result DataFrame
    result_df = pd.DataFrame(data=centers, index=cluster_labels, columns=other_labels)
    return result_df.T if not is_row_axis else result_df, assignments


def _cluster_with_validation(
    X: np.ndarray, num_samples: int, random_state: int, max_attempts: int = 10
) -> tuple[np.ndarray, np.ndarray]:
    """Optimized clustering with minimal retry overhead."""

    n_samples, n_features = X.shape
    effective_clusters = min(num_samples, n_samples)

    if effective_clusters < num_samples:
        print(f"Warning: Using {effective_clusters} clusters instead of {num_samples}")

    # Single clustering attempt with validation
    safe_seed = max(0, min(random_state, 2**31 - 1))

    for attempt in range(max_attempts):
        kmeans = MiniBatchKMeans(
            n_clusters=effective_clusters,
            init="k-means++",
            max_no_improvement=100,
            verbose=0,
            random_state=safe_seed + attempt,
        )

        assignments = kmeans.fit_predict(X)
        centers = kmeans.cluster_centers_

        # Fast unique check
        unique_clusters = np.unique(assignments)
        if len(unique_clusters) == effective_clusters:
            return centers[unique_clusters], assignments

        # Reorder centers for partial success
        centers = centers[unique_clusters]

    print(f"Warning: Could not achieve exact cluster count after {max_attempts} attempts")
    return centers, assignments


def _build_cluster_labels(
    assignments: np.ndarray,
    labels: list[str | tuple[str, ...]],
    num_clusters: int,
    cluster_name: str,
) -> list[tuple[str, ...]]:
    """Build cluster metadata labels with optimized category processing."""

    # Fast population count
    _, populations = np.unique(assignments, return_counts=True)

    # Early return for simple case
    if not labels or not isinstance(labels[0], tuple):
        return [
            (f"{cluster_name}-{i + 1}", f"number in clust: {populations[i]}")
            for i in range(num_clusters)
        ]

    # Optimized category processing for complex case
    categories = _extract_categories_optimized(labels, assignments, num_clusters)

    return [
        tuple(
            [f"{cluster_name}-{i + 1}"]
            + [f"{cat['title']}: {cat['types'][np.argmax(cat['counts'][i])]}" for cat in categories]
            + [f"number in clust: {populations[i]}"]
        )
        for i in range(num_clusters)
    ]


def _extract_categories_optimized(
    labels: list[tuple[str, ...]],
    assignments: np.ndarray,
    num_clusters: int,
) -> list[dict[str, Any]]:
    """Optimized category extraction with minimal memory allocation."""

    if not labels:
        return []

    # Single pass to identify string categories
    example = labels[0]
    string_indices = []

    for i in range(1, len(example)):
        value = (
            example[i].split(CATEGORY_SEPARATOR, 1)[-1]
            if CATEGORY_SEPARATOR in example[i]
            else example[i]
        )
        try:
            float(value)
        except ValueError:
            string_indices.append(i)

    if not string_indices:
        return []

    # Vectorized category processing
    categories = []
    labels_array = np.array(labels, dtype=object)

    for cat_idx in string_indices:
        # Extract all values for this category at once
        cat_column = labels_array[:, cat_idx]

        # Parse category values efficiently
        title = (
            cat_column[0].split(CATEGORY_SEPARATOR)[0]
            if CATEGORY_SEPARATOR in cat_column[0]
            else "Category"
        )
        values = np.array(
            [
                val.split(CATEGORY_SEPARATOR, 1)[-1] if CATEGORY_SEPARATOR in val else val
                for val in cat_column
            ]
        )

        unique_values = np.unique(values)

        # Vectorized counting per cluster
        cluster_counts = {}
        for cluster_id in range(num_clusters):
            mask = assignments == cluster_id
            if not np.any(mask):
                cluster_counts[cluster_id] = np.zeros(len(unique_values))
                continue

            cluster_values = values[mask]
            counts = np.array([np.sum(cluster_values == val) for val in unique_values])
            total = counts.sum()
            cluster_counts[cluster_id] = counts / total if total > 0 else counts

        categories.append(
            {
                "title": title,
                "types": unique_values.tolist(),
                "counts": cluster_counts,
            }
        )

    return categories


def _finalize_network(
    net: Any,
    ds_df: pd.DataFrame,
    axis: str,
    ds_name: str,
    cluster_series: pd.Series,
) -> None:
    """Efficiently update network with minimal data copying."""

    # Single axis-based processing
    if axis == "col":
        # Process columns
        net.meta_ds_col = net.make_df_from_cols(ds_df.columns.tolist())
        ds_df.columns = [col[0] if isinstance(col, tuple) else col for col in ds_df.columns]
        net.dat["nodes"]["col"] = ds_df.columns.tolist()
    else:
        # Process rows
        net.meta_ds_row = net.make_df_from_cols(ds_df.index.tolist())
        ds_df.index = [idx[0] if isinstance(idx, tuple) else idx for idx in ds_df.index]
        net.dat["nodes"]["row"] = ds_df.index.tolist()

    # Single network update
    net.load_df(ds_df, is_downsampled=True)

    # Conditional metadata update
    if net.meta_cat:
        target_meta = getattr(net, f"meta_{axis}")
        target_meta[ds_name] = cluster_series
