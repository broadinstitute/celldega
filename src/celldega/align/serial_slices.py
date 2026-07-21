"""Alignment of serial 3D slices at single-cell resolution.

Serial tissue sections are typically imaged and segmented independently, so
even adjacent slices can be offset, rotated, or warped relative to each
other. This module splits registering them into three composable steps:

1. :func:`~celldega.align.landmarks.calc_landmarks` — corresponding points
   per slice, from shared cluster labels (or manually placed, or both).
2. :func:`calc_alignment_transform` — fits a transform between corresponding
   landmarks (chain-walking outward from a reference slice, since physical
   section-to-section deformation accumulates between neighbors rather than
   between a slice and a distant reference) and returns a
   :class:`SerialAlignmentTransform` — a first-class, reusable object, not a
   byproduct that only lives inside one alignment call.
3. :func:`align_serial_slices` — applies a given :class:`SerialAlignmentTransform`
   to a specific set of ``AnnData``, aligning ``obsm["spatial"]`` and
   assigning a Z coordinate.

Splitting fit from apply means the fitted transform can be reused directly
on *other* point data tied to the same slices (segmentation-polygon
vertices, transcript coordinates, eventually raster image sampling grids —
anything reducible to an ``(n, 2)`` array of points), and persisted
independently of any one ``AnnData`` (:meth:`SerialAlignmentTransform.save`/
:meth:`~SerialAlignmentTransform.load`).

Because these are physical sections of the same tissue block, alignment is
always rigid when ``method="procrustes"`` — any apparent size difference
between slices is a measurement or segmentation artifact, not something to
correct for, so scaling is never applied.
"""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
import json
from pathlib import Path
from typing import Any
import warnings

import anndata as ad
from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.align._slices import _ordered_slices, _resolve_slice_order
from celldega.align._transform import (
    SimilarityTransform,
    Transform,
    fit_transform_procrustes,
    fit_transform_tps,
    leave_one_out_residuals,
    load_transform,
    save_transform,
)


__all__ = ["SerialAlignmentTransform", "align_serial_slices", "calc_alignment_transform"]

_METHODS = ("procrustes", "tps")

_IDENTITY_TRANSFORM = SimilarityTransform(rotation=np.eye(2), scale=1.0, translation=np.zeros(2))


def _validate_slices(slices: list[AnnData], slice_ids: list[Any]) -> None:
    for slice_id, adata in zip(slice_ids, slices, strict=True):
        spatial = adata.obsm.get("spatial")
        if spatial is None or np.asarray(spatial).shape[1] < 2:
            raise ValueError(
                f"slice {slice_id!r} must have obsm['spatial'] with at least 2 columns (x, y)"
            )


def _validate_landmarks(landmarks: pd.DataFrame, slice_attr: str) -> None:
    required = {slice_attr, "label", "x", "y"}
    missing = required - set(landmarks.columns)
    if missing:
        raise ValueError(f"landmarks is missing required column(s): {sorted(missing)}")


def _slice_landmarks(landmarks: pd.DataFrame, slice_id: Any, slice_attr: str) -> pd.DataFrame:
    """One slice's landmarks as a ``label``-indexed ``x``/``y``/``count`` table.

    ``slice_id`` always comes from resolving slice order directly out of
    ``landmarks[slice_attr]`` (see :func:`calc_alignment_transform`), so
    ``subset`` is guaranteed non-empty here by construction.
    """
    subset = landmarks.loc[landmarks[slice_attr] == slice_id]
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
    fields that are safe to stash in ``uns``/JSON (and skip the rest) rather than
    hardcoding knowledge of any one strategy here.
    """
    if not dataclasses.is_dataclass(transform):
        return {}
    return {
        f.name: getattr(transform, f.name)
        for f in dataclasses.fields(transform)
        if isinstance(getattr(transform, f.name), (int, float, str, bool, np.ndarray))
    }


def _json_safe(value: Any) -> Any:
    """Recursively convert numpy arrays/scalars in a nested dict/list into plain
    JSON-serializable Python types."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _z_values(n: int, reference: int, z_space: float, z_coord: list[float] | None) -> np.ndarray:
    if z_coord is None:
        return (np.arange(n) - reference) * float(z_space)

    z_coord = np.asarray(list(z_coord), dtype=float)
    if z_coord.shape != (n,):
        raise ValueError(
            f"z_coord must have length {n} (one absolute value per slice), got {z_coord.shape[0]}"
        )
    return z_coord


@dataclasses.dataclass(frozen=True)
class SerialAlignmentTransform:
    """A fitted, reusable serial-slice alignment.

    Returned by :func:`calc_alignment_transform`; consumed by
    :func:`align_serial_slices`. Holds one :class:`~celldega.align._transform.Transform`
    per slice (the reference slice's is an identity transform) and provenance
    from the fit — no Z information, since Z assignment doesn't affect the
    spatial fit at all and is decided when *applying* the transform (see
    :func:`align_serial_slices`'s ``z_space``/``z_coord``), not when fitting
    it. Persist it with :meth:`save`/:meth:`load` — everything here is plain
    data or a picklable-but-not-pickled ``RBFInterpolator``, so it also
    survives a plain :mod:`pickle` round-trip if that's more convenient.
    """

    slice_attr: str
    slice_ids: list[Any]
    reference: Any
    transforms: dict[Any, Transform]
    transform_log: dict[str, dict]
    landmarks_initial: pd.DataFrame
    landmarks_aligned: pd.DataFrame
    method: str
    allow_reflection: bool
    smoothing: float
    weight_by_adjacent_counts: bool
    alignment_window: int

    def apply_to_points(self, slice_id: Any, points: np.ndarray) -> np.ndarray:
        """Apply the fitted transform for ``slice_id`` to an ``(n, 2)`` array of points.

        The general reuse primitive: works identically for cell coordinates,
        segmentation-polygon vertices, transcript coordinates, or any other
        point data tied to that slice.
        """
        return self.transforms[slice_id].apply(points)

    def save(self, path: str | Path) -> None:
        """Save this transform to a directory of plain files — no ``pickle``.

        Layout: ``metadata.json`` (fit parameters, slice ids),
        ``transform_log.json`` (per-slice diagnostics), ``landmarks_initial
        .parquet``/``landmarks_aligned.parquet``, and one ``transforms/<slice
        id>.npz`` per slice (see :func:`~celldega.align._transform.save_transform`).
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        metadata = {
            "slice_attr": self.slice_attr,
            "slice_ids": self.slice_ids,
            "reference": self.reference,
            "method": self.method,
            "allow_reflection": self.allow_reflection,
            "smoothing": self.smoothing,
            "weight_by_adjacent_counts": self.weight_by_adjacent_counts,
            "alignment_window": self.alignment_window,
        }
        (path / "metadata.json").write_text(json.dumps(metadata, indent=2))
        (path / "transform_log.json").write_text(
            json.dumps(_json_safe(self.transform_log), indent=2)
        )
        self.landmarks_initial.to_parquet(path / "landmarks_initial.parquet")
        self.landmarks_aligned.to_parquet(path / "landmarks_aligned.parquet")

        transforms_dir = path / "transforms"
        transforms_dir.mkdir(exist_ok=True)
        for slice_id in self.slice_ids:
            save_transform(self.transforms[slice_id], transforms_dir / f"{slice_id}.npz")

    @classmethod
    def load(cls, path: str | Path) -> SerialAlignmentTransform:
        """Load a transform previously saved with :meth:`save`."""
        path = Path(path)
        metadata = json.loads((path / "metadata.json").read_text())
        transform_log = json.loads((path / "transform_log.json").read_text())
        slice_ids = metadata["slice_ids"]

        transforms_dir = path / "transforms"
        transforms = {
            slice_id: load_transform(transforms_dir / f"{slice_id}.npz") for slice_id in slice_ids
        }

        return cls(
            slice_attr=metadata["slice_attr"],
            slice_ids=slice_ids,
            reference=metadata["reference"],
            transforms=transforms,
            transform_log=transform_log,
            landmarks_initial=pd.read_parquet(path / "landmarks_initial.parquet"),
            landmarks_aligned=pd.read_parquet(path / "landmarks_aligned.parquet"),
            method=metadata["method"],
            allow_reflection=metadata["allow_reflection"],
            smoothing=metadata["smoothing"],
            weight_by_adjacent_counts=metadata["weight_by_adjacent_counts"],
            alignment_window=metadata["alignment_window"],
        )


def calc_alignment_transform(
    landmarks: pd.DataFrame,
    slice_attr: str | None = None,
    reference: int = 0,
    min_shared_landmarks: int = 3,
    alignment_window: int = 1,
    method: str = "procrustes",
    allow_reflection: bool = False,
    smoothing: float = 0.0,
    weight_by_adjacent_counts: bool = True,
    compute_residuals: bool = True,
) -> SerialAlignmentTransform:
    """Fit a serial-slice alignment transform from corresponding landmarks.

    Each slice is registered onto a window of its already-aligned neighbors
    by fitting a transform between corresponding landmarks. Alignment
    proceeds as a chain outward from ``reference`` in both directions along
    the slice order, so deformation is modeled between nearby physical
    neighbors rather than against a single distant reference. This function
    only touches ``landmarks`` — no cell data — so the returned transform
    can be fit once and reused (see :func:`align_serial_slices` and
    :meth:`SerialAlignmentTransform.apply_to_points`). Z assignment isn't
    part of this fit — it doesn't affect the spatial transform at all — see
    :func:`align_serial_slices`'s ``z_space``/``z_coord`` instead.

    Args:
        landmarks: A plain ``DataFrame`` of landmarks to fit against, with
            columns ``slice_attr`` (values defining slice order — see below),
            ``label`` (matches a landmark across slices; unique per slice),
            ``x``/``y``, and optionally ``count`` (omit or leave ``NaN`` for
            a landmark with no natural cell count, e.g. a manually-placed
            one). Build this with
            :func:`~celldega.align.landmarks.calc_landmarks`, a
            manually-placed landmark table in the same shape, or both
            concatenated together for a semi-manual mix.
        slice_attr: The column in ``landmarks`` identifying each row's slice
            (default ``"slice"``). Slice order is that column's categories
            if it's an ordered categorical, else sorted unique values.
        reference: Index (into the slice order) of the slice whose transform
            is the identity; other slices are aligned outward from it.
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

    Returns:
        The fitted :class:`SerialAlignmentTransform`.

    Raises:
        ValueError: If ``landmarks`` is missing a required column or has
            fewer than 2 slices, if ``reference`` is out of range, if
            ``alignment_window`` is less than 1, if ``method`` is not
            recognized, if a slice's landmarks contain duplicate labels, if
            a slice shares fewer than ``min_shared_landmarks`` labels with
            its neighbor window, or if the fit itself rejects the shared
            landmarks (e.g. a degenerate configuration for TPS).
    """
    slice_attr = slice_attr or "slice"
    _validate_landmarks(landmarks, slice_attr)
    slice_ids = _resolve_slice_order(landmarks[slice_attr])
    n = len(slice_ids)
    if n < 2:
        raise ValueError("calc_alignment_transform requires at least 2 slices")
    if not 0 <= reference < n:
        raise ValueError(f"reference must be in [0, {n - 1}], got {reference}")
    if alignment_window < 1:
        raise ValueError(f"alignment_window must be >= 1, got {alignment_window}")
    fit_transform = _resolve_fit_function(method, allow_reflection, smoothing)

    all_stats = [_slice_landmarks(landmarks, slice_id, slice_attr) for slice_id in slice_ids]

    transforms: dict[Any, Transform] = {slice_ids[reference]: _IDENTITY_TRANSFORM}
    centroids_cache: list[pd.DataFrame | None] = [None] * n
    centroids_cache[reference] = all_stats[reference]
    transform_log: dict[str, Any] = {}

    for chain in (range(reference - 1, -1, -1), range(reference + 1, n)):
        processed = [reference]
        for idx in chain:
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
            transforms[slice_ids[idx]] = transform

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

    aligned_frames = []
    for idx, stats in enumerate(centroids_cache):
        frame = stats.reset_index()
        frame[slice_attr] = slice_ids[idx]
        aligned_frames.append(frame)
    landmarks_aligned = pd.concat(aligned_frames, ignore_index=True)[
        [slice_attr, "label", "x", "y", "count"]
    ]

    return SerialAlignmentTransform(
        slice_attr=slice_attr,
        slice_ids=slice_ids,
        reference=slice_ids[reference],
        transforms=transforms,
        transform_log=transform_log,
        landmarks_initial=landmarks.copy(),
        landmarks_aligned=landmarks_aligned,
        method=method,
        allow_reflection=allow_reflection,
        smoothing=smoothing,
        weight_by_adjacent_counts=weight_by_adjacent_counts,
        alignment_window=alignment_window,
    )


def align_serial_slices(
    adatas: AnnData | list[AnnData],
    transform: SerialAlignmentTransform,
    z_space: float = 1.0,
    z_coord: list[float] | None = None,
    key_added: str = "Z",
    cell_name_prefix: bool = False,
) -> AnnData:
    """Apply a fitted :class:`SerialAlignmentTransform` to a set of ``AnnData``.

    Z assignment lives here, not in :func:`calc_alignment_transform` — it
    doesn't affect the spatial fit at all, so the same fitted transform can
    be applied with different Z choices without refitting anything.

    Args:
        adatas: Either a list of per-slice ``AnnData`` (list order must
            match the slice order ``transform`` was fit with), or a single
            ``AnnData`` combining all slices, split by the ``obs`` column
            named ``transform.slice_attr``. Only ``obsm["spatial"]`` is
            used — this function has no knowledge of cell metadata.
        transform: A :class:`SerialAlignmentTransform` from
            :func:`calc_alignment_transform` (or reloaded via
            :meth:`SerialAlignmentTransform.load`).
        z_space: Uniform distance between consecutive slices, applied
            outward from ``transform.reference`` (so that slice is
            ``Z = 0``). Ignored if ``z_coord`` is given.
        z_coord: Explicit absolute Z value for each slice (length
            ``n_slices``, matching slice order) — use this when slices have
            known, unevenly spaced, or non-reference-relative Z positions
            (e.g. from instrument metadata). Overrides ``z_space`` entirely
            when given.
        key_added: Name of the new per-cell ``obs`` column holding the
            assigned Z position.
        cell_name_prefix: If ``True``, prefix each slice's ``obs_names`` with
            its slice id (``f"{slice_id}_{name}"``) before concatenating, so
            cells stay uniquely named even when two slices reuse the same
            per-slice barcode convention. Matches
            :class:`~celldega.viz.widget.Landscape`'s ``cell_name_prefix``
            convention (a dataset/slice id, then the original cell name,
            split at the first ``_``), so the same aligned ``AnnData`` can be
            visualized there with ``cell_name_prefix=True``. Default
            ``False`` for backward compatibility — a uniqueness warning
            fires either way if names collide.

    Returns:
        A new ``AnnData`` concatenating all slices, with ``obsm["spatial"]``
        x/y columns replaced by the aligned coordinates, a new
        ``obs[key_added]`` Z column, and ``transform``'s fit parameters and
        landmark provenance recorded in ``uns["align_serial_slices"]``
        (plain, h5ad-safe data — the live ``transform`` object itself is
        not stored there; keep or persist it separately, see
        :meth:`SerialAlignmentTransform.save`).

    Raises:
        ValueError: If ``adatas`` resolves to a different set or order of
            slices than ``transform`` was fit with, if a slice is missing
            ``obsm["spatial"]``, or if ``z_coord`` is given with the wrong
            length.
    """
    slice_ids, slices, slice_attr = _ordered_slices(adatas, transform.slice_attr)
    if slice_ids != transform.slice_ids:
        raise ValueError(
            f"adatas resolve to slices {slice_ids!r}, which doesn't match the slices "
            f"{transform.slice_ids!r} that 'transform' was fit with"
        )
    _validate_slices(slices, slice_ids)

    reference_index = transform.slice_ids.index(transform.reference)
    z_values_arr = _z_values(len(slice_ids), reference_index, z_space, z_coord)
    z_values = dict(zip(slice_ids, z_values_arr, strict=True))

    aligned_slices = []
    for slice_id, adata in zip(slice_ids, slices, strict=True):
        spatial = np.asarray(adata.obsm["spatial"], dtype=float).copy()
        spatial[:, :2] = transform.apply_to_points(slice_id, spatial[:, :2])
        adata.obsm["spatial"] = spatial
        adata.obs[key_added] = z_values[slice_id]
        adata.obs[slice_attr] = slice_id
        if cell_name_prefix:
            adata.obs_names = [f"{slice_id}_{name}" for name in adata.obs_names]
        aligned_slices.append(adata)

    adata_aligned = ad.concat(aligned_slices, join="outer")
    if not adata_aligned.obs_names.is_unique:
        warnings.warn(
            "obs_names are not unique after concatenating slices; downstream indexing by "
            "cell name may behave unexpectedly. Pass cell_name_prefix=True to prefix each "
            "cell with its slice id (matching celldega.viz.widget.Landscape's "
            "cell_name_prefix convention) to keep names unique.",
            stacklevel=2,
        )
    adata_aligned.uns["align_serial_slices"] = {
        "slice_attr": transform.slice_attr,
        "reference": str(transform.reference),
        "alignment_window": transform.alignment_window,
        "method": transform.method,
        "allow_reflection": transform.allow_reflection,
        "smoothing": transform.smoothing,
        "weight_by_adjacent_counts": transform.weight_by_adjacent_counts,
        "z_space": z_space,
        "z_coord": z_coord,
        "transforms": transform.transform_log,
        "landmarks_initial": transform.landmarks_initial.copy(),
        "landmarks_aligned": transform.landmarks_aligned,
    }
    return adata_aligned
