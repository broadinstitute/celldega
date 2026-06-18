# Overview

Celldega is a spatial analysis and visualization library developed by the [Spatial Technology Platform](https://www.broadinstitute.org/spatial-technology-platform) at the [Broad Institute of MIT and Harvard](https://www.broadinstitute.org). It enables researchers to easily visualize and analyze large spatial transcriptomics (ST) datasets alongside single-cell and spatial analysis notebook workflows.

## Key Features

- **Large Dataset Support**: Efficiently visualize datasets with >100M transcripts
- **Interactive Widgets**: Jupyter Widget-based visualizations that integrate with notebook workflows
- **Multi-platform Support**: Works with Xenium, MERSCOPE, Visium HD, and Chromium data
- **Linked Visualizations**: Connect Landscape views with Clustergram heatmaps
- **Neighborhood Analysis**: Define and analyze tissue neighborhoods with alpha shapes and hextiles

## Architecture

Celldega consists of two main components:

### Python Library

Used in Jupyter notebooks for:

- Pre-processing raw ST data into LandscapeFiles format
- Clustering and analysis with the Matrix class
- Neighborhood computation with alpha shapes and hextiles
- Creating interactive visualization widgets

### JavaScript Library

Powers the interactive visualizations:

- Deck.gl-based spatial rendering
- Efficient tile-based data loading
- Synchronized multi-view displays
- Web-compatible standalone usage

## Workflow

A typical Celldega workflow involves:

1. **Pre-process** raw data to create LandscapeFiles
2. **Cluster** and analyze data using Scanpy/Squidpy
3. **Visualize** with interactive widgets
4. **Explore** spatial patterns and gene expression

```python
import celldega as dega
import scanpy as sc

# Pre-process data
dega.pre.main(technology="Xenium", data_dir="./data", path_dega_files="./output")

# Load and cluster
adata = sc.read_h5ad("processed.h5ad")
sc.tl.leiden(adata)

# Visualize
landscape = dega.viz.Landscape(base_url="./output", adata=adata, ini_zoom=-5)
landscape
```

## Getting Started

- [Getting Started Guide](getting_started.md) - Quick start with installation and examples
- [Installation](installation.md) - Detailed installation instructions
- [File Formats](file_formats.md) - Understanding LandscapeFiles
- [Usage](usage.md) - In-depth usage guide
