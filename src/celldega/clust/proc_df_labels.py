from ast import literal_eval as make_tuple

import numpy as np
import pandas as pd


def main(df: pd.DataFrame) -> pd.DataFrame:
    """Process DataFrame labels: numeric->string, tuple strings->tuples.

    Args:
        df: Input DataFrame to process

    Returns:
        DataFrame with processed labels

    Raises:
        TypeError: If df is not a pandas DataFrame
        ValueError: If tuple strings are malformed
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas DataFrame, got {type(df)}")

    for axis in ["index", "columns"]:
        data = getattr(df, axis)
        if len(data) == 0:
            continue

        first = data[0]

        # Skip if already tuple
        if isinstance(first, tuple):
            continue

        # Convert numbers to strings
        if isinstance(first, (int | float | np.integer | np.floating)):
            setattr(df, axis, [str(x) for x in data])

        # Convert tuple strings to tuples
        elif _is_tuple_string(first):
            try:
                setattr(df, axis, [_safe_make_tuple(x) for x in data])
            except ValueError as e:
                raise ValueError(f"Failed to parse tuple strings in {axis}: {e}") from e

    return df


def _is_tuple_string(s) -> bool:
    """Check if string represents tuple: starts with '(', ends with ')', has comma.

    Args:
        s: String to check

    Returns:
        True if string appears to be a tuple representation
    """
    try:
        return (
            isinstance(s, str)
            and len(s) >= 4  # Minimum "(,)" length
            and s[0] == "("
            and s[-1] == ")"
            and "," in s
        )
    except (TypeError, AttributeError):
        return False


def _safe_make_tuple(s) -> tuple:
    """Safely convert string to tuple with error handling.

    Args:
        s: String representation of tuple

    Returns:
        Parsed tuple

    Raises:
        ValueError: If string cannot be parsed as tuple
    """
    try:
        result = make_tuple(s)
        if not isinstance(result, tuple):
            raise ValueError(f"Expected tuple, got {type(result)}")
        return result
    except (SyntaxError, ValueError) as e:
        raise ValueError(f"Invalid tuple string '{s}': {e}") from e
