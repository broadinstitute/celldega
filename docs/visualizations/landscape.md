# Landscape

`Landscape` is Celldega's main spatial visualization: an interactive,
deck.gl-powered view of a tissue section that scales to datasets with
hundreds of millions of transcripts by loading data as vector tiles instead
of all at once.

## What it shows

- **Image**: the underlying microscopy image (e.g. H&E, DAPI), rendered as a
  zoomable tile pyramid, with per-channel visibility/contrast controls.
- **CELL**: cell segmentation boundaries, colored by cluster/category (e.g. a
  `leiden` column from an `AnnData`) or by gene expression, with a size
  slider.
- **TRX**: individual transcript locations, colored by gene, with a size
  slider.
- **NBHD**: tissue neighborhoods (alpha-shape or hextile regions), toggled
  on/off with their own opacity control.
- A **gene search** box and a bar graph that summarizes the currently visible
  cells by category or gene, updated as you pan/zoom.
- Support for **multiple datasets** via a dropdown selector.

For 3D, orbit-camera views of a dataset (thick tissue, multi-slice
alignments, or precomputed neighborhoods), see
[CellCloud](cell-cloud.md) and [NeighborhoodCloud](neighborhood-cloud.md),
which replace `Landscape`'s older `technology="point-cloud"` /
`"neighborhood-cloud"` modes.

## Usage

```python
import celldega as dega

landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    adata=adata,
    ini_zoom=-5,
)
landscape
```

`Landscape` can also be linked to a `Clustergram` so that selections in one
update the other — see [`dega.viz.spatial_clustergram`](../python/viz/api.md).

## Experimental SpatialData input

On the `adapt_dega_v2` branch, `base_url` can point to an opt-in, spatially tiled
SpatialData store produced by the matching `spatialdata-io` branch. Celldega first checks
for `landscape_parameters.json`, preserving the existing DegaFiles path, and then checks
the root `zarr.json` for a `spatial_tiling` manifest. A SpatialData store does not need a
`visualization/` directory.

The reader fetches canonical transcript row groups from
`points/<element>/points.parquet`. It sends the separate `x` and `y` Arrow buffers to a
custom ScatterplotLayer and applies the coordinate transform in its vertex shader. The
homogeneous coordinate used for the affine multiplication is reset to world `z = 0` for
the 2D orthographic view. No interleaved transcript-coordinate copy is created on the CPU.

Canonical cell boundaries are GeoParquet with `geoarrow.polygon` geometry. Celldega reads
the separated coordinate buffers, applies the affine transform while constructing visible
JavaScript path arrays, and renders them with deck.gl's standard `PathLayer`. It does not
depend on `@geoarrow/deck.gl-layers`. Table metadata, expression and native OME-Zarr images
are read from the same SpatialData store; images are currently windowed to 8-bit RGBA for
the existing image layers.

This integration is currently tested for Xenium-compatible element names, identifiers and
transforms. Parquet hosting must support HTTP byte-range requests. Celldega temporarily
depends on `@cornhundred/parquet-wasm@0.7.2-celldega.0`, which carries the column-projection
fix pending upstream merge and release.

For the full list of constructor arguments (multi-dataset support, point-cloud
options, `AnnData` integration, etc.), see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
