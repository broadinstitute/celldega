"""Tests for reduced-dimensionality views built by Matrix.clust(views=...)."""

from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.clust import Matrix


def _matrix(n_rows=40, n_cols=6, seed=0):
    rng = np.random.default_rng(seed)
    return Matrix(
        pd.DataFrame(
            rng.random((n_rows, n_cols)),
            index=[f"g{i}" for i in range(n_rows)],
            columns=[f"c{j}" for j in range(n_cols)],
        ),
        disable_processing=True,
    )


def _grouped_adata(n_cells=240, n_genes=60, n_groups=3, seed=1):
    """Cell-level data with a distinct block of marker genes per group."""
    rng = np.random.default_rng(seed)
    values = rng.random((n_cells, n_genes)).astype("float32")
    labels = np.array([f"group{index}" for index in range(n_groups)])[
        rng.integers(0, n_groups, n_cells)
    ]

    for index in range(n_groups):
        block = slice(index * 5, (index + 1) * 5)
        values[labels == f"group{index}", block] += 5

    return AnnData(
        X=values,
        obs=pd.DataFrame({"leiden": labels}, index=[f"cell{index}" for index in range(n_cells)]),
        var=pd.DataFrame(index=[f"g{index}" for index in range(n_genes)]),
    )


def test_views_default_to_no_views():
    mat = _matrix()
    mat.clust()
    assert mat.views == []
    assert mat.viz["views"] == []


def test_metric_views_need_no_differential_expression():
    mat = _matrix()
    mat.clust(views="var", levels=[5, 10, 25])

    assert [view["level"] for view in mat.views] == [5, 10, 25]
    for view in mat.views:
        assert view["view_type"] == "var"
        assert view["n_rows"] == view["level"]
        assert len(view["row_indices"]) == view["level"]


def test_view_arrays_are_sized_and_ordered_for_the_front_end():
    mat = _matrix(n_rows=40, n_cols=6)
    mat.clust(views="sum", levels=[10])
    (view,) = mat.views

    # Ascending row indices are what lets the front end map this view's scipy
    # leaf ids back onto matrix rows.
    assert view["row_indices"] == sorted(view["row_indices"])

    # Order arrays span the full matrix; linkage spans only the view.
    assert len(view["row_clust"]) == 40
    assert len(view["col_clust"]) == 6
    assert np.array(view["row_linkage"]).shape == (9, 4)
    assert np.array(view["col_linkage"]).shape == (5, 4)

    # Kept rows carry 1-based positions; everything else is zeroed out.
    kept = sorted(view["row_clust"][index] for index in view["row_indices"])
    assert kept == list(range(1, 11))
    assert all(
        view["row_clust"][index] == 0
        for index in range(40)
        if index not in set(view["row_indices"])
    )


def test_views_pick_the_highest_ranked_rows():
    frame = pd.DataFrame(
        np.zeros((10, 4)),
        index=[f"g{i}" for i in range(10)],
        columns=[f"c{j}" for j in range(4)],
    )
    # g0..g9 get strictly increasing row sums, with noise so clustering works.
    for index in range(10):
        frame.iloc[index] = [index + 1, index + 2, index + 3, index + 4]

    mat = Matrix(frame, disable_processing=True)
    mat.clust(views="sum", levels=[3])
    (view,) = mat.views

    assert sorted(mat.data.index[index] for index in view["row_indices"]) == [
        "g7",
        "g8",
        "g9",
    ]


def test_levels_at_or_above_the_row_count_are_dropped():
    mat = _matrix(n_rows=20)
    with pytest.warns(UserWarning, match="No requested view level fits"):
        mat.clust(views="var", levels=[20, 50])
    assert mat.views == []


def test_views_ride_along_in_the_exported_metadata():
    mat = _matrix()
    mat.clust(views="var", levels=[5, 10])
    meta = mat.export_viz_parquet()["meta"]
    assert [view["level"] for view in meta["views"]] == [5, 10]


def test_multiple_view_types_are_rejected():
    mat = _matrix()
    with pytest.raises(ValueError, match="single view type"):
        mat.clust(views=["var", "sum"])


def test_unknown_view_type_is_rejected():
    mat = _matrix()
    with pytest.raises(ValueError, match="unknown view type"):
        mat.clust(views="nonsense")


def test_rank_genes_groups_view_requires_stashed_results():
    mat = _matrix()
    with pytest.raises(ValueError, match="downsample_to"):
        mat.clust(views="rank_genes_groups")


def test_downsample_to_stashes_rank_genes_groups_results():
    pytest.importorskip("scanpy")

    mat = Matrix(_grouped_adata())
    mat.downsample_to("leiden", rank_genes=True)

    assert mat.marker_ranks is not None
    assert set(mat.marker_ranks["group"]) == {"group0", "group1", "group2"}
    # scanpy orders each group best-first; `rank` makes that explicit.
    for _, frame in mat.marker_ranks.groupby("group"):
        assert frame["rank"].tolist() == sorted(frame["rank"].tolist())

    # Aggregation still happened: columns are now the groups.
    assert sorted(mat.data.columns) == ["group0", "group1", "group2"]


def test_downsample_to_rejects_rank_genes_on_the_row_axis():
    pytest.importorskip("scanpy")

    mat = Matrix(_grouped_adata())
    with pytest.raises(ValueError, match="requires axis='col'"):
        mat.downsample_to("leiden", axis="row", rank_genes=True)


def test_set_marker_ranks_supports_matrices_built_without_downsample_to():
    pytest.importorskip("scanpy")

    adata = _grouped_adata()
    # Pre-aggregated by hand, the way a SetCollection signature arrives — this
    # matrix never passes through downsample_to.
    frame = pd.DataFrame(
        {
            group: np.asarray(adata[adata.obs["leiden"] == group].X).mean(axis=0)
            for group in sorted(adata.obs["leiden"].unique())
        },
        index=adata.var_names,
    )

    mat = Matrix(frame, disable_processing=True)
    assert mat.set_marker_ranks(adata, groupby="leiden") is mat
    assert mat.marker_ranks is not None

    mat.clust(views="rank_genes_groups", levels=[15])
    (view,) = mat.views
    assert {mat.data.index[index] for index in view["row_indices"]} == {
        f"g{index}" for index in range(15)
    }


def test_set_marker_ranks_rejects_a_missing_groupby():
    pytest.importorskip("scanpy")

    mat = _matrix()
    with pytest.raises(ValueError, match=r"not found in adata\.obs"):
        mat.set_marker_ranks(_grouped_adata(), groupby="missing")


def test_marker_view_interleaves_across_groups():
    pytest.importorskip("scanpy")

    mat = Matrix(_grouped_adata())
    mat.downsample_to("leiden", rank_genes=True)
    mat.clust(views="rank_genes_groups", levels=[3, 15])

    assert [view["level"] for view in mat.views] == [3, 15]

    # Round-robin means the smallest level takes one marker per group, and the
    # 15-row level covers all three planted 5-gene marker blocks.
    top = {mat.data.index[index] for index in mat.views[0]["row_indices"]}
    assert len(top) == 3

    fifteen = {mat.data.index[index] for index in mat.views[1]["row_indices"]}
    assert fifteen == {f"g{index}" for index in range(15)}

    # Levels nest: raising the slider only ever adds rows.
    assert top.issubset(fifteen)
