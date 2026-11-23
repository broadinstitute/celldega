"""Align serial tissue sections into a 3D stack of cells.

The main use is building a 3D point cloud from serial sections. Each section is
imaged and segmented on its own, so its cell centroids sit in their own 2D frame,
offset and rotated relative to the neighboring sections. When the cells of all
sections are clustered together, the same clusters appear in neighboring sections,
and those shared clusters line the sections up in two steps:

1. **Cluster centroids.** :func:`calc_landmarks` places one landmark at each
   cluster's centroid in each section; manually placed landmarks (e.g. from
   :class:`~celldega.viz.Landmark`) can be added to the same table.
   :func:`calc_alignment_transform` then fits a rigid transform (rotation and
   translation, no scaling) per section, working outward from a reference section
   so that each section is fitted against its already-aligned neighbors.
2. **Neighborhood overlap.** A centroid reduces a cluster to one point, which shifts
   with sampling and segmentation. :func:`neighborhood_alignment` refines each
   section's rigid transform so that the clusters' neighborhood polygons (e.g.
   alpha shapes from :func:`celldega.nbhd.alpha_shape_cell_clusters_by_slice`)
   overlap as much as possible across neighboring sections.

Both steps return a :class:`SerialAlignmentTransform`, one transform per section.
:func:`align_serial_slices` applies it to the cells (aligning ``obsm["spatial"]``
and giving each cell its section's z coordinate); it can also be applied to other
points of the same sections (``apply_to_points``) and saved for reuse
(``save``/``load``). The aligned cells are a 3D point cloud: write them as DegaFiles
with :func:`celldega.pre.write_point_cloud_dataset` to view them in a
:class:`~celldega.viz.CellCloud`.

The module also has tools this workflow doesn't need: a non-rigid thin-plate-spline
fit (``method="tps"``, :func:`fit_transform_tps`), per-landmark leave-one-out
residuals (:func:`leave_one_out_residuals`), a before/after plot of the landmarks
(:func:`plot_alignment`), applying a transform to polygons (:func:`transform_shapes`),
and saving a single 2D transform (:func:`save_transform`, :func:`load_transform`).
"""

from celldega.align._transform import (
    fit_transform_procrustes,
    fit_transform_tps,
    leave_one_out_residuals,
    load_transform,
    save_transform,
)
from celldega.align.landmarks import calc_landmarks
from celldega.align.neighborhood import neighborhood_alignment, transform_shapes
from celldega.align.plot import plot_alignment
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
]
