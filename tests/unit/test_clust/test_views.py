"""Tests for reduced-dimensionality views built by Matrix.clust(views=...)."""

import sys
from types import SimpleNamespace

from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.clust import Matrix
from celldega.clust.matrix import marker_ranks_to_uns
from celldega.clust.utils import compute_marker_ranks
from celldega.set import SetCollection


N_GROUPS = 4
MARKERS_PER_GROUP = 8


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


def _grouped_adata(n_cells=400, n_genes=80, seed=1):
    """Cell-level data with a distinct block of marker genes per group.

    Group ``i`` gets genes ``g[i * MARKERS_PER_GROUP : (i + 1) * MARKERS_PER_GROUP]``
    lifted, so which *block* a marker comes from is deterministic. The lift
    decreases across the block, but stays large enough that the strongest genes
    separate their group perfectly and tie on the Wilcoxon score — so the order
    *within* a block is scanpy's to decide, and tests assert on block membership
    and per-group counts rather than on exact within-block ranks.
    """
    rng = np.random.default_rng(seed)
    values = rng.random((n_cells, n_genes)).astype("float32")
    labels = np.array([f"group{index}" for index in range(N_GROUPS)])[
        rng.integers(0, N_GROUPS, n_cells)
    ]

    for group_index in range(N_GROUPS):
        member = labels == f"group{group_index}"
        for offset in range(MARKERS_PER_GROUP):
            gene = group_index * MARKERS_PER_GROUP + offset
            values[member, gene] += 20.0 - offset

    return AnnData(
        X=values,
        obs=pd.DataFrame({"leiden": labels}, index=[f"cell{index}" for index in range(n_cells)]),
        var=pd.DataFrame(index=[f"g{index}" for index in range(n_genes)]),
    )


def _marker_matrix():
    pytest.importorskip("scanpy")
    adata = _grouped_adata()
    setc = SetCollection(adata, set_col="leiden", name="leiden")
    setc.calc_signature(
        adata,
        modality_name="expression",
        normalization=None,
        rank_genes_groups=True,
    )
    return Matrix(collection=setc, color_by="expression")


def _expected_top_markers(mat, per_cluster):
    """The union of each group's top ``per_cluster`` persisted markers."""
    expected = set()
    for _, frame in mat._marker_ranks.groupby("group", observed=True):
        names = frame.sort_values("rank")["names"].astype(str)
        expected.update(names[names.isin(mat.data.index.astype(str))][:per_cluster])
    return expected


def _view_genes(mat, view):
    return {str(mat.data.index[index]) for index in view["row_indices"]}


def test_compute_marker_ranks_preserves_scanpy_expression_sources(monkeypatch):
    """The lightweight working AnnData must retain forwarded Scanpy inputs."""
    adata = AnnData(
        X=np.zeros((4, 2)),
        obs=pd.DataFrame(
            {"leiden": ["a", "a", "b", "b"]},
            index=[f"cell{i}" for i in range(4)],
        ),
        var=pd.DataFrame(
            {"marker_mask": [True, False]},
            index=["g0", "g1"],
        ),
        layers={"counts": np.array([[5, 0], [4, 0], [0, 7], [0, 8]])},
    )
    adata.raw = adata
    captured = {}

    def rank_genes_groups(working, *, groupby, **kwargs):
        captured["working"] = working
        captured["groupby"] = groupby
        captured["kwargs"] = kwargs

    def rank_genes_groups_df(_working, *, group, key):
        captured["result_key"] = key
        return pd.DataFrame(
            {
                "group": ["a", "b"],
                "names": ["g0", "g1"],
                "scores": [1.0, 0.5],
                "logfoldchanges": [2.0, 1.0],
                "pvals": [0.01, 0.02],
                "pvals_adj": [0.02, 0.04],
            }
        )

    fake_scanpy = SimpleNamespace(
        tl=SimpleNamespace(rank_genes_groups=rank_genes_groups),
        get=SimpleNamespace(rank_genes_groups_df=rank_genes_groups_df),
    )
    monkeypatch.setitem(sys.modules, "scanpy", fake_scanpy)

    markers = compute_marker_ranks(
        adata,
        "leiden",
        {
            "layer": "counts",
            "use_raw": False,
            "mask_var": "marker_mask",
            "key_added": "custom_markers",
        },
    )

    working = captured["working"]
    assert np.array_equal(working.layers["counts"], adata.layers["counts"])
    assert working.raw is not None
    assert working.var["marker_mask"].tolist() == [True, False]
    assert captured["kwargs"]["layer"] == "counts"
    assert captured["result_key"] == "custom_markers"
    assert markers["rank"].tolist() == [0, 0]


# ---------------------------------------------------------------------------
# View construction
# ---------------------------------------------------------------------------


def test_views_default_to_no_views():
    mat = _matrix()
    mat.clust()
    assert mat.views == []
    assert mat.viz["views"] == []


def test_metric_levels_count_total_rows():
    mat = _matrix()
    mat.clust(views="var", levels=[5, 10, 25])

    assert [view["level"] for view in mat.views] == [5, 10, 25]
    for view in mat.views:
        assert view["view_type"] == "var"
        assert view["level_unit"] == "rows"
        # For metric views the level *is* the row count.
        assert view["n_rows"] == view["level"]


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


# ---------------------------------------------------------------------------
# Which rows get filtered out
# ---------------------------------------------------------------------------


def test_metric_views_keep_exactly_the_top_ranked_rows():
    frame = pd.DataFrame(
        [[index + 1.0, index + 2.0, index + 3.0, index + 4.0] for index in range(10)],
        index=[f"g{index}" for index in range(10)],
        columns=[f"c{index}" for index in range(4)],
    )

    mat = Matrix(frame, disable_processing=True)
    mat.clust(views="sum", levels=[3, 5])

    # Row sums increase with the index, so the top rows are the last ones.
    assert _view_genes(mat, mat.views[0]) == {"g7", "g8", "g9"}
    assert _view_genes(mat, mat.views[1]) == {"g5", "g6", "g7", "g8", "g9"}


def test_metric_views_rank_by_the_requested_metric():
    rng = np.random.default_rng(7)
    values = rng.random((10, 6))
    index = [f"g{position}" for position in range(10)]

    # g0: large and flat -> top by sum, bottom by variance.
    values[0] = 100.0 + rng.random(6) * 0.01
    # g9: centered on zero but wildly spread -> top by variance, middling sum.
    values[9] = np.array([-60.0, 60.0, -60.0, 60.0, -60.0, 60.0]) + rng.random(6) * 0.01

    frame = pd.DataFrame(values, index=index, columns=[f"c{position}" for position in range(6)])

    by_sum = Matrix(frame, disable_processing=True)
    by_sum.clust(views="sum", levels=[3])
    top_by_sum = _view_genes(by_sum, by_sum.views[0])

    by_var = Matrix(frame, disable_processing=True)
    by_var.clust(views="var", levels=[3])
    top_by_var = _view_genes(by_var, by_var.views[0])

    assert "g0" in top_by_sum and "g0" not in top_by_var
    assert "g9" in top_by_var and "g9" not in top_by_sum


def test_marker_levels_count_markers_per_cluster():
    mat = _marker_matrix()
    mat.clust(views="rank_genes_groups", levels=[1, 2, 3])

    assert [view["level"] for view in mat.views] == [1, 2, 3]
    for view in mat.views:
        assert view["level_unit"] == "per_cluster"
        # Planted marker blocks don't overlap between groups, so the union is
        # exactly level * n_groups rows -- the point of the per-cluster unit.
        assert view["n_rows"] == view["level"] * N_GROUPS


def test_marker_view_keeps_each_clusters_top_markers():
    mat = _marker_matrix()
    mat.clust(views="rank_genes_groups", levels=[1, 3, 5])

    for view in mat.views:
        assert _view_genes(mat, view) == _expected_top_markers(mat, view["level"])


def test_marker_view_only_draws_from_the_planted_marker_blocks():
    mat = _marker_matrix()
    mat.clust(views="rank_genes_groups", levels=[2])
    (view,) = mat.views

    blocks = {
        group: {f"g{group * MARKERS_PER_GROUP + offset}" for offset in range(MARKERS_PER_GROUP)}
        for group in range(N_GROUPS)
    }
    genes = _view_genes(mat, view)

    # Every selected gene is a planted marker, and each group contributes
    # exactly two. Which two within a block is left to scanpy -- the lifts are
    # large enough that the top handful separate perfectly and tie on score.
    assert genes <= set().union(*blocks.values())
    for group, block in blocks.items():
        assert len(genes & block) == 2, group


def test_every_cluster_is_represented_at_the_smallest_level():
    mat = _marker_matrix()
    mat.clust(views="rank_genes_groups", levels=[1])
    (view,) = mat.views

    genes = _view_genes(mat, view)
    assert len(genes) == N_GROUPS

    # One gene from each group's block, so no cluster is squeezed out.
    for group in range(N_GROUPS):
        block = {f"g{group * MARKERS_PER_GROUP + offset}" for offset in range(MARKERS_PER_GROUP)}
        assert genes & block


def test_marker_levels_nest():
    mat = _marker_matrix()
    mat.clust(views="rank_genes_groups", levels=[1, 2, 3, 5])

    for finer, coarser in zip(mat.views, mat.views[1:], strict=False):
        assert set(finer["row_indices"]).issubset(set(coarser["row_indices"]))


def test_marker_view_deduplicates_genes_shared_between_clusters():
    """A gene that tops two clusters takes one row, not two.

    Driven off a hand-written ranking rather than scanpy: making one gene rank
    first for two groups at once is awkward to arrange statistically (a gene high
    in two groups is *less* specific to either), and the dedup is what's under
    test, not the differential expression.
    """
    mat = _matrix(n_rows=12, n_cols=4)
    mat._marker_ranks = pd.DataFrame(
        [
            # groupA and groupB share "g0" as their best marker.
            {"group": "groupA", "names": "g0", "rank": 0},
            {"group": "groupA", "names": "g1", "rank": 1},
            {"group": "groupB", "names": "g0", "rank": 0},
            {"group": "groupB", "names": "g3", "rank": 1},
            {"group": "groupC", "names": "g5", "rank": 0},
            {"group": "groupC", "names": "g6", "rank": 1},
        ]
    )

    mat.clust(views="rank_genes_groups", levels=[2])
    (view,) = mat.views

    genes = [str(mat.data.index[index]) for index in view["row_indices"]]
    assert len(genes) == len(set(genes))
    # Five distinct genes across three groups x 2 markers, not six.
    assert set(genes) == {"g0", "g1", "g3", "g5", "g6"}


# ---------------------------------------------------------------------------
# Level filtering
# ---------------------------------------------------------------------------


def test_levels_covering_the_whole_matrix_are_dropped():
    mat = _matrix(n_rows=20)
    with pytest.warns(UserWarning, match="No requested view level"):
        mat.clust(views="var", levels=[20, 50])
    assert mat.views == []


def test_levels_resolving_to_the_same_rows_are_deduplicated():
    mat = _marker_matrix()
    # Each group only has MARKERS_PER_GROUP genes above background, but asking
    # past that just keeps pulling in the same tail, so several high levels land
    # on identical row sets.
    mat.clust(views="rank_genes_groups", levels=[1, 2, 2, 3])

    levels = [view["level"] for view in mat.views]
    assert levels == sorted(set(levels))

    row_sets = [tuple(view["row_indices"]) for view in mat.views]
    assert len(row_sets) == len(set(row_sets))


def test_views_ride_along_in_the_exported_metadata():
    mat = _matrix()
    mat.clust(views="var", levels=[5, 10])
    meta = mat.export_viz_parquet()["meta"]
    assert [view["level"] for view in meta["views"]] == [5, 10]


# ---------------------------------------------------------------------------
# Errors and persisted inputs
# ---------------------------------------------------------------------------


def test_multiple_view_types_are_rejected():
    mat = _matrix()
    with pytest.raises(ValueError, match="single view type"):
        mat.clust(views=["var", "sum"])


def test_unknown_view_type_is_rejected():
    mat = _matrix()
    with pytest.raises(ValueError, match="unknown view type"):
        mat.clust(views="nonsense")


def test_rank_genes_groups_view_requires_differential_expression():
    mat = _matrix()
    with pytest.raises(ValueError, match="needs differential expression"):
        mat.clust(views="rank_genes_groups")


def test_marker_ranks_are_picked_up_from_adata_uns():
    """A Matrix built from a signature carrying DE needs no extra wiring."""
    mat = _marker_matrix()

    signature = AnnData(
        X=mat.data.values.T,
        obs=pd.DataFrame(index=mat.data.columns.astype(str)),
        var=pd.DataFrame(index=mat.data.index.astype(str)),
        uns={"rank_genes_groups": marker_ranks_to_uns(mat._marker_ranks)},
    )

    rebuilt = Matrix(signature)
    rebuilt.clust(views="rank_genes_groups", levels=[2])
    assert _view_genes(rebuilt, rebuilt.views[0]) == _expected_top_markers(rebuilt, 2)


def test_marker_ranks_are_picked_up_from_scanpy_native_uns():
    """An AnnData that already had sc.tl.rank_genes_groups run on it works too."""
    sc = pytest.importorskip("scanpy")

    adata = _grouped_adata()
    adata.obs["leiden"] = adata.obs["leiden"].astype("category")
    sc.tl.rank_genes_groups(adata, groupby="leiden", method="wilcoxon")

    mat = Matrix(adata)
    mat.clust(views="rank_genes_groups", levels=[3])
    assert mat.views
