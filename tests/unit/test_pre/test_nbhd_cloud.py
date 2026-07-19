import json

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from celldega.nbhd import NeighborhoodCollection, alpha_shape_cell_clusters_by_slice
from celldega.pre import (
    write_cell_clusters_meta,
    write_meta_gene_for_nbhd_cloud,
    write_meta_slice,
    write_nbhd_cloud_cells,
    write_nbhd_cloud_dataset,
    write_nbhd_cloud_shapes_and_features,
)


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
    gdf = alpha_shape_cell_clusters_by_slice(
        adata, cluster_attr="cluster", slice_attr="slice_id", z_attr="z", alphas=(150,)
    )
    return NeighborhoodCollection.from_gdf(gdf, nbhd_type="alpha_shape")


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


def test_write_nbhd_cloud_cells_by_slice(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud_cells(
        adata, tmp_path, cluster_attr="cluster", slice_attr="slice_id", z_attr="z"
    )

    by_slice_dir = tmp_path / "nbhd_cloud" / "cells" / "by_slice"
    assert {p.name for p in by_slice_dir.glob("*.parquet")} == {
        "slice_s0.parquet",
        "slice_s1.parquet",
    }

    df_slice_s0 = pd.read_parquet(by_slice_dir / "slice_s0.parquet")
    assert len(df_slice_s0) == 60  # slice s0, both clusters, 30 cells each
    assert set(df_slice_s0["cluster_id"]) == {"0", "1"}
    assert (df_slice_s0["z"] == 0.0).all()
    assert {"cell_id", "x", "y", "z", "cluster_id", "slice_id"}.issubset(df_slice_s0.columns)


def test_write_nbhd_cloud_shapes_and_features(tmp_path):
    adata = _synthetic_dataset()
    nbhd = _build_nbhd(adata)

    write_nbhd_cloud_shapes_and_features(
        adata, nbhd, tmp_path, cluster_attr="cluster", slice_attr="slice_id"
    )

    shapes_dir = tmp_path / "nbhd_cloud" / "shapes"
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

    expression_dir = tmp_path / "nbhd_cloud" / "expression"
    assert {p.name for p in expression_dir.glob("*.parquet")} == {
        "Gene0.parquet",
        "Gene1.parquet",
    }
    df_gene0 = pd.read_parquet(expression_dir / "Gene0.parquet")
    assert len(df_gene0) == 4
    assert set(df_gene0.columns) == {"neighborhood_id", "mean", "variance"}
    assert (df_gene0["variance"] >= 0).all()

    df_population = pd.read_parquet(tmp_path / "nbhd_cloud" / "population.parquet")
    assert set(df_population.columns) == {"neighborhood_id", "category", "proportion"}
    # each neighborhood's own cluster should be ~100% of its population, since
    # alpha shapes are tight blobs around a single cluster in this fixture
    per_neighborhood = df_population.pivot(
        index="neighborhood_id", columns="category", values="proportion"
    )
    assert np.isclose(per_neighborhood.sum(axis=1), 1.0).all()

    # feature spaces are also attached to the NeighborhoodCollection itself
    assert "gene" in nbhd.mod
    assert "population" in nbhd.mod
    assert "variance" in nbhd.mod["gene"].layers

    # cell_clusters/meta_cluster.parquet is also written so the existing
    # cluster-color/cluster-bar machinery (shared by every technology) works
    # for neighborhood-cloud datasets too.
    df_meta_cluster = pd.read_parquet(tmp_path / "cell_clusters" / "meta_cluster.parquet")
    assert set(df_meta_cluster.columns) == {"cluster", "color", "count"}
    assert set(df_meta_cluster["cluster"]) == {"0", "1"}
    # each cluster spans both slices, 30 cells each -> 60 total
    assert (df_meta_cluster["count"] == 60).all()


def test_write_cell_clusters_meta_requires_gdf_columns():
    import geopandas as gpd
    from shapely.geometry import Point

    bare_nbhd = NeighborhoodCollection(
        gdf=gpd.GeoDataFrame({"name": ["x"]}, geometry=[Point(0, 0).buffer(10)]),
        nbhd_type="manual",
    )

    with pytest.raises(ValueError, match="cluster_id"):
        write_cell_clusters_meta(bare_nbhd, "unused")


def test_write_nbhd_cloud_shapes_and_features_requires_slice_id_column():
    import geopandas as gpd
    from shapely.geometry import Point

    adata = _synthetic_dataset(n_slices=1, n_clusters=1)
    bare_nbhd = NeighborhoodCollection(
        gdf=gpd.GeoDataFrame({"name": ["x"]}, geometry=[Point(0, 0).buffer(10)]),
        nbhd_type="manual",
    )

    with pytest.raises(ValueError, match="slice_id"):
        write_nbhd_cloud_shapes_and_features(adata, bare_nbhd, "unused")


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
    assert (tmp_path / "nbhd_cloud" / "population.parquet").exists()
    assert (tmp_path / "nbhd_cloud" / "cells" / "by_slice" / "slice_s0.parquet").exists()
    assert (tmp_path / "nbhd_cloud" / "shapes" / "slice_s0.parquet").exists()
    assert (tmp_path / "nbhd_cloud" / "expression" / "Gene0.parquet").exists()
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
