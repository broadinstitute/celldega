"""Round trips of a clustered Matrix through its AnnData Zarr store."""

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from celldega.clust import Matrix
from celldega.clust.matrix import marker_ranks_to_uns
from celldega.viz import Clustergram


PARQUET_KEYS = ("mat", "dot_mat", "row_nodes", "col_nodes", "row_linkage", "col_linkage")


def _dataframe_matrix(seed=0):
    """Views by variance, a size matrix with a NaN, and categories with "/" and gaps."""
    rng = np.random.default_rng(seed)
    rows = [f"g{i}" for i in range(30)]
    cols = [f"c{j}" for j in range(8)]
    meta_row = pd.DataFrame(
        {"lineage": rng.choice(["T/NK", "B", "Myeloid"], size=30), "score": rng.random(30)},
        index=rows,
    )
    meta_row.loc["g3", "lineage"] = np.nan
    meta_col = pd.DataFrame(
        {"group": rng.choice(["a", "b"], size=8), "depth": rng.random(8)}, index=cols
    )
    mat = Matrix(
        pd.DataFrame(rng.normal(size=(30, 8)), index=rows, columns=cols),
        meta_col=meta_col,
        meta_row=meta_row,
        row_entity={"entity": "gene", "attr": "name"},
        col_entity={"entity": "cell", "attr": "leiden"},
        name="roundtrip",
    )
    size = pd.DataFrame(rng.random((30, 8)), index=rows, columns=cols)
    size.iloc[0, 0] = np.nan
    mat.set_size_matrix(size)
    mat.cluster(view="var", levels=[5, 10, 20])
    return mat


def _marker_matrix(seed=1):
    """Marker-ranked views from ranks carried in the AnnData's uns."""
    rng = np.random.default_rng(seed)
    groups = ["0", "1", "2"]
    genes = [f"gene{i}" for i in range(24)]
    markers = pd.DataFrame(
        {
            "group": np.repeat(groups, len(genes)),
            "names": genes * len(groups),
            "scores": rng.normal(size=len(groups) * len(genes)),
            "logfoldchanges": rng.normal(size=len(groups) * len(genes)),
            "pvals": rng.random(len(groups) * len(genes)),
            "pvals_adj": rng.random(len(groups) * len(genes)),
        }
    )
    markers = markers.sort_values(["group", "scores"], ascending=[True, False])
    markers["rank"] = markers.groupby("group").cumcount()
    adata = ad.AnnData(
        rng.random((len(groups), len(genes))),
        obs=pd.DataFrame({"leiden": pd.Categorical(groups)}, index=groups),
        var=pd.DataFrame(index=genes),
    )
    adata.uns["rank_genes_groups"] = marker_ranks_to_uns(markers.reset_index(drop=True))
    mat = Matrix(adata, col_attr=["leiden"])
    mat.norm("row", by="zscore")
    mat.cluster(view="rank_genes_groups", levels=[1, 2, 4])
    return mat


def _assert_same_clustergram(original, restored):
    expected, actual = original.export_viz_parquet(), restored.export_viz_parquet()
    for key in PARQUET_KEYS:
        assert actual[key] == expected[key], key
    assert actual["meta"] == expected["meta"]
    assert actual["row_entity"] == expected["row_entity"]
    assert actual["col_entity"] == expected["col_entity"]


@pytest.mark.parametrize("build", [_dataframe_matrix, _marker_matrix])
@pytest.mark.parametrize("zarr_format", [3, 2])
def test_round_trip_reproduces_the_clustergram(tmp_path, build, zarr_format):
    original = build()
    path = tmp_path / "matrix.zarr"
    original.write_zarr(path, zarr_format=zarr_format)

    restored = Matrix.read_zarr(path)

    _assert_same_clustergram(original, restored)
    assert restored.views == original.views
    pd.testing.assert_frame_equal(
        restored.cut_tree(axis="col", n_clusters=2).to_frame(),
        original.cut_tree(axis="col", n_clusters=2).to_frame(),
    )


def test_default_float32_and_lossless_float64(tmp_path):
    original = _dataframe_matrix()
    original.write_zarr(tmp_path / "float32.zarr")
    original.write_zarr(tmp_path / "native.zarr", dtype=None)

    assert Matrix.read_zarr(tmp_path / "float32.zarr").data.values.dtype == np.float32
    native = Matrix.read_zarr(tmp_path / "native.zarr")
    pd.testing.assert_frame_equal(native.data, original.data)
    pd.testing.assert_frame_equal(native.meta_row, original.meta_row)
    pd.testing.assert_frame_equal(native.meta_col, original.meta_col)


def test_reading_does_not_recluster(tmp_path, monkeypatch):
    original = _dataframe_matrix()
    original.write_zarr(tmp_path / "matrix.zarr")

    def fail(*args, **kwargs):
        raise AssertionError("read_zarr must not re-cluster")

    monkeypatch.setattr(Matrix, "cluster", fail)
    monkeypatch.setattr(Matrix, "make_viz", fail)
    monkeypatch.setattr("celldega.clust.matrix.linkage", fail)

    restored = Matrix.read_zarr(tmp_path / "matrix.zarr")
    assert restored._clustered


def test_restored_matrix_builds_the_same_widget(tmp_path):
    original = _marker_matrix()
    original.write_zarr(tmp_path / "matrix.zarr")
    restored = Matrix.read_zarr(tmp_path / "matrix.zarr")

    expected, actual = Clustergram(matrix=original), Clustergram(matrix=restored)
    for trait in ("mat_parquet", "row_nodes_parquet", "col_nodes_parquet", "row_entity"):
        assert getattr(actual, trait) == getattr(expected, trait), trait
    assert actual.network_meta == expected.network_meta


def test_plain_anndata_reader_keeps_entities_and_markers(tmp_path):
    original = _marker_matrix()
    original.write_zarr(tmp_path / "matrix.zarr")

    reloaded = Matrix(ad.read_zarr(tmp_path / "matrix.zarr"))

    assert reloaded.row_entity == original.row_entity
    assert reloaded.col_entity == original.col_entity
    assert reloaded._marker_ranks is not None
    assert set(reloaded._marker_ranks["names"]) == set(original._marker_ranks["names"])


def test_unclustered_matrix_cannot_be_saved(tmp_path):
    mat = Matrix(pd.DataFrame(np.ones((3, 2)), index=["a", "b", "c"], columns=["x", "y"]))
    with pytest.raises(ValueError, match="cluster"):
        mat.write_zarr(tmp_path / "matrix.zarr")


def test_reader_rejects_other_anndata():
    with pytest.raises(ValueError, match="clustered Matrix"):
        Matrix.from_clustered_adata(ad.AnnData(np.ones((2, 2))))
