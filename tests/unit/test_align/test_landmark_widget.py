"""Tests for the Landmark widget."""

from anndata import AnnData
import numpy as np
import pandas as pd
import pytest


try:
    from celldega.align import Landmark
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def _make_slice(rng, n=10, cluster=False):
    coords = rng.normal(size=(n, 2))
    obs = pd.DataFrame(index=[f"cell_{i}" for i in range(n)])
    if cluster:
        obs["cluster"] = rng.choice(["a", "b"], size=n)
    var = pd.DataFrame(index=["g0", "g1"])
    adata = AnnData(X=rng.poisson(1.0, size=(n, 2)).astype(float), obs=obs, var=var)
    adata.obsm["spatial"] = coords
    return adata


def _make_two_slices(rng):
    return [_make_slice(rng), _make_slice(rng)]


def _pair_feature(label, x, y):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [x, y]},
        "properties": {"label": label},
    }


def test_landmark_requires_adatas():
    with pytest.raises(ValueError, match="adatas"):
        Landmark()


def test_landmark_rejects_landscapes():
    rng = np.random.default_rng(0)
    with pytest.raises(NotImplementedError):
        Landmark(adatas=_make_two_slices(rng), landscapes=("a", "b"))


def test_landmark_requires_at_least_two_slices():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="at least 2"):
        Landmark(adatas=[_make_slice(rng)])


def test_landmark_defaults_from_list_of_two():
    rng = np.random.default_rng(1)
    lm = Landmark(adatas=_make_two_slices(rng))

    assert lm.component == "Landmark"
    assert lm.slice_ids == ["0", "1"]
    assert lm.slice_id_a == "0"
    assert lm.slice_id_b == "1"
    assert len(lm.centroids_parquet_a) > 0
    assert len(lm.centroids_parquet_b) > 0
    assert lm.landmarks is not None
    assert list(lm.landmarks.columns) == ["label", "x", "y", "slice"]
    assert lm.landmarks.empty


def test_landmark_picks_initial_pair_from_larger_pool():
    rng = np.random.default_rng(2)
    adatas = [_make_slice(rng) for _ in range(4)]
    lm = Landmark(adatas=adatas, slices=(1, 3))

    assert lm.slice_ids == ["0", "1", "2", "3"]
    assert lm.slice_id_a == "1"
    assert lm.slice_id_b == "3"


def test_landmark_slices_param_validates_length_and_membership():
    rng = np.random.default_rng(3)
    adatas = [_make_slice(rng) for _ in range(3)]

    with pytest.raises(ValueError, match="exactly 2"):
        Landmark(adatas=adatas, slices=(0, 1, 2))

    with pytest.raises(ValueError, match="not found"):
        Landmark(adatas=adatas, slices=(0, 99))


def test_landmark_cluster_key_colors_centroids():
    rng = np.random.default_rng(4)
    adatas = [_make_slice(rng, cluster=True), _make_slice(rng, cluster=True)]
    lm = Landmark(adatas=adatas, cluster_key="cluster")
    assert len(lm.centroids_parquet_a) > 0


def test_marking_a_pair_updates_landmarks_table():
    rng = np.random.default_rng(5)
    lm = Landmark(adatas=_make_two_slices(rng))

    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 2.0)],
    }
    lm.landmark_geojson_b = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 3.0, 4.0)],
    }

    landmarks = lm.landmarks
    assert len(landmarks) == 2
    assert set(landmarks["label"]) == {"1"}
    assert set(landmarks["slice"]) == {0, 1}
    row_a = landmarks.loc[landmarks["slice"] == 0].iloc[0]
    assert (row_a["x"], row_a["y"]) == (1.0, 2.0)
    assert lm.next_landmark_label == 2


def test_swapping_side_preserves_other_slices_landmarks():
    rng = np.random.default_rng(6)
    adatas = [_make_slice(rng) for _ in range(3)]
    lm = Landmark(adatas=adatas)  # initial pair 0, 1

    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0)],
    }
    lm.landmark_geojson_b = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 2.0, 2.0)],
    }

    # Swap side a to slice 2 - must not lose slice 0/1 landmarks.
    lm.slice_id_a = "2"
    assert set(lm.landmarks["slice"]) == {0, 1}
    assert lm.landmark_geojson_a == {"type": "FeatureCollection", "features": []}

    # Mark a landmark on the newly-shown slice 2.
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("2", 5.0, 5.0)],
    }
    assert set(lm.landmarks["slice"]) == {0, 1, 2}

    # Swap side a back to slice 0 - its landmark should reappear.
    lm.slice_id_a = "0"
    features = lm.landmark_geojson_a["features"]
    assert len(features) == 1
    assert features[0]["properties"]["label"] == "1"
    assert features[0]["geometry"]["coordinates"] == [1.0, 1.0]


def test_calc_alignment_transform_requires_landmarks():
    rng = np.random.default_rng(7)
    lm = Landmark(adatas=_make_two_slices(rng))
    with pytest.raises(ValueError, match="no landmarks"):
        lm.calc_alignment_transform()


def test_calc_alignment_transform_forwards_to_module_function():
    rng = np.random.default_rng(8)
    lm = Landmark(adatas=_make_two_slices(rng))

    pairs = {"1": (0.0, 0.0, 10.0, 0.0), "2": (1.0, 0.0, 11.0, 0.0)}
    for label, (xa, ya, xb, yb) in pairs.items():
        lm.landmark_geojson_a = {
            "type": "FeatureCollection",
            "features": [*lm.landmark_geojson_a["features"], _pair_feature(label, xa, ya)],
        }
        lm.landmark_geojson_b = {
            "type": "FeatureCollection",
            "features": [*lm.landmark_geojson_b["features"], _pair_feature(label, xb, yb)],
        }

    transform = lm.calc_alignment_transform(min_shared_landmarks=2)
    assert set(transform.slice_ids) == {0, 1}
