import io
import json
from pathlib import Path
import sys

import pandas as pd

from . import categories, data_formats, proc_df_labels


try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


def load_file(net, filename):
    # reset network when loading file, prevents errors when loading new file
    # have persistent categories

    net.reset()

    file_string = Path(filename).read_text()

    load_file_as_string(net, file_string, filename)


def load_file_as_string(net, file_content: str | bytes, filename: str = "") -> None:
    # Decode bytes → str if necessary
    if isinstance(file_content, bytes):
        file_content = file_content.decode()

    # Use StringIO as an in-memory text file; context manager auto-closes it.
    with io.StringIO(str(file_content)) as buffer:
        net.load_tsv_to_net(buffer, Path(filename).name)


def load_stdin(net):
    data = ""

    for line in sys.stdin:
        data = data + line

    data = StringIO.StringIO(data)

    net.load_tsv_to_net(data)


def load_tsv_to_net(net, file_buffer, filename=None):
    lines = file_buffer.getvalue().split("\n")
    num_labels = categories.check_categories(lines)

    row_arr = list(range(num_labels["row"]))
    col_arr = list(range(num_labels["col"]))

    # use header if there are col categories
    if len(col_arr) > 1:
        df = pd.read_table(file_buffer, index_col=row_arr, header=col_arr)
    else:
        df = pd.read_table(file_buffer, index_col=row_arr)

    df = proc_df_labels.main(df)

    net.df_to_dat(df, True)
    net.dat["filename"] = filename


def load_json_to_dict(filename):
    with Path.open(filename) as f:
        return json.load(f)


def load_gmt(filename):
    with Path.open(filename) as f:
        lines = f.readlines()

    gmt = {}
    for i in range(len(lines)):
        inst_line = lines[i].rstrip()
        inst_term = inst_line.split("\t")[0]
        inst_elems = inst_line.split("\t")[2:]
        gmt[inst_term] = inst_elems

    return gmt


def load_data_to_net(net, inst_net):
    """load data into nodes and mat, also convert mat to numpy array"""
    net.dat["nodes"] = inst_net["nodes"]
    net.dat["mat"] = inst_net["mat"]
    data_formats.mat_to_numpy_arr(net)
