from copy import deepcopy
import json
from pathlib import Path


def export_net_json(net, net_type, indent="no-indent"):
    """export json string of dat"""

    if net_type == "dat":
        exp_dict = deepcopy(net.dat)

        if not isinstance(exp_dict["mat"], list):
            exp_dict["mat"] = exp_dict["mat"].tolist()

    elif net_type == "viz":
        exp_dict = net.viz

    elif net_type == "sim_row":
        exp_dict = net.sim["row"]

    elif net_type == "sim_col":
        exp_dict = net.sim["col"]

    else:
        raise ValueError(
            f"Invalid net_type: '{net_type}'. Must be one of: 'dat', 'viz', 'sim_row', 'sim_col'"
        )

    return json.dumps(exp_dict, indent=2) if indent == "indent" else json.dumps(exp_dict)


def write_matrix_to_tsv(net, filename=None, df=None):
    """
    This will export the matrix in net.dat or a dataframe (optional df in
    arguments) as a tsv file. Row/column categories will be saved as tuples in
    tsv, which can be read back into the network object.
    """

    if df is None:
        df = net.dat_to_df()

    return df.to_csv(filename, sep="\t")


def write_json_to_file(net, net_type, filename, indent="no-indent"):
    """Write network JSON to file with error handling."""
    try:
        exp_json = net.export_net_json(net_type, indent)

        with Path(filename).open("w") as fw:
            fw.write(exp_json)

    except OSError as e:
        raise OSError(f"Failed to write JSON to file '{filename}': {e}") from e


def save_dict_to_json(inst_dict, filename, indent="no-indent"):
    """Save dictionary to JSON file with error handling."""
    try:
        with Path(filename).open("w") as fw:
            if indent == "indent":
                fw.write(json.dumps(inst_dict, indent=2))
            else:
                fw.write(json.dumps(inst_dict))

    except OSError as e:
        raise OSError(f"Failed to write JSON to file '{filename}': {e}") from e
    except (TypeError, ValueError) as e:
        raise ValueError(f"Failed to serialize dictionary to JSON: {e}") from e
