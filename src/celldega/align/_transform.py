"""Generic 2D transform fitting from paired points.

Deliberately decoupled from *how* the paired points were obtained (shared
cluster centroids in :mod:`celldega.align.serial_slices` today; manually
placed landmarks in a future paired multi-Z/multi-modality Landscape view)
so the same fit/apply code can be reused across alignment contexts, and from
*which orchestration* calls it (chain-walking slices, atlas registration,
modality registration), so new fitting algorithms plug in as another
``fit(source, target) -> Transform`` callable rather than requiring changes
to the callers. Two fitters are provided: :func:`fit_similarity_transform`
(rigid/similarity Procrustes: one global rotation, scale, and translation)
and :func:`fit_thin_plate_spline` (non-rigid: a smooth deformation that
matches the landmarks locally, for cases a single global transform can't
capture, e.g. section-to-section warping).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.interpolate import RBFInterpolator


__all__ = [
    "SimilarityTransform",
    "ThinPlateSplineTransform",
    "Transform",
    "fit_similarity_transform",
    "fit_thin_plate_spline",
]


class Transform(Protocol):
    """Structural interface every fitted transform in this module satisfies."""

    def apply(self, points: np.ndarray) -> np.ndarray: ...


def _validate_point_pairs(source: np.ndarray, target: np.ndarray, min_points: int) -> tuple[np.ndarray, np.ndarray]:
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    if source.shape != target.shape:
        raise ValueError(
            f"source and target must have the same shape, got {source.shape} vs {target.shape}"
        )
    if source.shape[0] < min_points or source.shape[1] != 2:
        raise ValueError(
            f"source/target must be (n, 2) with n >= {min_points}, got {source.shape}"
        )
    return source, target


@dataclass(frozen=True)
class SimilarityTransform:
    """A rotation + uniform scale + translation mapping source points onto target points."""

    rotation: np.ndarray
    scale: float
    translation: np.ndarray

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Apply this transform to an ``(n, 2)`` array of points."""
        points = np.asarray(points, dtype=float)
        return self.scale * points @ self.rotation.T + self.translation


def fit_similarity_transform(
    source: np.ndarray,
    target: np.ndarray,
    allow_scaling: bool = True,
    allow_reflection: bool = False,
) -> SimilarityTransform:
    """Fit the rotation/scale/translation that best maps ``source`` onto ``target``.

    Solves the classic Procrustes/Umeyama least-squares problem: minimize
    ``sum(||target_i - (scale * rotation @ source_i + translation)||^2)`` over
    a rotation, a single uniform scale, and a translation, given ``n``
    point-to-point correspondences (``source[i]`` corresponds to ``target[i]``).

    Args:
        source: ``(n, 2)`` points to move, ``n >= 2``.
        target: ``(n, 2)`` corresponding points to match, same order as ``source``.
        allow_scaling: If ``False``, force a rigid (scale = 1) transform.
        allow_reflection: If ``False`` (default), force a proper rotation
            (``det(rotation) == 1``) since flipping tissue is not physically
            valid for serial sections. Set ``True`` for contexts where a
            reflection is legitimate (e.g. some modality-to-modality mappings).

    Returns:
        The fitted :class:`SimilarityTransform`.

    Raises:
        ValueError: If fewer than 2 point pairs are given, or shapes mismatch.
    """
    source, target = _validate_point_pairs(source, target, min_points=2)
    n = source.shape[0]
    mu_source = source.mean(axis=0)
    mu_target = target.mean(axis=0)
    source_centered = source - mu_source
    target_centered = target - mu_target

    source_variance = (source_centered**2).sum() / n
    covariance = (target_centered.T @ source_centered) / n

    u, singular_values, vt = np.linalg.svd(covariance)
    correction = np.eye(2)
    if not allow_reflection and np.linalg.det(u @ vt) < 0:
        correction[-1, -1] = -1

    rotation = u @ correction @ vt
    scale = (
        float(np.trace(np.diag(singular_values) @ correction) / source_variance)
        if allow_scaling
        else 1.0
    )
    translation = mu_target - scale * rotation @ mu_source

    return SimilarityTransform(rotation=rotation, scale=scale, translation=translation)


@dataclass(frozen=True)
class ThinPlateSplineTransform:
    """A non-rigid warp mapping source landmarks onto target landmarks."""

    interpolator: RBFInterpolator

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Apply this warp to an ``(n, 2)`` array of points."""
        return self.interpolator(np.asarray(points, dtype=float))


def fit_thin_plate_spline(
    source: np.ndarray,
    target: np.ndarray,
    smoothing: float = 0.0,
    degree: int = 1,
) -> ThinPlateSplineTransform:
    """Fit a thin-plate-spline warp that maps ``source`` landmarks onto ``target`` landmarks.

    Unlike :func:`fit_similarity_transform`, this fits a smooth *non-rigid*
    deformation: it matches the landmarks locally rather than one global
    rotation/scale/translation, so it can recover warps a rigid fit cannot
    (e.g. non-uniform section stretching). Points far from every landmark
    fall back toward the affine (degree-1 polynomial) component rather than
    an arbitrary extrapolation.

    Args:
        source: ``(n, 2)`` landmark points to move, ``n >= 3`` and not all
            collinear (degree-1 TPS needs 3 affinely independent points).
        target: ``(n, 2)`` corresponding landmark points to match, same order
            as ``source``.
        smoothing: Bending-energy penalty. ``0`` (default) interpolates the
            landmarks exactly; increase it to relax exact matching, which is
            useful here since landmarks are noisy cluster-centroid estimates
            rather than exact manual clicks.
        degree: Degree of the polynomial term added to the spline (``1``
            gives an affine fallback away from the landmarks).

    Returns:
        The fitted :class:`ThinPlateSplineTransform`.

    Raises:
        ValueError: If fewer than 3 point pairs are given, shapes mismatch,
            or the landmarks are degenerate (e.g. collinear).
    """
    source, target = _validate_point_pairs(source, target, min_points=3)
    try:
        interpolator = RBFInterpolator(
            source, target, kernel="thin_plate_spline", smoothing=smoothing, degree=degree
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Could not fit a thin-plate spline to these landmarks — they may be collinear "
            "or otherwise degenerate. Add more spatially spread-out landmarks."
        ) from exc

    return ThinPlateSplineTransform(interpolator=interpolator)
