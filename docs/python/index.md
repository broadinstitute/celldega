# Python API Overview

The Celldega Python API provides modules for collection schemas,
dataset-level feature spaces, pre-processing spatial transcriptomics data, hierarchical bi-clustering
analysis, neighborhood computation, and interactive visualization.

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

# Create and cluster a matrix
mat = dega.clust.Matrix(adata, filter_genes=5000)
mat.cluster()

# Export for visualization
cgm = dega.viz.Clustergram(matrix=mat)
```

### [Collection Module](collection/api.md)

The `collection` module defines typed MuData profiles for aligned
dataset-level and neighborhood-level data:

- `dega.dataset.DatasetCollection` for dataset, sample, tissue section, or patient observations
- `NeighborhoodCollection` for neighborhood or spatial-region observations
- `HierarchyResult` for clustering or tree outputs derived from a modality or relation

```python
import celldega as dega

dset = dega.dataset.DatasetCollection(adata, dataset_col="sample_id")
nbhd = dega.NeighborhoodCollection(obs=neighborhood_obs, geometry=neighborhood_gdf)
```

### [Dataset Module](dataset/api.md)

The `dataset` module contains dataset-level modality constructors and helpers for
building `DatasetCollection` objects:

- Dataset-by-population modality
- Dataset/sample metadata aggregation into `DatasetCollection.obs`
- Dataset-by-signature modality
- Attachment of aligned modalities to `DatasetCollection.mod`
- H5MU writing through the underlying MuData object

```python
import celldega as dega

dset = dega.dataset.DatasetCollection(
    adata,
    dataset_col="sample_id",
    obs_columns=["patient_id", "condition"],
)

dset.calc_dataset_by_pop(adata, category="cell_type")
population = dset.mod["population"]
dset.write("dataset.h5mu")
```

### [Nbhd Module](nbhd/api.md)

The `nbhd` module contains functions for computing and analyzing tissue neighborhoods:

- Hexagonal tiling for regular neighborhood grids
- Alpha shape computation for cluster-based neighborhoods
- Gradient neighborhoods derived from initial region/neighborhood
- Collection-backed neighborhood-by-gene and neighborhood-by-population modalities
- Neighborhood overlap and bordering calculations
- Collection-backed methods for constructing gene, population, and relation data

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

# Attach feature-space modalities to a NeighborhoodCollection
nbhd = dega.nbhd.NeighborhoodCollection(gdf=gdf_alpha, nbhd_type="alpha_shape")
nbhd.calc_nbhd_by_gene(adata=adata, by="cell", modality_name="gene")
nbhd.calc_nbhd_by_pop(adata, category="leiden", modality_name="population")
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
)

# Display linked Landscape and Clustergram
display = dega.viz.landscape_clustergram(landscape, cgm)
```
