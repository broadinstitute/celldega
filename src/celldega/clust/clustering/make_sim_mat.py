"""
Similarity matrix computation and clustering for high-dimensional data.

This module converts distance matrices to similarity matrices with optional filtering
and generates clustered network visualizations.
"""

from copy import deepcopy

import numpy as np
from scipy.spatial.distance import squareform

from . import calc_clust


# Constants for filtering thresholds
MIN_SIMILARITY_THRESHOLD = 0.01
DEFAULT_KEEP_TOP = 20000


def main(
    net,
    distance_matrices: dict[str, np.ndarray],
    axes_to_process: list[str],
    filter_threshold: float,
    sim_mat_views: list[str] | None = None,
) -> dict[str, object]:
    """
    Generate similarity matrices from distance matrices and create clustered networks.
    """
    if not axes_to_process:
        return {}

    # Convert distance matrices to similarity matrices
    similarity_matrices = {
        axis: dm_to_sim(distance_matrices[axis], make_squareform=True, filter_sim=filter_threshold)
        for axis in axes_to_process
    }

    # Create clustered networks for each axis
    clustered_networks = {}
    for axis in axes_to_process:
        clustered_networks[axis] = _create_similarity_network(net, similarity_matrices[axis], axis)

    return clustered_networks


def dm_to_sim(
    distance_matrix: np.ndarray | object, make_squareform: bool = False, filter_sim: float = 0
) -> np.ndarray:
    """
    Convert distance matrix to similarity matrix with optional filtering.
    """
    # Input validation
    if not hasattr(distance_matrix, "size") or not hasattr(distance_matrix, "shape"):
        raise TypeError("distance_matrix must be a numpy array or array-like object")

    if distance_matrix.size == 0:
        return distance_matrix

    # Convert to square form if needed
    if make_squareform:
        distance_matrix = squareform(distance_matrix)

    # Convert distances to similarities
    similarity_matrix = 1 - distance_matrix

    # Apply filtering if threshold is specified
    if filter_sim > 0:
        adjusted_threshold = adjust_filter_sim(similarity_matrix, filter_sim)
        similarity_matrix[np.abs(similarity_matrix) < adjusted_threshold] = 0

    return similarity_matrix


def adjust_filter_sim(
    similarity_matrix: np.ndarray | object,
    filter_threshold: float,
    keep_top: int = DEFAULT_KEEP_TOP,
) -> float:
    """
    Adjust similarity filtering threshold based on value distribution.
    """
    # Input validation
    if not hasattr(similarity_matrix, "flatten") or not hasattr(similarity_matrix, "shape"):
        raise TypeError("similarity_matrix must be a numpy array or array-like object")

    # Extract significant similarity values
    significant_values = np.abs(similarity_matrix.flatten())
    significant_values = significant_values[significant_values > MIN_SIMILARITY_THRESHOLD]

    # Return original threshold if insufficient data
    if len(significant_values) <= keep_top:
        return filter_threshold

    # Find threshold that keeps only top similarities
    sorted_values = np.sort(significant_values)[::-1]  # Sort descending
    return sorted_values[keep_top]


def _create_similarity_network(original_net, similarity_matrix: np.ndarray, axis: str):
    """
    Create a new network object with similarity matrix for clustering.
    """
    # Create deep copy to avoid modifying original
    similarity_net = deepcopy(original_net)

    # Replace data matrix with similarity matrix
    similarity_net.dat["mat"] = similarity_matrix

    # Configure nodes for symmetric similarity matrix
    axis_nodes = original_net.dat["nodes"][axis]
    axis_node_info = original_net.dat["node_info"][axis]

    similarity_net.dat["nodes"]["row"] = axis_nodes
    similarity_net.dat["nodes"]["col"] = axis_nodes
    similarity_net.dat["node_info"]["row"] = axis_node_info
    similarity_net.dat["node_info"]["col"] = axis_node_info

    # Perform clustering on similarity matrix
    calc_clust.cluster_row_and_col(similarity_net)

    # Initialize visualization views
    similarity_net.viz["views"] = []

    return similarity_net
