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


def test_landmark_accepts_initial_landmarks_table():
    rng = np.random.default_rng(23)
    adatas = _make_two_slices(rng)  # initial pair 0, 1
    initial = pd.DataFrame({"label": ["3", "3"], "x": [1.0, 2.0], "y": [1.5, 2.5], "slice": [0, 1]})

    lm = Landmark(adatas=adatas, landmarks=initial)

    # Visible immediately on both initial sides, without needing to swap
    # away and back first.
    assert lm.landmark_geojson_a["features"][0]["properties"]["label"] == "3"
    assert lm.landmark_geojson_b["features"][0]["properties"]["label"] == "3"
    assert lm.landmark_coverage == {"3": 2}
    assert lm.landmark_slices == {"3": ["0", "1"]}
    # Auto-numbering continues past the highest pre-loaded numeric label.
    assert lm.next_landmark_label == 4


def test_landmark_initial_landmarks_covers_slice_not_currently_shown():
    rng = np.random.default_rng(24)
    adatas = [_make_slice(rng) for _ in range(3)]  # initial pair 0, 1
    initial = pd.DataFrame({"label": ["5"], "x": [1.0], "y": [1.0], "slice": [2]})

    lm = Landmark(adatas=adatas, landmarks=initial)

    assert lm.landmark_geojson_a == {"type": "FeatureCollection", "features": []}
    assert lm.landmark_geojson_b == {"type": "FeatureCollection", "features": []}
    assert lm.landmark_coverage == {"5": 1}
    assert lm.landmark_slices == {"5": ["2"]}


def test_landmark_initial_landmarks_can_be_appended_to():
    rng = np.random.default_rng(25)
    adatas = _make_two_slices(rng)
    initial = pd.DataFrame({"label": ["3"], "x": [1.0], "y": [1.0], "slice": [0]})
    lm = Landmark(adatas=adatas, landmarks=initial)

    lm.add_landmark_points = {
        "label": str(lm.next_landmark_label),
        "points": [{"slice_id": "1", "x": 9.0, "y": 9.0}],
    }

    assert set(lm.landmarks["label"]) == {"3", "4"}


def test_landmark_initial_landmarks_validates_required_columns():
    rng = np.random.default_rng(26)
    adatas = _make_two_slices(rng)
    missing_y = pd.DataFrame({"label": ["1"], "x": [1.0], "slice": [0]})

    with pytest.raises(ValueError, match="missing column"):
        Landmark(adatas=adatas, landmarks=missing_y)


def test_landmark_initial_landmarks_validates_slice_ids():
    rng = np.random.default_rng(27)
    adatas = _make_two_slices(rng)
    unknown_slice = pd.DataFrame({"label": ["1"], "x": [1.0], "y": [1.0], "slice": [99]})

    with pytest.raises(ValueError, match="not found"):
        Landmark(adatas=adatas, landmarks=unknown_slice)


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


def test_slice_cell_counts():
    rng = np.random.default_rng(9)
    lm = Landmark(adatas=[_make_slice(rng, n=7), _make_slice(rng, n=13)])
    assert lm.slice_cell_counts == {"0": 7, "1": 13}


def test_cluster_counts_and_colors_are_summed_and_consistent_across_slices():
    rng = np.random.default_rng(10)
    adata_0 = _make_slice(rng, n=10, cluster=True)
    adata_1 = _make_slice(rng, n=10, cluster=True)
    lm = Landmark(adatas=[adata_0, adata_1], cluster_key="cluster")

    assert set(lm.cluster_counts) == {"a", "b"}
    assert lm.cluster_counts["a"] + lm.cluster_counts["b"] == 20
    assert set(lm.cluster_colors) == {"a", "b"}
    # Same global color dict backs every slice's centroid parquet, so label
    # "a" is the same color regardless of which slice is currently shown.
    assert lm.cluster_colors["a"] != lm.cluster_colors["b"]


def test_cluster_key_missing_from_some_slice_raises():
    rng = np.random.default_rng(11)
    adatas = [_make_slice(rng, cluster=True), _make_slice(rng, cluster=False)]
    with pytest.raises(ValueError, match="cluster"):
        Landmark(adatas=adatas, cluster_key="cluster")


def test_no_cluster_key_leaves_cluster_counts_empty():
    rng = np.random.default_rng(12)
    lm = Landmark(adatas=_make_two_slices(rng))
    assert lm.cluster_counts == {}
    assert lm.cluster_colors == {}


def test_landmark_coverage_counts_distinct_slices_per_label():
    rng = np.random.default_rng(12)
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
    assert lm.landmark_coverage == {"1": 2}

    # Extend label "1" onto slice 2 by swapping side a there and saving the
    # same label again — slice 0's and slice 1's "1" rows are untouched
    # (commits only ever replace the currently-shown side's own slice), so
    # this adds a third slice to label "1"'s coverage rather than moving it.
    lm.slice_id_a = "2"
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 9.0, 9.0)],
    }
    assert lm.landmark_coverage == {"1": 3}

    lm.landmark_geojson_b = {
        "type": "FeatureCollection",
        "features": [*lm.landmark_geojson_b["features"], _pair_feature("2", 3.0, 3.0)],
    }
    assert lm.landmark_coverage == {"1": 3, "2": 1}
    assert lm.landmark_slices == {"1": ["0", "1", "2"], "2": ["1"]}


def test_rename_landmark_updates_table_coverage_and_visible_geojson():
    rng = np.random.default_rng(13)
    lm = Landmark(adatas=_make_two_slices(rng))  # initial pair 0, 1

    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0)],
    }
    lm.landmark_geojson_b = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 2.0, 2.0)],
    }

    lm.rename_landmark = {"old": "1", "new": "tongue"}

    assert set(lm.landmarks["label"]) == {"tongue"}
    assert lm.landmark_coverage == {"tongue": 2}
    assert lm.landmark_geojson_a["features"][0]["properties"]["label"] == "tongue"
    assert lm.landmark_geojson_b["features"][0]["properties"]["label"] == "tongue"
    # One-shot trigger resets itself so the same rename can't accidentally replay.
    assert lm.rename_landmark == {}


def test_rename_landmark_ignores_unknown_or_noop_requests():
    rng = np.random.default_rng(14)
    lm = Landmark(adatas=_make_two_slices(rng))
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0)],
    }

    lm.rename_landmark = {"old": "not_a_label", "new": "tongue"}
    assert set(lm.landmarks["label"]) == {"1"}

    lm.rename_landmark = {"old": "1", "new": "1"}
    assert set(lm.landmarks["label"]) == {"1"}


def test_delete_landmark_removes_every_instance_across_slices():
    rng = np.random.default_rng(15)
    adatas = [_make_slice(rng) for _ in range(3)]
    lm = Landmark(adatas=adatas)  # initial pair 0, 1

    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0), _pair_feature("2", 4.0, 4.0)],
    }
    lm.landmark_geojson_b = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 2.0, 2.0), _pair_feature("2", 5.0, 5.0)],
    }

    # Extend label "1" onto slice 2 too, so it spans 3 slices before deletion
    # ("2" already spans slices 0 and 1 from the initial commit above).
    lm.slice_id_a = "2"
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 9.0, 9.0)],
    }
    assert lm.landmark_coverage == {"1": 3, "2": 2}

    lm.delete_landmark = "1"

    assert "1" not in set(lm.landmarks["label"])
    assert lm.landmark_coverage == {"2": 2}
    assert lm.landmark_geojson_a == {"type": "FeatureCollection", "features": []}
    # One-shot trigger resets itself.
    assert lm.delete_landmark == ""

    # Side b still shows slice 1, which still has label "2" but no longer "1".
    labels_on_b = {f["properties"]["label"] for f in lm.landmark_geojson_b["features"]}
    assert labels_on_b == {"2"}


def test_rename_landmark_carries_its_color_override_to_the_new_label():
    rng = np.random.default_rng(17)
    lm = Landmark(adatas=_make_two_slices(rng))
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0)],
    }
    lm.landmark_colors = {"1": "#ff0000"}

    lm.rename_landmark = {"old": "1", "new": "tongue"}

    assert lm.landmark_colors == {"tongue": "#ff0000"}


def test_delete_landmark_removes_its_color_override():
    rng = np.random.default_rng(18)
    lm = Landmark(adatas=_make_two_slices(rng))
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0)],
    }
    lm.landmark_colors = {"1": "#ff0000"}

    lm.delete_landmark = "1"

    assert lm.landmark_colors == {}


def test_delete_landmark_ignores_unknown_label():
    rng = np.random.default_rng(16)
    lm = Landmark(adatas=_make_two_slices(rng))
    lm.landmark_geojson_a = {
        "type": "FeatureCollection",
        "features": [_pair_feature("1", 1.0, 1.0)],
    }

    lm.delete_landmark = "not_a_label"
    assert set(lm.landmarks["label"]) == {"1"}
    assert lm.delete_landmark == ""


def test_add_landmark_points_covers_slices_not_currently_on_screen():
    rng = np.random.default_rng(19)
    adatas = [_make_slice(rng) for _ in range(4)]
    lm = Landmark(adatas=adatas)  # initial pair is slices 0, 1

    # Slices "2" and "3" are shown on neither side.
    lm.add_landmark_points = {
        "label": "tongue",
        "points": [
            {"slice_id": "0", "x": 1.0, "y": 1.0},
            {"slice_id": "2", "x": 2.0, "y": 2.0},
            {"slice_id": "3", "x": 3.0, "y": 3.0},
        ],
    }

    assert lm.landmark_coverage == {"tongue": 3}
    assert lm.landmark_slices == {"tongue": ["0", "2", "3"]}
    # Side a is showing slice "0", which was among the points -- picks it up.
    assert lm.landmark_geojson_a["features"][0]["properties"]["label"] == "tongue"
    # One-shot trigger resets itself.
    assert lm.add_landmark_points == {}


def test_add_landmark_points_replaces_existing_point_for_the_same_slice():
    rng = np.random.default_rng(20)
    lm = Landmark(adatas=_make_two_slices(rng))
    lm.add_landmark_points = {
        "label": "1",
        "points": [{"slice_id": "0", "x": 1.0, "y": 1.0}],
    }

    lm.add_landmark_points = {
        "label": "1",
        "points": [{"slice_id": "0", "x": 9.0, "y": 9.0}],
    }

    subset = lm.landmarks.loc[lm.landmarks["label"] == "1"]
    assert len(subset) == 1
    assert subset.iloc[0]["x"] == 9.0
    assert subset.iloc[0]["y"] == 9.0


def test_add_landmark_points_bumps_the_label_counter():
    rng = np.random.default_rng(21)
    lm = Landmark(adatas=_make_two_slices(rng))

    lm.add_landmark_points = {
        "label": "5",
        "points": [{"slice_id": "0", "x": 1.0, "y": 1.0}],
    }

    assert lm.next_landmark_label == 6


def test_add_landmark_points_ignores_empty_or_unknown_slice_payloads():
    rng = np.random.default_rng(22)
    lm = Landmark(adatas=_make_two_slices(rng))

    lm.add_landmark_points = {"label": "", "points": [{"slice_id": "0", "x": 1, "y": 1}]}
    assert lm.landmarks.empty

    lm.add_landmark_points = {"label": "1", "points": []}
    assert lm.landmarks.empty

    lm.add_landmark_points = {"label": "1", "points": [{"slice_id": "not_a_slice", "x": 1, "y": 1}]}
    assert lm.landmarks.empty
    assert lm.add_landmark_points == {}
