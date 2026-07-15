"""Alignment and registration of spatial single-cell data.

Covers three related registration problems: (1) stitching serial 3D tissue
slices into a shared coordinate frame, (2) registering data onto a reference
(e.g. a common coordinate framework/atlas such as the Allen Institute mouse
brain, or a particular dataset within a cohort), and (3) registering across
modalities (e.g. Xenium to H&E). All three align in *physical* (spatial)
coordinates — image/tissue pixel or micron space. Batch correction /
integration in expression or embedding space (e.g. Harmony, scVI, Seurat
anchors) is a different problem and out of scope here, though a shared
framework for evaluating alignment quality could plausibly extend to that
space later.

Status: initial sketch. Implemented: :func:`align_serial_slices`, which
aligns serial slices in-plane from shared cluster centroid landmarks using an
injectable ``fit_transform`` strategy — rigid Procrustes
(:func:`fit_similarity_transform`) or non-rigid thin-plate-spline
(:func:`fit_thin_plate_spline`), both in :mod:`celldega.align._transform`.
Each slice registers against a *window* of already-aligned neighbors
(``alignment_window``, never a single distant reference), landmarks can be
weighted by cell count and/or cross-slice presence (``cluster_weight``), and
per-landmark leave-one-out residuals (:func:`leave_one_out_residuals`) are
recorded for diagnosing which landmarks disagree with the fit implied by the
rest. Planned: a reference/atlas-registration method sharing the same centroid/
landmark-based core (star topology onto one fixed reference, vs.
:func:`align_serial_slices`'s neighbor-chain); manually-defined landmark
pairs (reusing the same transform-fitting core, driven by a paired multi-Z/
multi-modality Landscape view for placing them — likely stored as a plain
``GeoDataFrame`` of point geometries rather than gated on
:class:`~celldega.nbhd.collection.NeighborhoodCollection` gaining point
support); and image-based modality-to-modality registration (deferred —
unlike the two centroid-based methods, this operates on raw image data, not
single-cell coordinates).
"""

from celldega.align._transform import (
    fit_similarity_transform,
    fit_thin_plate_spline,
    leave_one_out_residuals,
)
from celldega.align.serial_slices import align_serial_slices


__all__ = [
    "align_serial_slices",
    "fit_similarity_transform",
    "fit_thin_plate_spline",
    "leave_one_out_residuals",
]
