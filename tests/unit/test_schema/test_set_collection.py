"""Tests for the set-level SetCollection and its derived modalities."""

import numpy as np
import pandas as pd
import pytest
from anndata import AnnData
from mudata import MuData

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
    clust.calc_signature(adata)
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
    clust.calc_signature(mdata, feature_type="protein")
    assert clust.mod["protein"].n_vars == 4
    assert clust.mod["protein"].var["entity_type"].iloc[0] == "protein"


def test_calc_signature_stamps_axis_entities_for_landscape_linking():
    adata = _adata()
    clust = SetCollection(adata, set_col="cell_type", name="rctd")
    clust.calc_signature(adata, normalization=None)
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
        clust.calc_signature(mdata)


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
