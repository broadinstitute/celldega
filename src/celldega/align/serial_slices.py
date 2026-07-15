"""Alignment of serial 3D slices at single-cell resolution.

Serial tissue sections are typically imaged and segmented independently, so
even adjacent slices can be offset, rotated, or warped relative to each
other. :func:`align_serial_slices` in-plane registers a series of slices by
fitting a transform between corresponding landmarks, then applying that
transform to every cell in the slice — not just the landmarks used to fit
it. Slices are aligned in a chain outward from a chosen reference slice,
since physical section-to-section deformation accumulates between
neighbors rather than between a slice and a distant reference. Because
these are physical sections of the same tissue block, alignment is always
rigid — any apparent size difference between slices is a measurement or
segmentation artifact, not something to correct for, so scaling is never
applied.

:func:`align_serial_slices` itself knows nothing about cell metadata — only
each cell's physical location (``obsm["spatial"]``) and a ``landmarks``
table of corresponding points to fit against. Landmarks are always built by
the caller: :func:`~celldega.align.landmarks.calc_landmarks` computes them
from shared cluster labels, and manually-placed landmarks (e.g. from a
future point-drawing widget) use the same shape — the two are directly
``pandas.concat``-able for a semi-manual mix, before either is passed in
here. This keeps landmarks a visible, inspectable, disk-portable artifact
of the workflow rather than something hidden inside the alignment call.
"""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from typing import Any

import anndata as ad
from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.align._slices import _ordered_slices
from celldega.align._transform import (
    Transform,
    fit_transform_procrustes,
    fit_transform_tps,
    leave_one_out_residuals,
)


__all__ = ["align_serial_slices"]

_METHODS = ("procrustes", "tps")


def _validate_slices(slices: list[AnnData], slice_ids: list[Any]) -> None:
    for slice_id, adata in zip(slice_ids, slices, strict=True):
        spatial = adata.obsm.get("spatial")
        if spatial is None or np.asarray(spatial).shape[1] < 2:
            raise ValueError(
                f"slice {slice_id!r} must have obsm['spatial'] with at least 2 columns (x, y)"
            )


def _validate_landmarks(landmarks: pd.DataFrame, slice_key: str) -> None:
    required = {slice_key, "label", "x", "y"}
    missing = required - set(landmarks.columns)
    if missing:
        raise ValueError(f"landmarks is missing required column(s): {sorted(missing)}")


def _slice_landmarks(landmarks: pd.DataFrame, slice_id: Any, slice_key: str) -> pd.DataFrame:
    """One slice's landmarks as a ``label``-indexed ``x``/``y``/``count`` table."""
    subset = landmarks.loc[landmarks[slice_key] == slice_id]
    if subset.empty:
        raise ValueError(f"landmarks has no rows for slice {slice_id!r}")
    if subset["label"].duplicated().any():
        dupes = sorted(subset.loc[subset["label"].duplicated(), "label"].unique())
        raise ValueError(
            f"slice {slice_id!r} has duplicate landmark label(s) {dupes} in landmarks; "
            "labels must be unique per slice"
        )
    count = (
        subset["count"].to_numpy(dtype=float)
        if "count" in subset.columns
        else np.full(len(subset), np.nan)
    )
    return pd.DataFrame(
        {
            "x": subset["x"].to_numpy(dtype=float),
            "y": subset["y"].to_numpy(dtype=float),
            "count": count,
        },
        index=pd.Index(subset["label"].astype(str).to_numpy(), name="label"),
    )


def _adjacent_count_weights(
    weight_by_adjacent_counts: bool,
    labels: pd.Index,
    current_counts: pd.Series,
    neighbor_counts: pd.Series,
) -> np.ndarray | None:
    """Per-landmark fit weight from cell count in the current slice and its
    neighbor window (geometric mean), or ``None`` if disabled.

    Falls back to a neutral weight of ``1.0`` for a landmark whose count is
    ``NaN`` on either side (e.g. a manually-placed landmark has no cell
    population), rather than propagating ``NaN`` into the fit.
    """
    if not weight_by_adjacent_counts:
        return None
    current = current_counts.loc[labels].to_numpy(dtype=float)
    neighbor = neighbor_counts.loc[labels].to_numpy(dtype=float)
    weight = np.sqrt(current * neighbor)
    weight[np.isnan(weight)] = 1.0
    return weight


def _pooled_neighbor_stats(
    centroids_cache: list[pd.DataFrame], window_idxs: list[int]
) -> pd.DataFrame:
    """Average already-aligned centroid position (and summed cell count) across a window of neighbors."""
    stacked = pd.concat([centroids_cache[j] for j in window_idxs])
    return stacked.groupby(level=0).agg(
        x=("x", "mean"),
        y=("y", "mean"),
        count=("count", lambda s: s.sum(min_count=1)),
    )


def _resolve_fit_function(
    method: str, allow_reflection: bool, smoothing: float
) -> Callable[..., Transform]:
    if method == "procrustes":

        def _fit(
            source: np.ndarray, target: np.ndarray, weights: np.ndarray | None = None
        ) -> Transform:
            return fit_transform_procrustes(
                source,
                target,
                weights=weights,
                allow_scaling=False,
                allow_reflection=allow_reflection,
            )

        return _fit
    if method == "tps":

        def _fit(
            source: np.ndarray, target: np.ndarray, weights: np.ndarray | None = None
        ) -> Transform:
            return fit_transform_tps(source, target, weights=weights, smoothing=smoothing)

        return _fit
    raise ValueError(f"method must be one of {_METHODS}, got {method!r}")


def _transform_summary(transform: Transform) -> dict[str, Any]:
    """Best-effort, serialization-safe snapshot of a fitted transform's numeric fields.

    Different fit strategies expose different fields (rotation/scale/translation
    for a rigid fit, an opaque interpolator object for a spline) — only include
    fields that are safe to stash in ``uns`` (and skip the rest) rather than
    hardcoding knowledge of any one strategy here.
    """
    if not dataclasses.is_dataclass(transform):
        return {}
    return {
        f.name: getattr(transform, f.name)
        for f in dataclasses.fields(transform)
        if isinstance(getattr(transform, f.name), (int, float, str, bool, np.ndarray))
    }


def _z_values(n: int, reference: int, z_space: float, z_coord: list[float] | None) -> np.ndarray:
    if z_coord is None:
        return (np.arange(n) - reference) * float(z_space)

    z_coord = np.asarray(list(z_coord), dtype=float)
    if z_coord.shape != (n,):
        raise ValueError(
            f"z_coord must have length {n} (one absolute value per slice), got {z_coord.shape[0]}"
        )
    return z_coord


def align_serial_slices(
    adatas: AnnData | list[AnnData],
    landmarks: pd.DataFrame,
    slice_key: str | None = None,
    z_space: float = 1.0,
    z_coord: list[float] | None = None,
    reference: int = 0,
    min_shared_landmarks: int = 3,
    alignment_window: int = 1,
    method: str = "procrustes",
    allow_reflection: bool = False,
    smoothing: float = 0.0,
    weight_by_adjacent_counts: bool = True,
    compute_residuals: bool = True,
    key_added: str = "Z",
) -> AnnData:
    """In-plane align serial slices from corresponding landmarks.

    Each slice is registered onto a window of its already-aligned neighbors
    by fitting a transform between corresponding landmarks, then applying
    that transform to every cell in the slice — not just the landmarks used
    to fit it. Alignment proceeds as a chain outward from ``reference`` in
    both directions along the slice order, so deformation is modeled
    between nearby physical neighbors rather than against a single distant
    reference. Rescaling is never applied (see module docstring).

    Args:
        adatas: Either a list of per-slice ``AnnData`` (list order is slice
            order), or a single ``AnnData`` combining all slices, in which
            case ``slice_key`` is required to split it into slices. Only
            ``obsm["spatial"]`` is used — this function has no knowledge of
            cell metadata; landmarks are supplied separately.
        landmarks: A plain ``DataFrame`` of landmarks to fit against, with
            columns ``slice_key`` (values matching the resolved slice ids),
            ``label`` (matches a landmark across slices; unique per slice),
            ``x``/``y`` (in that slice's own ``obsm["spatial"]`` coordinate
            space), and optionally ``count`` (omit or leave ``NaN`` for a
            landmark with no natural cell count, e.g. a manually-placed
            one). Build this with
            :func:`~celldega.align.landmarks.calc_landmarks` (one call per
            slice, then ``pandas.concat``), a manually-placed landmark
            table in the same shape, or both concatenated together for a
            semi-manual mix.
        slice_key: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice (required in that case). For a
            list of ``AnnData``, the name to give the new ``obs`` column
            recording each cell's origin slice index in the output, and the
            column ``landmarks`` uses to identify each row's slice (default
            ``"slice"``).
        z_space: Uniform distance between consecutive slices, applied
            outward from ``reference`` (so the reference slice is ``Z = 0``).
            Ignored if ``z_coord`` is given.
        z_coord: Explicit absolute Z value for each slice (length
            ``n_slices``, matching slice order) — use this when slices have
            known, unevenly spaced, or non-reference-relative Z positions
            (e.g. from instrument metadata). Overrides ``z_space`` entirely
            when given; ``reference`` still controls which slice anchors the
            spatial-alignment chain, but no longer shifts Z.
        reference: Index (into the slice order) of the slice that is left
            untransformed; other slices are aligned outward from it.
        min_shared_landmarks: Minimum number of landmark labels a slice and
            its neighbor window must share to fit a transform between them.
        alignment_window: Number of already-aligned neighboring slices (in
            the same chain direction) to register each new slice against,
            instead of only the single immediately-previous one. A landmark
            label's target position is averaged across whichever of those
            neighbors have it. Stays a *local*, neighbor-window operation —
            never reaches back to a single distant reference — while
            reducing sensitivity to any one neighbor's noise. ``1``
            (default) reproduces the original single-neighbor chain exactly.
        method: ``"procrustes"`` (default) for a rigid rotation + translation
            fit (:func:`~celldega.align._transform.fit_transform_procrustes`,
            always with scaling disabled — see module docstring), or
            ``"tps"`` for a non-rigid thin-plate-spline warp
            (:func:`~celldega.align._transform.fit_transform_tps`) for
            deformation a single global transform can't capture.
        allow_reflection: ``method="procrustes"`` only. If ``False``
            (default), disallow mirrored fits, since flipping a tissue
            section is not physically valid.
        smoothing: ``method="tps"`` only. Bending-energy penalty passed to
            the thin-plate-spline fit; ``0`` (default) interpolates
            landmarks exactly.
        weight_by_adjacent_counts: If ``True`` (default), weight each shared
            landmark by the geometric mean of its cell count in the current
            slice and its neighbor window (a centroid from more cells is a
            lower-variance estimate) — a landmark with no count (e.g.
            manually placed) is weighted neutrally. Set ``False`` to weight
            every landmark equally.
        compute_residuals: If ``True`` (default), compute and record each
            slice's per-landmark leave-one-out residual (see
            :func:`~celldega.align._transform.leave_one_out_residuals`) —
            unlike in-sample residual, this is meaningful even for an
            exactly-interpolating fit like TPS. Set ``False`` to skip the
            extra refits if landmark counts ever make it costly.
        key_added: Name of the new per-cell ``obs`` column holding the
            assigned Z position.

    Returns:
        A new ``AnnData`` concatenating all slices, with ``obsm["spatial"]``
        x/y columns replaced by the aligned coordinates, a new
        ``obs[key_added]`` Z column, and provenance recorded in
        ``uns["align_serial_slices"]``: the fit parameters, per-slice
        transform details (including leave-one-out residuals, if computed),
        the ``landmarks`` given (``"landmarks_initial"``), and every
        landmark's final aligned position (``"landmarks_aligned"``) — useful
        for reproducibility and for deciding where to add further manual
        landmarks in a follow-up, iterative pass.

    Raises:
        ValueError: If ``adatas`` is a single ``AnnData`` without
            ``slice_key``, if fewer than 2 slices are given, if a slice is
            missing ``obsm["spatial"]``, if ``landmarks`` is missing a
            required column or has no rows for some slice, if ``reference``
            is out of range, if ``z_coord`` is given with the wrong length,
            if ``alignment_window`` is less than 1, if ``method`` is not
            recognized, if a slice's landmarks contain duplicate labels, if
            a slice shares fewer than ``min_shared_landmarks`` labels with
            its neighbor window, or if the fit itself rejects the shared
            landmarks (e.g. a degenerate configuration for TPS).
    """
    slice_ids, slices, slice_key = _ordered_slices(adatas, slice_key)
    n = len(slices)
    if n < 2:
        raise ValueError("align_serial_slices requires at least 2 slices")
    if not 0 <= reference < n:
        raise ValueError(f"reference must be in [0, {n - 1}], got {reference}")
    if alignment_window < 1:
        raise ValueError(f"alignment_window must be >= 1, got {alignment_window}")
    _validate_landmarks(landmarks, slice_key)
    fit_transform = _resolve_fit_function(method, allow_reflection, smoothing)
    _validate_slices(slices, slice_ids)

    all_stats = [_slice_landmarks(landmarks, slice_id, slice_key) for slice_id in slice_ids]

    aligned_slices: list[AnnData | None] = [None] * n
    centroids_cache: list[pd.DataFrame | None] = [None] * n
    transform_log: dict[str, Any] = {}

    aligned_slices[reference] = slices[reference]
    centroids_cache[reference] = all_stats[reference]

    for chain in (range(reference - 1, -1, -1), range(reference + 1, n)):
        processed = [reference]
        for idx in chain:
            current = slices[idx]
            current_stats = all_stats[idx]
            window_idxs = processed[-alignment_window:]
            neighbor_stats = _pooled_neighbor_stats(centroids_cache, window_idxs)

            shared = current_stats.index.intersection(neighbor_stats.index)
            if len(shared) < min_shared_landmarks:
                raise ValueError(
                    f"slice {slice_ids[idx]!r} shares only {len(shared)} landmark label(s) with "
                    f"its neighbor window {[str(slice_ids[j]) for j in window_idxs]!r} "
                    f"(need >= {min_shared_landmarks}). Check that landmark labels are "
                    "consistent across slices."
                )

            weights = _adjacent_count_weights(
                weight_by_adjacent_counts,
                shared,
                current_stats["count"],
                neighbor_stats["count"],
            )
            source = current_stats.loc[shared, ["x", "y"]].to_numpy()
            target = neighbor_stats.loc[shared, ["x", "y"]].to_numpy()
            transform = fit_transform(source, target, weights=weights)

            spatial = np.asarray(current.obsm["spatial"], dtype=float).copy()
            spatial[:, :2] = transform.apply(spatial[:, :2])
            current.obsm["spatial"] = spatial
            aligned_slices[idx] = current

            aligned_xy = transform.apply(current_stats[["x", "y"]].to_numpy())
            centroids_cache[idx] = pd.DataFrame(
                {
                    "x": aligned_xy[:, 0],
                    "y": aligned_xy[:, 1],
                    "count": current_stats["count"].to_numpy(),
                },
                index=current_stats.index,
            )

            residual_summary = None
            if compute_residuals:
                residuals = leave_one_out_residuals(source, target, fit_transform, weights=weights)
                per_landmark = dict(zip(shared, residuals, strict=True))
                finite = [v for v in per_landmark.values() if np.isfinite(v)]
                residual_summary = {
                    "per_landmark": {
                        str(label): float(value) for label, value in per_landmark.items()
                    },
                    "mean": float(np.mean(finite)) if finite else None,
                    "median": float(np.median(finite)) if finite else None,
                    "max": float(np.max(finite)) if finite else None,
                }

            entry = {
                "aligned_to": [str(slice_ids[j]) for j in window_idxs],
                "n_shared_landmarks": len(shared),
                **_transform_summary(transform),
            }
            if residual_summary is not None:
                entry["leave_one_out_residual"] = residual_summary
            transform_log[str(slice_ids[idx])] = entry
            processed.append(idx)

    z_values = _z_values(n, reference, z_space, z_coord)
    for idx, adata in enumerate(aligned_slices):
        adata.obs[key_added] = z_values[idx]
        adata.obs[slice_key] = slice_ids[idx]

    aligned_frames = []
    for idx, stats in enumerate(centroids_cache):
        frame = stats.reset_index()
        frame[slice_key] = slice_ids[idx]
        aligned_frames.append(frame)
    landmarks_aligned = pd.concat(aligned_frames, ignore_index=True)[
        [slice_key, "label", "x", "y", "count"]
    ]

    adata_aligned = ad.concat(aligned_slices, join="outer")
    adata_aligned.uns["align_serial_slices"] = {
        "slice_key": slice_key,
        "reference": str(slice_ids[reference]),
        "alignment_window": alignment_window,
        "method": method,
        "allow_reflection": allow_reflection,
        "smoothing": smoothing,
        "weight_by_adjacent_counts": weight_by_adjacent_counts,
        "transforms": transform_log,
        "landmarks_initial": landmarks.copy(),
        "landmarks_aligned": landmarks_aligned,
    }
    return adata_aligned
