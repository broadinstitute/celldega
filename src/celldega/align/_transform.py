"""Generic 2D transform fitting from paired points.

Deliberately decoupled from *how* the paired points were obtained (shared
cluster centroids in :mod:`celldega.align.serial_slices` today; manually
placed landmarks from :class:`~celldega.viz.Landmark` also) so the
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
    "compose_transforms",
    "fit_transform_procrustes",
    "fit_transform_tps",
    "leave_one_out_residuals",
    "load_transform",
    "rigid_delta_transform",
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
        """Apply this transform to an ``(n, 2)`` array of points.

        Computed component-wise rather than as a single ``points @ rotation.T``
        matmul so that two identical input points always map to bit-identical
        output points: a batched BLAS matmul can round identical rows
        differently depending on their position in the batch, which — when this
        transform is applied to a polygon ring's vertices (e.g. via
        ``shapely.transform``) — can leave the closing vertex no longer exactly
        equal to the first, so GEOS rejects the ring as not closed. The
        arithmetic is otherwise identical to ``scale * points @ rotation.T +
        translation``.
        """
        points = np.asarray(points, dtype=float)
        x = points[..., 0]
        y = points[..., 1]
        out_x = (
            self.scale * (self.rotation[0, 0] * x + self.rotation[0, 1] * y) + self.translation[0]
        )
        out_y = (
            self.scale * (self.rotation[1, 0] * x + self.rotation[1, 1] * y) + self.translation[1]
        )
        return np.stack([out_x, out_y], axis=-1)


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


def compose_transforms(
    outer: SimilarityTransform, inner: SimilarityTransform
) -> SimilarityTransform:
    """Compose two similarity transforms into one: ``compose(outer, inner)(x) == outer(inner(x))``.

    Because a rotation/scale/translation composed with another is again a
    single rotation/scale/translation, the result is a plain
    :class:`SimilarityTransform` — no wrapper or transform chain needed. This
    is what lets a residual refinement (see :func:`rigid_delta_transform`)
    applied on top of an initial fit collapse back into one transform that
    still saves/loads and applies exactly like any other (used by
    :func:`~celldega.align.neighborhood.neighborhood_alignment` to fold each
    slice's overlap-refinement delta into its initial Procrustes transform).

    Args:
        outer: The transform applied second (to ``inner``'s output).
        inner: The transform applied first (to the input points).

    Returns:
        A :class:`SimilarityTransform` equivalent to applying ``inner`` then
        ``outer``.
    """
    return SimilarityTransform(
        rotation=outer.rotation @ inner.rotation,
        scale=outer.scale * inner.scale,
        translation=outer.scale * (outer.rotation @ inner.translation) + outer.translation,
    )


def rigid_delta_transform(
    theta: float, dx: float, dy: float, center: np.ndarray | None = None
) -> SimilarityTransform:
    """A small rigid transform: rotate by ``theta`` about ``center``, then translate by ``(dx, dy)``.

    Rotating about a chosen ``center`` (rather than the origin) keeps the
    three parameters well-scaled and decoupled for optimization: ``theta`` is
    a pure local rotation of a shape sitting near ``center`` and ``dx``/``dy``
    are a pure translation, instead of a small ``theta`` implying a large
    origin-relative shift for a shape far from the origin. The returned
    transform is still expressed in the standard origin-relative
    rotation-then-translation form (its ``translation`` absorbs the
    center-relative offset), so it composes and applies like any other
    :class:`SimilarityTransform`.

    Args:
        theta: Rotation angle in radians.
        dx: Translation in x, applied after the rotation.
        dy: Translation in y, applied after the rotation.
        center: ``(2,)`` point to rotate about. Defaults to the origin.

    Returns:
        The rigid :class:`SimilarityTransform` ``x -> R(x - center) + center + [dx, dy]``.
    """
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)
    rotation = np.array([[cos_theta, -sin_theta], [sin_theta, cos_theta]])
    center = np.zeros(2) if center is None else np.asarray(center, dtype=float)
    translation = center - rotation @ center + np.array([dx, dy], dtype=float)
    return SimilarityTransform(rotation=rotation, scale=1.0, translation=translation)


@dataclass(frozen=True)
class ThinPlateSplineTransform:
    """A non-rigid warp mapping source landmarks onto target landmarks.

    The source (domain) is normalized by ``source_center``/``source_scale``
    before the spline is evaluated — see :func:`fit_transform_tps` for why
    (it makes ``smoothing`` scale-free). ``source_center = [0, 0]`` and
    ``source_scale = 1`` reproduce an un-normalized fit.

    ``output_affine`` is an optional ``2x2`` linear correction (applied about
    ``output_center``, in the target frame) *after* the spline — how
    :func:`fit_transform_tps`'s ``area_regularization``/``shape_regularization``
    pull the warp's global affine back toward area-/proportion-preserving.
    ``output_affine = None`` (or identity) is a no-op.
    """

    interpolator: RBFInterpolator
    source_center: np.ndarray = None
    source_scale: float = 1.0
    output_center: np.ndarray = None
    output_affine: np.ndarray = None

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Apply this warp to an ``(n, 2)`` array of points."""
        points = np.asarray(points, dtype=float)
        if self.source_center is not None:
            points = (points - self.source_center) / self.source_scale
        out = self.interpolator(points)
        if self.output_center is not None and self.output_affine is not None:
            out = self.output_center + (out - self.output_center) @ self.output_affine
        return out


def fit_transform_tps(
    source: np.ndarray,
    target: np.ndarray,
    weights: np.ndarray | None = None,
    smoothing: float = 0.0,
    degree: int = 1,
    normalize: bool = True,
    area_regularization: float = 0.0,
    shape_regularization: float = 0.0,
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
        smoothing: Bending-energy penalty trading exact landmark matching
            (``0``, the default — the spline passes through every landmark,
            which *overfits* noisy cluster-centroid landmarks by contorting
            the tissue to hit each one) against a smoother, stiffer warp
            (higher values relax the fit toward the plain affine transform,
            preserving each slice's own shape). With ``normalize=True`` this
            is measured in *normalized* domain units, so it's comparable
            across datasets regardless of coordinate scale — useful values
            are roughly ``0`` (exact) through ``~0.1`` to ``1`` (light local
            warp) to ``~10``+ (nearly rigid/affine). Without normalization it
            is in raw kernel units (``~distance² · log distance``), so for
            micron coordinates it would need to be enormous (``~1e6``+) to
            have any effect at all.
        degree: Degree of the polynomial term added to the spline (``1``
            gives an affine fallback away from the landmarks).
        normalize: If ``True`` (default), the source (domain) is recentered
            and scaled to unit RMS radius before fitting, and query points
            are normalized the same way on apply. This makes ``smoothing``
            scale-free (see above) and improves numerical conditioning. It
            does *not* change a ``smoothing=0`` fit (exact interpolation is
            exact in any units) — only the meaning of a nonzero ``smoothing``.
        area_regularization: Penalty in ``[0, 1]`` on the warp's *total*
            (global) area change. TPS's affine component freely rescales a
            slice to make landmarks coincide, undesirable when slices are
            genuinely different sizes. See below for how it and
            ``shape_regularization`` are applied together.
        shape_regularization: Penalty in ``[0, 1]`` on the warp's global
            *proportion* change — the affine's anisotropy (its two singular
            values' ratio, i.e. stretching one axis while squeezing the
            other, plus shear). This is separate from area: an affine can
            keep area constant while still distorting proportions (a taller,
            pinched-in-the-middle look), which ``area_regularization`` alone
            won't catch.

            Both are applied as a single post-fit correction: the warp's
            global affine ``A`` (best-fit linear map of the landmark cloud) is
            SVD'd into a rotation and two singular values; the geometric-mean
            scale is pulled toward 1 by ``area_regularization`` and the
            anisotropy toward 1 by ``shape_regularization``, then a uniform
            correction is applied about the output centroid — leaving
            rotation, translation, and *local* (bending) warp untouched. At
            ``0``/``0`` (default) the fit is unchanged; ``1``/``1`` makes the
            global part rigid (rotation only — area and proportions both
            preserved), leaving only local deformation.

    Returns:
        The fitted :class:`ThinPlateSplineTransform`.

    Raises:
        ValueError: If fewer than 3 point pairs are given, shapes mismatch,
            ``weights`` has the wrong shape or non-positive entries,
            ``area_regularization``/``shape_regularization`` are negative, or
            the landmarks are degenerate (e.g. collinear).
    """
    source, target = _validate_point_pairs(source, target, min_points=3)
    weights = _validate_weights(weights, source.shape[0])
    if not (0.0 <= area_regularization <= 1.0):
        raise ValueError(f"area_regularization must be in [0, 1], got {area_regularization}")
    if not (0.0 <= shape_regularization <= 1.0):
        raise ValueError(f"shape_regularization must be in [0, 1], got {shape_regularization}")

    if normalize:
        source_center = source.mean(axis=0)
        rms_radius = float(np.sqrt(np.mean(((source - source_center) ** 2).sum(axis=1))))
        source_scale = rms_radius if rms_radius > 0 else 1.0
    else:
        source_center = np.zeros(source.shape[1])
        source_scale = 1.0
    source_normalized = (source - source_center) / source_scale

    effective_smoothing = smoothing / weights
    try:
        interpolator = RBFInterpolator(
            source_normalized,
            target,
            kernel="thin_plate_spline",
            smoothing=effective_smoothing,
            degree=degree,
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Could not fit a thin-plate spline to these landmarks — they may be collinear "
            "or otherwise degenerate. Add more spatially spread-out landmarks."
        ) from exc

    output_center = None
    output_affine = None
    if area_regularization > 0 or shape_regularization > 0:
        # The warp's global affine `A` (best-fit linear map source->output,
        # row-vector convention: centered_source @ A ~ centered_output). SVD it
        # into rotation * (two singular values = the two axis stretches); pull
        # the geometric-mean scale toward 1 by `area_regularization` and the
        # anisotropy toward 1 by `shape_regularization`, then correct the
        # output so its global affine matches the regularized target. Rotation,
        # translation, and local bending are untouched.
        transformed = interpolator(source_normalized)
        centered_source = source - source.mean(axis=0)
        output_center = transformed.mean(axis=0)
        centered_output = transformed - output_center
        affine, *_ = np.linalg.lstsq(centered_source, centered_output, rcond=None)
        u_mat, singular_values, vt_mat = np.linalg.svd(affine)
        s1, s2 = singular_values
        if s1 > 1e-12 and s2 > 1e-12:
            scale = np.sqrt(s1 * s2)  # geometric-mean (area^0.5)
            anisotropy = np.sqrt(s1 / s2)
            scale_reg = scale ** (1.0 - area_regularization)
            anisotropy_reg = anisotropy ** (1.0 - shape_regularization)
            target_svals = np.array([scale_reg * anisotropy_reg, scale_reg / anisotropy_reg])
            target_affine = (u_mat * target_svals) @ vt_mat
            # correction C with A @ C = target_affine  ->  C = A^-1 @ target
            output_affine = np.linalg.solve(affine, target_affine)

    return ThinPlateSplineTransform(
        interpolator=interpolator,
        source_center=source_center,
        source_scale=source_scale,
        output_center=output_center if output_affine is not None else None,
        output_affine=output_affine,
    )


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
    kernel, epsilon, degree, plus the source normalization center/scale) that
    reconstruct an equivalent ``RBFInterpolator``, not the fitted object itself.

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
        n_dim = interpolator.y.shape[1]
        source_center = (
            transform.source_center if transform.source_center is not None else np.zeros(n_dim)
        )
        output_center = (
            transform.output_center if transform.output_center is not None else np.zeros(n_dim)
        )
        output_affine = (
            transform.output_affine if transform.output_affine is not None else np.eye(n_dim)
        )
        np.savez(
            path,
            kind="tps",
            y=interpolator.y,
            d=interpolator.d,
            smoothing=interpolator.smoothing,
            epsilon=np.asarray(interpolator.epsilon),
            kernel=np.asarray(interpolator.kernel),
            degree=np.asarray(degree),
            source_center=np.asarray(source_center),
            source_scale=np.asarray(transform.source_scale),
            output_center=np.asarray(output_center),
            output_affine=np.asarray(output_affine),
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
            # `source_center`/`source_scale` postdate this format — older
            # saves (no normalization) default to the identity normalization.
            source_center = (
                data["source_center"]
                if "source_center" in data
                else np.zeros(interpolator.y.shape[1])
            )
            source_scale = float(data["source_scale"]) if "source_scale" in data else 1.0
            # `output_*` (area/shape regularization) postdates the format.
            # New saves carry `output_affine` (2x2); an older save may carry
            # the isotropic `output_area_scale` (float) instead; oldest carry
            # neither -> a no-op.
            if "output_affine" in data:
                output_affine = np.asarray(data["output_affine"])
                if np.allclose(output_affine, np.eye(output_affine.shape[0])):
                    output_affine = None
            elif "output_area_scale" in data and float(data["output_area_scale"]) != 1.0:
                output_affine = float(data["output_area_scale"]) * np.eye(interpolator.y.shape[1])
            else:
                output_affine = None
            output_center = (
                data["output_center"]
                if "output_center" in data and output_affine is not None
                else None
            )
            return ThinPlateSplineTransform(
                interpolator=interpolator,
                source_center=source_center,
                source_scale=source_scale,
                output_center=output_center,
                output_affine=output_affine,
            )
        raise ValueError(f"unknown transform kind {kind!r} in {path}")
