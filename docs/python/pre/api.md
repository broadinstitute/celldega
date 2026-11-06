# Pre Module API Reference

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
