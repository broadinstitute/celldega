import numpy as np
import pytest

from celldega.align._transform import (
    fit_transform_procrustes,
    fit_transform_tps,
    leave_one_out_residuals,
    load_transform,
    save_transform,
)


def _rotation_matrix(angle_deg):
    theta = np.radians(angle_deg)
    return np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])


def test_fit_recovers_known_rotation_scale_translation():
    rng = np.random.default_rng(0)
    source = rng.uniform(-10, 10, size=(6, 2))
    rotation = _rotation_matrix(30)
    scale, translation = 1.7, np.array([5.0, -3.0])
    target = scale * source @ rotation.T + translation

    transform = fit_transform_procrustes(source, target)

    assert transform.scale == pytest.approx(scale, abs=1e-8)
    assert np.allclose(transform.rotation, rotation, atol=1e-8)
    assert np.allclose(transform.translation, translation, atol=1e-8)
    assert np.allclose(transform.apply(source), target, atol=1e-8)


def test_allow_scaling_false_forces_unit_scale():
    rng = np.random.default_rng(1)
    source = rng.uniform(-10, 10, size=(5, 2))
    rotation = _rotation_matrix(-45)
    target = 3.0 * source @ rotation.T + np.array([1.0, 1.0])

    transform = fit_transform_procrustes(source, target, allow_scaling=False)

    assert transform.scale == 1.0


def test_allow_reflection_false_forces_proper_rotation():
    rng = np.random.default_rng(2)
    source = rng.uniform(-10, 10, size=(5, 2))
    reflection = np.array([[1.0, 0.0], [0.0, -1.0]])
    target = source @ reflection.T

    transform = fit_transform_procrustes(source, target, allow_reflection=False)
    assert np.linalg.det(transform.rotation) == pytest.approx(1.0)

    transform_reflected = fit_transform_procrustes(source, target, allow_reflection=True)
    assert np.linalg.det(transform_reflected.rotation) == pytest.approx(-1.0)
    assert np.allclose(transform_reflected.apply(source), target, atol=1e-8)


def test_identity_when_source_equals_target():
    rng = np.random.default_rng(3)
    points = rng.uniform(-5, 5, size=(4, 2))

    transform = fit_transform_procrustes(points, points)

    assert np.allclose(transform.rotation, np.eye(2), atol=1e-8)
    assert transform.scale == pytest.approx(1.0)
    assert np.allclose(transform.translation, [0, 0], atol=1e-8)


def test_requires_at_least_two_points():
    with pytest.raises(ValueError, match="n >= 2"):
        fit_transform_procrustes(np.zeros((1, 2)), np.zeros((1, 2)))


def test_requires_matching_shapes():
    with pytest.raises(ValueError, match="same shape"):
        fit_transform_procrustes(np.zeros((3, 2)), np.zeros((4, 2)))


def test_tps_recovers_landmarks_exactly_by_default():
    rng = np.random.default_rng(4)
    source = rng.uniform(-10, 10, size=(6, 2))
    # A non-affine warp (quadratic in x) a rigid/affine fit cannot represent.
    target = source + np.column_stack([0.05 * source[:, 0] ** 2, np.zeros(6)])

    transform = fit_transform_tps(source, target)

    assert np.allclose(transform.apply(source), target, atol=1e-6)


def test_tps_smoothing_relaxes_exact_interpolation():
    rng = np.random.default_rng(5)
    source = rng.uniform(-10, 10, size=(8, 2))
    target = source + rng.normal(scale=0.5, size=source.shape)  # noisy correspondences

    exact = fit_transform_tps(source, target, smoothing=0.0)
    smoothed = fit_transform_tps(source, target, smoothing=10.0)

    exact_residual = np.linalg.norm(exact.apply(source) - target)
    smoothed_residual = np.linalg.norm(smoothed.apply(source) - target)
    assert exact_residual < 1e-6
    assert smoothed_residual > exact_residual


def test_tps_smoothing_is_scale_free_with_normalization():
    rng = np.random.default_rng(30)
    source = rng.uniform(-10, 10, size=(10, 2))
    target = source + rng.normal(scale=0.3, size=source.shape)  # noisy correspondences
    scale = 1000.0  # e.g. microns vs the small "unit" version

    small = fit_transform_tps(source, target, smoothing=1.0)
    big = fit_transform_tps(source * scale, target * scale, smoothing=1.0)

    # The same `smoothing` relaxes the fit by the same *relative* amount at
    # both coordinate scales, because the domain is normalized before fitting.
    small_resid = np.linalg.norm(small.apply(source) - target)
    big_resid = np.linalg.norm(big.apply(source * scale) - target * scale) / scale
    assert np.isclose(small_resid, big_resid, rtol=1e-5)

    # Without normalization, smoothing=1.0 is negligible against the large
    # micron-scale kernel, so the big-scale fit stays essentially exact
    # (much smaller residual) -- the footgun this normalization fixes.
    big_unnorm = fit_transform_tps(source * scale, target * scale, smoothing=1.0, normalize=False)
    big_unnorm_resid = np.linalg.norm(big_unnorm.apply(source * scale) - target * scale) / scale
    assert big_unnorm_resid < 0.1 * big_resid


def test_tps_save_load_round_trips_normalization(tmp_path):
    rng = np.random.default_rng(31)
    source = rng.uniform(-5000, 5000, size=(8, 2))  # micron-scale
    target = source + rng.normal(scale=50.0, size=source.shape)
    transform = fit_transform_tps(source, target, smoothing=1.0)
    assert transform.source_scale > 1.0  # normalization actually kicked in

    path = tmp_path / "tps.npz"
    save_transform(transform, path)
    reloaded = load_transform(path)

    query = rng.uniform(-5000, 5000, size=(6, 2))
    assert np.allclose(transform.apply(query), reloaded.apply(query))
    assert np.isclose(reloaded.source_scale, transform.source_scale)


def test_tps_affine_consistent_data_extrapolates_like_affine():
    rng = np.random.default_rng(6)
    source = rng.uniform(-5, 5, size=(6, 2))
    rotation = _rotation_matrix(15)
    target = 1.3 * source @ rotation.T + np.array([2.0, -1.0])

    transform = fit_transform_tps(source, target)

    far_points = rng.uniform(-50, 50, size=(5, 2))
    expected = 1.3 * far_points @ rotation.T + np.array([2.0, -1.0])
    assert np.allclose(transform.apply(far_points), expected, atol=1e-6)


def test_tps_requires_at_least_three_points():
    with pytest.raises(ValueError, match="n >= 3"):
        fit_transform_tps(np.zeros((2, 2)), np.zeros((2, 2)))


def test_tps_rejects_collinear_landmarks():
    source = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    target = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])

    with pytest.raises(ValueError, match="collinear"):
        fit_transform_tps(source, target)


def test_similarity_uniform_weights_match_unweighted():
    rng = np.random.default_rng(7)
    source = rng.uniform(-10, 10, size=(6, 2))
    rotation = _rotation_matrix(30)
    target = 1.7 * source @ rotation.T + np.array([5.0, -3.0])

    unweighted = fit_transform_procrustes(source, target)
    weighted = fit_transform_procrustes(source, target, weights=np.ones(6))

    assert np.allclose(unweighted.rotation, weighted.rotation, atol=1e-8)
    assert unweighted.scale == pytest.approx(weighted.scale)
    assert np.allclose(unweighted.translation, weighted.translation, atol=1e-8)


def test_similarity_down_weighting_noisy_points_recovers_true_transform():
    rng = np.random.default_rng(8)
    source = rng.uniform(-10, 10, size=(8, 2))
    rotation = _rotation_matrix(20)
    scale, translation = 1.3, np.array([2.0, -1.0])
    target = scale * source @ rotation.T + translation

    noisy_target = target.copy()
    noisy_target[4:] += rng.normal(scale=5.0, size=(4, 2))
    weights = np.array([1.0, 1.0, 1.0, 1.0, 0.001, 0.001, 0.001, 0.001])

    weighted = fit_transform_procrustes(source, noisy_target, weights=weights)
    unweighted = fit_transform_procrustes(source, noisy_target)

    weighted_error = np.abs(weighted.rotation - rotation).max()
    unweighted_error = np.abs(unweighted.rotation - rotation).max()
    assert weighted_error < unweighted_error
    assert weighted_error < 0.01


def test_similarity_weights_validation():
    source = np.zeros((3, 2))
    with pytest.raises(ValueError, match="shape"):
        fit_transform_procrustes(source, source, weights=np.ones(2))
    with pytest.raises(ValueError, match="positive"):
        fit_transform_procrustes(source, source, weights=np.array([1.0, 0.0, -1.0]))


def test_tps_weights_are_noop_at_zero_smoothing():
    rng = np.random.default_rng(9)
    source = rng.uniform(-10, 10, size=(6, 2))
    target = source + np.column_stack([0.05 * source[:, 0] ** 2, np.zeros(6)])

    unweighted = fit_transform_tps(source, target, smoothing=0.0)
    weighted = fit_transform_tps(
        source, target, weights=np.array([1, 1000, 1, 1, 1, 1], dtype=float), smoothing=0.0
    )

    assert np.allclose(unweighted.apply(source), weighted.apply(source), atol=1e-8)


def test_tps_weights_take_effect_when_smoothing_positive():
    rng = np.random.default_rng(10)
    source = rng.uniform(-10, 10, size=(6, 2))
    target = source + rng.normal(scale=1.0, size=source.shape)

    low_weight_first = fit_transform_tps(
        source, target, weights=np.array([0.01, 1, 1, 1, 1, 1]), smoothing=1.0
    )
    high_weight_first = fit_transform_tps(
        source, target, weights=np.array([100.0, 1, 1, 1, 1, 1]), smoothing=1.0
    )

    low_weight_residual = np.linalg.norm(low_weight_first.apply(source[:1]) - target[:1])
    high_weight_residual = np.linalg.norm(high_weight_first.apply(source[:1]) - target[:1])
    assert high_weight_residual < low_weight_residual


def test_leave_one_out_residuals_flags_the_mismatched_landmark():
    rng = np.random.default_rng(11)
    source = rng.uniform(-10, 10, size=(8, 2))
    rotation = _rotation_matrix(20)
    target = 1.3 * source @ rotation.T + np.array([2.0, -1.0])

    bad_target = target.copy()
    bad_target[3] += np.array([20.0, 0.0])

    residuals = leave_one_out_residuals(source, bad_target, fit_transform_procrustes)

    assert np.argmax(residuals) == 3
    assert residuals[3] > 2 * np.median(np.delete(residuals, 3))


def test_leave_one_out_residuals_small_for_consistent_landmarks():
    rng = np.random.default_rng(12)
    source = rng.uniform(-10, 10, size=(6, 2))
    rotation = _rotation_matrix(-10)
    target = 0.9 * source @ rotation.T + np.array([1.0, 1.0])

    residuals = leave_one_out_residuals(source, target, fit_transform_procrustes)

    assert np.all(residuals < 1e-6)
