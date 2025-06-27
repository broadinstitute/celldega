"""
Category management utilities for high-dimensional data clustering.

This module provides functions for processing, organizing, and managing
category data structures used in clustering visualization systems.
"""

from collections.abc import Iterable
from typing import Any

import pandas as pd


# Color palette as module constant to avoid repeated allocation
_COLOR_PALETTE = [
    "#393b79",
    "#aec7e8",
    "#ff7f0e",
    "#ffbb78",
    "#98df8a",
    "#bcbd22",
    "#404040",
    "#ff9896",
    "#c5b0d5",
    "#8c564b",
    "#1f77b4",
    "#5254a3",
    "#FFDB58",
    "#c49c94",
    "#e377c2",
    "#7f7f7f",
    "#2ca02c",
    "#9467bd",
    "#dbdb8d",
    "#17becf",
    "#637939",
    "#6b6ecf",
    "#9c9ede",
    "#d62728",
    "#8ca252",
    "#8c6d31",
    "#bd9e39",
    "#e7cb94",
    "#843c39",
    "#ad494a",
    "#d6616b",
    "#7b4173",
    "#a55194",
    "#ce6dbd",
    "#de9ed6",
]

_NEGATIVE_INDICATORS = frozenset(["false", "not "])


def check_categories(lines: list[str]) -> dict[str, int]:
    """
    Count row and column categories in file data.

    Args:
        lines: List of tab-separated strings representing file content

    Returns:
        Dictionary with 'row' and 'col' keys containing category counts
    """
    if not lines:
        return {"row": 1, "col": 1}

    # Count row categories from header line - single pass
    header_parts = lines[0].split("\t")
    row_cats = 0
    for part in header_parts[1:]:
        if part == "":
            row_cats += 1
        else:
            break  # Stop at first non-empty part

    # Count column categories - single pass with early termination
    col_cats = sum(
        1
        for i in range(min(15, len(lines) - 1))
        if (parts := lines[i + 1].split("\t")) and parts[0] == "" and len(parts) > 1
    )

    return {"row": row_cats + 1, "col": col_cats + 1}


def dict_cat(net: Any, define_cat_colors: bool = False) -> None:
    """
    Create node-category association dictionaries and optional color assignments.

    Args:
        net: Network object with dat and viz attributes
        define_cat_colors: Whether to generate category colors
    """
    if not hasattr(net, "persistent_cat_colors"):
        net.persistent_cat_colors = True

    # Ensure structure exists
    if not hasattr(net, "viz") or not isinstance(net.viz, dict):
        net.viz = {}
    if "cat_colors" not in net.viz:
        net.viz["cat_colors"] = {"row": {}, "col": {}}

    # Process both axes in single loop
    for axis in ("row", "col"):
        _process_axis_categories(net, axis)

    if define_cat_colors:
        _assign_category_colors(net)


def calc_cat_clust_order(net: Any, axis: str) -> None:
    """
    Calculate clustering order for category subsets.

    Args:
        net: Network object containing node and category information
        axis: Either "row" or "col" to specify processing axis
    """
    node_info = net.dat.get("node_info", {}).get(axis, {})
    if not node_info:
        return

    nodes = net.dat["nodes"][axis]

    # Create list to avoid dictionary size change during iteration
    cat_keys = [k for k in node_info if "cat-" in k]

    for cat_key in cat_keys:
        dict_key = f"dict_{cat_key.replace('-', '_')}"
        cat_dict = node_info.get(dict_key, {})

        if not cat_dict:
            continue

        # Create ordering with O(n) lookup
        ordered_names = _get_ordered_names(cat_dict)
        name_to_index = {name: idx for idx, name in enumerate(ordered_names)}

        index_key = f"{cat_key.replace('-', '_')}_index"
        node_info[index_key] = [name_to_index.get(node, idx) for idx, node in enumerate(nodes)]


def order_categories(categories: Iterable[str]) -> list[str]:
    """
    Sort categories alphabetically or numerically based on content.

    Args:
        categories: Iterable of category names

    Returns:
        Sorted list of category names
    """
    cat_list = list(categories)
    if not cat_list:
        return []

    values = _extract_category_values(cat_list)
    return _sort_numeric_categories(cat_list, values) if _all_numeric(values) else sorted(cat_list)


def order_cats_based_on_values(categories: list[str], values: list[str]) -> list[str]:
    """
    Sort categories by their numeric values.

    Args:
        categories: List of category names
        values: List of numeric values as strings

    Returns:
        Categories sorted by numeric values, or original order if error
    """
    try:
        # Single comprehension for conversion and Series creation
        return (
            pd.Series([float(val) for val in values], index=categories).sort_values().index.tolist()
        )
    except (ValueError, TypeError, Exception) as e:
        print(f"Error sorting categories by values: {e}")
        return list(categories)


def add_cats(net: Any, axis: str, cat_data: dict[str, Any]) -> None:
    """
    Add category information to network data.

    Args:
        net: Network object with export_df and load_df methods
        axis: Either "row" or "col" for target axis
        cat_data: Dictionary containing 'title' and 'cats' keys
    """
    try:
        if axis not in ("row", "col"):
            raise ValueError(f"Invalid axis '{axis}'. Must be 'row' or 'col'.")

        df = net.export_df()
        labels = (df.index if axis == "row" else df.columns).tolist()

        title = cat_data.get("title", "New Category")
        categories = cat_data.get("cats", {})

        # Create category lookup for O(1) membership testing
        cat_lookup = {
            member: cat_name
            for cat_name, members in categories.items()
            if isinstance(members, (list | tuple))
            for member in members
        }

        # Single pass label transformation
        new_labels = [_create_labeled_tuple(label, title, cat_lookup) for label in labels]

        if axis == "row":
            df.index = new_labels
        else:
            df.columns = new_labels

        net.load_df(df)

    except Exception as e:
        print(f"Error adding categories: {e}")


def is_number(value: Any) -> bool:
    """
    Check if value represents a numeric type.

    Args:
        value: Value to test for numeric conversion

    Returns:
        True if value can be converted to float, False otherwise
    """
    if value is None:
        return False
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def get_cat_color(index: int | float) -> str:
    """
    Get color for category at given index.

    Args:
        index: Category index for color selection

    Returns:
        Hex color code string
    """
    safe_index = max(0, int(index)) if isinstance(index, (int | float)) else 0
    return _COLOR_PALETTE[safe_index % len(_COLOR_PALETTE)]


# Private helper functions - optimized for performance and conciseness


def _process_axis_categories(net: Any, axis: str) -> None:
    """Process categories for a specific axis (row or col)."""
    node_info = net.dat.get("node_info", {}).get(axis, {})
    if not node_info:
        return

    nodes = net.dat["nodes"][axis]

    # Create list to avoid dictionary size change during iteration
    cat_keys = [k for k in node_info if "cat-" in k]

    for cat_key in cat_keys:
        categories = node_info[cat_key]
        min_length = min(len(categories), len(nodes))

        if len(categories) != len(nodes):
            print(
                f"Warning: Category/node length mismatch in {axis}. Using first {min_length} elements."
            )

        # Create category dictionary with defaultdict-like behavior using setdefault
        cat_dict: dict[str, list[str]] = {}
        for cat_name, node in zip(categories[:min_length], nodes[:min_length], strict=False):
            cat_dict.setdefault(cat_name, []).append(node)

        node_info[f"dict_{cat_key.replace('-', '_')}"] = cat_dict


def _assign_category_colors(net: Any) -> None:
    """Assign colors to all categories in the network."""
    cat_colors = net.viz["cat_colors"]
    global_colors = {}
    color_index = 0

    for axis in ("row", "col"):
        node_info = net.dat.get("node_info", {}).get(axis, {})

        # Create list to avoid dictionary size change during iteration
        cat_keys = [k for k in node_info if "cat-" in k]

        for cat_key in cat_keys:
            if cat_key not in cat_colors[axis]:
                cat_colors[axis][cat_key] = {}

            # Process unique categories only
            for cat_name in sorted(set(node_info[cat_key])):
                if cat_name not in cat_colors[axis][cat_key] and not is_number(cat_name):
                    color = _get_category_color(cat_name, color_index)
                    cat_colors[axis][cat_key][cat_name] = color

                    # Extract clean name for global colors
                    clean_name = cat_name.split(": ", 1)[1] if ": " in cat_name else cat_name
                    global_colors[clean_name] = color

                color_index += 1

    net.viz["global_cat_colors"] = global_colors


def _get_category_color(cat_name: str, base_index: int) -> str:
    """Get appropriate color for a category name."""
    clean_name = cat_name.split(": ", 1)[1] if ": " in cat_name else cat_name

    # Use neutral color for negative/false indicators
    return (
        "#eee"
        if any(indicator in clean_name.lower() for indicator in _NEGATIVE_INDICATORS)
        else get_cat_color(base_index)
    )


def _get_ordered_names(cat_dict: dict[str, list[str]]) -> list[str]:
    """Get ordered list of all names from category dictionary."""
    ordered_categories = order_categories(cat_dict.keys())
    # Flatten in single comprehension
    return [name for cat in ordered_categories for name in cat_dict.get(cat, [])]


def _extract_category_values(categories: list[str]) -> list[str]:
    """Extract values from category names, removing titles if all have them."""
    non_numeric = [cat for cat in categories if not is_number(cat)]

    if not non_numeric or not all(": " in cat for cat in non_numeric):
        return categories

    # Single comprehension for title extraction
    return [cat.split(": ", 1)[1] if ": " in cat else cat for cat in categories]


def _all_numeric(values: list[str]) -> bool:
    """Check if all values in list are numeric."""
    return all(is_number(val) for val in values)


def _sort_numeric_categories(categories: list[str], values: list[str]) -> list[str]:
    """Sort categories based on numeric values."""
    return order_cats_based_on_values(categories, values)


def _create_labeled_tuple(label: Any, title: str, cat_lookup: dict[str, str]) -> tuple:
    """Create a new tuple with category label added."""
    # Extract base name for matching
    base_name = str(label[0] if isinstance(label, tuple) else label)
    if ": " in base_name:
        base_name = base_name.split(": ", 1)[1]

    # O(1) category lookup instead of O(n) iteration
    category_name = cat_lookup.get(base_name, "False")
    category_label = f"{title}: {category_name}"

    # Build new tuple
    return (*label, category_label) if isinstance(label, tuple) else (label, category_label)


# Legacy compatibility functions (maintaining exact original names)
def check_all_numbers(values: list[str]) -> bool:
    """Check if all items in list are numeric (legacy compatibility)."""
    return _all_numeric(values)


def remove_titles(categories: list[str]) -> list[str]:
    """Remove titles from categories if all have them (legacy compatibility)."""
    return _extract_category_values(categories)
