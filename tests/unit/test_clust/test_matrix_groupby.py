"""Matrix(adata, groupby=...): scanpy-backed dot plots from cell-level AnnData."""

from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.clust import Matrix


sc = pytest.importorskip("scanpy")


def _cells(seed: int = 0) -> AnnData:
    rng = np.random.default_rng(seed)
    n_cells, groups = 120, ["a", "b", "c"]
    labels = np.array(groups)[np.arange(n_cells) % 3]
    X = rng.poisson(0.3, size=(n_cells, 9)).astype("float32")
    for i, group in enumerate(groups):
        X[labels == group, i * 3 : i * 3 + 3] += 5
    obs = pd.DataFrame(
        {"leiden": pd.Categorical(labels, categories=groups)},
        index=[f"cell{i}" for i in range(n_cells)],
    )
    adata = AnnData(X=X, obs=obs, var=pd.DataFrame(index=[f"g{i}" for i in range(9)]))
    adata.uns["leiden_colors"] = ["#ff0000", "#00ff00", "#0000ff"]
    return adata


def test_groupby_builds_mean_and_fraction_dot_plot():
    adata = _cells()

    mat = Matrix(adata, groupby="leiden")

    assert mat.data.shape == (9, 3)
    assert list(mat.data.columns) == ["a", "b", "c"]
    expected_mean = (
        pd.DataFrame(adata.X, columns=adata.var_names)
        .groupby(adata.obs["leiden"].to_numpy())
        .mean()
    )
    np.testing.assert_allclose(mat.data.T.to_numpy(), expected_mean.to_numpy(), rtol=1e-5)

    expected_fraction = (
        (pd.DataFrame(adata.X, columns=adata.var_names) > 0)
        .groupby(adata.obs["leiden"].to_numpy())
        .mean()
    )
    np.testing.assert_allclose(
        mat.size_matrix.T.loc[["a", "b", "c"]].to_numpy(), expected_fraction.to_numpy()
    )
    assert mat.col_entity == {"entity": "cell", "attr": "leiden"}
    assert mat.row_entity == {"entity": "gene", "attr": "name"}
    assert list(mat.meta_col["n_cells"]) == [40, 40, 40]
    assert mat.viz["global_cat_colors"]["a"] == "#ff0000"


def test_groupby_reuses_scanpy_rank_genes_groups_for_marker_views():
    adata = _cells()
    sc.tl.rank_genes_groups(adata, groupby="leiden", method="t-test")

    mat = Matrix(adata, groupby="leiden")
    mat.cluster(view="rank_genes_groups", levels=[1, 3])

    assert mat._marker_ranks is not None
    top_a = mat._marker_ranks.query("group == 'a'").sort_values("rank")["names"].iloc[0]
    assert top_a in {"g0", "g1", "g2"}
    assert mat.views


def test_groupby_runs_rank_genes_groups_on_request():
    adata = _cells()

    without = Matrix(adata, groupby="leiden")
    assert without._marker_ranks is None
    with pytest.raises(ValueError, match="rank_genes_groups"):
        without.cluster(view="rank_genes_groups")

    computed = Matrix(adata, groupby="leiden", rank_genes_groups={"method": "t-test"})
    assert computed._marker_ranks is not None
    assert set(computed._marker_ranks["group"]) == {"a", "b", "c"}
    assert "rank_genes_groups" not in adata.uns  # the caller's AnnData is untouched


def test_groupby_ignores_ranks_for_another_grouping_and_false_skips():
    adata = _cells()
    adata.obs["other"] = pd.Categorical(np.where(np.arange(adata.n_obs) < 60, "x", "y"))
    sc.tl.rank_genes_groups(adata, groupby="other", method="t-test")

    assert Matrix(adata, groupby="leiden")._marker_ranks is None
    sc.tl.rank_genes_groups(adata, groupby="leiden", method="t-test")
    assert Matrix(adata, groupby="leiden", rank_genes_groups=False)._marker_ranks is None


def test_groupby_drops_unlabelled_cells():
    adata = _cells()
    labels = adata.obs["leiden"].astype(object)
    labels.iloc[:3] = np.nan
    adata.obs["leiden"] = pd.Categorical(labels, categories=["a", "b", "c"])

    mat = Matrix(adata, groupby="leiden")

    assert list(mat.data.columns) == ["a", "b", "c"]
    assert list(mat.meta_col["n_cells"]) == [39, 39, 39]


def test_groupby_layer_and_input_errors():
    adata = _cells()
    adata.layers["counts"] = adata.X * 2

    mat = Matrix(adata, groupby="leiden", layer="counts")
    assert mat.data.loc["g0", "a"] == pytest.approx(
        2 * Matrix(adata, groupby="leiden").data.loc["g0", "a"]
    )

    with pytest.raises(ValueError, match="requires a cell-level AnnData"):
        Matrix(pd.DataFrame(adata.X), groupby="leiden")
    with pytest.raises(ValueError, match="require `groupby`"):
        Matrix(adata, layer="counts")
    with pytest.raises(ValueError, match="not found"):
        Matrix(adata, groupby="nope")
