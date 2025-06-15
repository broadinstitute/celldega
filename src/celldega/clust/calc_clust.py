"""Hierarchical clustering utilities for high-dimensional biological data."""

from typing import Any, Literal

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as hier
from scipy.spatial.distance import pdist


# Type aliases
AxisType = Literal["row", "col"]
NetworkType = Any
DistanceMatrix = np.ndarray
LinkageMatrix = np.ndarray


def cluster_row_and_col(
    net: NetworkType,
    dist_type: str = "cosine",
    linkage_type: str = "average",
    dendro: bool = True,
    run_clustering: bool = True,
    run_rank: bool = True,
    ignore_cat: bool = False,
    calc_cat_pval: bool = False,
    links: bool = False,
    clust_library: str = "scipy",
    min_samples: int = 1,
    min_cluster_size: int = 2,
) -> dict[AxisType, DistanceMatrix | None]:
    """Perform hierarchical clustering on network data for visualization."""
    from . import cat_pval, categories, make_viz

    # Process both axes in single loop
    distance_matrices = {}
    matrix = net.dat["mat"]  # Single reference, no deep copy needed

    for axis in ["row", "col"]:
        node_info = net.dat["node_info"][axis]
        n_nodes = len(net.dat["nodes"][axis])

        # Initialize with range generator
        node_info["ini"] = list(range(n_nodes, -1, -1))

        # Calculate distance matrix only if needed
        dm = None if clust_library == "hdbscan" else calc_distance_matrix(matrix, axis, dist_type)
        distance_matrices[axis] = dm

        # Clustering and ranking in single conditional block
        if run_clustering:
            node_info["clust"], node_info["Y"] = clust_and_group(
                net,
                dm,
                axis,
                matrix,
                dist_type,
                linkage_type,
                clust_library,
                min_samples,
                min_cluster_size,
            )
        else:
            dendro = False
            node_info["clust"] = node_info["ini"]

        # Vectorized ranking computation
        if run_rank:
            node_info["rank"] = sort_rank_nodes(net, axis, "sum")
            node_info["rankvar"] = sort_rank_nodes(net, axis, "var")
        else:
            node_info["rank"] = node_info["rankvar"] = node_info["ini"]

        # Category processing
        if not ignore_cat:
            categories.calc_cat_clust_order(net, axis)

    # Final processing
    if calc_cat_pval:
        cat_pval.main(net)
    make_viz.viz_json(net, dendro, links)

    return distance_matrices


def calc_distance_matrix(
    matrix: np.ndarray, axis: AxisType, dist_type: str = "cosine"
) -> DistanceMatrix:
    """Calculate pairwise distances with optimal memory usage."""
    if axis not in ["row", "col"]:
        raise ValueError(f"Invalid axis '{axis}'. Must be 'row' or 'col'")

    # Single data selection - no intermediate arrays
    data = matrix.T if axis == "col" else matrix

    # Early return for edge cases - O(1) space
    if data.shape[0] < 2:
        return np.array([])

    # Direct computation with in-place correction - minimal memory
    distances = pdist(data, metric=dist_type)
    np.maximum(distances, 0.0, out=distances)  # In-place operation
    return distances


def clust_and_group(
    net: NetworkType,
    distance_matrix: DistanceMatrix | None,
    axis: AxisType,
    matrix: np.ndarray,
    dist_type: str = "cosine",
    linkage_type: str = "average",
    clust_library: str = "scipy",
    min_samples: int = 1,
    min_cluster_size: int = 2,
) -> tuple[list[int], LinkageMatrix]:
    """Perform clustering with minimal memory allocation."""
    n_nodes = len(net.dat["nodes"][axis])

    # Single edge case check
    if n_nodes < 2 or (distance_matrix is not None and distance_matrix.size == 0):
        return list(range(n_nodes)), np.array([[0, 1, 0.0, 2]] if n_nodes >= 2 else []).reshape(
            -1, 4
        )

    # Efficient clustering dispatch using dict lookup
    clustering_methods = {
        "hdbscan": lambda: _cluster_hdbscan(
            net, axis, matrix, dist_type, min_samples, min_cluster_size
        ),
        "fastcluster": lambda: _cluster_fastcluster(distance_matrix, linkage_type),
        "scipy": lambda: hier.linkage(distance_matrix, method=linkage_type),
    }

    linkage_matrix = clustering_methods.get(clust_library, clustering_methods["scipy"])()

    # Single dendrogram call - no validation needed after clustering
    dendrogram = hier.dendrogram(linkage_matrix, no_plot=True)
    return dendrogram["leaves"], linkage_matrix


def sort_rank_nodes(
    net: NetworkType, axis: AxisType, rank_type: Literal["sum", "var"]
) -> list[int]:
    """Rank nodes using vectorized operations for optimal performance."""
    # Early validation - single check
    nodes = net.dat["nodes"][axis]
    matrix = net.dat["mat"]
    n_nodes = len(nodes)

    if n_nodes == 0 or matrix.shape[0 if axis == "row" else 1] != n_nodes:
        return list(range(n_nodes))

    # Single data selection and computation
    data = matrix if axis == "row" else matrix.T

    # Vectorized ranking computation
    ranking_values = np.sum(data, axis=1) if rank_type == "sum" else np.var(data, axis=1)

    # Direct index mapping - no intermediate data structures
    sort_order = np.argsort(ranking_values)
    rank_map = np.empty(n_nodes, dtype=int)
    rank_map[sort_order] = np.arange(n_nodes)

    return rank_map.tolist()


# Optimized helper functions with minimal overhead


def _cluster_hdbscan(
    net: NetworkType,
    axis: AxisType,
    matrix: np.ndarray,
    dist_type: str,
    min_samples: int,
    min_cluster_size: int,
) -> LinkageMatrix:
    """HDBSCAN clustering with optimized preprocessing pipeline."""
    import hdbscan
    from sklearn.decomposition import PCA
    import umap

    # Single data selection
    data = matrix if axis == "row" else matrix.T

    if data.shape[0] < 2:
        return np.array([]).reshape(0, 4)

    # Optimal PCA components selection
    n_components = min(50, data.shape[1], data.shape[0] - 1)
    if data.shape[1] > n_components:
        data = PCA(n_components=n_components, random_state=42).fit_transform(data)

    # Single UMAP transformation
    umap_data = umap.UMAP(
        metric=dist_type,
        n_neighbors=min(5, data.shape[0] - 1),
        min_dist=0.0,
        n_components=2,
        random_state=42,
    ).fit_transform(data)

    # Store results efficiently
    net.umap[axis] = pd.DataFrame(umap_data.T, index=["x", "y"], columns=net.dat["nodes"][axis])

    # Direct clustering
    return (
        hdbscan.HDBSCAN(min_samples=min_samples, min_cluster_size=min_cluster_size)
        .fit(umap_data)
        .single_linkage_tree_.to_numpy()
    )


def _cluster_fastcluster(distance_matrix: DistanceMatrix, linkage_type: str) -> LinkageMatrix:
    """Fastcluster with lazy import."""
    import fastcluster

    return fastcluster.linkage(distance_matrix, method=linkage_type)
