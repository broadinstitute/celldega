"""
Data format conversion utilities for clustering high-dimensional data.

This module provides functions to convert between pandas DataFrames and the internal
network data structure used by the clustering pipeline.
"""

from typing import Any

import numpy as np
import pandas as pd

from . import categories, make_unique_labels


def df_to_dat(net: Any, df: pd.DataFrame, define_cat_colors: bool = False) -> None:
    """
    Convert pandas DataFrame to internal network data structure.

    Processes DataFrame into network's internal format, handling both tuple-based
    categories (embedded in index/columns) and metadata-based categories.

    Args:
        net: Network object to populate with data
        df: Input DataFrame to convert
        define_cat_colors: Whether to define category colors during processing

    Raises:
        KeyError: If metadata indices don't match DataFrame indices
    """
    # Single pass: ensure unique labels and convert to internal format
    df = make_unique_labels.main(net, df)
    net.dat["mat"] = df.values

    # Process both axes in single loop to minimize iterations
    axis_data = [("row", df.index), ("col", df.columns)]
    net.dat["nodes"] = {axis: data.tolist() for axis, data in axis_data}

    # Choose processing strategy based on metadata availability
    processor = _process_metadata_categories if net.meta_cat else _process_tuple_categories
    processor(net, axis_data)

    categories.dict_cat(net, define_cat_colors=define_cat_colors)


def _process_tuple_categories(net: Any, axis_data: list[tuple[str, pd.Index]]) -> None:
    """
    Process categories embedded as tuples in DataFrame index/columns.

    Args:
        net: Network object to update
        axis_data: List of (axis_name, index_data) tuples
    """
    for axis, data in axis_data:
        nodes = net.dat["nodes"][axis]

        # Early exit for empty or non-tuple structures
        if not nodes or not isinstance(nodes[0], tuple):
            continue

        # Store original tuple structure
        net.dat["node_info"][axis]["full_names"] = data.tolist()

        # Extract all categories in single pass
        num_categories = len(nodes[0]) - 1
        for cat_idx in range(num_categories):
            cat_name = f"cat-{cat_idx}"
            tuple_pos = cat_idx + 1
            # Single list comprehension instead of loop
            net.dat["node_info"][axis][cat_name] = [node[tuple_pos] for node in nodes]

        # Extract base names (first tuple element) in-place
        net.dat["nodes"][axis] = [node[0] for node in nodes]


def _process_metadata_categories(net: Any, axis_data: list[tuple[str, pd.Index]]) -> None:
    """
    Process categories from separate metadata DataFrames.

    Args:
        net: Network object with metadata attributes
        axis_data: List of (axis_name, index_data) tuples
    """
    # Pre-cache metadata access for efficiency
    metadata_cache = {}

    for axis, data in axis_data:
        nodes = net.dat["nodes"][axis]
        net.dat["node_info"][axis]["full_names"] = data.tolist()

        # Get category names with memoization
        category_names = _get_category_names(net, axis)
        if not category_names:
            continue

        # Get metadata DataFrame once per axis
        if axis not in metadata_cache:
            metadata_cache[axis] = _get_metadata_dataframe(net, axis)
        metadata_df = metadata_cache[axis]

        # Process all categories for this axis in batch
        _extract_all_categories(net, axis, nodes, category_names, metadata_df)


def _get_category_names(net: Any, axis: str) -> list[str]:
    """
    Get category names for specified axis with safe attribute access.

    Args:
        net: Network object
        axis: Either "row" or "col"

    Returns:
        List of category names, empty if none available
    """
    cats = getattr(net, f"{axis}_cats", None)
    return cats if cats is not None else []


def _extract_all_categories(
    net: Any, axis: str, nodes: list[str], category_names: list[str], metadata_df: pd.DataFrame
) -> None:
    """
    Extract all category values for an axis in single DataFrame operation.

    Args:
        net: Network object
        axis: Either "row" or "col"
        nodes: List of node names
        category_names: List of category titles
        metadata_df: Metadata DataFrame to extract from
    """
    if not category_names:
        return

    # Single DataFrame slice for all categories - O(1) vs O(n) individual lookups
    all_cat_data = metadata_df.loc[nodes, category_names]

    # Process all categories in vectorized operations
    for cat_idx, cat_title in enumerate(category_names):
        cat_name = f"cat-{cat_idx}"
        # Vectorized string formatting - much faster than individual operations
        net.dat["node_info"][axis][cat_name] = [
            f"{cat_title}: {value}" for value in all_cat_data[cat_title]
        ]


def _get_metadata_dataframe(net: Any, axis: str) -> pd.DataFrame:
    """
    Get appropriate metadata DataFrame with downsampling fallback.

    Args:
        net: Network object
        axis: Either "row" or "col"

    Returns:
        Metadata DataFrame to use
    """
    # Check downsampled metadata first if applicable
    if net.is_downsampled:
        ds_attr = f"meta_ds_{axis}"
        ds_metadata = getattr(net, ds_attr, None)
        if ds_metadata is not None:
            return ds_metadata

    # Fallback to regular metadata
    return getattr(net, f"meta_{axis}")


def dat_to_df(net: Any) -> pd.DataFrame:
    """
    Convert internal network data structure back to pandas DataFrame.

    Args:
        net: Network object containing data to convert

    Returns:
        DataFrame with original structure restored
    """
    # Single dictionary comprehension for both axes
    nodes = {
        axis: net.dat["node_info"][axis].get("full_names", net.dat["nodes"][axis])
        for axis in ["row", "col"]
    }

    return pd.DataFrame(data=net.dat["mat"], columns=nodes["col"], index=nodes["row"])


def mat_to_numpy_arr(network: Any) -> None:
    """
    Convert matrix from list format to numpy array in-place.

    Args:
        network: Network object with matrix to convert

    Note:
        Modifies the network object's matrix in-place for memory efficiency.
        Uses numpy's optimized conversion for minimal memory overhead.
    """
    # numpy.asarray is O(1) if already array, O(n) copy only if needed
    network.dat["mat"] = np.asarray(network.dat["mat"])
