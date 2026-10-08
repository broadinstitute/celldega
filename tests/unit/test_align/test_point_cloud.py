"""Tests for celldega.align.write_alignment_point_cloud (synthetic data only)."""

import json

from anndata import AnnData
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from scipy.sparse import csr_matrix

from celldega.align import write_alignment_point_cloud


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
    path = write_alignment_point_cloud(adata, tmp_path, "procrustes", cluster_key="cluster")

    assert path.name == "cell_metadata_procrustes.parquet"
    assert path.exists()
    # create mode also writes a base cell_metadata.parquet so an alignment-less
    # Landscape still works
    assert (tmp_path / "cell_metadata.parquet").exists()
    assert (tmp_path / "cell_clusters" / "cluster.parquet").exists()
    assert (tmp_path / "cell_clusters" / "meta_cluster.parquet").exists()

    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["technology"] == "point-cloud"
    assert params["alignments"] == ["procrustes"]


def test_geometry_is_xyz_from_spatial_and_z(tmp_path):
    adata = _make_adata()
    path = write_alignment_point_cloud(adata, tmp_path, "a1")

    names, geometry = _read_geometry(path)
    assert names == list(adata.obs_names)
    assert all(len(g) == 3 for g in geometry)

    xy = np.asarray([g[:2] for g in geometry])
    z = np.asarray([g[2] for g in geometry])
    np.testing.assert_allclose(xy, adata.obsm["spatial"][:, :2], rtol=1e-5)
    np.testing.assert_allclose(z, adata.obs["Z"].to_numpy(), rtol=1e-5)


def test_z_falls_back_to_third_spatial_column(tmp_path):
    adata = _make_adata(with_z=False, spatial_dim=3)
    _, geometry = _read_geometry(write_alignment_point_cloud(adata, tmp_path, "a1"))
    z = np.asarray([g[2] for g in geometry])
    np.testing.assert_allclose(z, adata.obsm["spatial"][:, 2], rtol=1e-5)


def test_z_defaults_to_zero_when_absent(tmp_path):
    adata = _make_adata(with_z=False, spatial_dim=2)
    _, geometry = _read_geometry(write_alignment_point_cloud(adata, tmp_path, "a1"))
    z = np.asarray([g[2] for g in geometry])
    np.testing.assert_array_equal(z, np.zeros(adata.n_obs))


def test_append_mode_registers_without_clobbering(tmp_path):
    first = _make_adata(seed=0)
    write_alignment_point_cloud(first, tmp_path, "procrustes", cluster_key="cluster")
    base_before = (tmp_path / "cell_metadata.parquet").read_bytes()

    # append a second variant with different positions
    second = _make_adata(seed=1)
    path2 = write_alignment_point_cloud(second, tmp_path, "tps")

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
    write_alignment_point_cloud(adata, tmp_path, "a1")
    write_alignment_point_cloud(adata, tmp_path, "a1", overwrite=True)
    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["alignments"] == ["a1"]


def test_overwrite_guard(tmp_path):
    adata = _make_adata()
    write_alignment_point_cloud(adata, tmp_path, "a1")
    with pytest.raises(FileExistsError):
        write_alignment_point_cloud(adata, tmp_path, "a1")
    # overwrite=True is allowed
    write_alignment_point_cloud(adata, tmp_path, "a1", overwrite=True)


def test_append_preserves_existing_params(tmp_path):
    adata = _make_adata()
    write_alignment_point_cloud(adata, tmp_path, "a1")
    # simulate an existing DegaFiles with extra params + prior alignments
    params_path = tmp_path / "landscape_parameters.json"
    params = json.loads(params_path.read_text())
    params["use_int_index"] = False
    params["custom_key"] = {"keep": "me"}
    params_path.write_text(json.dumps(params))

    write_alignment_point_cloud(adata, tmp_path, "a2")
    out = json.loads(params_path.read_text())
    assert out["custom_key"] == {"keep": "me"}
    assert out["alignments"] == ["a1", "a2"]


@pytest.mark.parametrize("bad", ["default", "", "a/b", ".hidden", "-lead", "a b"])
def test_invalid_alignment_names_rejected(tmp_path, bad):
    adata = _make_adata()
    with pytest.raises(ValueError):
        write_alignment_point_cloud(adata, tmp_path, bad)


def test_requires_spatial(tmp_path):
    adata = AnnData(X=np.zeros((3, 1)), obs=pd.DataFrame(index=["a", "b", "c"]))
    with pytest.raises(ValueError):
        write_alignment_point_cloud(adata, tmp_path, "a1")


@pytest.mark.parametrize("sparse", [True, False])
def test_create_mode_writes_gene_expression_when_available(tmp_path, sparse):
    adata = _make_adata(n_genes=4, sparse=sparse)
    write_alignment_point_cloud(adata, tmp_path, "a1", cluster_key="cluster")

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
    write_alignment_point_cloud(adata, tmp_path, "a1", cluster_key="cluster")
    assert not (tmp_path / "cbg").exists()
    assert not (tmp_path / "meta_gene.parquet").exists()


def test_write_genes_false_disables_export(tmp_path):
    adata = _make_adata(n_genes=4)
    write_alignment_point_cloud(adata, tmp_path, "a1", write_genes=False)
    assert not (tmp_path / "cbg").exists()
    assert not (tmp_path / "meta_gene.parquet").exists()


def test_write_genes_true_without_expression_raises(tmp_path):
    adata = _make_adata(n_genes=0)
    with pytest.raises(ValueError):
        write_alignment_point_cloud(adata, tmp_path, "a1", write_genes=True)


def test_append_mode_leaves_gene_writing_to_existing_data(tmp_path):
    # create with genes, then append a variant with genes=True: append must not
    # touch gene data (write_genes only applies to create mode)
    adata = _make_adata(n_genes=3)
    write_alignment_point_cloud(adata, tmp_path, "a1")
    meta_before = (tmp_path / "meta_gene.parquet").read_bytes()
    write_alignment_point_cloud(adata, tmp_path, "a2", write_genes=True)
    assert (tmp_path / "meta_gene.parquet").read_bytes() == meta_before
