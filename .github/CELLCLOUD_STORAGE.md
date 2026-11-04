# CellCloud storage comparison

Measured on 2026-11-03 using the full Broad–Allen developing mouse brain E15.5
stack: 3,787,366 cells, 43 sections, 480 genes, and 481,070,559 nonzero counts.
This comparison concerns transfer and loading, rather than orbit frame rate.

| Artifact | Complete dataset | Data requested for first view | Initial data requests | Additional data for Dcx |
| --- | ---: | ---: | ---: | ---: |
| Original name-based DegaFiles | 4,585.70 MB | 100.60 MB | 5 | 30.76 MB |
| Compact indexed DegaFiles | 493.58 MB | 31.31 MB | 6 | 3.34 MB |
| AnnData Zarr | 583.03 MB | 25.69 MB | 39 | 3.43 MB |

MB means decimal megabytes. First-view requests include the selected
neighborhood alignment, original IDs, cluster labels/colors, and gene metadata;
they exclude the JavaScript/WASM bundle, fonts, and gene expression. Dcx is a
representative gene, not an average. Zarr fetches the sparse chunks overlapping
the gene, which can include neighboring entries. The first view does not fetch
`X/data` or `X/indices`.

The compact DegaFiles are **9.29× smaller overall** and need **68.9% less data
for first display**. Zarr needs **74.5% less initial data** than the original
DegaFiles. These byte savings do not imply the same wall-clock speedup: server
latency, HTTP concurrency, bandwidth, decoding, and browser caches also matter.
All three sources rendered successfully in a local browser; both new formats
also supported on-demand Dcx coloring without browser errors. The local first
render took roughly 2–3 seconds for each new source, excluding bundle startup;
this is not a hosted-service speed benchmark.

## What changed

- Positions are rounded to the nearest 1 µm and stored as int32. Maximum
  measured change was 0.5 µm on either axis, and about 0.707 µm in 3D because
  the stack-axis positions were already integral. CellCloud draws cells with
  a default diameter of 10 µm.
- DegaFiles store original IDs once in `cell_ids.parquet`. Geometry, clusters,
  and sparse genes use uint32 canonical row IDs. Zstd and delta encoding shrink
  repeated numeric IDs. Named alignments share this mapping.
- Exact integer counts are stored as uint16 here: the largest source count is
  544. There is no expression rounding or normalization.
- Zarr stores CSC counts, compressed observation metadata, and 262,144-cell
  XYZ chunks. Gene values load by sparse column. Original observation IDs stay
  available for picking, selection, and linking.
- The browser avoids an intermediate float64 geometry buffer and redundant
  point-position copy. CellCloud Zarr avoids millions of metadata objects.

The new Zarr contains the metadata needed by this visualization (`leiden_1.0`
and section ID), not every annotation or embedding from the source H5AD.
Both centroid and neighborhood alignments are included. The full original
H5AD remains the analysis source.

## Reproduce and validate

Run from the checkout with its Python environment and the Hugging Face CLI:

```bash
python scripts/prepare_allen_mouse_brain_cellcloud.py --download
python scripts/prepare_allen_mouse_brain_cellcloud.py --verify
```

Existing completed output is refused; `--verify` refreshes its report and
checksums without rewriting the data. `--resume` can reuse a completed DegaFiles
export after an interrupted Zarr write. The script never uploads data.

Inputs are pinned to Hugging Face revision
`df537e04ad0e51a91f3d68a53b788efb61552913` and alignment-repository revision
`e8d0d6fb17109333e982497fca1c526e5e457747`. The original files remain unchanged.
Original raw counts, cluster labels, colors, and gene statistics match; a full
round trip verified all sparse expression values in both formats, IDs, both
coordinate arrays, and palettes. This did not rerun the original clustering
or alignment algorithms.

Prepared local outputs are under `data/allen_mouse_brain_cellcloud_v2/artifacts/`:

- `github/xenium_E15.5_cell_cloud_v2_1um/`: compact Parquet DegaFiles.
- `huggingface/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr/`:
  complete AnnData Zarr directory.
- `size-report.json` and `SHA256SUMS`: per-file sizes and verification results.

These large artifacts are intentionally outside Git tracking. The new DegaFiles
belong in a new directory in the existing **data repository**, rather than
adding approximately 494 MB of scientific data to this library repository.
The script and documentation are tracked here.

## Hosting follow-up

- Publish the compact directory at a new GitHub path, leaving
  `xenium_E15.5_cell_cloud/` intact.
- Upload the complete Zarr directory to the new HF path
  `Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr/`. Confirm that path
  does not already exist; retain the source-data attribution and provenance.
- Publish a matching Celldega JavaScript bundle before pointing notebook
  saved state at it. For checkout testing, build the bundle and start the
  kernel with `CELLDEGA_LOCAL_ESM=1` before importing Celldega.
- Test both hosted URLs, then switch the gallery/default notebook source.
  The current public gallery still uses the original data until this step.

The public writers are `pre.write_point_cloud_dataset` (opt into
`use_int_index=True`, `coordinate_resolution=1.0`, and `compression="zstd"`)
and `pre.write_point_cloud_zarr`. CellCloud accepts either `base_url=` or
`zarr_url=` with the same alignment/category/view options. Existing name-based
DegaFiles remain supported.
