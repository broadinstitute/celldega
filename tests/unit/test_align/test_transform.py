import numpy as np
import pytest

from celldega.align._transform import fit_similarity_transform


def _rotation_matrix(angle_deg):
    theta = np.radians(angle_deg)
    return np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])


def test_fit_recovers_known_rotation_scale_translation():
    rng = np.random.default_rng(0)
    source = rng.uniform(-10, 10, size=(6, 2))
    rotation = _rotation_matrix(30)
    scale, translation = 1.7, np.array([5.0, -3.0])
    target = scale * source @ rotation.T + translation

    transform = fit_similarity_transform(source, target)

    assert transform.scale == pytest.approx(scale, abs=1e-8)
    assert np.allclose(transform.rotation, rotation, atol=1e-8)
    assert np.allclose(transform.translation, translation, atol=1e-8)
    assert np.allclose(transform.apply(source), target, atol=1e-8)


def test_allow_scaling_false_forces_unit_scale():
    rng = np.random.default_rng(1)
    source = rng.uniform(-10, 10, size=(5, 2))
    rotation = _rotation_matrix(-45)
    target = 3.0 * source @ rotation.T + np.array([1.0, 1.0])

    transform = fit_similarity_transform(source, target, allow_scaling=False)

    assert transform.scale == 1.0


def test_allow_reflection_false_forces_proper_rotation():
    rng = np.random.default_rng(2)
    source = rng.uniform(-10, 10, size=(5, 2))
    reflection = np.array([[1.0, 0.0], [0.0, -1.0]])
    target = source @ reflection.T

    transform = fit_similarity_transform(source, target, allow_reflection=False)
    assert np.linalg.det(transform.rotation) == pytest.approx(1.0)

    transform_reflected = fit_similarity_transform(source, target, allow_reflection=True)
    assert np.linalg.det(transform_reflected.rotation) == pytest.approx(-1.0)
    assert np.allclose(transform_reflected.apply(source), target, atol=1e-8)


def test_identity_when_source_equals_target():
    rng = np.random.default_rng(3)
    points = rng.uniform(-5, 5, size=(4, 2))

    transform = fit_similarity_transform(points, points)

    assert np.allclose(transform.rotation, np.eye(2), atol=1e-8)
    assert transform.scale == pytest.approx(1.0)
    assert np.allclose(transform.translation, [0, 0], atol=1e-8)


def test_requires_at_least_two_points():
    with pytest.raises(ValueError, match="n >= 2"):
        fit_similarity_transform(np.zeros((1, 2)), np.zeros((1, 2)))


def test_requires_matching_shapes():
    with pytest.raises(ValueError, match="same shape"):
        fit_similarity_transform(np.zeros((3, 2)), np.zeros((4, 2)))
