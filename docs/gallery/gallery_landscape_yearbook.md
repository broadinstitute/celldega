# Landscape-Yearbook Linked Visualization

This example demonstrates linking a Landscape visualization with a Yearbook view. The Yearbook shows individual cell "portraits" that can be queried by cluster or gene from the Landscape.

**Try it:** Select a gene or cluster in the Landscape (via the Clustergram if linked) to see the Yearbook automatically update!

<div id="visualization-container" style="display: flex; flex-direction: column; width: 100%; gap: 10px;">
    <div style="display: flex; flex-direction: row; gap: 10px;">
        <div id="landscape-yb" style="flex: 1; height: 500px; border: 1px solid #ccc;"></div>
    </div>
    <div id="yearbook-yb" style="width: 100%; height: 600px; border: 1px solid #ccc;"></div>
</div>

## How It Works

The Landscape and Yearbook are linked through callback functions:

- **`on_gene_select(callback)`**: Fires when a gene is selected - Yearbook ranks cells by expression
- **`on_cluster_select(callback)`**: Fires when a cluster is selected - Yearbook shows cells from that cluster
- **`on_clusters_select(callback)`**: Fires when multiple clusters are selected via dendrogram

The Yearbook provides update methods:

- **`update_gene(gene_name)`**: Update query to rank cells by gene expression
- **`update_cluster(cluster_id)`**: Update query to filter by cluster
- **`update_query(query_obj)`**: Update the full query object

## Usage in JavaScript

```javascript
import celldega from './celldega.js';

// Initialize Landscape
const landscape = await celldega.landscape_ist(el, {}, token, x, y, z, zoom, base_url);

// Initialize Yearbook
const yearbook = await celldega.yearbook(
    yb_el, {}, token, base_url, 'Dataset Name',
    [], 2, 3, 100, 4, 0, 600,
    {}, [], {}, [], 'default', {}, null, 0,
    { cluster: { attr: 'leiden', value: '1' } }
);

// Link them: when gene is selected in Landscape, update Yearbook
landscape.on_gene_select((gene_name) => {
    yearbook.update_gene(gene_name);
});

// Link them: when cluster is selected, show cells from that cluster
landscape.on_cluster_select((cluster_id) => {
    yearbook.update_cluster(cluster_id);
});
```

## Python Usage with Linked Widgets

In Jupyter notebooks, you can use the `landscape_yearbook` function to automatically link the widgets:

```python
import celldega as dega

landscape = dega.viz.Landscape(base_url="...", adata=adata)
yearbook = dega.viz.Yearbook(base_url="...", rows=2, cols=4)

# Create linked display - clicking clusters/genes in Landscape updates Yearbook
display = dega.viz.landscape_yearbook(landscape, yearbook)
```

[Dataset from 10X Genomics](https://www.10xgenomics.com/datasets)
