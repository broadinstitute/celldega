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

Status: initial sketch. Implemented: a three-step serial-slice pipeline,
each step an independently reusable artifact. (1) :func:`calc_landmarks`
computes landmarks from shared cluster labels (accepting a list of
``AnnData`` or one combined ``AnnData``, no manual per-slice loop needed),
or a manually-placed landmark table in the same shape (a plain
``DataFrame``, not a ``GeoDataFrame`` of shapely geometry, so it stays
trivially disk-portable; e.g. from :class:`~celldega.viz.Landmark`, a
point-drawing widget pairing with ``Landscape``) can be used instead, or
concatenated alongside it for a semi-manual mix. (2)
:func:`calc_alignment_transform` fits a rigid Procrustes
(:func:`fit_transform_procrustes`, always without scaling — see
:mod:`celldega.align.serial_slices`) or non-rigid thin-plate-spline
(:func:`fit_transform_tps`) transform per slice from those landmarks —
chain-walking outward from a reference slice against a *window* of
already-aligned neighbors (``alignment_window``, never a single distant
reference), optionally weighting landmarks by cell count
(``weight_by_adjacent_counts``) and recording per-landmark leave-one-out
residuals (:func:`leave_one_out_residuals`) — and returns a
:class:`~celldega.align.serial_slices.SerialAlignmentTransform`: a
first-class, reusable object (not a byproduct that only lives inside one
alignment call) that can be applied to *other* point data tied to the same
slices (segmentation-polygon vertices, transcript coordinates, eventually
raster sampling grids) via ``.apply_to_points()``, and persisted with
``.save()``/``.load()`` (a plain directory of ``.npz``/``.parquet``/``.json``
files, no ``pickle`` required, though it's picklable too), and visually
sanity-checked with :func:`plot_alignment` (also available as
``transform.plot()``): a 2D before/after scatter of the fitted landmarks,
so a bad fit (or a mislabeled landmark) is visible at a glance rather than
only showing up downstream. (3)
:func:`align_serial_slices` applies a given transform to a specific set of
``AnnData``, aligning ``obsm["spatial"]`` and assigning a Z coordinate;
`landmarks_initial`/`landmarks_aligned`/fit parameters are also recorded in
the output's ``uns["align_serial_slices"]`` for at-a-glance provenance.
Planned: a reference/atlas-registration method sharing the same
landmark-based core (star topology onto one fixed reference, vs.
:func:`align_serial_slices`'s neighbor-chain) and image-based
modality-to-modality registration (deferred — unlike the two centroid-based
methods, this operates on raw image data, not single-cell coordinates).
"""

from celldega.align._transform import (
    fit_transform_procrustes,
    fit_transform_tps,
    leave_one_out_residuals,
    load_transform,
    save_transform,
)
from celldega.align.landmarks import calc_landmarks
from celldega.align.nbhd_cloud import write_nbhd_cloud
from celldega.align.neighborhood import neighborhood_alignment, transform_shapes
from celldega.align.plot import plot_alignment
from celldega.align.point_cloud import write_alignment_point_cloud
from celldega.align.serial_slices import (
    SerialAlignmentTransform,
    align_serial_slices,
    calc_alignment_transform,
)


__all__ = [
    "SerialAlignmentTransform",
    "align_serial_slices",
    "calc_alignment_transform",
    "calc_landmarks",
    "fit_transform_procrustes",
    "fit_transform_tps",
    "leave_one_out_residuals",
    "load_transform",
    "neighborhood_alignment",
    "plot_alignment",
    "save_transform",
    "transform_shapes",
    "write_alignment_point_cloud",
    "write_nbhd_cloud",
]
