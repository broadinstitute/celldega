"""Alignment and registration of spatial single-cell data.

Covers three related registration problems: (1) stitching serial 3D tissue
slices into a shared coordinate frame, (2) registering data onto reference
atlas polygons (e.g. Allen Institute mouse brain), and (3) registering across
modalities (e.g. Xenium to H&E).

Status: initial sketch. Implemented: :func:`align_serial_slices`, which
aligns serial slices in-plane from shared cluster centroid landmarks using an
injectable ``fit_transform`` strategy — rigid Procrustes
(:func:`fit_similarity_transform`) or non-rigid thin-plate-spline
(:func:`fit_thin_plate_spline`), both in :mod:`celldega.align._transform`.
Planned: manually-defined landmark pairs (reusing the same transform-fitting
core, driven by a paired multi-Z/multi-modality Landscape view for placing
them), atlas polygon registration, and modality-to-modality registration.
"""

from celldega.align._transform import fit_similarity_transform, fit_thin_plate_spline
from celldega.align.serial_slices import align_serial_slices


__all__ = ["align_serial_slices", "fit_similarity_transform", "fit_thin_plate_spline"]
