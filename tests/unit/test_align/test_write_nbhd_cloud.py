"""Tests for celldega.align.write_nbhd_cloud (synthetic data only)."""

import json

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from celldega.align import write_nbhd_cloud


def _synthetic_dataset(seed=0, n_slices=2, n_clusters=2, n_per_cluster=30, n_genes=2):
    """Same shape as tests/unit/test_pre/test_nbhd_cloud.py's fixture, since
    write_nbhd_cloud is a thin orchestrator over the functions tested there."""
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
    # Half of each cluster's cells express every gene at a high value, the
    # other half at zero -- a clean, deterministic "expressing" population.
    X = np.zeros((n_cells, n_genes))
    X[::2, :] = 5.0

    adata = ad.AnnData(X=X, obs=obs, var=pd.DataFrame(index=gene_names))
    adata.obsm["spatial"] = np.vstack(xy)
    return adata


def test_write_nbhd_cloud_writes_cluster_shapes_only_by_default(tmp_path):
    adata = _synthetic_dataset()

    result = write_nbhd_cloud(adata, tmp_path, cluster_attr="cluster", z_attr="z")

    assert result == tmp_path
    assert (tmp_path / "nbhd_cloud" / "meta_slice.parquet").exists()
    assert (tmp_path / "nbhd_cloud" / "meta_neighborhood.parquet").exists()
    assert (tmp_path / "cell_clusters" / "meta_cluster.parquet").exists()

    shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_slice"
    assert {p.name for p in shapes_dir.glob("*.parquet")} == {
        "slice_s0.parquet",
        "slice_s1.parquet",
    }

    cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_cluster"
    assert {p.name for p in cells_dir.glob("*.parquet")} == {
        "cluster_0.parquet",
        "cluster_1.parquet",
    }

    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["technology"] == "neighborhood-cloud"

    # Gene-nbhds are opt-in -- none of this should exist without
    # compute_gene_nbhds=True.
    assert not (tmp_path / "nbhd_cloud" / "shapes" / "by_gene").exists()
    assert not (tmp_path / "nbhd_cloud" / "cells" / "by_gene").exists()


def test_write_nbhd_cloud_max_cell_scatter_caps_cluster_cells(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud(adata, tmp_path, cluster_attr="cluster", z_attr="z", max_cell_scatter=10)

    cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_cluster"
    for cluster_id in ("0", "1"):
        df_cluster = pd.read_parquet(cells_dir / f"cluster_{cluster_id}.parquet")
        assert len(df_cluster) == 10


def test_write_nbhd_cloud_max_cell_scatter_none_writes_every_cell(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud(adata, tmp_path, cluster_attr="cluster", z_attr="z", max_cell_scatter=None)

    df_cluster_0 = pd.read_parquet(
        tmp_path / "nbhd_cloud" / "cells" / "by_cluster" / "cluster_0.parquet"
    )
    assert len(df_cluster_0) == 60  # both slices, 30 cells each, uncapped


def test_write_nbhd_cloud_computes_gene_nbhds_when_requested(tmp_path):
    adata = _synthetic_dataset()

    write_nbhd_cloud(
        adata,
        tmp_path,
        cluster_attr="cluster",
        z_attr="z",
        compute_gene_nbhds=True,
        gene_list=["Gene0", "Gene1"],
        gene_min_cells=4,
    )

    gene_shapes_dir = tmp_path / "nbhd_cloud" / "shapes" / "by_gene"
    assert {p.name for p in gene_shapes_dir.glob("*.parquet")} == {
        "Gene0.parquet",
        "Gene1.parquet",
    }
    assert (gene_shapes_dir / "available_genes.json").exists()

    gene_cells_dir = tmp_path / "nbhd_cloud" / "cells" / "by_gene"
    assert {p.name for p in gene_cells_dir.glob("*.parquet")} == {
        "Gene0.parquet",
        "Gene1.parquet",
    }


def test_write_nbhd_cloud_requires_gene_list_when_gene_nbhds_requested(tmp_path):
    adata = _synthetic_dataset()

    with pytest.raises(ValueError, match="requires an explicit gene_list"):
        write_nbhd_cloud(adata, tmp_path, cluster_attr="cluster", compute_gene_nbhds=True)


def test_write_nbhd_cloud_gene_z_jitter_defaults_to_shape_z_jitter(tmp_path):
    """gene_z_jitter isn't passed -- it should fall back to z_jitter rather
    than write_gene_shapes_streaming's own 0.1 default, so cluster and gene
    shapes land on a consistent Z scale unless the caller deliberately
    diverges."""
    adata = _synthetic_dataset(n_slices=1, n_genes=2)

    write_nbhd_cloud(
        adata,
        tmp_path,
        cluster_attr="cluster",
        z_attr="z",
        z_jitter=0.25,
        compute_gene_nbhds=True,
        gene_list=["Gene0", "Gene1"],
        gene_min_cells=4,
    )

    df_gene1 = pd.read_parquet(tmp_path / "nbhd_cloud" / "shapes" / "by_gene" / "Gene1.parquet")
    geometry = json.loads(df_gene1["geometry_geojson"].iloc[0])
    z_values = {coord[2] for poly in geometry["coordinates"] for ring in poly for coord in ring}

    # Gene1 is index 1 in gene_list -- its Z offset is exactly 1 * z_jitter
    # (see _gene_z_offset). The only slice here sits at z=0.0, so this shape's
    # own Z is purely that offset. It must reflect the *shape* z_jitter
    # (0.25) passed to write_nbhd_cloud, not write_gene_shapes_streaming's
    # own default (0.1), since gene_z_jitter wasn't set explicitly.
    assert len(z_values) == 1
    assert z_values.pop() == pytest.approx(0.25)


def test_write_nbhd_cloud_works_on_a_plain_anndata_without_point_cloud_files(tmp_path):
    """The whole point of write_nbhd_cloud (and write_gene_shapes_streaming
    under the hood) is that it needs nothing beyond the AnnData itself -- no
    pre-existing point-cloud DegaFiles / cbg/ directory."""
    adata = _synthetic_dataset(n_genes=1)
    assert "cbg" not in dir(adata)  # sanity: nothing point-cloud-specific involved

    write_nbhd_cloud(
        adata,
        tmp_path,
        cluster_attr="cluster",
        z_attr="z",
        compute_gene_nbhds=True,
        gene_list=["Gene0"],
        gene_min_cells=4,
    )

    assert (tmp_path / "nbhd_cloud" / "shapes" / "by_gene" / "Gene0.parquet").exists()


def test_write_nbhd_cloud_reports_missing_obs_columns_clearly(tmp_path):
    adata = ad.AnnData(
        X=np.zeros((5, 1)),
        obs=pd.DataFrame(index=[f"c{i}" for i in range(5)]),
    )
    adata.obsm["spatial"] = np.random.default_rng(0).random((5, 2))

    with pytest.raises(ValueError, match=r"cluster_attr='cluster'.*slice_attr='slice_id'"):
        write_nbhd_cloud(adata, tmp_path)


def test_write_nbhd_cloud_reports_missing_z_attr_clearly(tmp_path):
    adata = ad.AnnData(
        X=np.zeros((5, 1)),
        obs=pd.DataFrame(
            {"cluster": ["a"] * 5, "slice_id": ["s0"] * 5},
            index=[f"c{i}" for i in range(5)],
        ),
    )
    adata.obsm["spatial"] = np.random.default_rng(0).random((5, 2))

    with pytest.raises(ValueError, match=r"z_attr='Z'"):
        write_nbhd_cloud(adata, tmp_path, z_attr="Z")


def test_write_nbhd_cloud_reports_missing_spatial_clearly(tmp_path):
    adata = ad.AnnData(
        X=np.zeros((5, 1)),
        obs=pd.DataFrame(
            {"cluster": ["a"] * 5, "slice_id": ["s0"] * 5},
            index=[f"c{i}" for i in range(5)],
        ),
    )

    with pytest.raises(ValueError, match=r"obsm\['spatial'\] is required"):
        write_nbhd_cloud(adata, tmp_path)


def test_write_nbhd_cloud_reports_progress_by_default(tmp_path, capsys):
    """progress_every defaults to 1 (every slice) here -- unlike
    alpha_shape_cell_clusters_by_slice's own off-by-default, since this is
    the one-call, large-dataset entry point where feedback matters most."""
    adata = _synthetic_dataset(n_slices=2)

    write_nbhd_cloud(adata, tmp_path, cluster_attr="cluster", z_attr="z")

    out = capsys.readouterr().out
    assert "slice 1/2" in out
    assert "slice 2/2" in out


def test_write_nbhd_cloud_progress_every_zero_disables_reporting(tmp_path, capsys):
    adata = _synthetic_dataset(n_slices=2)

    write_nbhd_cloud(adata, tmp_path, cluster_attr="cluster", z_attr="z", progress_every=0)

    out = capsys.readouterr().out
    assert "alpha shapes:" not in out
