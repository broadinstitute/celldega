"""Regression coverage for Atera stores with NumPy variable-length strings."""

import numpy as np
import pandas as pd
import zarr

from celldega.pre.atera import read_atera_cbg, read_atera_clusters


def test_read_atera_variable_length_strings(tmp_path):
    path = tmp_path / "cell_feature_matrix.zarr.zip"
    with zarr.storage.ZipStore(str(path), mode="w") as store:
        root = zarr.open_group(store=store, mode="w")
        x = root.create_group("X", attributes={"shape": [3, 2]})
        x.create_array("data", data=np.array([1, 4, 2], dtype=np.int32))
        x.create_array("indices", data=np.array([0, 1, 1], dtype=np.int32))
        x.create_array("indptr", data=np.array([0, 2, 2, 3], dtype=np.int32))
        obs = root.create_group("obs")
        obs.create_array("barcode", data=np.array(["cell-a", "cell-b", "cell-c"], dtype="T"))
        clustering = obs.create_group("leiden_res_1.0")
        clustering.create_array("codes", data=np.array([1, -1, 0], dtype=np.int32))
        clustering.create_array("categories", data=np.array(["0", "10"], dtype="T"))
        var = root.create_group("var")
        var.create_array("feature_name", data=np.array(["A1BG", "LONG_GENE_NAME"], dtype="T"))

    cbg = read_atera_cbg(path)
    assert cbg.index.tolist() == ["cell-a", "cell-b", "cell-c"]
    assert cbg.columns.tolist() == ["A1BG", "LONG_GENE_NAME"]
    np.testing.assert_array_equal(cbg.sparse.to_dense(), [[1, 4], [0, 0], [0, 2]])

    clusters = read_atera_clusters(path)
    assert clusters.index.tolist() == cbg.index.tolist()
    assert clusters.loc["cell-a"] == "10"
    assert pd.isna(clusters.loc["cell-b"])
    assert clusters.loc["cell-c"] == "0"
