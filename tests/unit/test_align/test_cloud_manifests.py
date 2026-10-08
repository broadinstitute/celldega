"""The point-cloud / neighborhood-cloud writers emit the new manifest filenames
(cell_cloud.json / neighborhood_cloud.json) alongside the legacy
landscape_parameters.json, with identical content, during the transition."""

import json

from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.align import write_alignment_point_cloud
from celldega.pre.nbhd_cloud import _write_nbhd_cloud_landscape_parameters


def _make_adata(n: int = 30, seed: int = 0) -> AnnData:
    rng = np.random.default_rng(seed)
    obs = pd.DataFrame(
        {"cluster": rng.choice(list("AB"), n)},
        index=[f"cell{i}-0" for i in range(n)],
    )
    obs["Z"] = (np.arange(n) % 3).astype(float) * 100.0
    adata = AnnData(X=np.zeros((n, 1), dtype=float), obs=obs)
    adata.obsm["spatial"] = rng.normal(size=(n, 2)) * 50.0
    return adata


# --- point-cloud (celldega.align.write_alignment_point_cloud) ---------------


def test_point_cloud_create_writes_both_manifests(tmp_path) -> None:
    write_alignment_point_cloud(_make_adata(), tmp_path, "procrustes", cluster_key="cluster")

    legacy = json.loads((tmp_path / "landscape_parameters.json").read_text())
    new = json.loads((tmp_path / "cell_cloud.json").read_text())

    assert new == legacy
    assert new["technology"] == "point-cloud"
    assert new["alignments"] == ["procrustes"]


def test_point_cloud_append_keeps_manifests_in_sync(tmp_path) -> None:
    adata = _make_adata()
    write_alignment_point_cloud(adata, tmp_path, "a1", cluster_key="cluster")
    write_alignment_point_cloud(adata, tmp_path, "a2")  # append mode

    legacy = json.loads((tmp_path / "landscape_parameters.json").read_text())
    new = json.loads((tmp_path / "cell_cloud.json").read_text())

    assert legacy == new
    assert new["alignments"] == ["a1", "a2"]


# --- neighborhood-cloud (celldega.pre.nbhd_cloud) ---------------------------


def test_nbhd_cloud_writes_both_manifests(tmp_path) -> None:
    _write_nbhd_cloud_landscape_parameters(tmp_path)

    legacy = json.loads((tmp_path / "landscape_parameters.json").read_text())
    new = json.loads((tmp_path / "neighborhood_cloud.json").read_text())

    assert new == legacy
    assert new["technology"] == "neighborhood-cloud"
