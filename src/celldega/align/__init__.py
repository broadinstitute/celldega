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
aligns serial slices in-plane from corresponding landmarks using either a
rigid Procrustes fit (:func:`fit_transform_procrustes`, always without
scaling — see :mod:`celldega.align.serial_slices`) or a non-rigid
thin-plate-spline warp (:func:`fit_transform_tps`), both in
:mod:`celldega.align._transform`. Landmarks are always built by the caller,
never computed implicitly: :func:`calc_landmarks`
(:mod:`celldega.align.landmarks`) computes them from shared cluster labels,
accepting the same list-of-``AnnData``-or-one-combined-``AnnData``
input shapes as :func:`align_serial_slices` itself (no manual per-slice loop
needed), and a manually-placed landmark table in the same shape (a plain
``DataFrame``, not
a ``GeoDataFrame`` of shapely geometry, so it stays trivially disk-portable;
e.g. from a future point-drawing widget, tentatively named ``Landmark`` —
pairs with ``Landscape``) can be used instead, or concatenated alongside it
for a semi-manual mix — keeping landmarks a visible, inspectable artifact of
the workflow rather than something hidden inside the alignment call. Each
slice registers against a *window* of already-aligned neighbors
(``alignment_window``, never a single distant reference), landmarks can be
weighted by cell count (``weight_by_adjacent_counts``), and per-landmark
leave-one-out residuals (:func:`leave_one_out_residuals`) are recorded for
diagnosing which landmarks disagree with the fit implied by the rest. Both
the landmarks given and every landmark's final aligned position are
recorded in the output's ``uns["align_serial_slices"]`` for reproducibility
and for planning further manual landmarks in a follow-up pass. Planned: a
reference/atlas-registration method sharing the same landmark-based core
(star topology onto one fixed reference, vs. :func:`align_serial_slices`'s
neighbor-chain) and image-based modality-to-modality registration (deferred
— unlike the two centroid-based methods, this operates on raw image data,
not single-cell coordinates).
"""

from celldega.align._transform import (
    fit_transform_procrustes,
    fit_transform_tps,
    leave_one_out_residuals,
)
from celldega.align.landmarks import calc_landmarks
from celldega.align.serial_slices import align_serial_slices


__all__ = [
    "align_serial_slices",
    "calc_landmarks",
    "fit_transform_procrustes",
    "fit_transform_tps",
    "leave_one_out_residuals",
]
