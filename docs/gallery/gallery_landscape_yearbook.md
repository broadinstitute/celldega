# Landscape-Yearbook Linked Visualization

This example demonstrates linking a Landscape visualization with a Yearbook view. The Yearbook shows individual cell "portraits" that can be queried by cluster or gene from the Landscape.

<div id="visualization-container" style="display: flex; flex-direction: column; width: 100%; gap: 10px;">
    <div style="display: flex; flex-direction: row; gap: 10px;">
        <div id="landscape-yb" style="flex: 1; height: 500px; border: 1px solid #ccc;"></div>
    </div>
    <div id="yearbook-yb" style="width: 100%; height: 600px; border: 1px solid #ccc;"></div>
</div>

## How It Works

The Landscape and Yearbook can be linked through the query system:

- **Cluster Query**: Select cells from a specific cluster to display as portraits
- **Gene Query**: Rank cells by gene expression, showing highest expressors first
- **Combined Query**: Filter by cluster AND rank by gene expression

## Usage in JavaScript

```javascript
import celldega from './widget.js';

// Initialize Landscape
const landscape = await celldega.landscape_ist(el, {}, token, x, y, z, zoom, base_url);

// Initialize Yearbook with a query
const yearbook = await celldega.yearbook(
    yb_el,
    {},
    token,
    base_url,
    'Dataset Name',
    [],           // cells (empty = use query)
    2,            // num_rows
    3,            // num_cols
    100,          // portrait_size_um
    4,            // portrait_gap
    0,            // width
    600,          // height
    {},           // meta_cell
    [],           // meta_cell_attr
    {},           // meta_cluster
    [],           // meta_cluster_attr
    'default',    // segmentation
    {},           // creds
    null,         // scale_bar_microns_per_pixel
    0,            // current_page
    { cluster: { attr: 'leiden', value: '1' }, gene: 'COL1A1' }  // query
);
```

[Dataset from 10X Genomics](https://www.10xgenomics.com/datasets)
