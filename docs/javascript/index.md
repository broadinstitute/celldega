# JavaScript API Overview

Use Celldega in a web page to explore prepared datasets without a Python
kernel. The same Landscape and Clustergram views used in notebooks can read
hosted DegaFiles or AnnData Zarr directly.

## Quick start

Serve the page and the built `celldega.js` module over HTTP. This example
opens a spatial Landscape; replace `base_url` with your dataset's DegaFiles URL.

```html
<!doctype html>
<html lang="en">
<body>
  <div id="landscape"></div>
  <script type="module">
    import celldega from "./celldega.js";

    const landscape = await celldega.landscape(
      document.getElementById("landscape"),
      {
        base_url: "https://your-data-host/DegaFiles",
        width: 900,
        height: 600,
      },
    );
  </script>
</body>
</html>
```

For a single-cell UMAP/XY Landscape, use `zarr_url` and `zarr_layer` instead.
For a saved clustered Matrix, use `clustergram(element, {url})`.

## Main APIs

| Function | Purpose |
| --- | --- |
| `landscape(element, options)` | Spatial tissue and low dimensional embedding landscapes |
| `clustergram(element, options)` | Heatmap or dot plot from a network, DegaFiles, or a saved Matrix Zarr |
| `link_models(source, key, target, key)` | Link selections between visualizations |
| `anndata_zarr_source(url, options)` | Cell-level Zarr metadata and per-gene expression reader |
| `network_from_zarr(url)` | Restore a saved Matrix's browser visualization network |

See the [API reference](api.md#visualizations-without-python-landscape-clustergram-and-link_models)
for complete options and a linked Landscape/Clustergram example. Lower-level
renderers remain available for custom integrations.

## Data and hosting

- Spatial Landscapes use image pyramids, cell metadata, transcript/boundary
  tiles, and expression in DegaFiles.
- Single-cell Landscapes use AnnData Zarr with a CSC expression matrix.
- Clustergrams can read the complete clustered Matrix AnnData Zarr format.
- Cross-origin hosting must allow browser requests. Row-group DegaFiles
  also require HTTP byte ranges.

See [File Formats](../getting-started/file_formats.md) for the layouts, and
the [Gallery](../gallery/index.md) for live examples.
