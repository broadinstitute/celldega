def main(real_net, vect_post):
    from copy import deepcopy

    import numpy as np

    from . import proc_df_labels
    from .__init__ import Network

    net = deepcopy(Network())

    sigs = vect_post["columns"]

    all_rows = []
    all_sigs = []
    for inst_sig in sigs:
        all_sigs.append(inst_sig["col_name"])

        col_data = inst_sig["data"]

        all_rows.extend(inst_row_data["row_name"] for inst_row_data in col_data)

    all_rows = sorted(set(all_rows))
    all_sigs = sorted(set(all_sigs))

    net.dat["nodes"]["row"] = all_rows
    net.dat["nodes"]["col"] = all_sigs

    net.dat["mat"] = np.empty((len(all_rows), len(all_sigs)))
    net.dat["mat"][:] = np.nan

    for inst_sig in sigs:
        inst_sig_name = inst_sig["col_name"]
        col_data = inst_sig["data"]

        for inst_row_data in col_data:
            inst_row = inst_row_data["row_name"]
            inst_value = inst_row_data["val"]

            row_index = all_rows.index(inst_row)
            col_index = all_sigs.index(inst_sig_name)

            net.dat["mat"][row_index, col_index] = inst_value

    tmp_df = net.dat_to_df()
    tmp_df = proc_df_labels.main(tmp_df)

    real_net.df_to_dat(tmp_df)
