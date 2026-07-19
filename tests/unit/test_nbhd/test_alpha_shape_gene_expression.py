from unittest.mock import patch

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from celldega.nbhd import alpha_shape_gene_expression_by_slice, iter_gene_alpha_shapes_by_slice


def _synthetic_gene_expression_adata(seed=0, n_slices=2, n_cells=60, n_genes=2):
    rng = np.random.RandomState(seed)
    rows = []
    xy = []
    X = []
    for slice_idx in range(n_slices):
        center = np.array([slice_idx * 300.0, 0.0])
        pts = rng.normal(loc=center, scale=10.0, size=(n_cells, 2))
        xy.append(pts)
        rows.extend([{"slice_id": f"s{slice_idx}", "z": float(slice_idx) * 100.0}] * n_cells)
        # Half the cells (evens) express every gene at a high value; the
        # other half sit at zero -- gives a clean, deterministic "expressing"
        # mask to assert against.
        slice_expr = np.zeros((n_cells, n_genes))
        slice_expr[::2, :] = 5.0
        X.append(slice_expr)

    obs = pd.DataFrame(rows)
    obs.index = [f"cell_{i}" for i in range(len(obs))]
    gene_names = [f"Gene{i}" for i in range(n_genes)]
    adata = ad.AnnData(X=np.vstack(X), obs=obs, var=pd.DataFrame(index=gene_names))
    adata.obsm["spatial"] = np.vstack(xy)
    return adata


def test_alpha_shape_gene_expression_by_slice_builds_one_shape_per_slice_gene():
    adata = _synthetic_gene_expression_adata(n_slices=2, n_genes=2)

    gdf = alpha_shape_gene_expression_by_slice(
        adata,
        ["Gene0", "Gene1"],
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_expression=1.0,
        min_cells=4,
    )

    assert set(gdf["slice_id"]) == {"s0", "s1"}
    assert set(gdf["gene"]) == {"Gene0", "Gene1"}
    assert len(gdf) == 4
    assert list(gdf["name"]) == [
        f"{s}__{g}" for s, g in zip(gdf["slice_id"], gdf["gene"], strict=True)
    ]
    # 30 of 60 cells per slice are the "expressing" (value=5.0) half.
    assert (gdf["cell_count"] == 30).all()
    assert np.allclose(gdf["mean_expression"], 5.0)


def test_alpha_shape_gene_expression_by_slice_stamps_each_slices_z():
    adata = _synthetic_gene_expression_adata(n_slices=2, n_genes=1)

    gdf = alpha_shape_gene_expression_by_slice(
        adata, ["Gene0"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
    )

    by_slice = gdf.set_index("slice_id")
    z0 = {
        round(coord[2], 3)
        for g in by_slice.loc["s0", "geometry"].geoms
        for coord in g.exterior.coords
    }
    z1 = {
        round(coord[2], 3)
        for g in by_slice.loc["s1", "geometry"].geoms
        for coord in g.exterior.coords
    }
    assert z0 == {0.0}
    assert z1 == {100.0}


def test_alpha_shape_gene_expression_by_slice_skips_genes_below_min_cells():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_cells=10, n_genes=1)
    # min_cells higher than the 5 expressing cells present -> nothing to compute.
    with pytest.raises(ValueError, match="no gene alpha shapes"):
        alpha_shape_gene_expression_by_slice(
            adata, ["Gene0"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=6
        )


def test_alpha_shape_gene_expression_by_slice_min_expression_is_inclusive():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_cells=20, n_genes=1)
    # Bump the expressing half's value down to exactly the default threshold
    # (2.0) -- inclusive (>=) means these should still count.
    adata.X[adata.X == 5.0] = 2.0

    gdf = alpha_shape_gene_expression_by_slice(
        adata, ["Gene0"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
    )

    assert len(gdf) == 1
    assert gdf.iloc[0]["cell_count"] == 10
    assert gdf.iloc[0]["mean_expression"] == pytest.approx(2.0)


def test_alpha_shape_gene_expression_by_slice_rejects_unknown_gene():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=1)

    with pytest.raises(ValueError, match="not found in adata.var_names"):
        alpha_shape_gene_expression_by_slice(adata, ["NotAGene"], slice_attr="slice_id")


def test_alpha_shape_gene_expression_by_slice_rejects_multiple_alphas():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=1)

    with pytest.raises(ValueError, match="single alpha-shape"):
        alpha_shape_gene_expression_by_slice(adata, ["Gene0"], alphas=(100, 150))


def test_alpha_shape_gene_expression_by_slice_skips_a_gene_whose_shape_fails():
    """A libpysal/GEOS failure (e.g. GEOSException: "side location conflict"
    on a self-intersecting triangulation) computing one gene's shape must not
    abort shapes for the other genes in the same batch -- seen in practice
    when scaling the curated gene list up from a handful to ~150 genes."""
    from celldega.nbhd.alpha_shapes import libpysal_alpha_shape as real_libpysal_alpha_shape

    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=2)

    call_count = {"n": 0}

    def fake_alpha_shape(coords, alpha):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Gene0 is processed first (gene_list order) -- fail only this call.
            raise Exception("GEOSException: TopologyException: side location conflict")
        return real_libpysal_alpha_shape(coords, alpha)

    with patch("celldega.nbhd.alpha_shapes.libpysal_alpha_shape", side_effect=fake_alpha_shape):
        gdf = alpha_shape_gene_expression_by_slice(
            adata,
            ["Gene0", "Gene1"],
            slice_attr="slice_id",
            z_attr="z",
            alphas=(150,),
            min_cells=4,
        )

    # Gene0's shape failed and was skipped; Gene1's still computed normally.
    assert list(gdf["gene"]) == ["Gene1"]


def test_alpha_shape_gene_expression_by_slice_raises_when_every_shape_fails():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=1)

    def always_raises(_coords, _alpha):
        raise Exception("GEOSException: TopologyException: side location conflict")

    with (
        patch("celldega.nbhd.alpha_shapes.libpysal_alpha_shape", side_effect=always_raises),
        pytest.raises(ValueError, match="no gene alpha shapes"),
    ):
        alpha_shape_gene_expression_by_slice(
            adata, ["Gene0"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
        )


def test_iter_gene_alpha_shapes_by_slice_yields_one_gene_at_a_time():
    adata = _synthetic_gene_expression_adata(n_slices=2, n_genes=2)

    genes_seen = []
    for gene, gdf_gene in iter_gene_alpha_shapes_by_slice(
        adata, ["Gene0", "Gene1"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
    ):
        genes_seen.append(gene)
        assert set(gdf_gene["gene"]) == {gene}
        assert set(gdf_gene["slice_id"]) == {"s0", "s1"}
        assert (gdf_gene["cell_count"] == 30).all()

    assert genes_seen == ["Gene0", "Gene1"]


def test_iter_gene_alpha_shapes_by_slice_yields_empty_for_a_gene_with_no_shapes():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_cells=10, n_genes=1)

    results = list(
        iter_gene_alpha_shapes_by_slice(
            adata, ["Gene0"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=6
        )
    )

    assert len(results) == 1
    gene, gdf_gene = results[0]
    assert gene == "Gene0"
    assert gdf_gene.empty


def test_iter_gene_alpha_shapes_by_slice_is_lazy():
    """Validation errors (unknown gene, multiple alphas) must only surface
    once the generator is actually iterated, not when it's merely called --
    calling a generator function never runs its body up to the first
    `yield`."""
    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=1)

    generator = iter_gene_alpha_shapes_by_slice(adata, ["NotAGene"], slice_attr="slice_id")
    with pytest.raises(ValueError, match=r"not found in adata\.var_names"):
        next(generator)


def test_iter_gene_alpha_shapes_by_slice_rejects_multiple_alphas_on_first_iteration():
    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=1)

    generator = iter_gene_alpha_shapes_by_slice(adata, ["Gene0"], alphas=(100, 150))
    with pytest.raises(ValueError, match="single alpha-shape"):
        next(generator)


def test_iter_gene_alpha_shapes_by_slice_gives_different_genes_distinct_z_offsets():
    """Different genes' shapes landing in the same slice need distinct Z so
    they don't z-fight -- `_gene_z_offset` derives this from each gene's
    position in `gene_list` rather than a per-slice running count, since the
    streaming writer processes one gene (across all its slices) at a time
    and never has a "how many other genes already succeeded in this slice"
    count available."""
    adata = _synthetic_gene_expression_adata(n_slices=1, n_genes=2)

    results = dict(
        iter_gene_alpha_shapes_by_slice(
            adata, ["Gene0", "Gene1"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
        )
    )

    z0 = {
        round(c[2], 6)
        for g in results["Gene0"]["geometry"].iloc[0].geoms
        for c in g.exterior.coords
    }
    z1 = {
        round(c[2], 6)
        for g in results["Gene1"]["geometry"].iloc[0].geoms
        for c in g.exterior.coords
    }
    assert z0 != z1
    # Gene0 is index 0 -- its offset is always exactly 0 (matches the
    # single-gene z-stamping test's exact-z-val expectation).
    assert z0 == {0.0}
