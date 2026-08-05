"""Tests for alpha-shape overlap refinement (``neighborhood_alignment``)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import Polygon

from celldega.align._transform import (
    SimilarityTransform,
    compose_transforms,
    fit_transform_tps,
    rigid_delta_transform,
)
from celldega.align.neighborhood import (
    _distance_weight,
    neighborhood_alignment,
    transform_shapes,
)
from celldega.align.serial_slices import SerialAlignmentTransform
from celldega.nbhd.utils import _stamp_z


# --- composition / delta helpers -------------------------------------------------


def test_compose_transforms_matches_sequential_application():
    rng = np.random.default_rng(0)
    inner = rigid_delta_transform(0.3, 5.0, -2.0, center=np.array([10.0, 4.0]))
    outer = SimilarityTransform(
        rotation=np.array([[0.6, -0.8], [0.8, 0.6]]), scale=1.3, translation=np.array([1.0, 2.0])
    )
    points = rng.normal(size=(20, 2)) * 30

    composed = compose_transforms(outer, inner)

    np.testing.assert_allclose(composed.apply(points), outer.apply(inner.apply(points)))


def test_compose_with_identity_outer_returns_inner():
    identity = SimilarityTransform(rotation=np.eye(2), scale=1.0, translation=np.zeros(2))
    inner = rigid_delta_transform(0.2, 3.0, 4.0, center=np.array([1.0, 1.0]))

    composed = compose_transforms(identity, inner)

    np.testing.assert_allclose(composed.rotation, inner.rotation)
    np.testing.assert_allclose(composed.translation, inner.translation)
    assert composed.scale == pytest.approx(inner.scale)


def test_rigid_delta_leaves_center_only_translated():
    center = np.array([7.0, -3.0])
    delta = rigid_delta_transform(0.5, 2.0, -1.0, center=center)

    # A rotation about `center` leaves `center` fixed; only the translation moves it.
    np.testing.assert_allclose(delta.apply(center[None, :])[0], center + np.array([2.0, -1.0]))


def test_rigid_delta_zero_rotation_is_pure_translation():
    delta = rigid_delta_transform(0.0, 5.0, 6.0, center=np.array([100.0, 200.0]))

    np.testing.assert_allclose(delta.rotation, np.eye(2))
    np.testing.assert_allclose(delta.translation, [5.0, 6.0])


# --- fixtures --------------------------------------------------------------------


def _square(cx: float, cy: float, size: float = 20.0) -> Polygon:
    h = size / 2
    return Polygon([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)])


def _reference_clusters() -> dict[str, Polygon]:
    # Three spread-out, non-collinear clusters.
    return {"0": _square(0.0, 0.0), "1": _square(100.0, 0.0), "2": _square(50.0, 80.0)}


def _offset_transform(rotation_deg: float, tx: float, ty: float) -> SimilarityTransform:
    theta = np.deg2rad(rotation_deg)
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    return SimilarityTransform(rotation=rotation, scale=1.0, translation=np.array([tx, ty]))


def _shapes_gdf(slice_clusters: dict[str, dict[str, Polygon]]) -> gpd.GeoDataFrame:
    rows = [
        {"slice_id": slice_id, "cluster_id": cluster_id, "geometry": geom}
        for slice_id, clusters in slice_clusters.items()
        for cluster_id, geom in clusters.items()
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry")


def _identity_initial(
    slice_ids: list[str],
    reference_index: int = 0,
    slice_attr: str = "slice",
    window: int = 1,
    transforms: dict | None = None,
) -> SerialAlignmentTransform:
    identity = SimilarityTransform(rotation=np.eye(2), scale=1.0, translation=np.zeros(2))
    resolved = transforms or dict.fromkeys(slice_ids, identity)
    empty = pd.DataFrame(columns=[slice_attr, "label", "x", "y", "count", "source"])
    return SerialAlignmentTransform(
        slice_attr=slice_attr,
        slice_ids=list(slice_ids),
        reference=slice_ids[reference_index],
        transforms=resolved,
        transform_log={},
        landmarks_initial=empty,
        landmarks_aligned=empty.copy(),
        method="procrustes",
        allow_reflection=False,
        smoothing=0.0,
        degree=1,
        area_regularization=0.0,
        shape_regularization=0.0,
        weight_by_adjacent_counts=True,
        manual_landmark_weight="equal",
        alignment_window=window,
    )


def _iou(a, b) -> float:
    inter = a.intersection(b).area
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


# --- core behavior ---------------------------------------------------------------


def test_neighborhood_alignment_recovers_a_known_rigid_offset():
    reference = _reference_clusters()
    offset = _offset_transform(rotation_deg=5.0, tx=3.0, ty=-2.0)
    slice1 = {k: shapely.transform(g, offset.apply) for k, g in reference.items()}
    shapes = _shapes_gdf({"s0": reference, "s1": slice1})
    initial = _identity_initial(["s0", "s1"], window=1)

    refined = neighborhood_alignment(
        shapes, initial, n_sweeps=3, rotation_range=10.0, translation_range=0.3
    )

    # Applying the refined transform to slice 1's native shapes should land them
    # back on the reference slice's shapes.
    for cluster_id, geom in slice1.items():
        aligned = shapely.transform(geom, refined.transforms["s1"].apply)
        assert _iou(aligned, reference[cluster_id]) > 0.9

    # The reference slice is untouched (residual identity composes to its
    # initial transform).
    np.testing.assert_allclose(refined.transforms["s0"].rotation, np.eye(2), atol=1e-9)
    np.testing.assert_allclose(refined.transforms["s0"].translation, np.zeros(2), atol=1e-9)


def test_neighborhood_alignment_improves_overlap_over_initial():
    reference = _reference_clusters()
    offset = _offset_transform(rotation_deg=6.0, tx=4.0, ty=3.0)
    slice1 = {k: shapely.transform(g, offset.apply) for k, g in reference.items()}
    shapes = _shapes_gdf({"s0": reference, "s1": slice1})
    initial = _identity_initial(["s0", "s1"], window=1)

    refined = neighborhood_alignment(shapes, initial, n_sweeps=3, translation_range=0.3)

    entry = refined.transform_log["s1"]
    assert entry["overlap_final"] >= entry["overlap_initial"]
    assert entry["n_shared_clusters"] == 3
    assert entry["skipped"] is False
    assert abs(entry["residual_rotation_deg"] - (-6.0)) < 2.5


def test_neighborhood_alignment_metadata_and_provenance():
    reference = _reference_clusters()
    slice1 = {
        k: shapely.transform(g, _offset_transform(3.0, 2.0, 1.0).apply)
        for k, g in reference.items()
    }
    shapes = _shapes_gdf({"s0": reference, "s1": slice1})
    initial = _identity_initial(["s0", "s1"], window=2)

    refined = neighborhood_alignment(shapes, initial)

    assert refined.method == "neighborhood"
    assert refined.slice_ids == ["s0", "s1"]
    assert refined.reference == "s0"
    assert refined.slice_attr == "slice"
    assert refined.alignment_window == 2  # inherited from initial
    assert set(refined.transforms) == {"s0", "s1"}


def test_neighborhood_alignment_three_slice_window_runs_and_aligns():
    reference = _reference_clusters()
    s1 = {
        k: shapely.transform(g, _offset_transform(4.0, 3.0, -2.0).apply)
        for k, g in reference.items()
    }
    s2 = {
        k: shapely.transform(g, _offset_transform(8.0, 6.0, -4.0).apply)
        for k, g in reference.items()
    }
    shapes = _shapes_gdf({"s0": reference, "s1": s1, "s2": s2})
    initial = _identity_initial(["s0", "s1", "s2"], reference_index=0, window=1)

    refined = neighborhood_alignment(
        shapes, initial, n_sweeps=4, rotation_range=12.0, translation_range=0.3
    )

    for cluster_id, geom in s1.items():
        aligned = shapely.transform(geom, refined.transforms["s1"].apply)
        assert _iou(aligned, reference[cluster_id]) > 0.85


def test_neighborhood_alignment_survives_save_load_round_trip(tmp_path):
    reference = _reference_clusters()
    slice1 = {
        k: shapely.transform(g, _offset_transform(3.0, 2.0, 1.0).apply)
        for k, g in reference.items()
    }
    shapes = _shapes_gdf({"s0": reference, "s1": slice1})
    initial = _identity_initial(["s0", "s1"], window=1)
    refined = neighborhood_alignment(shapes, initial)

    refined.save(tmp_path / "nbhd_transform")
    reloaded = SerialAlignmentTransform.load(tmp_path / "nbhd_transform")

    assert reloaded.method == "neighborhood"
    for slice_id in refined.slice_ids:
        np.testing.assert_allclose(
            reloaded.transforms[slice_id].rotation, refined.transforms[slice_id].rotation
        )
        np.testing.assert_allclose(
            reloaded.transforms[slice_id].translation, refined.transforms[slice_id].translation
        )


def test_neighborhood_alignment_skips_slice_without_enough_shared_clusters():
    reference = {"0": _square(0.0, 0.0), "1": _square(100.0, 0.0)}
    # slice 1 shares no cluster labels with the reference.
    slice1 = {"7": _square(3.0, 2.0), "8": _square(103.0, 2.0)}
    shapes = _shapes_gdf({"s0": reference, "s1": slice1})
    initial = _identity_initial(["s0", "s1"], window=1)

    refined = neighborhood_alignment(shapes, initial, min_shared_clusters=1)

    entry = refined.transform_log["s1"]
    assert entry["skipped"] is True
    assert entry["n_shared_clusters"] == 0
    # No shared clusters -> residual stays identity, transform unchanged.
    np.testing.assert_allclose(refined.transforms["s1"].rotation, np.eye(2), atol=1e-9)
    np.testing.assert_allclose(refined.transforms["s1"].translation, np.zeros(2), atol=1e-9)


# --- validation ------------------------------------------------------------------


def test_neighborhood_alignment_rejects_unknown_distance_weight():
    shapes = _shapes_gdf({"s0": _reference_clusters(), "s1": _reference_clusters()})
    initial = _identity_initial(["s0", "s1"])
    with pytest.raises(ValueError, match="distance_weight"):
        neighborhood_alignment(shapes, initial, distance_weight="nope")


def test_neighborhood_alignment_rejects_missing_column():
    shapes = _shapes_gdf({"s0": _reference_clusters(), "s1": _reference_clusters()})
    initial = _identity_initial(["s0", "s1"])
    with pytest.raises(ValueError, match="not_a_column"):
        neighborhood_alignment(shapes, initial, cluster_attr="not_a_column")


def test_neighborhood_alignment_rejects_unknown_slice_in_shapes():
    shapes = _shapes_gdf({"s0": _reference_clusters(), "s99": _reference_clusters()})
    initial = _identity_initial(["s0", "s1"])
    with pytest.raises(ValueError, match="s99"):
        neighborhood_alignment(shapes, initial)


# --- distance weighting ----------------------------------------------------------


def test_distance_weight_modes_all_start_at_one_and_fall_off():
    # Every mode weights the adjacent (d=1) neighbor at 1.0.
    for mode in ("inverse", "uniform", "exponential", "gaussian"):
        assert _distance_weight(1, mode, 1.0) == pytest.approx(1.0)

    # Beyond adjacent, uniform stays flat; the others decay.
    assert _distance_weight(3, "uniform", 1.0) == 1.0
    assert _distance_weight(3, "inverse", 1.0) == pytest.approx(1 / 3)
    assert _distance_weight(3, "exponential", 1.0) == pytest.approx(np.exp(-2.0))
    assert _distance_weight(3, "gaussian", 1.0) == pytest.approx(np.exp(-2.0))

    # Gaussian falls off slower than exponential just past adjacent (d=2)...
    assert _distance_weight(2, "gaussian", 1.0) > _distance_weight(2, "exponential", 1.0)
    # ...and larger decay keeps farther slices more influential.
    assert _distance_weight(3, "gaussian", 2.0) > _distance_weight(3, "gaussian", 1.0)


def test_neighborhood_alignment_accepts_gaussian_weight_and_rejects_bad_decay():
    reference = _reference_clusters()
    s1 = {
        k: shapely.transform(g, _offset_transform(4.0, 3.0, -2.0).apply)
        for k, g in reference.items()
    }
    s2 = {
        k: shapely.transform(g, _offset_transform(7.0, 5.0, -3.0).apply)
        for k, g in reference.items()
    }
    shapes = _shapes_gdf({"s0": reference, "s1": s1, "s2": s2})
    initial = _identity_initial(["s0", "s1", "s2"], reference_index=0, window=2)

    refined = neighborhood_alignment(
        shapes, initial, alignment_window=2, distance_weight="gaussian", distance_decay=1.5
    )
    for cluster_id, geom in s1.items():
        aligned = shapely.transform(geom, refined.transforms["s1"].apply)
        assert _iou(aligned, reference[cluster_id]) > 0.85

    with pytest.raises(ValueError, match="distance_decay"):
        neighborhood_alignment(shapes, initial, distance_weight="gaussian", distance_decay=0.0)


# --- transform_shapes ------------------------------------------------------------


def test_transform_shapes_applies_per_slice_transform_and_preserves_area():
    reference = _reference_clusters()
    shapes = _shapes_gdf({"s0": reference, "s1": reference})
    shapes["area"] = shapes.geometry.area
    offset = _offset_transform(10.0, 5.0, -3.0)
    identity = SimilarityTransform(rotation=np.eye(2), scale=1.0, translation=np.zeros(2))
    transform = _identity_initial(["s0", "s1"], transforms={"s0": identity, "s1": offset})

    out = transform_shapes(shapes, transform, slice_attr="slice_id")

    for cluster_id, geom in reference.items():
        s0_geom = out[(out.slice_id == "s0") & (out.cluster_id == cluster_id)].geometry.iloc[0]
        assert _iou(s0_geom, geom) > 0.999  # reference slice unchanged
        s1_geom = out[(out.slice_id == "s1") & (out.cluster_id == cluster_id)].geometry.iloc[0]
        expected = shapely.transform(geom, offset.apply)
        assert _iou(s1_geom, expected) > 0.999  # moved by the offset
    # Rigid transform preserves area.
    np.testing.assert_allclose(out["area"].to_numpy(), shapes["area"].to_numpy(), rtol=1e-9)


def test_transform_shapes_preserves_z_stamp():
    reference = _reference_clusters()
    stamped = {k: _stamp_z(g, 42.0) for k, g in reference.items()}
    shapes = _shapes_gdf({"s0": stamped})
    offset = _offset_transform(8.0, 4.0, -2.0)
    transform = _identity_initial(["s0"], transforms={"s0": offset})

    out = transform_shapes(shapes, transform, slice_attr="slice_id")

    for geom in out.geometry:
        assert geom.has_z
        assert {round(coord[2], 3) for coord in geom.exterior.coords} == {42.0}


def test_neighborhood_alignment_rejects_non_rigid_initial_transform():
    reference = _reference_clusters()
    shapes = _shapes_gdf({"s0": reference, "s1": reference})
    source = np.array([[0.0, 0.0], [100.0, 0.0], [50.0, 80.0]])
    target = source + 1.0
    tps = fit_transform_tps(source, target)
    identity = SimilarityTransform(rotation=np.eye(2), scale=1.0, translation=np.zeros(2))
    initial = _identity_initial(["s0", "s1"], transforms={"s0": identity, "s1": tps})

    with pytest.raises(ValueError, match="non-rigid"):
        neighborhood_alignment(shapes, initial)
