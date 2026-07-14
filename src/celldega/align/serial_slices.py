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

import dataclasses
from typing import Any, Callable

import anndata as ad
from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.align._transform import Transform, fit_similarity_transform


__all__ = ["align_serial_slices"]


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


def _cluster_centroids(adata: AnnData, cluster_key: str) -> pd.DataFrame:
    xy = np.asarray(adata.obsm["spatial"])[:, :2]
    df = pd.DataFrame(xy, columns=["x", "y"], index=adata.obs_names)
    df["cluster"] = adata.obs[cluster_key].astype(str).to_numpy()
    return df.groupby("cluster")[["x", "y"]].mean()


def _callable_name(fn: Callable) -> str:
    return getattr(fn, "__name__", None) or getattr(getattr(fn, "func", None), "__name__", None) or repr(fn)


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


def _z_offsets(n: int, reference: int, z_spacing: float | list[float]) -> np.ndarray:
    if isinstance(z_spacing, (int, float)):
        return (np.arange(n) - reference) * float(z_spacing)

    spacing = np.asarray(list(z_spacing), dtype=float)
    if spacing.shape != (n - 1,):
        raise ValueError(
            f"z_spacing list must have length {n - 1} (n_slices - 1), got {spacing.shape[0]}"
        )
    positions = np.concatenate([[0.0], np.cumsum(spacing)])
    return positions - positions[reference]


def align_serial_slices(
    adatas: AnnData | list[AnnData],
    cluster_key: str,
    slice_key: str | None = None,
    z_spacing: float | list[float] = 1.0,
    reference: int = 0,
    min_shared_clusters: int = 3,
    fit_transform: Callable[[np.ndarray, np.ndarray], Transform] = fit_similarity_transform,
    key_added: str = "Z",
) -> AnnData:
    """In-plane align serial slices from shared cluster centroids.

    Each slice is registered onto its already-aligned neighbor by fitting a
    transform between the centroids of clusters the two slices have in
    common, then applying that transform to every cell in the slice — not
    just the centroids used to fit it. Alignment proceeds as a chain outward
    from ``reference`` in both directions along the slice order, so
    deformation is modeled between physical neighbors rather than against a
    single distant reference.

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
        z_spacing: Either a single distance applied uniformly between
            consecutive slices, or a list of length ``n_slices - 1`` giving
            the distance between each pair of consecutive slices in input
            order (for unevenly spaced sections).
        reference: Index (into the slice order) of the slice that is left
            untransformed; other slices are aligned outward from it.
        min_shared_clusters: Minimum number of cluster labels two neighboring
            slices must share to fit a transform between them.
        fit_transform: A ``fit(source, target) -> Transform`` callable used to
            register each slice onto its neighbor, where ``source``/``target``
            are ``(n, 2)`` arrays of corresponding cluster centroids and the
            returned object implements ``.apply(points)``. Defaults to
            :func:`~celldega.align._transform.fit_similarity_transform`
            (rigid rotation + uniform scale + translation). Pass
            :func:`~celldega.align._transform.fit_thin_plate_spline` for a
            non-rigid warp instead, or bind either one's extra keyword
            arguments with :func:`functools.partial` (e.g.
            ``partial(fit_similarity_transform, allow_scaling=False)``).
        key_added: Name of the new per-cell ``obs`` column holding the
            assigned Z position.

    Returns:
        A new ``AnnData`` concatenating all slices, with ``obsm["spatial"]``
        x/y columns replaced by the aligned coordinates, a new
        ``obs[key_added]`` Z column, and per-slice transform parameters
        recorded in ``uns["align_serial_slices"]``.

    Raises:
        ValueError: If ``adatas`` is a single ``AnnData`` without
            ``slice_key``, if fewer than 2 slices are given, if a slice is
            missing ``cluster_key`` or ``obsm["spatial"]``, if ``reference``
            is out of range, if ``z_spacing`` is a list of the wrong length,
            if two neighboring slices share fewer than
            ``min_shared_clusters`` cluster labels, or if ``fit_transform``
            itself rejects the shared centroids (e.g. a degenerate landmark
            configuration).
    """
    slice_ids, slices, slice_key = _ordered_slices(adatas, slice_key)
    n = len(slices)
    if not 0 <= reference < n:
        raise ValueError(f"reference must be in [0, {n - 1}], got {reference}")
    _validate_slices(slices, slice_ids, cluster_key)

    aligned_slices: list[AnnData | None] = [None] * n
    centroids_cache: list[pd.DataFrame | None] = [None] * n
    transform_log: dict[str, Any] = {}

    aligned_slices[reference] = slices[reference]
    centroids_cache[reference] = _cluster_centroids(slices[reference], cluster_key)

    for chain in (range(reference - 1, -1, -1), range(reference + 1, n)):
        prev_idx = reference
        for idx in chain:
            current = slices[idx]
            current_centroids = _cluster_centroids(current, cluster_key)
            prev_centroids = centroids_cache[prev_idx]

            shared = current_centroids.index.intersection(prev_centroids.index)
            if len(shared) < min_shared_clusters:
                raise ValueError(
                    f"slice {slice_ids[idx]!r} shares only {len(shared)} cluster label(s) with "
                    f"slice {slice_ids[prev_idx]!r} (need >= {min_shared_clusters}). Check that "
                    f"'{cluster_key}' labels are consistent across slices."
                )

            transform = fit_transform(
                current_centroids.loc[shared].to_numpy(),
                prev_centroids.loc[shared].to_numpy(),
            )

            spatial = np.asarray(current.obsm["spatial"], dtype=float).copy()
            spatial[:, :2] = transform.apply(spatial[:, :2])
            current.obsm["spatial"] = spatial
            aligned_slices[idx] = current

            centroids_cache[idx] = pd.DataFrame(
                transform.apply(current_centroids.to_numpy()),
                columns=["x", "y"],
                index=current_centroids.index,
            )
            transform_log[str(slice_ids[idx])] = {
                "aligned_to": str(slice_ids[prev_idx]),
                "n_shared_clusters": len(shared),
                **_transform_summary(transform),
            }
            prev_idx = idx

    z_values = _z_offsets(n, reference, z_spacing)
    for idx, adata in enumerate(aligned_slices):
        adata.obs[key_added] = z_values[idx]
        adata.obs[slice_key] = slice_ids[idx]

    combined = ad.concat(aligned_slices, join="outer")
    combined.uns["align_serial_slices"] = {
        "cluster_key": cluster_key,
        "slice_key": slice_key,
        "reference": str(slice_ids[reference]),
        "fit_transform": _callable_name(fit_transform),
        "transforms": transform_log,
    }
    return combined
