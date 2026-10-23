"""Neighborhood functions on GeoDataFrame + AnnData/MuData inputs."""

from anndata import AnnData
import geopandas as gpd
from mudata import MuData
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from shapely.geometry import Point, box

from celldega.clust import Matrix
from celldega.nbhd import (
    alpha_shape_cell_clusters,
    calc_nbhd_bordering,
    calc_nbhd_by_gene,
    calc_nbhd_by_pop,
    calc_nbhd_overlap,
    calc_nbhd_transcript_assignment,
    generate_hextile,
)


def _neighborhoods() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["A", "B"], "cat": ["x", "y"], "color": ["#ff0000", "#0000ff"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)],
    )


def _cells() -> AnnData:
    """Six cells in A, four in B, two outside both."""
    coords = np.array([[1, 1]] * 6 + [[11, 1]] * 4 + [[50, 50]] * 2, dtype=float)
    X = np.array(
        [
            *[[1, 0], [2, 0], [3, 1], [4, 1], [5, 0], [6, 1]],
            *[[10, 2], [20, 2], [30, 0], [40, 0]],
            *[[99, 99], [99, 99]],
        ],
        dtype=float,
    )
    obs = pd.DataFrame(
        {"leiden": pd.Categorical(["0", "1", "0", "0", "1", "1", "0", "0", "1", "1", "0", "1"])},
        index=[f"cell{i}" for i in range(len(coords))],
    )
    adata = AnnData(X=X, obs=obs, var=pd.DataFrame(index=["GeneA", "GeneB"]))
    adata.obsm["spatial"] = coords
    adata.uns["leiden_colors"] = ["#111111", "#222222"]
    return adata


def _expected_means(adata: AnnData) -> pd.DataFrame:
    x = pd.DataFrame(adata.X, index=adata.obs_names, columns=adata.var_names)
    return pd.DataFrame({"A": x.iloc[:6].mean(), "B": x.iloc[6:10].mean()}).T


def test_calc_nbhd_by_gene_matches_cell_means():
    adata = _cells()

    result = calc_nbhd_by_gene(_neighborhoods(), "cell", adata)

    assert list(result.obs_names) == ["A", "B"]
    np.testing.assert_allclose(result.X, _expected_means(adata).to_numpy())
    assert list(result.obs["n_cells"]) == [6, 4]
    assert list(result.obs["cat"]) == ["x", "y"]
    assert list(result.obs["color"]) == ["#ff0000", "#0000ff"]
    assert (result.var["entity_type"] == "gene").all()
    assert result.uns["by"] == "cell"
    assert result.uns["axis_entities"] == {
        "row_entity": {"entity": "gene", "attr": "name"},
        "col_entity": {"entity": "nbhd", "attr": "name"},
    }


def test_calc_nbhd_by_gene_sparse_and_variance():
    adata = _cells()
    dense = calc_nbhd_by_gene(_neighborhoods(), adata=adata, include_variance=True)
    adata.X = sparse.csr_matrix(adata.X)
    sparse_result = calc_nbhd_by_gene(_neighborhoods(), adata=adata, include_variance=True)

    np.testing.assert_allclose(sparse_result.X, dense.X)
    x = pd.DataFrame(_cells().X)
    expected_var = np.vstack([x.iloc[:6].var(ddof=0), x.iloc[6:10].var(ddof=0)])
    np.testing.assert_allclose(dense.layers["variance"], expected_var)
    np.testing.assert_allclose(sparse_result.layers["variance"], expected_var)


def test_calc_nbhd_by_gene_min_cells_and_overlapping_neighborhoods():
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B", "AB"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10), box(0, 0, 20, 10)],
    )

    result = calc_nbhd_by_gene(gdf, adata=_cells(), min_cells=5)

    # B has 4 cells (< 5); AB contains the cells of A and B
    assert list(result.obs_names) == ["A", "AB"]
    assert list(result.obs["n_cells"]) == [6, 10]


def test_calc_nbhd_by_gene_mudata_per_modality():
    adata = _cells()
    protein = AnnData(
        X=np.arange(len(adata) * 3, dtype=float).reshape(len(adata), 3),
        obs=pd.DataFrame(index=adata.obs_names),
        var=pd.DataFrame(index=["CD3", "CD20", "PanCK"]),
    )
    mdata = MuData({"rna": adata.copy(), "protein": protein})
    mdata.obsm["spatial"] = adata.obsm["spatial"]

    result = calc_nbhd_by_gene(_neighborhoods(), adata=mdata)

    assert isinstance(result, MuData)
    assert set(result.mod) == {"rna", "protein"}
    np.testing.assert_allclose(result.mod["rna"].X, _expected_means(adata).to_numpy())
    assert (result.mod["rna"].var["entity_type"] == "gene").all()
    assert (result.mod["protein"].var["entity_type"] == "protein").all()

    rna_only = calc_nbhd_by_gene(_neighborhoods(), adata=mdata, modality="rna")
    assert isinstance(rna_only, AnnData)
    np.testing.assert_allclose(rna_only.X, result.mod["rna"].X)


def test_calc_nbhd_by_gene_mudata_coordinates_from_modality():
    adata = _cells()
    mdata = MuData({"rna": adata.copy()})

    result = calc_nbhd_by_gene(_neighborhoods(), adata=mdata, modality="rna")

    np.testing.assert_allclose(result.X, _expected_means(adata).to_numpy())


def test_calc_nbhd_by_gene_cell_free_counts_transcripts():
    gdf_trx = gpd.GeoDataFrame(
        {"feature_name": ["GeneA", "GeneA", "GeneB", "GeneA", "GeneB"]},
        geometry=[Point(1, 1), Point(2, 2), Point(3, 3), Point(11, 1), Point(50, 50)],
    )

    result = calc_nbhd_by_gene(_neighborhoods(), by="cell-free", gdf_trx=gdf_trx)

    assert result.uns["by"] == "cell-free"
    counts = pd.DataFrame(result.X, index=result.obs_names, columns=result.var_names)
    assert counts.loc["A", "GeneA"] == 2
    assert counts.loc["A", "GeneB"] == 1
    assert counts.loc["B", "GeneA"] == 1
    assert list(result.obs["n_transcripts"]) == [3, 1]


def test_calc_nbhd_by_gene_input_errors():
    with pytest.raises(ValueError, match="adata is required"):
        calc_nbhd_by_gene(_neighborhoods())
    with pytest.raises(ValueError, match="include_variance"):
        calc_nbhd_by_gene(_neighborhoods(), by="cell-free", include_variance=True)
    with pytest.raises(ValueError, match="gdf_trx or data_dir"):
        calc_nbhd_by_gene(_neighborhoods(), by="cell-free")


def test_calc_nbhd_by_pop_proportions_colors_and_entities():
    result = calc_nbhd_by_pop(_cells(), _neighborhoods(), category="leiden", min_cells=3)

    props = pd.DataFrame(result.X, index=result.obs_names, columns=result.var_names)
    assert props.loc["A", "0"] == pytest.approx(0.5)
    assert props.loc["B", "1"] == pytest.approx(0.5)
    assert list(result.obs["n_cells"]) == [6, 4]
    assert list(result.var["color"]) == ["#111111", "#222222"]
    assert (result.var["entity_type"] == "cell_population").all()
    assert result.uns["axis_entities"]["row_entity"] == {"entity": "cell", "attr": "leiden"}

    mat = Matrix(result)
    assert mat.col_entity == {"entity": "nbhd", "attr": "name"}
    assert mat.row_entity == {"entity": "cell", "attr": "leiden"}


def test_calc_nbhd_by_pop_reads_mudata_obs():
    adata = _cells()
    rna = AnnData(X=adata.X, obs=pd.DataFrame(index=adata.obs_names), var=adata.var)
    rna.obs["leiden"] = adata.obs["leiden"].to_numpy()
    rna.uns["leiden_colors"] = adata.uns["leiden_colors"]
    mdata = MuData({"rna": rna})
    mdata.obsm["spatial"] = adata.obsm["spatial"]

    from_mudata = calc_nbhd_by_pop(mdata, _neighborhoods(), category="leiden", min_cells=3)
    from_adata = calc_nbhd_by_pop(adata, _neighborhoods(), category="leiden", min_cells=3)

    np.testing.assert_allclose(from_mudata.X, from_adata.X)
    assert list(from_mudata.var["color"]) == list(from_adata.var["color"])


def test_calc_nbhd_overlap_and_bordering():
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B", "C"], "cat": ["x", "y", "z"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10), box(5, 0, 15, 10)],
    )

    overlap = calc_nbhd_overlap(gdf, metric="iou")
    iou = pd.DataFrame(overlap.X, index=overlap.obs_names, columns=overlap.var_names)
    assert iou.loc["A", "B"] == 0
    assert iou.loc["A", "C"] == pytest.approx(50 / 150, abs=1e-4)
    assert overlap.uns["axis_entities"] == {
        "row_entity": {"entity": "nbhd", "attr": "name"},
        "col_entity": {"entity": "nbhd", "attr": "name"},
    }
    assert list(overlap.obs["leiden"]) == ["x", "y", "z"]

    bordering = calc_nbhd_bordering(gdf.iloc[:2], metric="border_ratio")
    ratio = pd.DataFrame(bordering.X, index=bordering.obs_names, columns=bordering.var_names)
    assert ratio.loc["A", "B"] == pytest.approx(0.25)
    assert ratio.loc["B", "A"] == pytest.approx(0.25)


def test_calc_nbhd_transcript_assignment():
    gdf_trx = gpd.GeoDataFrame(
        {"feature_name": ["g"] * 4, "cell_id": ["c1", "UNASSIGNED", "c2", "UNASSIGNED"]},
        geometry=[Point(1, 1), Point(2, 2), Point(3, 3), Point(11, 1)],
    )

    stats = calc_nbhd_transcript_assignment(_neighborhoods(), gdf_trx)

    assert list(stats.index) == ["A", "B"]
    assert list(stats["total_transcripts"]) == [3, 1]
    assert list(stats["unassigned_transcripts"]) == [1, 1]
    assert stats.loc["A", "transcript_assignment_proportion"] == pytest.approx(2 / 3)


class _NeighborhoodLike:
    def __init__(self, gdf: gpd.GeoDataFrame, nbhd_col: str) -> None:
        self._gdf = gdf
        self.nbhd_col = nbhd_col

    def to_geodataframe(self) -> gpd.GeoDataFrame:
        return self._gdf


def test_functions_accept_neighborhood_like_objects_and_id_fallbacks():
    gdf = _neighborhoods().rename(columns={"name": "region"})
    nbhd = _NeighborhoodLike(gdf, nbhd_col="region")

    result = calc_nbhd_by_gene(nbhd, adata=_cells())
    assert list(result.obs_names) == ["A", "B"]

    by_fallback = calc_nbhd_by_gene(
        _neighborhoods().rename(columns={"name": "neighborhood_id"}), adata=_cells()
    )
    assert list(by_fallback.obs_names) == ["A", "B"]


def test_neighborhood_ids_must_be_unique_and_present():
    gdf = _neighborhoods()
    gdf["name"] = ["A", "A"]
    with pytest.raises(ValueError, match="unique"):
        calc_nbhd_by_gene(gdf, adata=_cells())

    with pytest.raises(ValueError, match="gdf_nbhd missing required columns"):
        calc_nbhd_by_gene(_neighborhoods().drop(columns="name"), adata=_cells())

    with pytest.raises(TypeError, match="to_geodataframe"):
        calc_nbhd_by_gene(object(), adata=_cells())


def test_generation_accepts_mudata():
    adata = _cells()
    mdata = MuData({"rna": adata.copy()})

    hex_from_mudata = generate_hextile(mdata, diameter=10)
    hex_from_adata = generate_hextile(adata, diameter=10)
    assert len(hex_from_mudata) == len(hex_from_adata)

    rng = np.random.default_rng(0)
    clusters = AnnData(
        X=np.zeros((60, 1)),
        obs=pd.DataFrame(
            {"leiden": pd.Categorical(["0"] * 30 + ["1"] * 30)},
            index=[f"c{i}" for i in range(60)],
        ),
    )
    clusters.obsm["spatial"] = np.vstack([rng.normal(0, 5, (30, 2)), rng.normal(100, 5, (30, 2))])
    clusters.uns["leiden_colors"] = ["#aa0000", "#00aa00"]
    shapes = alpha_shape_cell_clusters(
        MuData({"rna": clusters}), cat="leiden", alphas=[50], modality="rna"
    )
    assert set(shapes["cat"]) == {"0", "1"}
    assert set(shapes["color"]) == {"#aa0000", "#00aa00"}
