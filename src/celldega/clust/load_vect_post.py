from copy import deepcopy
from typing import Any

import numpy as np

from . import proc_df_labels
from .__init__ import Network


def main(real_net: Any, vect_post: dict[str, list[dict[str, Any]]]) -> None:
    """
    Process vector post data into a network matrix format.

    Args:
        real_net: Network object to populate with processed data
        vect_post: Dictionary containing columns data with structure:
                  {"columns": [{"col_name": str, "data": [{"row_name": str, "val": Union[int, float]}]}]}
    """
    net = deepcopy(Network())
    columns = vect_post["columns"]

    # Extract unique rows and columns in single pass with better space efficiency
    all_rows = set()
    all_sigs = set()

    for column in columns:
        all_sigs.add(column["col_name"])
        all_rows.update(row_data["row_name"] for row_data in column["data"])

    # Convert to sorted lists for consistent ordering
    sorted_rows = sorted(all_rows)
    sorted_sigs = sorted(all_sigs)

    # Initialize network structure
    net.dat["nodes"]["row"] = sorted_rows
    net.dat["nodes"]["col"] = sorted_sigs

    # Pre-allocate matrix with NaN values
    matrix = np.full((len(sorted_rows), len(sorted_sigs)), np.nan)

    # Create O(1) lookup mappings
    row_indices = {row: idx for idx, row in enumerate(sorted_rows)}
    col_indices = {col: idx for idx, col in enumerate(sorted_sigs)}

    # Populate matrix efficiently
    for column in columns:
        col_name = column["col_name"]
        col_idx = col_indices[col_name]

        for row_data in column["data"]:
            row_idx = row_indices[row_data["row_name"]]
            matrix[row_idx, col_idx] = row_data["val"]

    net.dat["mat"] = matrix

    # Process and transfer data to real network
    processed_df = proc_df_labels.main(net.dat_to_df())
    real_net.df_to_dat(processed_df)
