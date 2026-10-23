import json

import anndata as ad
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

from celldega.nbhd import alpha_shape_cell_clusters_by_slice
from celldega.pre import (
    write_cell_clusters_meta,
    write_gene_cell_scatter,
    write_meta_gene_for_nbhd_cloud,
    write_meta_slice,
    write_nbhd_cloud_cells,
    write_nbhd_cloud_dataset,
    write_nbhd_cloud_shapes_and_features,
)
from celldega.pre.nbhd_cloud import _write_nbhd_cloud_landscape_parameters


def _synthetic_dataset(seed=0, n_slices=2, n_clusters=2, n_per_cluster=30, n_genes=2):
    rng = np.random.RandomState(seed)
    rows = []
    xy = []
    for slice_idx in range(n_slices):
        for cluster_idx in range(n_clusters):
            center = np.array([cluster_idx * 200.0, slice_idx * 200.0])
            pts = rng.normal(loc=center, scale=5.0, size=(n_per_cluster, 2))
            xy.append(pts)
            rows.extend(
                [
                    {
                        "cluster": str(cluster_idx),
                        "slice_id": f"s{slice_idx}",
                        "z": float(slice_idx) * 100.0,
                    }
                ]
                * n_per_cluster
            )

    obs = pd.DataFrame(rows)
    n_cells = len(obs)
    obs.index = [f"cell_{i}" for i in range(n_cells)]

    gene_names = [f"Gene{i}" for i in range(n_genes)]
    X = rng.uniform(0, 10, size=(n_cells, n_genes))

    adata = ad.AnnData(
        X=X,
        obs=obs,
        var=pd.DataFrame(index=gene_names),
    )
    adata.obsm["spatial"] = np.vstack(xy)
    return adata


def _build_nbhd(adata):
    return alpha_shape_cell_clusters_by_slice(
        adata, cluster_attr="cluster", slice_attr="slice_id", z_attr="z", alphas=(150,)
    )


class _NeighborhoodLike:
    """Duck-typed neighborhood object exposing to_geodataframe()."""

    def __init__(self, gdf):
        self._gdf = gdf

    def to_geodataframe(self):
        return self._gdf


def test_write_meta_slice(tmp_path):
    adata = _synthetic_dataset()

    df_meta_slice = write_meta_slice(adata, tmp_path, slice_attr="slice_id", z_attr="z")

    assert set(df_meta_slice["slice_id"]) == {"s0", "s1"}
    assert (df_meta_slice["cell_count"] == 60).all()
    by_slice = df_meta_slice.set_index("slice_id")
    assert by_slice.loc["s0", "z"] == 0.0
    assert by_slice.loc["s1", "z"] == 100.0

    df_on_disk = pd.read_parquet(tmp_path / "nbhd_cloud" / "meta_slice.parquet")
    pd.testing.assert_frame_equal(df_on_disk, df_meta_slice)


def test_write_nbhd_cloud_cells_by_cluster(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud_cells(
        adata, tmp_path, cluster_attr="cluster", slice_attr="slice_id", z_attr="z"
    )

    by_cluster_dir = tmp_path / "nbhd_cloud" / "cells" / "by_cluster"
    assert {p.name for p in by_cluster_dir.glob("*.parquet")} == {
        "cluster_0.parquet",
        "cluster_1.parquet",
    }

    df_cluster_0 = pd.read_parquet(by_cluster_dir / "cluster_0.parquet")
    assert len(df_cluster_0) == 60  # cluster 0, both slices, 30 cells each
    assert set(df_cluster_0["slice_id"]) == {"s0", "s1"}
    assert {"cell_id", "x", "y", "z", "cluster_id", "slice_id"}.issubset(df_cluster_0.columns)


def test_write_nbhd_cloud_cells_max_cells_none_writes_every_cell(tmp_path):
    """Default (`max_cells=None`) must be unchanged from this function's
    original, uncapped behavior."""
    adata = _synthetic_dataset()

    write_nbhd_cloud_cells(
        adata, tmp_path, cluster_attr="cluster", slice_attr="slice_id", z_attr="z"
    )

    df_cluster_0 = pd.read_parquet(
        tmp_path / "nbhd_cloud" / "cells" / "by_cluster" / "cluster_0.parquet"
    )
    assert len(df_cluster_0) == 60


def test_write_nbhd_cloud_cells_caps_at_max_cells(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud_cells(
        adata,
        tmp_path,
        cluster_attr="cluster",
        slice_attr="slice_id",
        z_attr="z",
        max_cells=10,
    )

    by_cluster_dir = tmp_path / "nbhd_cloud" / "cells" / "by_cluster"
    for cluster_id in ("0", "1"):
        df_cluster = pd.read_parquet(by_cluster_dir / f"cluster_{cluster_id}.parquet")
        assert len(df_cluster) == 10


def test_write_nbhd_cloud_cells_leaves_small_clusters_untouched(tmp_path):
    """No subsampling should occur when a cluster is already at or below
    `max_cells`."""
    adata = _synthetic_dataset()

    write_nbhd_cloud_cells(
        adata,
        tmp_path,
        cluster_attr="cluster",
        slice_attr="slice_id",
        z_attr="z",
        max_cells=1000,
    )

    df_cluster_0 = pd.read_parquet(
        tmp_path / "nbhd_cloud" / "cells" / "by_cluster" / "cluster_0.parquet"
    )
    assert len(df_cluster_0) == 60


def test_write_nbhd_cloud_cells_max_cells_is_reproducible_for_the_same_seed(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud_cells(
        adata,
        tmp_path / "run1",
        cluster_attr="cluster",
        slice_attr="slice_id",
        z_attr="z",
        max_cells=10,
        random_state=0,
    )
    write_nbhd_cloud_cells(
        adata,
        tmp_path / "run2",
        cluster_attr="cluster",
        slice_attr="slice_id",
        z_attr="z",
        max_cells=10,
        random_state=0,
    )

    df_1 = pd.read_parquet(
        tmp_path / "run1" / "nbhd_cloud" / "cells" / "by_cluster" / "cluster_0.parquet"
    )
    df_2 = pd.read_parquet(
        tmp_path / "run2" / "nbhd_cloud" / "cells" / "by_cluster" / "cluster_0.parquet"
    )
    assert set(df_1["cell_id"]) == set(df_2["cell_id"])


def test_write_nbhd_cloud_shapes_and_features(tmp_path):
    adata = _synthetic_dataset()
    nbhd = _build_nbhd(adata)

    write_nbhd_cloud_shapes_and_features(nbhd, tmp_path)

    shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_slice"
    assert {p.name for p in shapes_dir.glob("*.parquet")} == {
        "slice_s0.parquet",
        "slice_s1.parquet",
    }
    df_shape_s0 = pd.read_parquet(shapes_dir / "slice_s0.parquet")
    assert len(df_shape_s0) == 2  # one polygon per cluster in this slice
    assert "geometry_geojson" in df_shape_s0.columns
    assert "geometry" not in df_shape_s0.columns
    # The JS parser (parse_shapes_table_to_features) keys off `neighborhood_id`
    # specifically -- without it, rows silently parse to zero features.
    assert "neighborhood_id" in df_shape_s0.columns
    assert df_shape_s0["neighborhood_id"].notna().all()
    parsed_geometries = [json.loads(g) for g in df_shape_s0["geometry_geojson"]]
    assert all(g["type"] == "MultiPolygon" for g in parsed_geometries)
    # Z should have been stamped onto every vertex by alpha_shape_cell_clusters_by_slice
    assert all(
        len(coord) == 3
        for g in parsed_geometries
        for poly in g["coordinates"]
        for ring in poly
        for coord in ring
    )

    df_meta_nbhd = pd.read_parquet(tmp_path / "nbhd_cloud" / "meta_neighborhood.parquet")
    assert len(df_meta_nbhd) == 4  # 2 slices x 2 clusters
    assert {
        "neighborhood_id",
        "cluster_id",
        "slice_id",
        "color",
        "area",
        "cell_count",
        "inv_alpha",
    }.issubset(df_meta_nbhd.columns)
    assert (df_meta_nbhd["cell_count"] == 30).all()

    # Per-neighborhood gene expression / population are not computed or
    # written here -- gene coloring comes from the per-gene cell scatter
    # (see write_gene_cell_scatter), and population was never surfaced in the
    # frontend.
    assert not (tmp_path / "nbhd_cloud" / "expression").exists()
    assert not (tmp_path / "nbhd_cloud" / "population.parquet").exists()

    # cell_clusters/meta_cluster.parquet is also written so the existing
    # cluster-color/cluster-bar machinery (shared by every technology) works
    # for neighborhood-cloud datasets too.
    df_meta_cluster = pd.read_parquet(tmp_path / "cell_clusters" / "meta_cluster.parquet")
    assert set(df_meta_cluster.columns) == {"cluster", "color", "count"}
    assert set(df_meta_cluster["cluster"]) == {"0", "1"}
    # each cluster spans both slices, 30 cells each -> 60 total
    assert (df_meta_cluster["count"] == 60).all()


def _synthetic_multi_gene_adata(n_slices=2, n_cells=20, gene_names=("Gene0", "Gene1", "Gene2")):
    rng = np.random.RandomState(0)
    rows = []
    xy = []
    X = []
    for slice_idx in range(n_slices):
        center = np.array([slice_idx * 300.0, 0.0])
        pts = rng.normal(loc=center, scale=10.0, size=(n_cells, 2))
        xy.append(pts)
        rows.extend([{"slice_id": f"s{slice_idx}", "z": float(slice_idx) * 100.0}] * n_cells)
        slice_expr = np.zeros((n_cells, len(gene_names)))
        slice_expr[::2, :] = 5.0
        X.append(slice_expr)

    obs = pd.DataFrame(rows)
    obs.index = [f"cell_{i}" for i in range(len(obs))]
    adata = ad.AnnData(X=np.vstack(X), obs=obs, var=pd.DataFrame(index=list(gene_names)))
    adata.obsm["spatial"] = np.vstack(xy)
    return adata


def test_write_gene_cell_scatter_writes_cells_but_no_shape(tmp_path):
    """The whole point of this writer: a gene gets a capped cell scatter,
    never an alpha shape -- no `shapes/by_gene/` directory at all."""
    adata = _synthetic_multi_gene_adata()
    gene_list = ["Gene0", "Gene1", "Gene2"]

    n_written = write_gene_cell_scatter(
        adata,
        gene_list,
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        min_cells=4,
        progress_every=0,
    )

    assert n_written == 3
    assert not (tmp_path / "nbhd_cloud" / "shapes").exists()

    cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_gene"
    assert {p.name for p in cells_dir.glob("*.parquet")} == {
        "Gene0.parquet",
        "Gene1.parquet",
        "Gene2.parquet",
    }
    df_cells = pd.read_parquet(cells_dir / "Gene0.parquet")
    assert {"cell_id", "gene", "slice_id", "x", "y", "z", "expression"}.issubset(df_cells.columns)
    assert (df_cells["gene"] == "Gene0").all()

    with (cells_dir / "available_gene_scatter.json").open() as f:
        manifest = json.load(f)
    assert set(manifest) == {"Gene0", "Gene1", "Gene2"}


def test_write_gene_cell_scatter_skips_genes_below_min_cells(tmp_path):
    adata = _synthetic_multi_gene_adata(gene_names=("Gene0", "Gene1"))
    adata.X[:, adata.var_names.get_loc("Gene1")] = 0

    n_written = write_gene_cell_scatter(
        adata,
        ["Gene0", "Gene1"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        min_cells=4,
        progress_every=0,
    )

    assert n_written == 1
    cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_gene"
    assert {p.name for p in cells_dir.glob("*.parquet")} == {"Gene0.parquet"}
    with (cells_dir / "available_gene_scatter.json").open() as f:
        manifest = json.load(f)
    assert set(manifest) == {"Gene0"}


def test_write_gene_cell_scatter_caps_cells_at_max_cells(tmp_path):
    adata = _synthetic_multi_gene_adata(n_slices=2, n_cells=20, gene_names=("Gene0",))
    gene_col = adata.var_names.get_loc("Gene0")
    expressing_mask = adata.X[:, gene_col] != 0
    adata.X[expressing_mask, gene_col] = np.arange(1, expressing_mask.sum() + 1)

    write_gene_cell_scatter(
        adata,
        ["Gene0"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        min_cells=4,
        max_cells=5,
        progress_every=0,
    )

    df_cells = pd.read_parquet(tmp_path / "nbhd_cloud" / "cells" / "by_gene" / "Gene0.parquet")
    assert len(df_cells) == 5
    max_expr = expressing_mask.sum()
    assert set(df_cells["expression"]) == set(range(max_expr - 4, max_expr + 1))


def test_write_gene_cell_scatter_raises_for_missing_gene(tmp_path):
    adata = _synthetic_multi_gene_adata(gene_names=("Gene0",))

    with pytest.raises(ValueError, match="Gene1"):
        write_gene_cell_scatter(
            adata,
            ["Gene0", "Gene1"],
            tmp_path,
            slice_attr="slice_id",
            z_attr="z",
        )


def test_write_cell_clusters_meta_requires_gdf_columns():
    bare_nbhd = gpd.GeoDataFrame({"name": ["x"]}, geometry=[Point(0, 0).buffer(10)])

    with pytest.raises(ValueError, match="cluster_id"):
        write_cell_clusters_meta(bare_nbhd, "unused")


def test_write_nbhd_cloud_shapes_and_features_requires_slice_id_column():
    bare_nbhd = gpd.GeoDataFrame(
        {"name": ["x"], "cluster_id": ["0"], "color": ["#ff0000"], "cell_count": [5]},
        geometry=[Point(0, 0).buffer(10)],
    )

    with pytest.raises(ValueError, match="slice_id"):
        write_nbhd_cloud_shapes_and_features(bare_nbhd, "unused")


def test_write_nbhd_cloud_shapes_and_features_rejects_duplicate_ids(tmp_path):
    gdf = _build_nbhd(_synthetic_dataset())
    gdf.loc[1, "name"] = gdf.loc[0, "name"]

    with pytest.raises(ValueError, match="unique"):
        write_nbhd_cloud_shapes_and_features(gdf, tmp_path)


def test_write_nbhd_cloud_shapes_accepts_neighborhood_like_object(tmp_path):
    gdf = _build_nbhd(_synthetic_dataset())

    write_nbhd_cloud_shapes_and_features(_NeighborhoodLike(gdf), tmp_path)

    df_meta_nbhd = pd.read_parquet(tmp_path / "nbhd_cloud" / "meta_neighborhood.parquet")
    assert list(df_meta_nbhd["neighborhood_id"]) == list(gdf["name"])


def test_nbhd_cloud_writes_both_manifests(tmp_path) -> None:
    _write_nbhd_cloud_landscape_parameters(tmp_path)

    legacy = json.loads((tmp_path / "landscape_parameters.json").read_text())
    new = json.loads((tmp_path / "neighborhood_cloud.json").read_text())

    assert new == legacy
    assert new["technology"] == "neighborhood-cloud"


def test_write_nbhd_cloud_dataset_end_to_end(tmp_path):
    adata = _synthetic_dataset()
    nbhd = _build_nbhd(adata)

    write_nbhd_cloud_dataset(
        adata,
        nbhd,
        tmp_path,
        cluster_attr="cluster",
        slice_attr="slice_id",
        z_attr="z",
    )

    assert (tmp_path / "nbhd_cloud" / "meta_slice.parquet").exists()
    assert (tmp_path / "nbhd_cloud" / "meta_neighborhood.parquet").exists()
    assert not (tmp_path / "nbhd_cloud" / "population.parquet").exists()
    assert not (tmp_path / "nbhd_cloud" / "expression").exists()
    assert (tmp_path / "nbhd_cloud" / "cells" / "by_cluster" / "cluster_0.parquet").exists()
    assert (tmp_path / "nbhd_cloud" / "shapes" / "by_slice" / "slice_s0.parquet").exists()
    assert (tmp_path / "cell_clusters" / "meta_cluster.parquet").exists()
    assert (tmp_path / "meta_gene.parquet").exists()

    with (tmp_path / "landscape_parameters.json").open() as f:
        landscape_parameters = json.load(f)

    assert landscape_parameters["technology"] == "neighborhood-cloud"


def test_write_meta_gene_for_nbhd_cloud(tmp_path):
    adata = _synthetic_dataset(n_genes=3)

    write_meta_gene_for_nbhd_cloud(adata, tmp_path)

    df_meta_gene = pd.read_parquet(tmp_path / "meta_gene.parquet")
    assert set(df_meta_gene.index) == {"Gene0", "Gene1", "Gene2"}
    assert {"mean", "std", "max", "non-zero", "color"}.issubset(df_meta_gene.columns)
    assert df_meta_gene["color"].notna().all()


def test_write_meta_gene_for_nbhd_cloud_accepts_sparse_x(tmp_path):
    import scipy.sparse as sp

    adata = _synthetic_dataset(n_genes=3)
    adata.X = sp.csr_matrix(adata.X)

    write_meta_gene_for_nbhd_cloud(adata, tmp_path)

    df_meta_gene = pd.read_parquet(tmp_path / "meta_gene.parquet")
    assert set(df_meta_gene.index) == {"Gene0", "Gene1", "Gene2"}
    assert {"mean", "std", "max", "non-zero", "color"}.issubset(df_meta_gene.columns)
