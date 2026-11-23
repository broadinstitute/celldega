# Pre Module API Reference

## Motivation

Spatial omics datasets are large. One tissue section can hold hundreds of
thousands of cells, hundreds of millions of transcripts and gigapixel images,
far more than a browser can load at once. Celldega's widgets instead fetch only
what is in view: zoomed out, a downsampled image and the cells as points;
zoomed in, the image tiles, cell boundaries and transcripts of that region; and
a gene's expression only when you select it.

`pre` makes this possible by reorganizing instrument output once into
**DegaFiles**: image tile pyramids, cell boundaries and transcripts split into
spatial tiles, per-gene expression, and cell and gene metadata. They are static
Parquet and image files, so they can be hosted anywhere that serves files
(GitHub, Hugging Face, cloud storage or a local server) and read directly by the
browser, with no server doing computation.

## Tiling in SpatialData

[SpatialData](https://spatialdata.scverse.org/) is the established data format
for spatial omics. We are working with its developers to bring Celldega's
spatial tiling for scalable visualization into the format, through its proposals
for [tiled points](https://spatialdata-spec.scverse.org/rfcs/0003-tiled-points.html)
(such as transcripts) and
[tiled shapes](https://spatialdata-spec.scverse.org/rfcs/0004-tiled-shapes.html)
(such as cell boundaries).

## Overview

- `main`: pre-process a Xenium or MERSCOPE output directory into DegaFiles.
- `add_clustering_from_adata`: add cluster labels and colors from an `AnnData`.
- `add_aligned_he`: tile an H&E image aligned to the same coordinates.
- `write_point_cloud_dataset` / `write_point_cloud_zarr`: cells in 3D for
  `CellCloud`.
- `write_nbhd_cloud_dataset`: neighborhood alpha shapes in 3D for
  `NeighborhoodCloud`.

Single-cell `AnnData` needs no pre-processing: `Landscape(zarr_url=...)` reads an
AnnData Zarr store directly.

Prepare instrument output for Landscape with the
[DegaFiles preparation and hosting guide](../../getting-started/usage/index.md#prepare-degafiles-from-instrument-output).
Examples include [Atera preprocessing](../../examples/brief_notebooks/Atera_Pre-process.ipynb)
and [custom segmentation](../../examples/brief_notebooks/Custom_Segmentation.ipynb).

See [Add aligned H&E to DegaFiles](../aligned_he.md) for importing an optional
histology background into Landscape and Yearbook.

For CellCloud, use `write_point_cloud_dataset` for compact indexed Parquet
DegaFiles or `write_point_cloud_zarr` for an AnnData Zarr with sparse CSC
expression. Both support rounded XYZ positions and named alignments; see the
[CellCloud preparation examples](../../visualizations/cell-cloud.md#prepare-either-format)
and [mouse-brain workflow](../../gallery/gallery_broad_allen_mouse_brain_3d.md#use-degafiles-or-anndata-zarr).

<!-- ::: celldega.pre.landscape -->
::: celldega.pre
