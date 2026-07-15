from anndata import AnnData
import numpy as np
import pandas as pd
import pytest

from celldega.align import calc_landmarks


_CENTERS = {"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (0.0, 10.0)}


def _make_adata(rng, counts):
    labels, coords = [], []
    for label, center in _CENTERS.items():
        n = counts[label]
        pts = np.asarray(center) + rng.normal(scale=1e-6, size=(n, 2))
        coords.append(pts)
        labels += [label] * n
    coords = np.concatenate(coords, axis=0)
    obs = pd.DataFrame({"cluster": labels})
    var = pd.DataFrame(index=["g0", "g1"])
    adata = AnnData(X=rng.poisson(1.0, size=(coords.shape[0], 2)).astype(float), obs=obs, var=var)
    adata.obsm["spatial"] = coords
    return adata


def test_calc_landmarks_shape_and_values():
    rng = np.random.default_rng(0)
    counts = {"a": 5, "b": 8, "c": 3}
    adata = _make_adata(rng, counts)

    landmarks = calc_landmarks(adata, "cluster")

    assert set(landmarks["label"]) == set(_CENTERS)
    assert set(landmarks.columns) >= {"label", "x", "y", "count"}
    for label, center in _CENTERS.items():
        row = landmarks.loc[landmarks["label"] == label].iloc[0]
        assert row["count"] == counts[label]
        assert np.allclose([row["x"], row["y"]], center, atol=1e-3)


def test_calc_landmarks_requires_cluster_key():
    rng = np.random.default_rng(1)
    adata = _make_adata(rng, {"a": 2, "b": 2, "c": 2})

    with pytest.raises(ValueError, match="not a column"):
        calc_landmarks(adata, "not_a_column")


def test_calc_landmarks_requires_spatial():
    rng = np.random.default_rng(2)
    adata = _make_adata(rng, {"a": 2, "b": 2, "c": 2})
    del adata.obsm["spatial"]

    with pytest.raises(ValueError, match="spatial"):
        calc_landmarks(adata, "cluster")
