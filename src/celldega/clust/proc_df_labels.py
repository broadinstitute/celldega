from ast import literal_eval as make_tuple

import numpy as np
import pandas as pd


def main(df: pd.DataFrame) -> pd.DataFrame:
    """Process DataFrame labels: numeric->string, tuple strings->tuples."""
    for axis in ["index", "columns"]:
        data = getattr(df, axis)
        if len(data) == 0:
            continue

        first = data[0]

        # Skip if already tuple
        if isinstance(first, tuple):
            continue

        # Convert numbers to strings
        if isinstance(first, int | float | np.int64):
            setattr(df, axis, [str(x) for x in data])

        # Convert tuple strings to tuples
        elif _is_tuple_string(first):
            setattr(df, axis, [make_tuple(x) for x in data])

    return df


def _is_tuple_string(s) -> bool:
    """Check if string represents tuple: starts with '(', ends with ')', has comma."""
    try:
        return s[0] == "(" and s[-1] == ")" and 0 < s.find(",") < len(s)
    except (TypeError, IndexError, AttributeError):
        return False
