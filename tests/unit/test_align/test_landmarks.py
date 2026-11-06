import anndata as ad
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

    assert set(landmarks["label"]) == {f"C-{label}" for label in _CENTERS}
    assert set(landmarks.columns) >= {"label", "x", "y", "count", "source"}
    assert set(landmarks["source"]) == {"automated"}
    for label, center in _CENTERS.items():
        row = landmarks.loc[landmarks["label"] == f"C-{label}"].iloc[0]
        assert row["count"] == counts[label]
        assert np.allclose([row["x"], row["y"]], center, atol=1e-3)


def test_calc_landmarks_label_prefix_disabled():
    rng = np.random.default_rng(7)
    adata = _make_adata(rng, {"a": 5, "b": 8, "c": 3})

    landmarks = calc_landmarks(adata, "cluster", label_prefix="")

    assert set(landmarks["label"]) == set(_CENTERS)


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


def test_calc_landmarks_list_mode_tags_slice_column():
    rng = np.random.default_rng(3)
    adata0 = _make_adata(rng, {"a": 5, "b": 8, "c": 3})
    adata1 = _make_adata(rng, {"a": 4, "b": 6, "c": 2})

    landmarks = calc_landmarks([adata0, adata1], "cluster")

    assert set(landmarks.columns) == {"label", "x", "y", "count", "source", "slice"}
    assert sorted(landmarks["slice"].unique().tolist()) == [0, 1]
    assert len(landmarks) == 2 * len(_CENTERS)


def test_calc_landmarks_combined_anndata_mode_matches_list_mode():
    rng = np.random.default_rng(4)
    adata0 = _make_adata(rng, {"a": 5, "b": 8, "c": 3})
    adata1 = _make_adata(rng, {"a": 4, "b": 6, "c": 2})

    from_list = calc_landmarks([adata0, adata1], "cluster")

    adata0 = adata0.copy()
    adata1 = adata1.copy()
    adata0.obs["batch"] = "x"
    adata1.obs["batch"] = "y"
    combined = ad.concat([adata0, adata1])
    from_combined = calc_landmarks(combined, "cluster", slice_attr="batch")

    assert set(from_combined.columns) == {"label", "x", "y", "count", "source", "batch"}
    assert sorted(from_combined["batch"].unique().tolist()) == ["x", "y"]
    for label in _CENTERS:
        label = f"C-{label}"
        list_row = from_list.loc[(from_list["slice"] == 0) & (from_list["label"] == label)].iloc[0]
        combined_row = from_combined.loc[
            (from_combined["batch"] == "x") & (from_combined["label"] == label)
        ].iloc[0]
        assert np.allclose([list_row["x"], list_row["y"]], [combined_row["x"], combined_row["y"]])


def test_calc_landmarks_excludes_nan_cluster_labels():
    rng = np.random.default_rng(6)
    adata = _make_adata(rng, {"a": 5, "b": 8, "c": 3})
    labels = adata.obs["cluster"].astype(object)
    labels.iloc[:4] = np.nan  # unclustered/QC-filtered cells
    adata.obs["cluster"] = labels

    landmarks = calc_landmarks(adata, "cluster")

    assert "C-nan" not in set(landmarks["label"])
    assert set(landmarks["label"]) == {f"C-{label}" for label in _CENTERS}
    row_a = landmarks.loc[landmarks["label"] == "C-a"].iloc[0]
    assert row_a["count"] == 1  # 5 "a" cells, 4 of which were nulled out above


def test_calc_landmarks_single_anndata_missing_slice_attr_column_raises():
    rng = np.random.default_rng(5)
    adata = _make_adata(rng, {"a": 2, "b": 2, "c": 2})  # has no "batch" column

    with pytest.raises(ValueError, match="not a column"):
        calc_landmarks(adata, "cluster", slice_attr="batch")
