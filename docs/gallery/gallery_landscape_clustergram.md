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

## Saving Clustergram to DegaFiles

To enable the Clustergram in a JavaScript-only environment, you need to save the data using Python:

```python
import celldega as dega

# Create and cluster your matrix
mat = dega.clust.Matrix(adata)
mat.clust()

# Save to DegaFiles directory
mat.write_dega_files("./my_dega_files", name="my_clustergram")
```

## Usage in JavaScript

```javascript
import celldega from './widget.js';

// Initialize Landscape
const landscape = await celldega.landscape_ist(el, {}, token, x, y, z, zoom, base_url);

// Load and render Clustergram from DegaFiles with callbacks
const matrix = await celldega.matrix_from_dega_files(
    matrix_el,
    base_url,
    'my_clustergram',              // Clustergram name (matches name used in write_dega_files)
    500,                            // width
    500,                            // height
    landscape.update_matrix_gene,   // Gene click callback
    landscape.update_matrix_col,    // Cluster click callback
    landscape.update_matrix_dendro_col // Dendrogram callback
);
```

[Dataset from 10X Genomics](https://www.10xgenomics.com/datasets)
