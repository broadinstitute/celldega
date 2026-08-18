# JavaScript API Overview

Celldega's visualization methods can be used as a stand-alone JavaScript library outside the context of a Jupyter notebook. This enables creating showcase visualizations with publicly hosted data, embedding visualizations in web applications, and building custom interactive experiences.

## Getting Started

### Using in HTML

You can include Celldega in any HTML page by importing the bundled JavaScript module:

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        #landscape-container {
            width: 100%;
            height: 800px;
            border: 1px solid #ccc;
        }
    </style>
</head>
<body>
    <div id="landscape-container"></div>

    <script type="module">
        import celldega from './celldega.js';

        document.addEventListener("DOMContentLoaded", async () => {
            const el = document.getElementById('landscape-container');

            const landscape = await celldega.landscape_ist(
                el,                    // DOM element
                {},                    // model (empty for standalone)
                '',                    // token
                10000,                 // initial X
                10000,                 // initial Y
                0,                     // initial Z
                -5,                    // initial zoom
                'https://your-data-url/LandscapeFiles',  // base URL
                'Dataset Name',        // dataset name
                0.25,                  // transcript radius
                '100%',                // width
                '100%'                 // height
            );
        });
    </script>
</body>
</html>
```

### Using with ObservableHQ

Celldega can be used in ObservableHQ notebooks. See the [Celldega Landscape Xenium example](https://observablehq.com/@cornhundred/celldega-xenium_prime_mouse_brain_coronal_ff_outs) for a working demo.

## Available Functions

Celldega exports the following main visualization functions:

| Function | Description |
|----------|-------------|
| `landscape_ist` | Create an interactive spatial transcriptomics (IST) landscape visualization |
| `landscape_h_e` | Create an H&E image visualization |
| `matrix_viz` | Create a Clustergrammer-style matrix/heatmap visualization |
| `yearbook` | Create a yearbook-style grid of cell portraits |

## Data Requirements

For standalone JavaScript visualizations, your data must be hosted publicly (e.g., on GitHub, S3, or a web server). The data should be in the LandscapeFiles format, which includes:

- `landscape_parameters.json` - Configuration file
- `pyramid_images/` - Image tile pyramids
- `cell_metadata.parquet` - Cell positions
- `cell_segmentation/` - Cell boundary tiles
- `trx_tiles/` - Transcript location tiles
- `meta_gene.parquet` - Gene metadata

See the [File Formats](../file_formats/index.md) documentation for details.

## API Reference

For detailed API documentation of each function, see the [API Reference](api.md).
