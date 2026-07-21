"""Generic 2D transform fitting from paired points.

Deliberately decoupled from *how* the paired points were obtained (shared
cluster centroids in :mod:`celldega.align.serial_slices` today; manually
placed landmarks from :class:`~celldega.align.widget.Landmark` also) so the
same fit/apply code can be reused across alignment contexts, and from
*which orchestration* calls it (chain-walking slices, atlas registration,
modality registration), so new fitting algorithms plug in as another
``fit(source, target) -> Transform`` callable rather than requiring changes
to the callers. Two fitters are provided: :func:`fit_transform_procrustes`
(rigid/similarity Procrustes: one global rotation, scale, and translation)
and :func:`fit_transform_tps` (non-rigid: a smooth deformation that
matches the landmarks locally, for cases a single global transform can't
capture, e.g. section-to-section warping).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from scipy.interpolate import RBFInterpolator


__all__ = [
    "SimilarityTransform",
    "ThinPlateSplineTransform",
    "Transform",
    "fit_transform_procrustes",
    "fit_transform_tps",
    "leave_one_out_residuals",
    "load_transform",
    "save_transform",
]


class Transform(Protocol):
    """Structural interface every fitted transform in this module satisfies."""

    def apply(self, points: np.ndarray) -> np.ndarray: ...


def _validate_point_pairs(
    source: np.ndarray, target: np.ndarray, min_points: int
) -> tuple[np.ndarray, np.ndarray]:
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    if source.shape != target.shape:
        raise ValueError(
            f"source and target must have the same shape, got {source.shape} vs {target.shape}"
        )
    if source.shape[0] < min_points or source.shape[1] != 2:
        raise ValueError(f"source/target must be (n, 2) with n >= {min_points}, got {source.shape}")
    return source, target


def _validate_weights(weights: np.ndarray | None, n: int) -> np.ndarray:
    if weights is None:
        return np.ones(n)
    weights = np.asarray(weights, dtype=float)
    if weights.shape != (n,):
        raise ValueError(f"weights must have shape ({n},), got {weights.shape}")
    if np.any(weights <= 0):
        raise ValueError("weights must all be positive")
    return weights


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


def fit_transform_procrustes(
    source: np.ndarray,
    target: np.ndarray,
    weights: np.ndarray | None = None,
    allow_scaling: bool = True,
    allow_reflection: bool = False,
) -> SimilarityTransform:
    """Fit the rotation/scale/translation that best maps ``source`` onto ``target``.

    Solves the classic Procrustes/Umeyama least-squares problem: minimize
    ``sum(weights_i * ||target_i - (scale * rotation @ source_i + translation)||^2)``
    over a rotation, a single uniform scale, and a translation, given ``n``
    point-to-point correspondences (``source[i]`` corresponds to ``target[i]``).

    Args:
        source: ``(n, 2)`` points to move, ``n >= 2``.
        target: ``(n, 2)`` corresponding points to match, same order as ``source``.
        weights: Optional ``(n,)`` positive per-point weights (e.g. landmark
            confidence). ``None`` (default) weights every point equally,
            reproducing the unweighted fit exactly.
        allow_scaling: If ``False``, force a rigid (scale = 1) transform.
        allow_reflection: If ``False`` (default), force a proper rotation
            (``det(rotation) == 1``) since flipping tissue is not physically
            valid for serial sections. Set ``True`` for contexts where a
            reflection is legitimate (e.g. some modality-to-modality mappings).

    Returns:
        The fitted :class:`SimilarityTransform`.

    Raises:
        ValueError: If fewer than 2 point pairs are given, shapes mismatch, or
            ``weights`` has the wrong shape or non-positive entries.
    """
    source, target = _validate_point_pairs(source, target, min_points=2)
    weights = _validate_weights(weights, source.shape[0])
    total_weight = weights.sum()
    mu_source = (weights[:, None] * source).sum(axis=0) / total_weight
    mu_target = (weights[:, None] * target).sum(axis=0) / total_weight
    source_centered = source - mu_source
    target_centered = target - mu_target

    source_variance = (weights * (source_centered**2).sum(axis=1)).sum() / total_weight
    covariance = (target_centered * weights[:, None]).T @ source_centered / total_weight

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
    """A non-rigid warp mapping source landmarks onto target landmarks.

    The source (domain) is normalized by ``source_center``/``source_scale``
    before the spline is evaluated — see :func:`fit_transform_tps` for why
    (it makes ``smoothing`` scale-free). ``source_center = [0, 0]`` and
    ``source_scale = 1`` reproduce an un-normalized fit.
    """

    interpolator: RBFInterpolator
    source_center: np.ndarray = None
    source_scale: float = 1.0

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Apply this warp to an ``(n, 2)`` array of points."""
        points = np.asarray(points, dtype=float)
        if self.source_center is not None:
            points = (points - self.source_center) / self.source_scale
        return self.interpolator(points)


def fit_transform_tps(
    source: np.ndarray,
    target: np.ndarray,
    weights: np.ndarray | None = None,
    smoothing: float = 0.0,
    degree: int = 1,
) -> ThinPlateSplineTransform:
    """Fit a thin-plate-spline warp that maps ``source`` landmarks onto ``target`` landmarks.

    Unlike :func:`fit_transform_procrustes`, this fits a smooth *non-rigid*
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
        weights: Optional ``(n,)`` positive per-point weights, converted into
            per-point ``smoothing`` (``smoothing / weights``): a higher-weight
            landmark gets a smaller effective smoothing (fit more tightly), a
            lower-weight one gets more slack. Only has an effect when
            ``smoothing > 0`` — at ``smoothing = 0`` the spline interpolates
            every landmark exactly regardless of weight, since there's no
            such thing as a weighted *exact* interpolation.
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
            ``weights`` has the wrong shape or non-positive entries, or the
            landmarks are degenerate (e.g. collinear).
    """
    source, target = _validate_point_pairs(source, target, min_points=3)
    weights = _validate_weights(weights, source.shape[0])
    effective_smoothing = smoothing / weights
    try:
        interpolator = RBFInterpolator(
            source, target, kernel="thin_plate_spline", smoothing=effective_smoothing, degree=degree
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Could not fit a thin-plate spline to these landmarks — they may be collinear "
            "or otherwise degenerate. Add more spatially spread-out landmarks."
        ) from exc

    return ThinPlateSplineTransform(interpolator=interpolator)


def leave_one_out_residuals(
    source: np.ndarray,
    target: np.ndarray,
    fit_transform: Callable[..., Transform],
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Per-landmark leave-one-out residual: how well does the fit implied by the
    *other* landmarks predict this one?

    In-sample residual is a poor diagnostic for an interpolating fit (e.g.
    :func:`fit_transform_tps` at ``smoothing=0`` matches every landmark
    exactly by construction, regardless of whether the landmarks are actually
    consistent). Leave-one-out residual instead measures, for each landmark,
    whether it agrees with a fit built from everything *except* it — a large
    value flags a landmark that may be mislabeled, noisy, or otherwise
    inconsistent with the rest.

    Args:
        source: ``(n, 2)`` landmark points.
        target: ``(n, 2)`` corresponding landmark points.
        fit_transform: A ``fit(source, target, weights=None) -> Transform``
            callable, e.g. :func:`fit_transform_procrustes` or
            :func:`fit_transform_tps` (bind extra keyword arguments with
            :func:`functools.partial`).
        weights: Optional ``(n,)`` positive per-point weights, passed through
            to ``fit_transform`` for both the leave-one-out fits.

    Returns:
        An ``(n,)`` array of residual distances, ``NaN`` for any landmark
        whose leave-one-out refit failed (e.g. too few or degenerate points
        remained).
    """
    n = source.shape[0]
    residuals = np.full(n, np.nan)
    mask = np.ones(n, dtype=bool)
    for i in range(n):
        mask[i] = False
        held_out_weights = None if weights is None else weights[mask]
        try:
            transform = fit_transform(source[mask], target[mask], weights=held_out_weights)
        except ValueError:
            mask[i] = True
            continue
        residuals[i] = np.linalg.norm(transform.apply(source[i : i + 1])[0] - target[i])
        mask[i] = True
    return residuals


def save_transform(transform: Transform, path: str | Path) -> None:
    """Save a fitted :class:`SimilarityTransform` or :class:`ThinPlateSplineTransform`
    to a plain ``.npz`` file — no ``pickle`` involved, so the result is portable,
    inspectable with any numpy install, and doesn't depend on matching library
    versions the way a pickled object graph would. A :class:`ThinPlateSplineTransform`
    is saved as the plain-array inputs (landmark positions, per-point smoothing,
    kernel, epsilon, degree) that reconstruct an equivalent ``RBFInterpolator``,
    not the fitted object itself.

    Args:
        transform: The transform to save.
        path: Destination ``.npz`` file path.

    Raises:
        TypeError: If ``transform`` is neither a :class:`SimilarityTransform`
            nor a :class:`ThinPlateSplineTransform`.
    """
    if isinstance(transform, SimilarityTransform):
        np.savez(
            path,
            kind="procrustes",
            rotation=transform.rotation,
            scale=np.asarray(transform.scale),
            translation=transform.translation,
        )
        return
    if isinstance(transform, ThinPlateSplineTransform):
        interpolator = transform.interpolator
        powers = interpolator.powers
        degree = int(powers.sum(axis=1).max()) if powers.size else -1
        np.savez(
            path,
            kind="tps",
            y=interpolator.y,
            d=interpolator.d,
            smoothing=interpolator.smoothing,
            epsilon=np.asarray(interpolator.epsilon),
            kernel=np.asarray(interpolator.kernel),
            degree=np.asarray(degree),
        )
        return
    raise TypeError(f"don't know how to save a transform of type {type(transform)!r}")


def load_transform(path: str | Path) -> Transform:
    """Load a transform previously saved with :func:`save_transform`.

    Args:
        path: Path to the ``.npz`` file.

    Returns:
        The reconstructed :class:`SimilarityTransform` or
        :class:`ThinPlateSplineTransform` — for the latter, a fresh
        ``RBFInterpolator`` rebuilt from the saved plain-array inputs,
        numerically equivalent to the one originally fitted.

    Raises:
        ValueError: If the file's ``kind`` is not recognized.
    """
    with np.load(path, allow_pickle=False) as data:
        kind = str(data["kind"])
        if kind == "procrustes":
            return SimilarityTransform(
                rotation=data["rotation"],
                scale=float(data["scale"]),
                translation=data["translation"],
            )
        if kind == "tps":
            interpolator = RBFInterpolator(
                data["y"],
                data["d"],
                smoothing=data["smoothing"],
                kernel=str(data["kernel"]),
                epsilon=float(data["epsilon"]),
                degree=int(data["degree"]),
            )
            return ThinPlateSplineTransform(interpolator=interpolator)
        raise ValueError(f"unknown transform kind {kind!r} in {path}")
