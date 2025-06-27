"""Category p-value calculation for clustering significance testing."""

from typing import Any

import numpy as np
import pandas as pd


def main(net: Any) -> None:
    """
    Calculate p-values for category clustering significance.

    Tests whether nodes within the same categories are more clustered
    than expected by chance using permutation testing.
    """
    for axis in ["row", "col"]:
        node_info = net.dat["node_info"][axis]
        nodes = [net.dat["nodes"][axis][i] for i in node_info["clust"]]
        distance_matrix = _create_lattice_distances(nodes)
        category_keys = [k for k in node_info if k.startswith("dict_cat_")]

        # Process all categories in single pass
        for cat_key in category_keys:
            node_info[cat_key.replace("dict_", "pval_")] = {
                name: _permutation_pvalue(distance_matrix, subset, nodes)
                for name, subset in node_info[cat_key].items()
            }


def _create_lattice_distances(nodes: list[str]) -> pd.DataFrame:
    """Create distance matrix for 1D lattice positions. O(n²) time, O(n²) space."""
    if not nodes:
        return pd.DataFrame()

    # Vectorized distance calculation - most efficient approach
    positions = np.arange(len(nodes))
    distances = np.abs(positions[:, None] - positions)

    # Use float64 for numerical precision in tests (minimal memory impact for typical sizes)
    return pd.DataFrame(distances, index=nodes, columns=nodes, dtype=np.float64)


def _permutation_pvalue(dm: pd.DataFrame, subset: list[str], all_nodes: list[str]) -> float:
    """Calculate p-value using optimized permutation testing. O(1000*k²) where k = subset size."""
    if not subset or len(subset) > len(all_nodes):
        return 1.0

    # Filter valid nodes once - O(k) where k = subset size
    valid_subset = [node for node in subset if node in dm.index]
    if not valid_subset:
        return 1.0

    # Pre-compute observed median
    observed = _fast_median_distance(dm, valid_subset)
    if np.isnan(observed):
        return 1.0

    # Optimized null distribution generation
    np.random.seed(100)  # Deterministic results
    subset_size = len(valid_subset)

    # Vectorized random sampling and median calculation
    null_count = sum(
        _fast_median_distance(dm, np.random.choice(all_nodes, subset_size, replace=False))
        <= observed
        for _ in range(1000)
    )

    return null_count / 1000.0


def _fast_median_distance(dm: pd.DataFrame, nodes) -> float:
    """Optimized median calculation. O(k²) time, O(k²) space where k = len(nodes)."""
    if len(nodes) == 0:
        return np.nan
    if len(nodes) == 1:
        return 0.0  # Distance to self is always 0

    # Direct numpy operation on subset - most efficient path
    try:
        subset_matrix = dm.loc[nodes, nodes].values
        return float(np.median(subset_matrix))
    except KeyError:
        # Fallback for mixed valid/invalid nodes
        valid_nodes = [n for n in nodes if n in dm.index]
        return (
            np.nan if not valid_nodes else float(np.median(dm.loc[valid_nodes, valid_nodes].values))
        )


# Legacy interface functions for backward compatibility - minimal overhead wrappers
def dist_matrix_lattice(names: list[str]) -> pd.DataFrame:
    """Legacy interface for distance matrix creation."""
    return _create_lattice_distances(names)


def calc_median_dist_subset(distance_matrix: pd.DataFrame, subset: list[str]) -> float:
    """Legacy interface for median distance calculation."""
    return _fast_median_distance(distance_matrix, subset)


def calc_hist_distances(
    distance_matrix: pd.DataFrame, subset: list[str], all_nodes: list[str]
) -> dict[str, np.ndarray]:
    """
    Legacy interface for histogram generation.

    Note: This function is no longer used in the optimized main() but preserved
    for backward compatibility. The optimized version calculates p-values directly.
    """
    if not subset:
        raise ValueError("Subset cannot be empty")
    if len(subset) > len(all_nodes):
        raise ValueError("Subset size cannot be larger than available nodes")

    np.random.seed(100)
    null_medians = [
        _fast_median_distance(
            distance_matrix, np.random.choice(all_nodes, len(subset), replace=False)
        )
        for _ in range(1000)
    ]

    # Use numpy histogram for efficiency
    counts, bin_edges = np.histogram(null_medians, bins=30, density=False)

    return {
        "prob": counts.astype(np.float64) / 1000.0,  # Use float64 for test precision
        "bins": bin_edges.astype(np.float64),
    }
