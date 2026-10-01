"""Tests for the set-level SetCollection and its derived modalities."""

from anndata import AnnData
from mudata import MuData
import numpy as np
import pandas as pd
import pytest

from celldega.set import SetCollection, concat_sets


def _adata(seed=0, n=60, g=8):
    rng = np.random.default_rng(seed)
    cells = [f"cell{i}" for i in range(n)]
    obs = pd.DataFrame(
        {
            "leiden": rng.integers(0, 3, n).astype(str),
            "spagcn": rng.integers(0, 4, n).astype(str),
            "cell_type": rng.choice(["T", "B", "Mac"], n),
            "center_x": rng.random(n),
            "center_y": rng.random(n),
        },
        index=cells,
    )
    var = pd.DataFrame(index=[f"g{j}" for j in range(g)])
    return AnnData(X=rng.poisson(2, (n, g)).astype(float), obs=obs, var=var)


def test_membership_modality_shape_and_coords():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    membership = clust.mod["membership"]
    # one row per set, one column per cell
    assert membership.n_obs == adata.obs["leiden"].nunique()
    assert membership.n_vars == adata.n_obs
    # n_cells in obs equals membership row sums
    assert clust.obs["n_cells"].sum() == adata.n_obs
    # spatial coordinates tagged onto the cell (var) axis
    assert {"center_x", "center_y"}.issubset(membership.var.columns)


def test_calc_signature_gene_default_and_protein_mudata():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    clust.calc_signature(adata, modality_name="expression")
    expression = clust.mod["expression"]
    assert expression.n_obs == clust.obs.shape[0]
    assert expression.n_vars == adata.n_vars
    assert expression.var["entity_type"].iloc[0] == "gene"

    prot = AnnData(
        X=np.random.default_rng(1).poisson(5, (adata.n_obs, 4)).astype(float),
        obs=pd.DataFrame(index=adata.obs_names),
        var=pd.DataFrame(index=[f"p{j}" for j in range(4)]),
    )
    mdata = MuData({"rna": adata.copy(), "protein": prot})
    clust.calc_signature(mdata, modality_name="protein", feature_type="protein")
    assert clust.mod["protein"].n_vars == 4
    assert clust.mod["protein"].var["entity_type"].iloc[0] == "protein"


def test_calc_signature_stores_fraction_expressing_as_a_layer():
    adata = _adata()
    combined = SetCollection(adata, set_col="leiden", name="leiden")
    combined.calc_signature(
        adata,
        modality_name="expression",
        aggregate="sum",
        normalization="log1p_cpm",
        fraction_expressing_layer="fraction_expressing",
    )

    reference = SetCollection(adata, set_col="leiden", name="leiden")
    reference.calc_signature(
        adata,
        modality_name="fraction_expressing",
        aggregate="fraction",
        normalization=None,
    )

    expression = combined.mod["expression"]
    assert set(combined.mod) == {"membership", "expression"}
    assert expression.uns["fraction_expressing_layer"] == "fraction_expressing"
    np.testing.assert_allclose(
        expression.layers["fraction_expressing"],
        reference.mod["fraction_expressing"].X,
    )

    with pytest.raises(ValueError, match="only valid with aggregate"):
        combined.calc_signature(
            adata,
            modality_name="invalid",
            aggregate="fraction",
            fraction_expressing_layer="fraction_expressing",
        )


def test_obs_color_stored_from_category_colors():
    adata = _adata()
    # categorical labels + a scanpy-style colors palette aligned to categories
    adata.obs["leiden"] = adata.obs["leiden"].astype("category")
    cats = list(adata.obs["leiden"].cat.categories)
    palette = ["#111111", "#222222", "#333333", "#444444"][: len(cats)]
    adata.uns["leiden_colors"] = palette
    expected = {str(c): palette[i] for i, c in enumerate(cats)}

    clust = SetCollection(adata, set_col="leiden", name="leiden")
    assert "color" in clust.obs.columns
    assert all(clust.obs.loc[s, "color"] == expected[s] for s in clust.obs.index)

    # color travels into the signature modality so Matrix can auto-color the Clustergram
    clust.calc_signature(adata, modality_name="expression", normalization=None)
    assert "color" in clust.mod["expression"].obs.columns


def test_obs_has_no_color_without_palette():
    adata = _adata()  # no *_colors in uns
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    assert "color" not in clust.obs.columns


def test_calc_signature_stamps_axis_entities_for_landscape_linking():
    adata = _adata()
    clust = SetCollection(adata, set_col="cell_type", name="rctd")
    clust.calc_signature(adata, modality_name="expression", normalization=None)
    axis = clust.mod["expression"].uns.get("axis_entities")
    assert axis is not None
    assert axis["row_entity"] == {"entity": "gene", "attr": "name"}
    assert axis["col_entity"] == {"entity": "cell", "attr": "cell_type"}

    # Matrix should auto-infer the non-leiden col_entity from the stamped hint
    from celldega.clust import Matrix

    mat = Matrix(clust.mod["expression"])
    assert mat.col_entity == {"entity": "cell", "attr": "cell_type"}


def test_calc_signature_requires_feature_type_for_mudata():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    mdata = MuData({"rna": adata.copy()})
    with pytest.raises(ValueError, match="feature_type is required"):
        clust.calc_signature(mdata, modality_name="expression")


def test_calc_population_proportions_sum_to_one():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    clust.calc_population(adata, category="cell_type")
    population = clust.mod["population"]
    assert population.n_vars == adata.obs["cell_type"].nunique()
    row_sums = np.asarray(population.X).sum(axis=1)
    assert np.allclose(row_sums, 1.0)


def test_calc_overlap_self_is_square_relation():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    overlap = clust.calc_overlap()
    n = clust.obs.shape[0]
    assert overlap.shape == (n, n)
    assert "overlap" in clust.relations
    # IoU diagonal is 1 (a set fully overlaps itself)
    assert np.allclose(np.diag(overlap), 1.0)


def test_calc_overlap_cross_collection_is_rectangular_modality():
    adata = _adata()
    a = SetCollection(adata, set_col="leiden", name="leiden")
    b = SetCollection(adata, set_col="spagcn", name="spagcn")
    overlap = a.calc_overlap(b)
    assert overlap.shape == (a.obs.shape[0], b.obs.shape[0])
    assert "spagcn_overlap" in a.mod


def test_concat_sets_prefixes_ids_and_unions_cells():
    adata = _adata()
    a = SetCollection(adata, set_col="leiden", name="leiden")
    b = SetCollection(adata, set_col="spagcn", name="spagcn")
    combined = concat_sets([a, b])
    assert combined.obs.shape[0] == a.obs.shape[0] + b.obs.shape[0]
    assert all("::" in idx for idx in combined.obs.index)
    assert combined.mod["membership"].n_vars == adata.n_obs
    # self-overlap on the combined collection is square over all sets
    rel = combined.calc_overlap()
    assert rel.shape == (combined.obs.shape[0], combined.obs.shape[0])


def test_calc_signature_attaches_and_persists_rank_genes_groups(tmp_path):
    """DE computed alongside the signature is what a marker view reads."""
    pytest.importorskip("scanpy")

    adata = _adata(n=200, g=20)
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    clust.calc_signature(
        adata,
        modality_name="expression",
        normalization=None,
        fraction_expressing_layer="fraction_expressing",
        rank_genes_groups=True,
    )

    payload = clust.mod["expression"].uns["rank_genes_groups"]
    assert set(payload) >= {"group", "names", "rank"}
    assert set(payload["group"]) == set(adata.obs["leiden"].astype(str))

    # A Matrix built from the modality picks it up with no extra wiring, which
    # is the whole point of attaching it here rather than after the fact.
    from celldega.clust import Matrix

    mat = Matrix(collection=clust, color_by="expression")
    mat.cluster(view="rank_genes_groups", levels=[1, 2])
    assert [view["level_unit"] for view in mat.views] == ["per_cluster"] * len(mat.views)
    assert mat.views

    path = tmp_path / "set_collection.h5mu"
    clust.write(path)
    loaded = SetCollection.read(path)
    assert loaded.set_col == "leiden"
    assert "rank_genes_groups" in loaded.mod["expression"].uns
    assert "fraction_expressing" in loaded.mod["expression"].layers

    reloaded_mat = Matrix(
        collection=loaded,
        color_by="expression",
        size_by_layer="fraction_expressing",
    )
    assert reloaded_mat.size_matrix is not None
    reloaded_mat.cluster(view="rank_genes_groups", levels=[1])
    assert reloaded_mat.views


def test_calc_signature_ranks_the_layer_it_aggregates(monkeypatch):
    adata = _adata()
    adata.layers["counts"] = adata.X + 10
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    captured = {}

    def capture_marker_ranks(_adata, groupby, kwargs):
        captured["groupby"] = groupby
        captured["kwargs"] = kwargs

    monkeypatch.setattr("celldega.set.collection.compute_marker_ranks", capture_marker_ranks)

    clust.calc_signature(
        adata,
        modality_name="counts_signature",
        layer="counts",
        normalization=None,
        rank_genes_groups=True,
    )

    assert captured["groupby"] == "leiden"
    assert captured["kwargs"] == {"layer": "counts", "use_raw": False}


def test_calc_signature_accepts_an_alternate_marker_layer(monkeypatch):
    adata = _adata()
    adata.layers["counts"] = adata.X + 10
    adata.layers["normalized"] = adata.X
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    captured = []

    def capture_marker_ranks(_adata, groupby, kwargs):
        captured.append((groupby, kwargs))

    monkeypatch.setattr("celldega.set.collection.compute_marker_ranks", capture_marker_ranks)

    clust.calc_signature(
        adata,
        modality_name="counts_rank_x",
        layer="counts",
        normalization=None,
        rank_genes_groups=True,
        rank_genes_groups_layer="X",
    )
    clust.calc_signature(
        adata,
        modality_name="counts_rank_normalized",
        layer="counts",
        normalization=None,
        rank_genes_groups=True,
        rank_genes_groups_layer="normalized",
    )

    assert captured == [
        ("leiden", {"use_raw": False}),
        ("leiden", {"layer": "normalized", "use_raw": False}),
    ]


def test_calc_signature_validates_marker_expression_source():
    adata = _adata()
    adata.layers["counts"] = adata.X + 10
    adata.layers["normalized"] = adata.X
    clust = SetCollection(adata, set_col="leiden", name="leiden")

    with pytest.raises(ValueError, match="must match"):
        clust.calc_signature(
            adata,
            modality_name="conflicting_layers",
            layer="counts",
            normalization=None,
            rank_genes_groups=True,
            rank_genes_groups_layer="X",
            rank_genes_groups_kwargs={"layer": "normalized"},
        )

    with pytest.raises(ValueError, match=r"cannot be combined with use_raw=True"):
        clust.calc_signature(
            adata,
            modality_name="raw_conflict",
            layer="counts",
            normalization=None,
            rank_genes_groups=True,
            rank_genes_groups_layer="X",
            rank_genes_groups_kwargs={"use_raw": True},
        )

    with pytest.raises(ValueError, match="missing requested marker layer"):
        clust.calc_signature(
            adata,
            modality_name="missing_layer",
            layer="counts",
            normalization=None,
            rank_genes_groups=True,
            rank_genes_groups_layer="missing",
        )


def test_calc_signature_rank_genes_groups_needs_a_set_col():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    clust.set_col = None
    with pytest.raises(ValueError, match="needs a set_col"):
        clust.calc_signature(adata, modality_name="expression", rank_genes_groups=True)


def test_calc_signature_reports_expression_sources(monkeypatch, capsys):
    adata = _adata()
    adata.layers["counts"] = adata.X.copy()
    adata.X = np.log1p(adata.X)
    clust = SetCollection(adata, set_col="leiden", name="leiden")
    monkeypatch.setattr("celldega.set.collection.compute_marker_ranks", lambda *_: None)

    clust.calc_signature(
        adata,
        modality_name="expression",
        layer="counts",
        aggregate="sum",
        fraction_expressing_layer="fraction_expressing",
        rank_genes_groups=True,
        rank_genes_groups_layer="X",
        rank_genes_groups_kwargs={"method": "t-test"},
    )

    out = capsys.readouterr().out
    assert "sum of adata.layers['counts'] (normalization='log1p_cpm')" in out
    assert (
        "layers['fraction_expressing']: fraction of cells with adata.layers['counts'] > 0.0" in out
    )
    assert "uns['rank_genes_groups']: t-test on adata.X, grouped by 'leiden'" in out

    clust.calc_signature(adata, modality_name="quiet", layer="counts", verbose=False)
    assert capsys.readouterr().out == ""


def test_calc_signature_warns_when_aggregating_non_count_data():
    adata = _adata()
    adata.X = np.log1p(adata.X)
    clust = SetCollection(adata, set_col="leiden", name="leiden")

    with pytest.warns(UserWarning, match=r"from adata\.X, which has non-integer values"):
        clust.calc_signature(
            adata,
            modality_name="expression",
            fraction_expressing_layer="fraction_expressing",
            verbose=False,
        )


def test_calc_signature_warns_when_marker_layer_is_ignored():
    adata = _adata()
    clust = SetCollection(adata, set_col="leiden", name="leiden")

    with pytest.warns(UserWarning, match="rank_genes_groups_layer is ignored"):
        clust.calc_signature(
            adata, modality_name="expression", rank_genes_groups_layer="X", verbose=False
        )
