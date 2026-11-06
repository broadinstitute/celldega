"""Tests for celldega.pre.write_point_cloud_dataset (synthetic data only)."""

import json

from anndata import AnnData
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from scipy.sparse import csr_matrix

from celldega.pre import POINT_CLOUD_MANIFEST_NAMES, write_point_cloud_dataset


def _make_adata(n=30, n_slices=3, with_z=True, spatial_dim=2, seed=0, n_genes=0, sparse=True):
    rng = np.random.default_rng(seed)
    slice_ids = np.repeat(np.arange(n_slices), int(np.ceil(n / n_slices)))[:n]
    obs = pd.DataFrame(
        {
            "batch": slice_ids,
            "cluster": rng.choice(list("AB"), n),
        },
        index=[f"cell{i}-0" for i in range(n)],
    )
    if with_z:
        obs["Z"] = slice_ids.astype(float) * 100.0
    if n_genes:
        counts = rng.poisson(0.5, size=(n, n_genes)).astype(float)
        x = csr_matrix(counts) if sparse else counts
        var = pd.DataFrame(index=[f"Gene{j}" for j in range(n_genes)])
        adata = AnnData(X=x, obs=obs, var=var)
    else:
        adata = AnnData(X=np.zeros((n, 1), dtype=float), obs=obs)
    adata.obsm["spatial"] = rng.normal(size=(n, spatial_dim)) * 50.0
    return adata


def _read_geometry(path):
    table = pq.read_table(path)
    assert table.schema.names == ["name", "geometry"]
    names = [str(x) for x in table.column("name").to_pylist()]
    geometry = table.column("geometry").to_pylist()
    return names, geometry


def test_create_mode_writes_full_point_cloud(tmp_path):
    adata = _make_adata()
    path = write_point_cloud_dataset(adata, tmp_path, name="procrustes", cluster_key="cluster")

    assert path.name == "cell_metadata_procrustes.parquet"
    assert path.exists()
    # create mode also writes a base cell_metadata.parquet so a variant-less
    # CellCloud still works
    assert (tmp_path / "cell_metadata.parquet").exists()
    assert (tmp_path / "cell_clusters" / "cluster.parquet").exists()
    assert (tmp_path / "cell_clusters" / "meta_cluster.parquet").exists()

    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["technology"] == "point-cloud"
    assert params["alignments"] == ["procrustes"]


def test_geometry_is_xyz_from_spatial_and_z(tmp_path):
    adata = _make_adata()
    path = write_point_cloud_dataset(adata, tmp_path, name="a1")

    names, geometry = _read_geometry(path)
    assert names == list(adata.obs_names)
    assert all(len(g) == 3 for g in geometry)

    xy = np.asarray([g[:2] for g in geometry])
    z = np.asarray([g[2] for g in geometry])
    np.testing.assert_allclose(xy, adata.obsm["spatial"][:, :2], rtol=1e-5)
    np.testing.assert_allclose(z, adata.obs["Z"].to_numpy(), rtol=1e-5)


def test_z_falls_back_to_third_spatial_column(tmp_path):
    adata = _make_adata(with_z=False, spatial_dim=3)
    _, geometry = _read_geometry(write_point_cloud_dataset(adata, tmp_path, name="a1"))
    z = np.asarray([g[2] for g in geometry])
    np.testing.assert_allclose(z, adata.obsm["spatial"][:, 2], rtol=1e-5)


def test_z_defaults_to_zero_when_absent(tmp_path):
    adata = _make_adata(with_z=False, spatial_dim=2)
    _, geometry = _read_geometry(write_point_cloud_dataset(adata, tmp_path, name="a1"))
    z = np.asarray([g[2] for g in geometry])
    np.testing.assert_array_equal(z, np.zeros(adata.n_obs))


def test_append_mode_registers_without_clobbering(tmp_path):
    first = _make_adata(seed=0)
    write_point_cloud_dataset(first, tmp_path, name="procrustes", cluster_key="cluster")
    base_before = (tmp_path / "cell_metadata.parquet").read_bytes()

    # append a second variant with different positions
    second = _make_adata(seed=1)
    path2 = write_point_cloud_dataset(second, tmp_path, name="tps")

    assert path2.name == "cell_metadata_tps.parquet"
    # base cell_metadata is untouched by an append
    assert (tmp_path / "cell_metadata.parquet").read_bytes() == base_before
    # both variants registered, in order
    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["alignments"] == ["procrustes", "tps"]
    # append does not re-write clusters (reuses existing)
    _, g2 = _read_geometry(path2)
    np.testing.assert_allclose(
        np.asarray([g[:2] for g in g2]), second.obsm["spatial"][:, :2], rtol=1e-5
    )


def test_register_is_idempotent(tmp_path):
    adata = _make_adata()
    write_point_cloud_dataset(adata, tmp_path, name="a1")
    write_point_cloud_dataset(adata, tmp_path, name="a1", overwrite=True)
    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["alignments"] == ["a1"]


def test_overwrite_guard(tmp_path):
    adata = _make_adata()
    write_point_cloud_dataset(adata, tmp_path, name="a1")
    with pytest.raises(FileExistsError):
        write_point_cloud_dataset(adata, tmp_path, name="a1")
    # overwrite=True is allowed
    write_point_cloud_dataset(adata, tmp_path, name="a1", overwrite=True)


def test_append_preserves_existing_params(tmp_path):
    adata = _make_adata()
    write_point_cloud_dataset(adata, tmp_path, name="a1")
    # simulate an existing DegaFiles with extra params + prior alignments
    params_path = tmp_path / "landscape_parameters.json"
    params = json.loads(params_path.read_text())
    params["use_int_index"] = False
    params["custom_key"] = {"keep": "me"}
    params_path.write_text(json.dumps(params))

    write_point_cloud_dataset(adata, tmp_path, name="a2")
    out = json.loads(params_path.read_text())
    assert out["custom_key"] == {"keep": "me"}
    assert out["alignments"] == ["a1", "a2"]


@pytest.mark.parametrize("bad", ["default", "", "a/b", ".hidden", "-lead", "a b"])
def test_invalid_variant_names_rejected(tmp_path, bad):
    adata = _make_adata()
    with pytest.raises(ValueError):
        write_point_cloud_dataset(adata, tmp_path, name=bad)


def test_requires_spatial(tmp_path):
    adata = AnnData(X=np.zeros((3, 1)), obs=pd.DataFrame(index=["a", "b", "c"]))
    with pytest.raises(ValueError):
        write_point_cloud_dataset(adata, tmp_path, name="a1")


@pytest.mark.parametrize("sparse", [True, False])
def test_create_mode_writes_gene_expression_when_available(tmp_path, sparse):
    adata = _make_adata(n_genes=4, sparse=sparse)
    write_point_cloud_dataset(adata, tmp_path, name="a1", cluster_key="cluster")

    cbg_dir = tmp_path / "cbg"
    assert cbg_dir.is_dir()
    assert (tmp_path / "meta_gene.parquet").exists()

    # each gene file is keyed by cell name (pandas index -> __index_level_0__)
    gene_files = sorted(p.name for p in cbg_dir.glob("*.parquet"))
    assert gene_files, "expected per-gene parquet files"
    table = pq.read_table(cbg_dir / gene_files[0])
    gene = gene_files[0][: -len(".parquet")]
    assert gene in table.schema.names
    assert "__index_level_0__" in table.schema.names
    cell_names = {str(x) for x in table.column("__index_level_0__").to_pylist()}
    assert cell_names <= set(adata.obs_names)  # only expressing cells, by name

    meta_gene = pd.read_parquet(tmp_path / "meta_gene.parquet")
    assert "color" in meta_gene.columns
    assert set(meta_gene.index) == set(adata.var_names)


def test_create_mode_skips_genes_without_expression(tmp_path):
    adata = _make_adata(n_genes=0)  # no genes
    write_point_cloud_dataset(adata, tmp_path, name="a1", cluster_key="cluster")
    assert not (tmp_path / "cbg").exists()
    assert not (tmp_path / "meta_gene.parquet").exists()


def test_write_genes_false_disables_export(tmp_path):
    adata = _make_adata(n_genes=4)
    write_point_cloud_dataset(adata, tmp_path, name="a1", write_genes=False)
    assert not (tmp_path / "cbg").exists()
    assert not (tmp_path / "meta_gene.parquet").exists()


def test_write_genes_true_without_expression_raises(tmp_path):
    adata = _make_adata(n_genes=0)
    with pytest.raises(ValueError):
        write_point_cloud_dataset(adata, tmp_path, name="a1", write_genes=True)


def test_append_mode_leaves_gene_writing_to_existing_data(tmp_path):
    # create with genes, then append a variant with genes=True: append must not
    # touch gene data (write_genes only applies to create mode)
    adata = _make_adata(n_genes=3)
    write_point_cloud_dataset(adata, tmp_path, name="a1")
    meta_before = (tmp_path / "meta_gene.parquet").read_bytes()
    write_point_cloud_dataset(adata, tmp_path, name="a2", write_genes=True)
    assert (tmp_path / "meta_gene.parquet").read_bytes() == meta_before


def test_create_without_name_writes_base_positions_only(tmp_path):
    adata = _make_adata()
    path = write_point_cloud_dataset(adata, tmp_path, cluster_key="cluster")

    assert path.name == "cell_metadata.parquet"
    names, geometry = _read_geometry(path)
    assert names == list(adata.obs_names)
    assert all(len(g) == 3 for g in geometry)
    assert not list(tmp_path.glob("cell_metadata_*.parquet"))
    params = json.loads((tmp_path / "cell_cloud.json").read_text())
    assert params["technology"] == "point-cloud"
    assert params["alignments"] == []


def test_existing_dataset_without_name_requires_overwrite(tmp_path):
    adata = _make_adata()
    write_point_cloud_dataset(adata, tmp_path)
    with pytest.raises(FileExistsError):
        write_point_cloud_dataset(adata, tmp_path)
    write_point_cloud_dataset(adata, tmp_path, overwrite=True)


def test_manifests_written_and_kept_in_sync(tmp_path):
    adata = _make_adata()
    write_point_cloud_dataset(adata, tmp_path, name="a1", cluster_key="cluster")
    write_point_cloud_dataset(adata, tmp_path, name="a2")  # append mode

    manifests = [json.loads((tmp_path / name).read_text()) for name in POINT_CLOUD_MANIFEST_NAMES]
    assert manifests[0] == manifests[1]
    assert manifests[0]["technology"] == "point-cloud"
    assert manifests[0]["alignments"] == ["a1", "a2"]


def test_create_mode_validates_before_writing(tmp_path):
    adata = _make_adata()

    with pytest.raises(ValueError, match="cluster_key"):
        write_point_cloud_dataset(adata, tmp_path / "pc", name="a1", cluster_key="nope")
    with pytest.raises(ValueError, match="write_genes"):
        write_point_cloud_dataset(adata, tmp_path / "pc2", name="a1", write_genes=True)

    assert not (tmp_path / "pc").exists()
    assert not (tmp_path / "pc2").exists()
    # a corrected retry still runs in create mode and writes clusters
    write_point_cloud_dataset(adata, tmp_path / "pc", name="a1", cluster_key="cluster")
    assert (tmp_path / "pc" / "cell_clusters" / "meta_cluster.parquet").exists()


def test_compact_files_share_numeric_ids_and_preserve_original_names(tmp_path):
    adata = _make_adata(n=31, n_genes=4)
    adata.obsm["spatial"][0] = [12.49, -8.51]
    write_point_cloud_dataset(
        adata,
        tmp_path,
        name="neighborhood",
        cluster_key="cluster",
        use_int_index=True,
        coordinate_resolution=1.0,
        compression="zstd",
        compression_level=6,
    )
    manifest = json.loads((tmp_path / "cell_cloud.json").read_text())
    assert manifest["use_int_index"] is True
    assert manifest["cell_ids"] == "cell_ids.parquet"
    assert manifest["coordinate_resolution"] == 1.0
    assert (
        pd.read_parquet(tmp_path / "cell_ids.parquet")["name"].tolist() == adata.obs_names.tolist()
    )
    table = pq.read_table(tmp_path / "cell_metadata_neighborhood.parquet")
    import pyarrow as pa

    assert table.schema.field("name").type == pa.uint32()
    assert table.schema.field("geometry").type.value_type == pa.int32()
    assert table["name"].to_pylist() == list(range(adata.n_obs))
    np.testing.assert_array_equal(table["geometry"].to_pylist()[0], [12, -9, 0])
    cluster = pd.read_parquet(tmp_path / "cell_clusters" / "cluster.parquet")
    assert cluster["name"].tolist() == list(range(adata.n_obs))
    assert cluster["cluster"].astype(str).tolist() == adata.obs["cluster"].astype(str).tolist()
    for gene_index, gene in enumerate(adata.var_names):
        path = tmp_path / "cbg" / f"{gene}.parquet"
        source = adata.X[:, gene_index].toarray().ravel()
        if not path.exists():
            assert not np.any(source)
            continue
        values = pq.read_table(path)
        ids = np.asarray(values["__index_level_0__"])
        np.testing.assert_array_equal(values[gene].to_numpy(), source[ids])
        assert np.all(source[ids] != 0)


def test_indexed_alignment_reorders_shuffled_cells_and_rejects_missing_ids(tmp_path):
    adata = _make_adata(n_genes=2)
    write_point_cloud_dataset(
        adata, tmp_path, name="first", use_int_index=True, coordinate_resolution=1
    )
    shuffled = adata[np.arange(adata.n_obs)[::-1]].copy()
    shuffled.obsm["spatial"] += 20
    write_point_cloud_dataset(shuffled, tmp_path, name="second")
    first = np.asarray(
        pq.read_table(tmp_path / "cell_metadata_first.parquet")["geometry"].to_pylist()
    )
    second = np.asarray(
        pq.read_table(tmp_path / "cell_metadata_second.parquet")["geometry"].to_pylist()
    )
    np.testing.assert_array_equal(second[:, :2], first[:, :2] + 20)
    with pytest.raises(ValueError, match="exactly the existing cells"):
        write_point_cloud_dataset(adata[:-1], tmp_path, name="bad")
    assert not (tmp_path / "cell_metadata_bad.parquet").exists()
    assert json.loads((tmp_path / "cell_cloud.json").read_text())["alignments"] == [
        "first",
        "second",
    ]


@pytest.mark.parametrize("resolution", [0, -1, float("inf"), float("nan")])
def test_invalid_coordinate_resolution_does_not_write(tmp_path, resolution):
    target = tmp_path / "new"
    with pytest.raises(ValueError, match="coordinate_resolution"):
        write_point_cloud_dataset(_make_adata(), target, coordinate_resolution=resolution)
    assert not target.exists()


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), float(2**32)])
def test_invalid_rounded_coordinates_dont_overflow_or_write(tmp_path, coordinate):
    adata = _make_adata()
    adata.obsm["spatial"][0, 0] = coordinate
    target = tmp_path / "new"
    with pytest.raises(ValueError, match=r"finite|int32"):
        write_point_cloud_dataset(adata, target, coordinate_resolution=1)
    assert not target.exists()


def test_duplicate_names_are_rejected_before_writing(tmp_path):
    adata = _make_adata()
    adata.obs_names = ["duplicate"] * adata.n_obs
    target = tmp_path / "new"
    with pytest.raises(ValueError, match="unique"):
        write_point_cloud_dataset(adata, target, use_int_index=True)
    assert not target.exists()


def test_compact_append_cannot_change_indexing_or_resolution(tmp_path):
    adata = _make_adata()
    write_point_cloud_dataset(
        adata, tmp_path, name="first", use_int_index=True, coordinate_resolution=1
    )
    for kwargs in [{"use_int_index": False}, {"coordinate_resolution": 2}]:
        with pytest.raises(ValueError, match="must match"):
            write_point_cloud_dataset(adata, tmp_path, name="bad", **kwargs)
    assert not (tmp_path / "cell_metadata_bad.parquet").exists()


def test_point_cloud_zarr_roundtrip_preserves_counts_ids_colors_and_alignments(tmp_path):
    import anndata as ad
    import zarr

    from celldega.pre import write_point_cloud_zarr

    adata = _make_adata(n=31, n_genes=4)
    adata.obs["cluster"] = pd.Categorical(adata.obs["cluster"])
    adata.uns["cluster_colors"] = np.asarray(["#ff0000", "#0000ff"])
    original_spatial = adata.obsm["spatial"].copy()
    alternative = np.column_stack([original_spatial + 20, adata.obs["Z"]])
    path = write_point_cloud_zarr(
        adata,
        tmp_path / "new.zarr",
        cluster_key="cluster",
        alignments={"centroids": alternative},
        obs_columns=["cluster"],
        chunk_rows=8,
        expression_chunk_size=16,
    )
    result = ad.read_zarr(path)
    assert result.X.format == "csc"
    np.testing.assert_array_equal(result.X.toarray(), adata.X.toarray())
    assert result.obs_names.tolist() == adata.obs_names.tolist()
    assert result.var_names.tolist() == adata.var_names.tolist()
    assert list(result.obs.columns) == ["cluster"]
    assert result.obsm["spatial"].dtype == np.int32
    np.testing.assert_allclose(result.obsm["spatial"][:, :2], original_spatial, atol=0.5)
    np.testing.assert_array_equal(
        result.obsm["spatial_centroids"], np.rint(alternative).astype(np.int32)
    )
    np.testing.assert_array_equal(result.uns["cluster_colors"], adata.uns["cluster_colors"])
    assert result.uns["cell_cloud"]["coordinate_resolution"] == 1.0
    assert (path / ".zmetadata").exists()
    group = zarr.open_group(path)
    assert group["obs/_index"].compressors[0].cname == "zstd"
    assert group["obs/_index"].compressors[0].shuffle == 0
    assert group["obs/cluster/codes"].compressors[0].cname == "zstd"
    assert group["obs/cluster/categories"].compressors[0].cname == "zstd"
    assert group["X/data"].chunks == (16,)
    assert group["obsm/spatial"].chunks == (8, 3)
    np.testing.assert_array_equal(adata.obsm["spatial"], original_spatial)
    with pytest.raises(FileExistsError):
        write_point_cloud_zarr(adata, path)
    assert ad.read_zarr(path).obs_names.tolist() == adata.obs_names.tolist()


def test_zarr_export_rejects_bad_alignment_without_output(tmp_path):
    from celldega.pre import write_point_cloud_zarr

    adata = _make_adata(n_genes=2)
    target = tmp_path / "new.zarr"
    with pytest.raises(ValueError, match="one coordinate per cell"):
        write_point_cloud_zarr(adata, target, alignments={"wrong": np.zeros((2, 3))})
    assert not target.exists()


def test_compact_metadata_uses_explicit_cluster_labels_and_matching_palette(tmp_path):
    adata = _make_adata(n_genes=3)
    labels = ["20", "1", "7"]
    adata.obs["cluster"] = pd.Categorical(np.resize(labels, adata.n_obs), categories=labels)
    adata.uns["cluster_colors"] = np.asarray(["#200000", "#010000", "#070000"])
    adata.var_names.name = "custom_gene_name"
    write_point_cloud_dataset(adata, tmp_path, cluster_key="cluster", use_int_index=True)
    meta_path = tmp_path / "cell_clusters" / "meta_cluster.parquet"
    meta = pd.read_parquet(meta_path)
    assert dict(meta["color"]) == dict(zip(labels, adata.uns["cluster_colors"], strict=True))
    assert "__index_level_0__" in pq.read_table(meta_path).column_names
    assert "__index_level_0__" in pq.read_table(tmp_path / "meta_gene.parquet").column_names


def test_zarr_metadata_compression_preserves_unicode_ids_and_categories(tmp_path):
    import anndata as ad
    import zarr

    from celldega.pre import write_point_cloud_zarr

    adata = _make_adata(n=3, n_genes=2)
    adata.obs_names = ["细胞_1_é", "细胞_2_ß", "细胞_3_λ"]
    adata.obs["cluster"] = pd.Categorical(["皮层", None, "深部"], categories=["深部", "皮层"])
    path = write_point_cloud_zarr(adata, tmp_path / "unicode.zarr", cluster_key="cluster")
    result = ad.read_zarr(path)
    assert result.obs_names.tolist() == adata.obs_names.tolist()
    assert result.obs["cluster"].equals(adata.obs["cluster"])
    group = zarr.open_group(path)
    assert group["obsm/spatial"].chunks == (3, 3)
    assert group["obs/_index"].compressors[0].cname == "zstd"
    assert group["obs/_index"].compressors[0].shuffle == 0
