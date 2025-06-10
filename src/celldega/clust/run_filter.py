def df_filter_row_sum(df, threshold, take_abs=True):
    """filter rows in matrix at some threshold
    and remove columns that have a sum below this threshold"""

    from copy import deepcopy

    from .__init__ import Network

    _ = Network()

    df_copy = deepcopy(df.abs()) if take_abs else deepcopy(df)

    ini_rows = df_copy.index.values.tolist()
    df_copy = df_copy.transpose()
    tmp_sum = df_copy.sum(axis=0)
    tmp_sum = tmp_sum.abs()
    tmp_sum.sort_values(inplace=True, ascending=False)

    tmp_sum = tmp_sum[tmp_sum > threshold]
    keep_rows = sorted(tmp_sum.index.values.tolist())

    if len(keep_rows) < len(ini_rows):
        df = grab_df_subset(df, keep_rows=keep_rows)

    return df


def df_filter_col_sum(df, threshold, take_abs=True):
    """filter columns in matrix at some threshold
    and remove rows that have all zero values"""

    from copy import deepcopy

    from .__init__ import Network

    _ = Network()

    df_copy = deepcopy(df.abs()) if take_abs else deepcopy(df)

    df_copy = df_copy.transpose()
    df_copy = df_copy[df_copy.sum(axis=1) > threshold]
    df_copy = df_copy.transpose()
    df_copy = df_copy[df_copy.sum(axis=1) > 0]

    if take_abs:
        inst_rows = df_copy.index.tolist()
        inst_cols = df_copy.columns.tolist()
        df = grab_df_subset(df, inst_rows, inst_cols)

    else:
        df = df_copy

    return df


def grab_df_subset(df, keep_rows="all", keep_cols="all"):
    if keep_cols != "all":
        df = df[keep_cols]
    if keep_rows != "all":
        df = df.loc[keep_rows]
    return df


def get_sorted_rows(df, rank_type="sum"):
    from copy import deepcopy

    inst_df = deepcopy(df)
    inst_df = inst_df.transpose()

    tmp_sum = inst_df.sum(axis=0) if rank_type == "sum" else inst_df.var(axis=0)

    tmp_sum = tmp_sum.abs()
    tmp_sum.sort_values(inplace=True, ascending=False)
    return tmp_sum.index.values.tolist()


def filter_n_top(inst_rc, df, n_top, rank_type="sum"):
    if inst_rc == "col":
        df = df.transpose()

    rows_sorted = get_sorted_rows(df, rank_type)

    keep_rows = rows_sorted[:n_top]

    df = df.loc[keep_rows]

    if inst_rc == "col":
        df = df.transpose()

    return df


def filter_threshold(df, inst_rc, threshold, num_occur=1):
    """
    Filter a network's rows or cols based on num_occur values being above a
    threshold (in absolute_value)
    """
    from copy import deepcopy

    inst_df = deepcopy(df)

    if inst_rc == "col":
        inst_df = inst_df.transpose()

    inst_df = inst_df.abs()

    ini_rows = inst_df.index.values.tolist()

    inst_df[inst_df < threshold] = 0
    inst_df[inst_df >= threshold] = 1

    tmp_sum = inst_df.sum(axis=1)

    tmp_sum = tmp_sum[tmp_sum >= num_occur]

    keep_names = tmp_sum.index.values.tolist()

    if inst_rc == "row":
        if len(keep_names) < len(ini_rows):
            df = grab_df_subset(df, keep_rows=keep_names)

    elif inst_rc == "col":
        inst_df = inst_df.transpose()

        inst_rows = inst_df.index.values.tolist()
        inst_cols = keep_names

        df = grab_df_subset(df, inst_rows, inst_cols)

    return df


def filter_cat(net, axis, cat_index, cat_name):
    try:
        df = net.export_df()

        # DataFrame filtering will be run always be run on columns if the user
        # wants to filter rows, transpose the matrix before and after
        if axis == "row":
            df = df.transpose()

        all_names = df.columns.tolist()

        if found_names := [i for i in all_names if i[cat_index] == cat_name]:
            df = df[found_names]

            if axis == "row":
                df = df.transpose()
        else:
            print(f"no {axis}s were found with this category and filtering was not run")

        net.load_df(df)

    except Exception:
        print(
            "category filtering did not run\n check that your category filtering is set up correctly"
        )


def filter_names(net, axis, names):
    print("filter_names")
    print(names)

    try:
        df = net.export_df()

        # Dataframe filtering will always be run on the columns. If the user wants to filter rows, then it will transpose back and forth.

        if axis == "row":
            df = df.transpose()

        all_names = df.columns.tolist()

        found_names = []
        for inst_name in all_names:
            check_name = inst_name[0] if isinstance(inst_name, tuple) else inst_name

            if ": " in check_name:
                check_name = check_name.split(": ")[1]

            if check_name in names:
                found_names.append(inst_name)

        if found_names:
            df = df[found_names]

            if axis == "row":
                df = df.transpose()

            net.load_df(df)

        else:
            print(f"no {axis}s were found with these names")

    except Exception:
        print("error in filtering names")

    print(found_names)
