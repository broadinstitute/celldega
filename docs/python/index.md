# Python API Overview

The Celldega Python API provides modules for pre-processing spatial
transcriptomics data, hierarchical bi-clustering analysis, neighborhood
computation, and interactive visualization. Every function works on standard
scverse data structures (`AnnData`, `MuData`) and `GeoDataFrame` neighborhoods,
and returns new objects of the same kinds.

Higher-level data structures built on top of these (dataset, neighborhood, and
set collections), cell selection queries, and serial-slice alignment live in the
separate `dega-collection` package, much like AnnData lives apart from Scanpy.

## Installation

```bash
pip install celldega
```

## Core Modules

### [Clust Module](clust/api.md)

The `clust` module provides the `Matrix` class for hierarchical bi-clustering as a
precursor to interactive clustergram visualization. It supports:

- Multiple normalization methods (zscore, quantile, total)
- Hierarchical clustering with dendrograms
- Integration with Clustergram widget

```python
import celldega as dega
import scanpy as sc

# Create and cluster a matrix
mat = dega.clust.Matrix(adata)
mat.filter("row", by="var", num=5000)
mat.norm("col", by="total")
mat.norm("row", by="zscore")
mat.cluster()

# Export for visualization
cgm = dega.viz.Clustergram(matrix=mat)

# Marker dot plot straight from a cell-level AnnData
sc.tl.rank_genes_groups(adata, groupby="leiden")
mat = dega.clust.Matrix(adata, groupby="leiden")
mat.cluster(view="rank_genes_groups")
```

### [Nbhd Module](nbhd/api.md)

The `nbhd` module builds tissue neighborhoods as `GeoDataFrame`s and summarizes
cells within them:

- Alpha shapes for cluster-based neighborhoods (per dataset or per slice)
- Hexagonal tiling for regular neighborhood grids
- Gradient neighborhoods around a region of interest
- Neighborhood-by-gene and neighborhood-by-population matrices from `AnnData` or `MuData`
- Neighborhood overlap and bordering relations

```python
import celldega as dega

# Compute alpha shapes for cell clusters
gdf_alpha = dega.nbhd.alpha_shape_cell_clusters(adata, cat="leiden", alphas=[150])

# Generate hexagonal tiles
gdf_hex = dega.nbhd.generate_hextile(adata, diameter=100)

# Summarize cells per neighborhood as new AnnData objects
adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_hex, "cell", adata)
adata_nbp = dega.nbhd.calc_nbhd_by_pop(adata, gdf_hex, category="leiden")
```


### [Pre Module](pre/api.md)

The `pre` module contains functions for pre-processing raw spatial
transcriptomics data into DegaFiles format. This includes:

- Creating image tile pyramids for efficient zooming
- Generating cell metadata and boundary tiles
- Processing transcript tiles

```python
import celldega as dega

# Pre-process Xenium data
dega.pre.main(
    technology="Xenium",
    data_dir="/path/to/xenium_outs",
    path_dega_files="/path/to/output",
    tile_size=250
)
```

### [Viz Module](viz/api.md)

The `viz` module provides Jupyter Widget classes for interactive
visualization. See the [Visualizations](../visualizations/index.md) section
for what each one shows and how it works:

| Widget | Description |
|--------|-------------|
| `Landscape` | Main spatial visualization for segmented spatial data |
| `Clustergram` | Hierarchical clustering heatmap |
| `Yearbook` | Grid of cell "portraits" |
| `CellCloud` | 3D orbit view of cell centroids |
| `NeighborhoodCloud` | 3D orbit view of tissue neighborhoods |
| `Composition` | Category composition across groups (`Clustergram` variant) |
| `Enrich` | Gene enrichment analysis |

```python
import celldega as dega

# Create a Landscape widget
landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    adata=adata,
)

# Display linked Landscape and Clustergram
display = dega.viz.landscape_clustergram(landscape, cgm)
```
