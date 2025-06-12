"""Process DataFrame labels to ensure uniqueness."""

from typing import Any

import pandas as pd


def main(net, df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Make row and column names unique by adding numeric suffixes if duplicates exist.
    """
    if df is None:
        if net is None:
            raise ValueError("Either net or df must be provided")
        df = net.export_df()

    if df.empty:
        return df

    # Process with original warning message format
    _make_axis_unique(df, "row", "index")
    _make_axis_unique(df, "col", "columns")

    return df


def _make_axis_unique(df: pd.DataFrame, axis_name: str, axis_attr: str) -> None:
    """
    Make single axis unique if duplicates exist.
    """
    items = getattr(df, axis_attr).tolist()

    if not items:
        return

    if isinstance(items[0], str):
        if _has_duplicates(items):
            print(f"warning: making {axis_name} names unique")
            setattr(df, axis_attr, add_index_list(items))

    elif isinstance(items[0], tuple):
        try:
            first_elements = [item[0] for item in items]
        except (IndexError, TypeError) as e:
            # Use "column" for error messages but "col" for warnings
            error_axis = "column" if axis_name == "col" else axis_name
            raise ValueError(f"Empty tuples found in {error_axis} index") from e

        if _has_duplicates(first_elements):
            print(f"warning: making {axis_name} names unique")
            unique_first = add_index_list(first_elements)
            new_items = [(unique_first[i], *item[1:]) for i, item in enumerate(items)]
            setattr(df, axis_attr, new_items)


def _has_duplicates(items: list[Any]) -> bool:
    """
    Check if list contains duplicates. O(n) time, O(n) space.
    """
    return len(items) != len(set(items))


def add_index_list(nodes: list[Any]) -> list[str]:
    """
    Add numeric suffixes: ['gene', 'gene'] -> ['gene-1', 'gene-2'].
    """
    return [f"{node}-{i + 1}" for i, node in enumerate(nodes)]
