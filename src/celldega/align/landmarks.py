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
"""

from __future__ import annotations

from anndata import AnnData
import numpy as np
import pandas as pd


__all__ = ["calc_landmarks"]


def calc_landmarks(adata: AnnData, cluster_key: str) -> pd.DataFrame:
    """Compute one landmark per cluster label, at that cluster's centroid.

    Args:
        adata: An ``AnnData`` with 2D coordinates in ``obsm["spatial"]``.
        cluster_key: ``obs`` column with cluster labels to compute
            centroids for.

    Returns:
        A ``DataFrame`` with columns ``label`` (cluster label, as ``str``),
        ``x``/``y`` (the cluster's centroid, in ``adata.obsm["spatial"]``'s
        coordinate space), and ``count`` (number of cells in that cluster) —
        the shape :func:`~celldega.align.serial_slices.align_serial_slices`'s
        ``landmarks`` parameter expects, so manually-defined landmarks (same
        columns, ``count`` absent or ``NaN``) can be combined with this via
        :func:`pandas.concat` before being passed in.

    Raises:
        ValueError: If ``cluster_key`` is not a column in ``adata.obs``, or
            ``adata.obsm["spatial"]`` is missing or has fewer than 2 columns.
    """
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
