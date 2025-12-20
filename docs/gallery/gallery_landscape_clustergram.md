# Landscape-Clustergram Linked Visualization

This example demonstrates linking a Landscape visualization with a Clustergram heatmap. Clicking on genes in the Clustergram highlights them in the Landscape, and clicking on clusters colors the cells accordingly.

<div id="visualization-container" style="display: flex; flex-direction: row; width: 100%; gap: 10px; margin-bottom: 20px;">
    <div id="landscape-linked" style="flex: 1; height: 600px; border: 1px solid #ccc;"></div>
    <div id="matrix-linked" style="width: 500px; height: 600px; border: 1px solid #ccc;"></div>
</div>

## How It Works

The Landscape and Clustergram are linked through callback functions:

- **`update_matrix_gene(gene)`**: Called when clicking on a gene row in the Clustergram - highlights the gene's transcripts in the Landscape
- **`update_matrix_col(cluster)`**: Called when clicking on a cluster column - colors cells by that cluster
- **`update_matrix_dendro_col(clusters)`**: Called when selecting multiple clusters via dendrogram

## Usage in JavaScript

```javascript
import celldega from './widget.js';

// Initialize Landscape
const landscape = await celldega.landscape_ist(el, {}, token, x, y, z, zoom, base_url);

// Initialize Matrix with callbacks to Landscape
celldega.matrix_viz(
    {},
    matrix_el,
    network,
    500,
    500,
    landscape.update_matrix_gene,     // Gene click callback
    landscape.update_matrix_col,      // Cluster click callback
    landscape.update_matrix_dendro_col // Dendrogram callback
);
```

[Dataset from 10X Genomics](https://www.10xgenomics.com/datasets)
