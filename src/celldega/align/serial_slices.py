"""Alignment of serial 3D slices at single-cell resolution.

Serial tissue sections are typically imaged and segmented independently, so
even adjacent slices can be offset, rotated, warped, or slightly rescaled
relative to each other. :func:`align_serial_slices` in-plane registers a
series of slices by fitting a transform between the centroids of clusters
shared by neighboring slices, then applying that transform to every cell in
the slice — not just the centroids used to fit it. Slices are aligned in a
chain outward from a chosen reference slice, since physical section-to-
section deformation accumulates between neighbors rather than between a
slice and a distant reference. The fitting algorithm itself (rigid Procrustes
by default, thin-plate-spline, or any other ``fit(source, target) ->
Transform`` callable) is injected via ``fit_transform``, so it plugs in
without changing this orchestration.
"""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from typing import Any

import anndata as ad
from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.align._transform import (
    Transform,
    fit_similarity_transform,
    leave_one_out_residuals,
)


__all__ = ["align_serial_slices"]

_CLUSTER_WEIGHT_MODES = ("cell_count", "presence", "cell_count_and_presence")


def _ordered_slices(
    adatas: AnnData | list[AnnData], slice_key: str | None
) -> tuple[list[Any], list[AnnData], str]:
    if isinstance(adatas, AnnData):
        if slice_key is None:
            raise ValueError(
                "slice_key is required when 'adatas' is a single combined AnnData, "
                "so slices can be identified from an obs column"
            )
        if slice_key not in adatas.obs.columns:
            raise ValueError(f"'{slice_key}' is not a column in adatas.obs")

        column = adatas.obs[slice_key]
        if isinstance(column.dtype, pd.CategoricalDtype) and column.dtype.ordered:
            slice_ids = [c for c in column.dtype.categories if c in column.unique()]
        else:
            slice_ids = sorted(column.unique().tolist())
        slices = [adatas[column == slice_id].copy() for slice_id in slice_ids]
        return slice_ids, slices, slice_key

    slices = list(adatas)
    if len(slices) < 2:
        raise ValueError("align_serial_slices requires at least 2 slices")
    slice_ids = list(range(len(slices)))
    return slice_ids, [s.copy() for s in slices], slice_key or "slice"


def _validate_slices(slices: list[AnnData], slice_ids: list[Any], cluster_key: str) -> None:
    for slice_id, adata in zip(slice_ids, slices, strict=True):
        if cluster_key not in adata.obs.columns:
            raise ValueError(f"'{cluster_key}' is not a column in obs of slice {slice_id!r}")
        spatial = adata.obsm.get("spatial")
        if spatial is None or np.asarray(spatial).shape[1] < 2:
            raise ValueError(
                f"slice {slice_id!r} must have obsm['spatial'] with at least 2 columns (x, y)"
            )


def _cluster_stats(adata: AnnData, cluster_key: str) -> pd.DataFrame:
    """Per-cluster centroid (``x``, ``y``) and cell ``count`` for one slice."""
    xy = np.asarray(adata.obsm["spatial"])[:, :2]
    df = pd.DataFrame(xy, columns=["x", "y"], index=adata.obs_names)
    df["cluster"] = adata.obs[cluster_key].astype(str).to_numpy()
    grouped = df.groupby("cluster")
    stats = grouped[["x", "y"]].mean()
    stats["count"] = grouped.size()
    return stats


def _presence_fractions(all_stats: list[pd.DataFrame]) -> dict[str, float]:
    """Fraction of all slices in which each cluster label appears at all."""
    n = len(all_stats)
    counts: dict[str, int] = {}
    for stats in all_stats:
        for label in stats.index:
            counts[label] = counts.get(label, 0) + 1
    return {label: count / n for label, count in counts.items()}


def _cluster_weights(
    cluster_weight: str | None,
    labels: pd.Index,
    current_counts: pd.Series,
    neighbor_counts: pd.Series,
    presence_fraction: dict[str, float],
) -> np.ndarray | None:
    """Per-landmark fit weight from cell count and/or cross-slice presence, or ``None``."""
    if cluster_weight is None:
        return None
    weight = np.ones(len(labels))
    if cluster_weight in ("cell_count", "cell_count_and_presence"):
        current = current_counts.loc[labels].to_numpy(dtype=float)
        neighbor = neighbor_counts.loc[labels].to_numpy(dtype=float)
        weight = weight * np.sqrt(current * neighbor)
    if cluster_weight in ("presence", "cell_count_and_presence"):
        weight = weight * np.array([presence_fraction[label] for label in labels])
    return weight


def _pooled_neighbor_stats(
    centroids_cache: list[pd.DataFrame], window_idxs: list[int]
) -> pd.DataFrame:
    """Average already-aligned centroid position (and summed cell count) across a window of neighbors."""
    stacked = pd.concat([centroids_cache[j] for j in window_idxs])
    return stacked.groupby(level=0).agg(x=("x", "mean"), y=("y", "mean"), count=("count", "sum"))


def _callable_name(fn: Callable) -> str:
    return (
        getattr(fn, "__name__", None)
        or getattr(getattr(fn, "func", None), "__name__", None)
        or repr(fn)
    )


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
    cluster_key: str,
    slice_key: str | None = None,
    z_space: float = 1.0,
    z_coord: list[float] | None = None,
    reference: int = 0,
    min_shared_clusters: int = 3,
    alignment_window: int = 1,
    cluster_weight: str | None = None,
    fit_transform: Callable[..., Transform] = fit_similarity_transform,
    compute_residuals: bool = True,
    key_added: str = "Z",
) -> AnnData:
    """In-plane align serial slices from shared cluster centroids.

    Each slice is registered onto a window of its already-aligned neighbors
    by fitting a transform between the centroids of clusters they have in
    common, then applying that transform to every cell in the slice — not
    just the centroids used to fit it. Alignment proceeds as a chain outward
    from ``reference`` in both directions along the slice order, so
    deformation is modeled between nearby physical neighbors rather than
    against a single distant reference.

    Args:
        adatas: Either a list of per-slice ``AnnData`` (list order is slice
            order), or a single ``AnnData`` combining all slices, in which
            case ``slice_key`` is required to split it into slices.
        cluster_key: ``obs`` column with cluster labels used to compute the
            per-slice, per-cluster centroids used as landmarks for the fit.
            Labels must be comparable across slices (e.g. a joint clustering).
        slice_key: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice (required in that case). For a list
            of ``AnnData``, the name to give the new ``obs`` column recording
            each cell's origin slice index in the output (default ``"slice"``).
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
        min_shared_clusters: Minimum number of cluster labels a slice and its
            neighbor window must share to fit a transform between them.
        alignment_window: Number of already-aligned neighboring slices (in
            the same chain direction) to register each new slice against,
            instead of only the single immediately-previous one. A cluster
            label's target landmark is averaged across whichever of those
            neighbors have it. Stays a *local*, neighbor-window operation —
            never reaches back to a single distant reference — while
            reducing sensitivity to any one neighbor's noise. ``1``
            (default) reproduces the original single-neighbor chain exactly.
        cluster_weight: How much to trust each shared cluster as a landmark,
            passed to ``fit_transform`` as per-landmark ``weights``. One of:
            ``None`` (default, every cluster weighted equally),
            ``"cell_count"`` (weight by the geometric mean of the cluster's
            cell count in the current slice and its neighbor window — a
            centroid from more cells is a lower-variance estimate),
            ``"presence"`` (weight by the fraction of *all* slices in which
            the label appears at all — a cluster present broadly across the
            stack is a more plausible stable landmark than one confined to
            two adjacent slices), or ``"cell_count_and_presence"`` (both,
            multiplied).
        fit_transform: A ``fit(source, target, weights=None) -> Transform``
            callable used to register each slice onto its neighbor window,
            where ``source``/``target`` are ``(n, 2)`` arrays of
            corresponding cluster centroids and the returned object
            implements ``.apply(points)``. Defaults to
            :func:`~celldega.align._transform.fit_similarity_transform`
            (rigid rotation + uniform scale + translation). Pass
            :func:`~celldega.align._transform.fit_thin_plate_spline` for a
            non-rigid warp instead, or bind either one's extra keyword
            arguments with :func:`functools.partial` (e.g.
            ``partial(fit_similarity_transform, allow_scaling=False)``).
        compute_residuals: If ``True`` (default), compute and record each
            slice's per-cluster leave-one-out landmark residual (see
            :func:`~celldega.align._transform.leave_one_out_residuals`) —
            unlike in-sample residual, this is meaningful even for an
            exactly-interpolating fit like TPS. Set ``False`` to skip the
            extra refits if landmark counts ever make it costly.
        key_added: Name of the new per-cell ``obs`` column holding the
            assigned Z position.

    Returns:
        A new ``AnnData`` concatenating all slices, with ``obsm["spatial"]``
        x/y columns replaced by the aligned coordinates, a new
        ``obs[key_added]`` Z column, and per-slice transform parameters
        (including leave-one-out residuals, if computed) recorded in
        ``uns["align_serial_slices"]``.

    Raises:
        ValueError: If ``adatas`` is a single ``AnnData`` without
            ``slice_key``, if fewer than 2 slices are given, if a slice is
            missing ``cluster_key`` or ``obsm["spatial"]``, if ``reference``
            is out of range, if ``z_coord`` is given with the wrong length,
            if ``alignment_window`` is less than 1, if ``cluster_weight`` is
            not a recognized preset, if a slice shares fewer than
            ``min_shared_clusters`` cluster labels with its neighbor window,
            or if ``fit_transform`` itself rejects the shared centroids (e.g.
            a degenerate landmark configuration).
    """
    slice_ids, slices, slice_key = _ordered_slices(adatas, slice_key)
    n = len(slices)
    if not 0 <= reference < n:
        raise ValueError(f"reference must be in [0, {n - 1}], got {reference}")
    if alignment_window < 1:
        raise ValueError(f"alignment_window must be >= 1, got {alignment_window}")
    if cluster_weight is not None and cluster_weight not in _CLUSTER_WEIGHT_MODES:
        raise ValueError(
            f"cluster_weight must be one of {_CLUSTER_WEIGHT_MODES} or None, got {cluster_weight!r}"
        )
    _validate_slices(slices, slice_ids, cluster_key)

    all_stats = [_cluster_stats(slice_, cluster_key) for slice_ in slices]
    presence_fraction = _presence_fractions(all_stats)

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
            if len(shared) < min_shared_clusters:
                raise ValueError(
                    f"slice {slice_ids[idx]!r} shares only {len(shared)} cluster label(s) with "
                    f"its neighbor window {[str(slice_ids[j]) for j in window_idxs]!r} "
                    f"(need >= {min_shared_clusters}). Check that '{cluster_key}' labels are "
                    "consistent across slices."
                )

            weights = _cluster_weights(
                cluster_weight,
                shared,
                current_stats["count"],
                neighbor_stats["count"],
                presence_fraction,
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
                per_cluster = dict(zip(shared, residuals, strict=True))
                finite = [v for v in per_cluster.values() if np.isfinite(v)]
                residual_summary = {
                    "per_cluster": {
                        str(label): float(value) for label, value in per_cluster.items()
                    },
                    "mean": float(np.mean(finite)) if finite else None,
                    "median": float(np.median(finite)) if finite else None,
                    "max": float(np.max(finite)) if finite else None,
                }

            entry = {
                "aligned_to": [str(slice_ids[j]) for j in window_idxs],
                "n_shared_clusters": len(shared),
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

    combined = ad.concat(aligned_slices, join="outer")
    combined.uns["align_serial_slices"] = {
        "cluster_key": cluster_key,
        "slice_key": slice_key,
        "reference": str(slice_ids[reference]),
        "alignment_window": alignment_window,
        "cluster_weight": cluster_weight,
        "fit_transform": _callable_name(fit_transform),
        "transforms": transform_log,
    }
    return combined
