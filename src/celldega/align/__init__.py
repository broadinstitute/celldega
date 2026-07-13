"""Alignment and registration of spatial single-cell data.

Covers three related registration problems: (1) stitching serial 3D tissue
slices into a shared coordinate frame, (2) registering data onto reference
atlas polygons (e.g. Allen Institute mouse brain), and (3) registering across
modalities (e.g. Xenium to H&E).

Status: initial sketch. Implemented: :func:`align_serial_slices`, which
similarity-aligns serial slices in-plane from shared cluster centroids via
Procrustes (:mod:`celldega.align._transform`). Planned: manually-defined
landmark pairs (reusing the same transform-fitting core, driven by a paired
multi-Z/multi-modality Landscape view for placing them), non-rigid (e.g.
thin-plate-spline) warping from landmarks, atlas polygon registration, and
modality-to-modality registration.
"""

from celldega.align.serial_slices import align_serial_slices


__all__ = ["align_serial_slices"]
