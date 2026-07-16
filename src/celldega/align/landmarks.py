"""Cluster-centroid landmarks for alignment.

Computes one landmark per cluster label, decoupled from any particular
alignment orchestration (:mod:`celldega.align.serial_slices` today; a future
reference/atlas-registration method tomorrow, matching a query dataset's
cluster centroids onto a reference dataset's). The output shape is the same
one manually- or semi-manually-defined landmarks (e.g. from a future
point-drawing widget) use, so the two are directly ``pandas.concat``-able.
A plain ``DataFrame`` (rather than a ``GeoDataFrame`` of shapely geometry)
keeps this trivially disk-portable (``to_parquet``/``to_csv`` with no WKB/WKT
round-trip); a future geometry-based landmark source (e.g. GeoJSON points
from a drawing widget) is a small ``x``/``y`` extraction away from this shape.

Accepts the same two multi-slice input shapes as
:func:`~celldega.align.serial_slices.align_serial_slices` (a list of
``AnnData``, or one combined ``AnnData`` + ``slice_attr``), so building a
multi-slice landmarks table doesn't require a manual per-slice loop.
"""

from __future__ import annotations

from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.align._slices import _ordered_slices


__all__ = ["calc_landmarks"]


def _one_slice_landmarks(adata: AnnData, cluster_key: str) -> pd.DataFrame:
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"'{cluster_key}' is not a column in adata.obs")
    spatial = adata.obsm.get("spatial")
    if spatial is None or np.asarray(spatial).shape[1] < 2:
        raise ValueError("adata must have obsm['spatial'] with at least 2 columns (x, y)")

    xy = np.asarray(spatial)[:, :2]
    df = pd.DataFrame(xy, columns=["x", "y"], index=adata.obs_names)
    df["label"] = adata.obs[cluster_key].astype(str).to_numpy()
    grouped = df.groupby("label")
    stats = grouped[["x", "y"]].mean()
    stats["count"] = grouped.size()
    return stats.reset_index()[["label", "x", "y", "count"]]


def calc_landmarks(
    adatas: AnnData | list[AnnData], cluster_key: str, slice_attr: str | None = None
) -> pd.DataFrame:
    """Compute one landmark per cluster label, at that cluster's centroid.

    Args:
        adatas: A single ``AnnData`` with 2D coordinates in
            ``obsm["spatial"]`` (returns landmarks with no slice tagging,
            matching the ``landmarks`` shape for a single dataset), a list
            of per-slice ``AnnData`` (list order is slice order), or a
            single combined ``AnnData`` with ``slice_attr`` given, to be
            split into slices by that ``obs`` column. In the latter two
            cases the result is tagged with a ``slice_attr`` column so it can
            be passed straight to
            :func:`~celldega.align.serial_slices.align_serial_slices`.
        cluster_key: ``obs`` column with cluster labels to compute
            centroids for.
        slice_attr: For a single combined ``AnnData``, the ``obs`` column
            identifying each cell's slice (required in that case, and
            triggers multi-slice output). For a list of ``AnnData``, the
            name to give the output's slice-tagging column (default
            ``"slice"``). Ignored for a single, non-split ``AnnData``.

    Returns:
        A ``DataFrame`` with columns ``label`` (cluster label, as ``str``),
        ``x``/``y`` (the cluster's centroid, in each slice's own
        ``obsm["spatial"]`` coordinate space), and ``count`` (number of
        cells in that cluster) — plus a ``slice_attr`` column when computed
        over multiple slices. This is the shape
        :func:`~celldega.align.serial_slices.align_serial_slices`'s
        ``landmarks`` parameter expects, so manually-defined landmarks (same
        columns, ``count`` absent or ``NaN``) can be combined with this via
        :func:`pandas.concat` before being passed in.

    Raises:
        ValueError: If ``cluster_key`` is not a column in some slice's
            ``obs``, if some slice is missing ``obsm["spatial"]`` or has
            fewer than 2 columns there, or (multi-slice mode) if ``adatas``
            is a single ``AnnData`` without ``slice_attr``.
    """
    if isinstance(adatas, AnnData) and slice_attr is None:
        return _one_slice_landmarks(adatas, cluster_key)

    slice_ids, slices, slice_attr = _ordered_slices(adatas, slice_attr, copy=False)
    frames = []
    for slice_id, adata in zip(slice_ids, slices, strict=True):
        frame = _one_slice_landmarks(adata, cluster_key)
        frame[slice_attr] = slice_id
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)
