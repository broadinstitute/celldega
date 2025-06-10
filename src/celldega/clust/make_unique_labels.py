# make_unique_labels


def main(net, df=None):
    """
    Run in load_data module (which runs when file is loaded or dataframe is loaded),
    check for duplicate row/col names, and add index to names if necessary
    """
    if df is None:
        df = net.export_df()

    # rows
    #############
    rows = df.index.tolist()
    if isinstance(rows[0], str):
        if len(rows) != len(list(set(rows))):
            print("warning: making row names unique")
            new_rows = add_index_list(rows)
            df.index = new_rows

    elif isinstance(rows[0], tuple):
        row_names = [inst_row[0] for inst_row in rows]

        if len(row_names) != len(list(set(row_names))):
            print("warning: making row names unique")
            row_names = add_index_list(row_names)

            # add back to tuple
            new_rows = []
            for inst_index in range(len(rows)):
                inst_row = rows[inst_index]
                new_row = list(inst_row)
                new_row[0] = row_names[inst_index]
                new_rows.append(tuple(new_row))

            df.index = new_rows

    # cols
    #############
    cols = df.columns.tolist()
    if isinstance(cols[0], str):
        # list column names
        if len(cols) != len(list(set(cols))):
            print("warning: making col names unique")
            new_cols = add_index_list(cols)
            df.columns = new_cols

    elif isinstance(cols[0], tuple):
        col_names = [inst_col[0] for inst_col in cols]

        if len(col_names) != len(list(set(col_names))):
            print("warning: making col names unique")
            col_names = add_index_list(col_names)

            # add back to tuple
            new_cols = []
            for inst_index in range(len(cols)):
                inst_col = cols[inst_index]
                new_col = list(inst_col)
                new_col[0] = col_names[inst_index]
                new_cols.append(tuple(new_col))

            df.columns = new_cols

    # return dataframe with unique names
    return df


def add_index_list(nodes):
    return [f"{nodes[i]}-{i + 1}" for i in range(len(nodes))]
