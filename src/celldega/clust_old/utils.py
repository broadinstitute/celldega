"""
Utility functions for clustering operations.

This module contains standalone utility functions that don't belong to any specific class
but are useful for the clustering workflow.
"""

from typing import Any

import pandas as pd

from .core.network import Network


def hc(
    df: pd.DataFrame,
    filter_n_top: int | None = None,
    norm_col: str | None = "total",
    norm_row: str | None = "zscore",
) -> dict[str, Any]:
    """
    Perform hierarchical clustering and return visualization JSON.

    Convenience function that creates a Network, applies filtering and normalization,
    performs clustering, and returns the visualization data.

    Args:
        df: Input DataFrame with samples as columns and features as rows
        filter_n_top: Number of top features to keep after filtering
        norm_col: Column normalization method ("total" for UMI normalization)
        norm_row: Row normalization method ("zscore" for z-score normalization)

    Returns:
        Visualization dictionary compatible with Clustergrammer.js
    """
    net = Network()
    net.load_df(df)

    if filter_n_top is not None:
        net.filter_n_top(axis="row", n_top=filter_n_top)

    if norm_col == "total":
        net.normalize(axis="col", norm_type="umi")

    if norm_row == "zscore":
        net.normalize(axis="row", norm_type="zscore")

    net.cluster()
    return net.viz
