"""Generic 2D similarity-transform fitting from paired points.

Deliberately decoupled from *how* the paired points were obtained (shared
cluster centroids in :mod:`celldega.align.serial_slices` today; manually
placed landmarks in a future paired multi-Z/multi-modality Landscape view)
so the same fit/apply code can be reused by both.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


__all__ = ["SimilarityTransform", "fit_similarity_transform"]


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
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    if source.shape != target.shape:
        raise ValueError(
            f"source and target must have the same shape, got {source.shape} vs {target.shape}"
        )
    if source.shape[0] < 2 or source.shape[1] != 2:
        raise ValueError(f"source/target must be (n, 2) with n >= 2, got {source.shape}")

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
