"""Tests for the CellCloud / NeighborhoodCloud widgets and _SpatialWidget base."""

import numpy as np
import pandas as pd
import pytest


try:
    from anndata import AnnData

    from celldega.viz import CellCloud, NeighborhoodCloud
    from celldega.viz.cloud import _SpatialWidget
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _make_adata(n: int = 40, seed: int = 0) -> "AnnData":
    rng = np.random.default_rng(seed)
    obs = pd.DataFrame(
        {"leiden": pd.Categorical(rng.choice(["0", "1", "2"], n))},
        index=[f"cell_{i}" for i in range(n)],
    )
    adata = AnnData(X=np.zeros((n, 1), dtype=float), obs=obs)
    adata.obsm["spatial"] = rng.normal(size=(n, 2)) * 50.0
    adata.obs["Z"] = (np.arange(n) % 5).astype(float)
    adata.obsm["X_umap"] = rng.normal(size=(n, 2))
    return adata


# --- identity / inheritance -------------------------------------------------


def test_both_inherit_spatial_base() -> None:
    assert issubclass(CellCloud, _SpatialWidget)
    assert issubclass(NeighborhoodCloud, _SpatialWidget)


def test_cell_cloud_component_technology_manifest() -> None:
    cc = CellCloud(base_url="https://example.com/data")
    assert cc.component == "CellCloud"
    assert cc.technology == "point-cloud"
    assert cc.manifest_name == "cell_cloud.json"


def test_neighborhood_cloud_component_technology_manifest() -> None:
    nc = NeighborhoodCloud(base_url="https://example.com/data")
    assert nc.component == "NeighborhoodCloud"
    assert nc.technology == "neighborhood-cloud"
    assert nc.manifest_name == "neighborhood_cloud.json"


# --- shared base behavior (base_url normalization, adata plumbing) ----------


def test_single_base_url_normalized() -> None:
    cc = CellCloud(base_url="https://example.com/data")
    assert cc.base_url == "https://example.com/data"
    assert cc.base_urls[0]["url"] == "https://example.com/data"


def test_base_urls_list_with_dataset_names() -> None:
    cc = CellCloud(base_urls=["u1", "u2"], dataset_names=["A", "B"])
    assert cc.base_url == "u1"
    assert [d["url"] for d in cc.base_urls] == ["u1", "u2"]
    assert cc.base_urls[0]["short_label"] == "A"


def test_adata_populates_meta_parquets() -> None:
    cc = CellCloud(base_url="https://example.com/data", adata=_make_adata())
    assert len(cc.meta_cell_parquet) > 0
    assert len(cc.meta_cluster_parquet) > 0
    assert len(cc.umap_parquet) > 0
    assert cc.cluster_attr == "leiden"
    assert "leiden" in cc.cell_attr


def test_highlight_cells_sets_selection() -> None:
    cc = CellCloud(base_url="https://example.com/data")
    cc.highlight_cells(["a", "b"])
    assert cc.selected_cells == ["a", "b"]


# --- CellCloud centroids (comm vs sidecar) ----------------------------------


def test_alignment_trait() -> None:
    cc = CellCloud(base_url="https://example.com/data", alignment="procrustes")
    assert cc.alignment == "procrustes"


def test_centroids_comm_path_for_remote_base_url() -> None:
    # A non-local base_url syncs centroids through the widget comm channel.
    cc = CellCloud(base_url="https://example.com/data", adata=_make_adata())
    assert len(cc.centroids_parquet) > 0
    assert cc.centroids_url == ""


def test_centroids_sidecar_for_local_base_url(tmp_path, monkeypatch) -> None:
    # A local dev-server base_url writes a sidecar parquet and syncs only its URL.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    cc = CellCloud(base_url="http://localhost:8080/data", adata=_make_adata())
    assert cc.centroids_url.startswith("http://localhost:8080/data/.celldega_centroids_")
    sidecars = list((tmp_path / "data").glob(".celldega_centroids_*.parquet"))
    assert len(sidecars) == 1
    assert not hasattr(cc, "centroids_parquet")


def test_use_adata_3d_centroids_false_skips_centroids() -> None:
    cc = CellCloud(
        base_url="https://example.com/data",
        adata=_make_adata(),
        use_adata_3d_centroids=False,
    )
    assert not hasattr(cc, "centroids_parquet")
    assert cc.centroids_url == ""


def test_neighborhood_cloud_has_no_centroid_traits() -> None:
    nc = NeighborhoodCloud(base_url="https://example.com/data", adata=_make_adata())
    assert not hasattr(nc, "centroids_parquet")
    assert not hasattr(nc, "centroids_url")


def test_z_key_without_adata_does_not_leak_into_traits() -> None:
    # z_key is a construction-time param, not a trait; passing it without an
    # adata must not raise (it would if it reached super().__init__).
    cc = CellCloud(base_url="https://example.com/data", z_key="depth")
    assert not hasattr(cc, "z_key")


def test_explicit_centroids_parquet_suppresses_adata_extraction() -> None:
    sentinel = b"explicit-centroid-bytes"
    cc = CellCloud(
        base_url="https://example.com/data",
        adata=_make_adata(),
        centroids_parquet=sentinel,
    )
    assert bytes(cc.centroids_parquet) == sentinel


def test_explicit_centroids_url_suppresses_adata_extraction() -> None:
    cc = CellCloud(
        base_url="https://example.com/data",
        adata=_make_adata(),
        centroids_url="https://example.com/data/my_centroids.parquet",
    )
    assert cc.centroids_url == "https://example.com/data/my_centroids.parquet"
    assert not hasattr(cc, "centroids_parquet")
