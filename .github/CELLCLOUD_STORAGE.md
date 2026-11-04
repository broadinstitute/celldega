# CellCloud storage comparison

Measured on 2026-11-03 using the full Broad–Allen developing mouse brain E15.5
stack: 3,787,366 cells, 43 sections, 480 genes, and 481,070,559 nonzero counts.
This comparison concerns transfer and loading, rather than orbit frame rate.

| Artifact | Complete dataset | Unique data for first view | Initial unique files | Additional data for Dcx |
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

## Hosted exports and comparison

- [Compact DegaFiles on the cornhundred fork](https://github.com/cornhundred/celldega_xenium_E15.5_cell_cloud/tree/8d3cd06fc1a478f386826c27ba0e900b40703a3a/xenium_E15.5_cell_cloud_compact):
  491 uploaded files, including README and checksums. Every Git blob matches the
  prepared copy; the original root entries are unchanged. The upstream
  [data PR #1](https://github.com/broadinstitute/celldega_xenium_E15.5_cell_cloud/pull/1)
  is open and awaiting merge.
- [AnnData Zarr on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/f76a3fa95ed9af8b6e96484a720cf4cbedc31819/Allen-Broad_Dev-Mouse-Brain/E15.5/cellcloud_v2_1um.zarr):
  all 3,828 file sizes and Git/LFS hashes match the validated local store.
- The gallery and saved CellCloud notebook now default to this Zarr. The gallery
  has a source picker, and the notebook demonstrates changing `zarr_url=` to
  `base_url=`. Neither original dataset was overwritten.

Three new-widget loads and first Dcx selections were measured per source,
alternating their order, from the actual hosts with browser HTTP caching
bypassed. CDN cache state was uncontrolled. The same local renderer was used
for both; times include transfer, decoding, point-buffer updates, and two
animation frames, excluding JavaScript-bundle startup. Counting response bytes
clones each response, adding some instrumentation overhead.

| Hosted source | Initial median (range), seconds | First Dcx median (range), seconds | Initial payload / requests | Dcx payload / requests |
| --- | ---: | ---: | ---: | ---: |
| GitHub compact DegaFiles | 3.616 (3.528–8.232) | 0.669 (0.445–0.690) | 31.335 MB / 7 | 3.336 MB / 1 |
| Hugging Face AnnData Zarr | 4.429 (4.409–6.691) | 1.081 (0.841–2.121) | 25.687 MB / 39 | 3.432 MB / 28 |

All twelve measured operations completed without HTTP errors. DegaFiles was
faster in this small test. Zarr remains the default to support the requested
AnnData/Scverse workflow: its median overhead was about 0.8 seconds initially
and 0.4 seconds for Dcx, while its initial payload was smaller. The source
picker retains the faster Parquet alternative. These observations concern one
client, one gene, and these hosts; they are not universal performance guarantees.
The DegaFiles reader requests its small gene-metadata file twice, so the hosted
payload/request totals differ slightly from the unique-file inventory above.

Results: `data/allen_mouse_brain_cellcloud_v2/hosted-final-benchmark-results.jsonl`.
Repeat with [the benchmark script](../scripts/benchmark_cellcloud_sources.py);
see [benchmark details](CELLCLOUD_HOSTED_BENCHMARK.md).

## Rendering validation

Translucent expression cells skip depth testing/writes during the color pass;
opaque clusters and the picking pass retain depth behavior. Expression uses a
single red hue with per-cell alpha, so consistent blending does not require
sorting millions of points on camera movement. The full brain was inspected
from front and back. A three-cell WebGL fixture reproduced the original
front/back alpha difference (90 versus 148) and showed matching alpha 148 from
both sides after the fix, with no GL errors. Picking still returns the nearest
original cell in regression tests.

Programmatic gene selection also rebuilds binary point data after expression
loads; previously it could repaint the empty pre-load buffer. The updated
front-end passes all 639 JavaScript tests. The existing exporter validation
passed 531 Python tests (2 skipped). The original full scientific clustering
and alignment analyses were not rerun.

A matching JavaScript bundle still needs to be published with the library
release. Saved documentation widgets use the documentation bundle; for local
checkout testing, build it and start the kernel with `CELLDEGA_LOCAL_ESM=1`
before importing Celldega.

The public writers are `pre.write_point_cloud_dataset` (opt into
`use_int_index=True`, `coordinate_resolution=1.0`, and `compression="zstd"`)
and `pre.write_point_cloud_zarr`. CellCloud accepts either `base_url=` or
`zarr_url=` with the same alignment/category/view options. Existing name-based
DegaFiles remain supported.
