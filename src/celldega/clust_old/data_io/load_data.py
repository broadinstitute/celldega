"""Data loading utilities for clustering analysis."""

import io
import json
from pathlib import Path
import sys
from typing import Any, TextIO

import pandas as pd

from ..categories import categories
from ..core import data_formats
from . import proc_df_labels


try:
    import StringIO
except ImportError:
    from io import StringIO

# Type aliases for clarity
NetworkType = Any  # Network object type not defined in this module
PathLike = str | Path
FileContent = str | bytes
BufferType = TextIO | io.StringIO


def load_file(net: NetworkType, filename: PathLike) -> None:
    """
    Load data from a file into the network object.
    """
    net.reset()
    file_content = Path(filename).read_text()
    load_file_as_string(net, file_content, filename)


def load_file_as_string(
    net: NetworkType, file_content: FileContent, filename: PathLike = ""
) -> None:
    """
    Load data from string content into the network object.
    """
    # Convert bytes to string if necessary
    content = file_content.decode() if isinstance(file_content, bytes) else file_content

    with io.StringIO(content) as buffer:
        net.load_tsv_to_net(buffer, Path(filename).name)


def load_stdin(net: NetworkType) -> None:
    """
    Load data from standard input into the network object.
    """
    content = "".join(sys.stdin)
    buffer = StringIO(content)
    net.load_tsv_to_net(buffer, None)


def load_tsv_to_net(net: NetworkType, file_buffer: BufferType, filename=None) -> None:
    """
    Load TSV data from buffer into network object with category detection.
    """
    # Reset buffer position for reliable reading
    file_buffer.seek(0)

    # Detect category structure
    lines = file_buffer.getvalue().split("\n")
    category_counts = categories.check_categories(lines)

    # Prepare index arrays for pandas
    row_indices = list(range(category_counts["row"]))
    col_indices = list(range(category_counts["col"]))

    # Reset buffer position for pandas
    file_buffer.seek(0)

    # Load data with appropriate header configuration
    dataframe = (
        pd.read_table(file_buffer, index_col=row_indices, header=col_indices)
        if len(col_indices) > 1
        else pd.read_table(file_buffer, index_col=row_indices)
    )

    # Process labels and integrate into network
    processed_df = proc_df_labels.main(dataframe)
    net.df_to_dat(processed_df, True)
    net.dat["filename"] = filename


def load_json_to_dict(filename: PathLike) -> dict[str, Any]:
    """
    Load JSON data from file.
    """
    with Path(filename).open() as file:
        return json.load(file)


def load_gmt(filename: PathLike) -> dict[str, list[str]]:
    """
    Load GMT (Gene Matrix Transposed) format file.
    """
    with Path(filename).open() as file:
        lines = file.readlines()

    gmt_data = {}
    for line in lines:
        stripped_line = line.rstrip()
        pathway_name = stripped_line.split("\t")[0]
        gene_list = stripped_line.split("\t")[2:]
        gmt_data[pathway_name] = gene_list

    return gmt_data


def load_data_to_net(net: NetworkType, inst_net: dict[str, Any]) -> None:
    """
    Load pre-structured data into network object.
    """
    net.dat["nodes"] = inst_net["nodes"]
    net.dat["mat"] = inst_net["mat"]
    data_formats.mat_to_numpy_arr(net)
