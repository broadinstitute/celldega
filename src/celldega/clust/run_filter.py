from typing import Literal
import warnings

import pandas as pd


def df_filter_row_sum(df: pd.DataFrame, threshold: float, take_abs: bool = True) -> pd.DataFrame:
    """Filter rows by sum threshold, keeping only rows with sum > threshold.

    Args:
        df: Input DataFrame
        threshold: Minimum sum threshold
        take_abs: Whether to use absolute values for filtering

    Returns:
        Filtered DataFrame

    Raises:
        ValueError: If threshold is invalid
    """
    if not isinstance(threshold, int | float):
        raise ValueError(f"threshold must be numeric, got {type(threshold)}")

    if df.empty:
        return df

    work_df = df.abs() if take_abs else df
    row_sums = work_df.sum(axis=1).abs()
    keep_rows = row_sums[row_sums > threshold].index.tolist()

    return grab_df_subset(df, keep_rows=keep_rows) if len(keep_rows) < len(df) else df


def df_filter_col_sum(df: pd.DataFrame, threshold: float, take_abs: bool = True) -> pd.DataFrame:
    """Filter columns by sum threshold, remove zero-sum rows.

    Args:
        df: Input DataFrame
        threshold: Minimum sum threshold
        take_abs: Whether to use absolute values for filtering

    Returns:
        Filtered DataFrame

    Raises:
        ValueError: If threshold is invalid
    """
    if not isinstance(threshold, int | float):
        raise ValueError(f"threshold must be numeric, got {type(threshold)}")

    if df.empty:
        return df

    work_df = df.abs() if take_abs else df

    # Filter columns by threshold
    col_sums = work_df.sum(axis=0)
    keep_cols = col_sums[col_sums > threshold].index.tolist()

    if not keep_cols:
        return pd.DataFrame(index=df.index, columns=[])

    filtered_df = work_df[keep_cols]

    # Remove zero-sum rows
    row_sums = filtered_df.sum(axis=1)
    keep_rows = row_sums[row_sums > 0].index.tolist()

    result_df = filtered_df.loc[keep_rows] if keep_rows else pd.DataFrame(columns=keep_cols)

    # Return subset of original df if using abs, otherwise return filtered
    return grab_df_subset(df, keep_rows, keep_cols) if take_abs else result_df


def grab_df_subset(
    df: pd.DataFrame, keep_rows: list | str = "all", keep_cols: list | str = "all"
) -> pd.DataFrame:
    """Extract subset of DataFrame by specified rows and columns.

    Args:
        df: Input DataFrame
        keep_rows: Row indices to keep, or "all" for all rows
        keep_cols: Column names to keep, or "all" for all columns

    Returns:
        Subset DataFrame
    """
    result = df
    if keep_cols != "all":
        result = result[keep_cols]
    if keep_rows != "all":
        result = result.loc[keep_rows]
    return result


def get_sorted_rows(df: pd.DataFrame, rank_type: Literal["sum", "var"] = "sum") -> list[str]:
    """Get row names sorted by sum or variance in descending order.

    Args:
        df: Input DataFrame
        rank_type: Ranking metric - "sum" or "var"

    Returns:
        List of row names sorted in descending order
    """
    if df.empty:
        return []

    work_df = df.T
    metric = work_df.sum(axis=0) if rank_type == "sum" else work_df.var(axis=0)
    return metric.abs().sort_values(ascending=False).index.tolist()


def filter_n_top(
    inst_rc: Literal["row", "col"],
    df: pd.DataFrame,
    n_top: int,
    rank_type: Literal["sum", "var"] = "sum",
) -> pd.DataFrame:
    """Keep only top N rows/columns by specified ranking metric.

    Args:
        inst_rc: Filter axis - "row" or "col"
        df: Input DataFrame
        n_top: Number of top items to keep
        rank_type: Ranking metric - "sum" or "var"

    Returns:
        Filtered DataFrame

    Raises:
        ValueError: If n_top is negative
    """
    if n_top < 0:
        raise ValueError(f"n_top must be non-negative, got {n_top}")

    if df.empty or n_top == 0:
        if inst_rc == "row":
            return pd.DataFrame(index=df.index[:0], columns=df.columns)
        return pd.DataFrame(index=df.index, columns=df.columns[:0])

    work_df = df.T if inst_rc == "col" else df
    sorted_rows = get_sorted_rows(work_df, rank_type)
    keep_rows = sorted_rows[:n_top]
    result_df = work_df.loc[keep_rows] if keep_rows else work_df.iloc[:0]

    return result_df.T if inst_rc == "col" else result_df


def filter_threshold(
    df: pd.DataFrame, inst_rc: Literal["row", "col"], threshold: float, num_occur: int = 1
) -> pd.DataFrame:
    """Filter rows/columns by number of values above threshold.

    Args:
        df: Input DataFrame
        inst_rc: Filter axis - "row" or "col"
        threshold: Value threshold
        num_occur: Minimum number of occurrences above threshold

    Returns:
        Filtered DataFrame

    Raises:
        ValueError: If parameters are invalid
    """
    if not isinstance(threshold, int | float):
        raise ValueError(f"threshold must be numeric, got {type(threshold)}")

    if num_occur < 0:
        raise ValueError(f"num_occur must be non-negative, got {num_occur}")

    if df.empty:
        return df

    work_df = df.T if inst_rc == "col" else df

    # Convert to binary mask and count occurrences above threshold
    above_threshold = (work_df.abs() >= threshold).sum(axis=1)
    keep_names = above_threshold[above_threshold >= num_occur].index.tolist()

    if len(keep_names) < len(work_df):
        if inst_rc == "row":
            return grab_df_subset(df, keep_rows=keep_names)
        return grab_df_subset(df, keep_cols=keep_names)

    return df


def filter_cat(net, axis: Literal["row", "col"], cat_index: int, cat_name: str) -> None:
    """Filter network by category at specified index.

    Args:
        net: Network object with export_df/load_df methods
        axis: Filter axis - "row" or "col"
        cat_index: Index of category in tuple
        cat_name: Category name to filter by

    Raises:
        ValueError: If cat_index is negative
        AttributeError: If net object missing required methods
    """
    if cat_index < 0:
        raise ValueError(f"cat_index must be non-negative, got {cat_index}")

    try:
        df = net.export_df()

        if df.empty:
            warnings.warn("DataFrame is empty, no filtering applied", stacklevel=2)
            return

        # DataFrame filtering always works on columns - transpose if filtering rows
        if axis == "row":
            df = df.T

        # Use walrus operator for concise filtering
        try:
            found_names = [col for col in df.columns if col[cat_index] == cat_name]
        except (IndexError, TypeError) as e:
            raise ValueError(f"Cannot access category at index {cat_index}: {e}") from e

        if found_names:
            df = df[found_names]

            if axis == "row":
                df = df.T

            net.load_df(df)
        else:
            print(f"No {axis}s found with category '{cat_name}' at index {cat_index}")

    except AttributeError as e:
        raise AttributeError(f"Network object missing required methods: {e}") from e
    except Exception as e:
        print(f"Category filtering failed: {e}")
        raise


def filter_names(net, axis: Literal["row", "col"], names: list[str]) -> None:
    """Filter network by specified names on given axis.

    Args:
        net: Network object with export_df/load_df methods
        axis: Filter axis - "row" or "col"
        names: List of names to filter by

    Raises:
        ValueError: If names is empty
        AttributeError: If net object missing required methods
    """
    if not names:
        raise ValueError("names list cannot be empty")

    try:
        df = net.export_df()

        if df.empty:
            warnings.warn("DataFrame is empty, no filtering applied", stacklevel=2)
            return

        # DataFrame filtering always works on columns - transpose if filtering rows
        if axis == "row":
            df = df.T

        # Use set for O(1) lookup performance
        name_set = set(names)
        found_names = [col for col in df.columns if _extract_name(col) in name_set]

        if found_names:
            df = df[found_names]

            if axis == "row":
                df = df.T

            net.load_df(df)
        else:
            print(f"No {axis}s found with specified names")

    except AttributeError as e:
        raise AttributeError(f"Network object missing required methods: {e}") from e
    except Exception as e:
        print(f"Name filtering failed: {e}")
        raise


def _extract_name(name: str | tuple) -> str:
    """Extract comparable name from column identifier.

    Args:
        name: Column identifier (string or tuple)

    Returns:
        Extracted name string
    """
    # Handle MultiIndex tuples
    check_name = name[0] if isinstance(name, tuple) else name
    # Extract name after colon separator if present
    return check_name.split(": ", 1)[1] if ": " in check_name else check_name
