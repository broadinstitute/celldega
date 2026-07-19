import json

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from celldega.nbhd import (
    NeighborhoodCollection,
    alpha_shape_cell_clusters_by_slice,
    alpha_shape_gene_expression_by_slice,
)
from celldega.pre import (
    write_cell_clusters_meta,
    write_gene_shapes,
    write_gene_shapes_from_cbg,
    write_gene_shapes_streaming,
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

    # Per-neighborhood gene expression / population are no longer computed or
    # written here -- gene coloring comes from the curated gene-shapes
    # feature instead (see write_gene_shapes), and population was never
    # surfaced in the frontend.
    assert not (tmp_path / "nbhd_cloud" / "expression").exists()
    assert not (tmp_path / "nbhd_cloud" / "population.parquet").exists()
    assert "gene" not in nbhd.mod
    assert "population" not in nbhd.mod

    # cell_clusters/meta_cluster.parquet is also written so the existing
    # cluster-color/cluster-bar machinery (shared by every technology) works
    # for neighborhood-cloud datasets too.
    df_meta_cluster = pd.read_parquet(tmp_path / "cell_clusters" / "meta_cluster.parquet")
    assert set(df_meta_cluster.columns) == {"cluster", "color", "count"}
    assert set(df_meta_cluster["cluster"]) == {"0", "1"}
    # each cluster spans both slices, 30 cells each -> 60 total
    assert (df_meta_cluster["count"] == 60).all()


def test_write_gene_shapes(tmp_path):
    rng = np.random.RandomState(0)
    rows = []
    xy = []
    X = []
    for slice_idx in range(2):
        center = np.array([slice_idx * 300.0, 0.0])
        pts = rng.normal(loc=center, scale=10.0, size=(20, 2))
        xy.append(pts)
        rows.extend([{"slice_id": f"s{slice_idx}", "z": float(slice_idx) * 100.0}] * 20)
        slice_expr = np.zeros((20, 1))
        slice_expr[::2, :] = 5.0
        X.append(slice_expr)

    obs = pd.DataFrame(rows)
    obs.index = [f"cell_{i}" for i in range(len(obs))]
    adata = ad.AnnData(X=np.vstack(X), obs=obs, var=pd.DataFrame(index=["Matn1"]))
    adata.obsm["spatial"] = np.vstack(xy)

    gdf = alpha_shape_gene_expression_by_slice(
        adata, ["Matn1"], slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
    )

    write_gene_shapes(gdf, tmp_path)

    gene_shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_gene"
    assert {p.name for p in gene_shapes_dir.glob("*")} == {
        "Matn1.parquet",
        "available_genes.json",
    }

    df_matn1 = pd.read_parquet(gene_shapes_dir / "Matn1.parquet")
    assert len(df_matn1) == 2  # one shape per slice
    assert set(df_matn1["slice_id"]) == {"s0", "s1"}
    assert "geometry_geojson" in df_matn1.columns
    assert "geometry" not in df_matn1.columns
    parsed_geometries = [json.loads(g) for g in df_matn1["geometry_geojson"]]
    assert all(
        len(coord) == 3
        for g in parsed_geometries
        for poly in g["coordinates"]
        for ring in poly
        for coord in ring
    )

    with (gene_shapes_dir / "available_genes.json").open() as f:
        manifest = json.load(f)
    assert set(manifest) == {"Matn1"}
    assert manifest["Matn1"] == pytest.approx(5.0)


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


def test_write_gene_shapes_streaming(tmp_path):
    adata = _synthetic_multi_gene_adata()

    n_written = write_gene_shapes_streaming(
        adata,
        ["Gene0", "Gene1", "Gene2"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        progress_every=0,
    )

    assert n_written == 3
    gene_shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_gene"
    assert {p.name for p in gene_shapes_dir.glob("*")} == {
        "Gene0.parquet",
        "Gene1.parquet",
        "Gene2.parquet",
        "available_genes.json",
    }

    df_gene0 = pd.read_parquet(gene_shapes_dir / "Gene0.parquet")
    assert len(df_gene0) == 2  # one shape per slice
    assert set(df_gene0["slice_id"]) == {"s0", "s1"}
    assert "geometry_geojson" in df_gene0.columns
    assert "geometry" not in df_gene0.columns

    with (gene_shapes_dir / "available_genes.json").open() as f:
        manifest = json.load(f)
    assert set(manifest) == {"Gene0", "Gene1", "Gene2"}
    assert manifest["Gene0"] == pytest.approx(5.0)


def test_write_gene_shapes_streaming_skips_genes_with_no_shape(tmp_path):
    adata = _synthetic_multi_gene_adata(gene_names=("Gene0", "Gene1"))
    # Gene1 has no cells at all expressing above min_expression (all zero) --
    # nothing to compute, and it must not appear on disk or in the manifest.
    # (Indexing directly into the array, not `adata[:, "Gene1"].X`, since the
    # latter operates on a disconnected view/copy and never touches `adata`.)
    adata.X[:, adata.var_names.get_loc("Gene1")] = 0

    n_written = write_gene_shapes_streaming(
        adata,
        ["Gene0", "Gene1"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        progress_every=0,
    )

    assert n_written == 1
    gene_shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_gene"
    assert {p.name for p in gene_shapes_dir.glob("*.parquet")} == {"Gene0.parquet"}

    with (gene_shapes_dir / "available_genes.json").open() as f:
        manifest = json.load(f)
    assert set(manifest) == {"Gene0"}

    # Gene1 has no shape (and thus no manifest entry, so it's unreachable
    # from the frontend) -- its cells file must not exist either.
    gene_cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_gene"
    assert {p.name for p in gene_cells_dir.glob("*.parquet")} == {"Gene0.parquet"}


def test_write_gene_shapes_streaming_writes_top_expressing_cells(tmp_path):
    adata = _synthetic_multi_gene_adata(n_slices=2, n_cells=20, gene_names=("Gene0",))
    # Distinct expression values on the "expressing" cells so the top-K
    # selection is unambiguous.
    gene_col = adata.var_names.get_loc("Gene0")
    expressing_mask = adata.X[:, gene_col] != 0
    adata.X[expressing_mask, gene_col] = np.arange(1, expressing_mask.sum() + 1)

    write_gene_shapes_streaming(
        adata,
        ["Gene0"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        max_cells=5,
        progress_every=0,
    )

    df_cells = pd.read_parquet(tmp_path / "nbhd_cloud" / "cells" / "by_gene" / "Gene0.parquet")
    assert len(df_cells) == 5
    assert {"cell_id", "gene", "slice_id", "x", "y", "z", "expression"}.issubset(df_cells.columns)
    assert (df_cells["gene"] == "Gene0").all()
    # Top-5 expressing cells across both slices are the 5 highest values.
    max_expr = expressing_mask.sum()
    assert set(df_cells["expression"]) == set(range(max_expr - 4, max_expr + 1))


def test_write_gene_shapes_streaming_max_cells_zero_writes_no_cells_files(tmp_path):
    adata = _synthetic_multi_gene_adata()

    write_gene_shapes_streaming(
        adata,
        ["Gene0", "Gene1", "Gene2"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        max_cells=0,
        progress_every=0,
    )

    gene_cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_gene"
    assert not any(gene_cells_dir.glob("*.parquet"))


def test_write_gene_shapes_streaming_matches_non_streaming_output(tmp_path):
    """The streaming and non-streaming writers must produce the same files
    for the same input -- streaming is purely a memory-bounding change to
    *when* things get written, not a different computation."""
    adata = _synthetic_multi_gene_adata()
    gene_list = ["Gene0", "Gene1", "Gene2"]

    streaming_dir = tmp_path / "streaming"
    write_gene_shapes_streaming(
        adata,
        gene_list,
        streaming_dir,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        progress_every=0,
    )

    non_streaming_dir = tmp_path / "non_streaming"
    gdf = alpha_shape_gene_expression_by_slice(
        adata, gene_list, slice_attr="slice_id", z_attr="z", alphas=(150,), min_cells=4
    )
    write_gene_shapes(gdf, non_streaming_dir)

    streaming_files = {
        p.name for p in (streaming_dir / "nbhd_cloud" / "shapes" / "by_gene").glob("*")
    }
    non_streaming_files = {
        p.name for p in (non_streaming_dir / "nbhd_cloud" / "shapes" / "by_gene").glob("*")
    }
    assert streaming_files == non_streaming_files

    for gene in gene_list:
        df_streaming = pd.read_parquet(
            streaming_dir / "nbhd_cloud" / "shapes" / "by_gene" / f"{gene}.parquet"
        )
        df_non_streaming = pd.read_parquet(
            non_streaming_dir / "nbhd_cloud" / "shapes" / "by_gene" / f"{gene}.parquet"
        )
        pd.testing.assert_frame_equal(
            df_streaming.sort_values("slice_id").reset_index(drop=True),
            df_non_streaming.sort_values("slice_id").reset_index(drop=True),
        )


def _write_fake_cbg_dir(cbg_dir, adata):
    """One `<gene>.parquet` per gene -- a single-column sparse series indexed
    by cell id, zeros dropped, mirroring the real `cbg/` layout
    `write_gene_shapes_from_cbg` reads from."""
    cbg_dir.mkdir(parents=True, exist_ok=True)
    X = np.asarray(adata.X)
    for j, gene in enumerate(adata.var_names):
        col = pd.Series(X[:, j], index=adata.obs_names.astype(str), name=gene)
        col = col[col != 0]
        col.to_frame().to_parquet(cbg_dir / f"{gene}.parquet")


def test_write_gene_shapes_from_cbg_matches_streaming_output(tmp_path):
    """Reading each gene's expression on-the-fly from `cbg/<gene>.parquet`
    (no combined AnnData ever built) must produce the same shapes as the
    AnnData-based streaming writer, for the same underlying data."""
    adata = _synthetic_multi_gene_adata()
    gene_list = ["Gene0", "Gene1", "Gene2"]

    cbg_dir = tmp_path / "cbg"
    _write_fake_cbg_dir(cbg_dir, adata)

    from_cbg_dir = tmp_path / "from_cbg"
    n_written = write_gene_shapes_from_cbg(
        cbg_dir,
        gene_list,
        adata.obs,
        adata.obsm["spatial"],
        from_cbg_dir,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        progress_every=0,
    )
    assert n_written == 3

    streaming_dir = tmp_path / "streaming"
    write_gene_shapes_streaming(
        adata,
        gene_list,
        streaming_dir,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        progress_every=0,
    )

    from_cbg_files = {
        p.name for p in (from_cbg_dir / "nbhd_cloud" / "shapes" / "by_gene").glob("*")
    }
    streaming_files = {
        p.name for p in (streaming_dir / "nbhd_cloud" / "shapes" / "by_gene").glob("*")
    }
    assert from_cbg_files == streaming_files

    for gene in gene_list:
        df_from_cbg = pd.read_parquet(
            from_cbg_dir / "nbhd_cloud" / "shapes" / "by_gene" / f"{gene}.parquet"
        )
        df_streaming = pd.read_parquet(
            streaming_dir / "nbhd_cloud" / "shapes" / "by_gene" / f"{gene}.parquet"
        )
        pd.testing.assert_frame_equal(
            df_from_cbg.sort_values("slice_id").reset_index(drop=True),
            df_streaming.sort_values("slice_id").reset_index(drop=True),
        )

        df_cells_from_cbg = pd.read_parquet(
            from_cbg_dir / "nbhd_cloud" / "cells" / "by_gene" / f"{gene}.parquet"
        )
        df_cells_streaming = pd.read_parquet(
            streaming_dir / "nbhd_cloud" / "cells" / "by_gene" / f"{gene}.parquet"
        )
        pd.testing.assert_frame_equal(
            df_cells_from_cbg.sort_values("cell_id").reset_index(drop=True),
            df_cells_streaming.sort_values("cell_id").reset_index(drop=True),
        )


def test_write_gene_shapes_from_cbg_skips_genes_with_no_shape(tmp_path):
    adata = _synthetic_multi_gene_adata(gene_names=("Gene0", "Gene1"))
    adata.X[:, adata.var_names.get_loc("Gene1")] = 0

    cbg_dir = tmp_path / "cbg"
    _write_fake_cbg_dir(cbg_dir, adata)

    n_written = write_gene_shapes_from_cbg(
        cbg_dir,
        ["Gene0", "Gene1"],
        adata.obs,
        adata.obsm["spatial"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        progress_every=0,
    )

    assert n_written == 1
    gene_shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_gene"
    assert {p.name for p in gene_shapes_dir.glob("*.parquet")} == {"Gene0.parquet"}

    with (gene_shapes_dir / "available_genes.json").open() as f:
        manifest = json.load(f)
    assert set(manifest) == {"Gene0"}

    gene_cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_gene"
    assert {p.name for p in gene_cells_dir.glob("*.parquet")} == {"Gene0.parquet"}


def test_write_gene_shapes_from_cbg_caps_cells_at_max_cells(tmp_path):
    adata = _synthetic_multi_gene_adata(n_slices=2, n_cells=20, gene_names=("Gene0",))
    gene_col = adata.var_names.get_loc("Gene0")
    expressing_mask = adata.X[:, gene_col] != 0
    adata.X[expressing_mask, gene_col] = np.arange(1, expressing_mask.sum() + 1)

    cbg_dir = tmp_path / "cbg"
    _write_fake_cbg_dir(cbg_dir, adata)

    write_gene_shapes_from_cbg(
        cbg_dir,
        ["Gene0"],
        adata.obs,
        adata.obsm["spatial"],
        tmp_path,
        slice_attr="slice_id",
        z_attr="z",
        alphas=(150,),
        min_cells=4,
        max_cells=5,
        progress_every=0,
    )

    df_cells = pd.read_parquet(tmp_path / "nbhd_cloud" / "cells" / "by_gene" / "Gene0.parquet")
    assert len(df_cells) == 5
    max_expr = expressing_mask.sum()
    assert set(df_cells["expression"]) == set(range(max_expr - 4, max_expr + 1))


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

    bare_nbhd = NeighborhoodCollection(
        gdf=gpd.GeoDataFrame({"name": ["x"]}, geometry=[Point(0, 0).buffer(10)]),
        nbhd_type="manual",
    )

    with pytest.raises(ValueError, match="slice_id"):
        write_nbhd_cloud_shapes_and_features(bare_nbhd, "unused")


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
