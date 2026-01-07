# Python API Overview

The Celldega Python API provides modules for pre-processing spatial transcriptomics data, clustering analysis, neighborhood computation, and interactive visualization.

## Installation

```bash
pip install celldega
```

## Core Modules

### [Pre Module](pre/api.md)

The `pre` module contains functions for pre-processing raw spatial transcriptomics data into LandscapeFiles format. This includes:

- Creating image tile pyramids for efficient zooming
- Generating cell metadata and boundary tiles
- Processing transcript data
- Building cluster assignments and gene expression signatures

```python
import celldega as dega

# Pre-process Xenium data
dega.pre.main(
    technology="Xenium",
    data_dir="/path/to/xenium_outs",
    path_landscape_files="/path/to/output",
    tile_size=250
)
```

### [Clust Module](clust/api.md)

The `clust` module provides the `Matrix` class for hierarchical clustering and heatmap visualization. It supports:

- Automatic data processing pipelines
- Multiple normalization methods (zscore, quantile, total)
- Hierarchical clustering with dendrograms
- Integration with Clustergram widget

```python
import celldega as dega

# Create and cluster a matrix
mat = dega.clust.Matrix(adata, filter_genes=5000)
mat.cluster()

# Export for visualization
cgm = dega.viz.Clustergram(matrix=mat)
```

### [Nbhd Module](nbhd/api.md)

The `nbhd` module contains functions for computing and analyzing tissue neighborhoods:

- Alpha shape computation for cluster-based neighborhoods
- Hexagonal tiling for regular neighborhood grids
- Neighborhood-by-gene expression analysis
- Neighborhood overlap and bordering calculations

```python
import celldega as dega

# Compute alpha shapes for cell clusters
gdf_alpha = dega.nbhd.alpha_shape_cell_clusters(
    adata, 
    cat="leiden", 
    alphas=[100, 150, 200]
)

# Generate hexagonal tiles
gdf_hex = dega.nbhd.generate_hextile(adata, diameter=100)

# Calculate neighborhood-by-gene expression
adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_alpha, by="cell", adata=adata)
```

### [Viz Module](viz/api.md)

The `viz` module provides Jupyter Widget classes for interactive visualization:

| Widget | Description |
|--------|-------------|
| `Landscape` | Main spatial visualization for IST/SST data |
| `Clustergram` | Hierarchical clustering heatmap |
| `Yearbook` | Grid of cell "portraits" |
| `Enrich` | Gene enrichment analysis |

```python
import celldega as dega

# Create a Landscape widget
landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    adata=adata,
    ini_x=10000,
    ini_y=10000,
    ini_zoom=-5
)

# Display linked Landscape and Clustergram
display = dega.viz.landscape_clustergram(landscape, cgm)
```

## Quick Reference

### Common Imports

```python
import celldega as dega

# Access submodules
dega.pre      # Pre-processing functions
dega.clust    # Clustering (Matrix class)
dega.nbhd     # Neighborhood analysis
dega.viz      # Visualization widgets
```

### Key Classes and Functions

| Module | Key Components |
|--------|---------------|
| `dega.pre` | `main()`, `create_image_tiles()`, `make_meta_gene()` |
| `dega.clust` | `Matrix` |
| `dega.nbhd` | `alpha_shape_cell_clusters()`, `generate_hextile()`, `calc_nbhd_by_gene()`, `NBHD` |
| `dega.viz` | `Landscape`, `Clustergram`, `Yearbook`, `Enrich`, `landscape_clustergram()` |
