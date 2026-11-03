# Getting Started

Celldega is a spatial analysis and visualization library developed by the [Spatial Technology Platform](https://www.broadinstitute.org/spatial-technology-platform) at the [Broad Institute of MIT and Harvard](https://www.broadinstitute.org). Use its linked views to explore spatial tissue data, single-cell UMAP/XY landscapes, expression patterns, and gene-set enrichment.

## Video Tutorial

This narrated tutorial links a Landscape, Clustergram, and Enrich to analyze a Visium HD human colorectal cancer dataset. Follow along in the [Visium HD Human CRC Landscape-Clustergram-Enrich](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb) notebook.

<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;">
    <iframe src="https://www.youtube.com/embed/IjGsIykVIUE" title="Visium HD human colorectal cancer tutorial in Celldega" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe>
</div>

## What you can explore

Celldega provides:

- **Landscape**: Explore tissue images, cells, transcripts, and neighborhoods, or switch to UMAP and gene-expression XY views
- **Matrix/Clustergram Visualization**: View hierarchical clustering heatmaps linked to spatial data
- **Yearbook View**: Visualize individual cells as "portraits" in a grid layout
- **Neighborhood Analysis**: Define and analyze tissue neighborhoods with alpha shapes and hextiles
- **Multi-dataset Support**: Compare multiple datasets side-by-side

## Key Concepts

### DegaFiles and AnnData Zarr

**DegaFiles** prepare spatial datasets for browser visualization, with image
pyramids, cell metadata and boundaries, transcripts, expression, and cluster
assignments. Landscape loads the tiles needed for the current view.

**AnnData Zarr** stores analysis inputs and complete clustered Matrix objects.
A single-cell Landscape can also read cell metadata, UMAP coordinates, and
per-gene expression directly from an AnnData Zarr store.

See [File Formats](file_formats.md) for layouts, row-group storage within
DegaFiles, and Matrix persistence before and after clustering.

### Widgets

Celldega provides several Jupyter Widget classes for interactive visualization:

| Widget | Description |
|--------|-------------|
| `Landscape` | Spatial tissue and low dimensional embedding landscapes (UMAP/XY) |
| `Clustergram` | Hierarchical clustering heatmap (matrix) |
| `Yearbook` | Grid of cell portraits |
| `Enrich` | Gene enrichment analysis widget |

See [Visualizations](../visualizations/index.md) for all views and how to
use them together.

### Supported Technologies

Celldega supports multiple spatial transcriptomics platforms:

- **Xenium** (10x Genomics)
- **MERSCOPE** (Vizgen)
- **Visium HD** (10x Genomics)
- **CosMx** (NanoString)
- **Chromium** (single-cell RNA-seq)
- **Custom point-cloud data**

## Quick Start

### 1. Install Celldega

```bash
pip install celldega
```

### 2. Visualize Pre-processed Data

If you have prepared DegaFiles:

```python
import celldega as dega

# Create a Landscape widget
landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    ini_x=10000,
    ini_y=10000,
    ini_zoom=-5,
    height=600
)
landscape
```

### 3. Pre-process Your Own Data

For Xenium data:

```python
import celldega as dega

# Pre-process the Xenium sample directory into DegaFiles
dega.pre.main(
    sample="xenium_outs",
    data_root_dir="/path/to",
    path_dega_files="/path/to/output",
    tile_size=250
)
```

### 4. Integrate with AnnData

Use an analyzed AnnData to supply cell annotations, cluster colors, and UMAP coordinates:

```python
import anndata as ad
import celldega as dega

adata = ad.read_h5ad("your_analyzed_data.h5ad")

# Cell IDs in adata.obs_names must match the DegaFiles cell IDs.
landscape = dega.viz.Landscape(
    base_url="https://your-landscape-files-url",
    adata=adata,
    ini_x=10000,
    ini_y=10000,
    ini_zoom=-5
)
landscape
```

For a single-cell Landscape, use a cell-level AnnData Zarr with a CSC
expression layer instead of `base_url`:

```python
adata.layers["counts_csc"] = adata.layers["counts"].tocsc()
adata.write_zarr("cells.zarr")

single_cell = dega.viz.Landscape(
    zarr_url="cells.zarr",
    zarr_layer="counts_csc",
    cluster_attr="leiden",
)
```

This example assumes sparse counts in `adata.layers["counts"]`.
See the [Landscape guide](../visualizations/landscape.md) for preparation,
viewport summaries, and neighborhood selection.

### 5. Create a Clustergram

```python
import celldega as dega

# Create a Matrix from AnnData
mat = dega.clust.Matrix(adata)
mat.cluster()

# Visualize as a Clustergram
cgm = dega.viz.Clustergram(matrix=mat, width=800, height=600)
cgm
```

Save a complete clustered Matrix with `mat.write_zarr("matrix.zarr")` and
restore it with `dega.clust.Matrix.read_zarr("matrix.zarr")`. See the
[Matrix API](../python/clust/api.md#saving-matrix-inputs-and-clustered-objects)
for details.

## Try It Online

### Google Colab

Try Celldega in Google Colab without any installation:

- [Celldega Xenium Landscape Visualizations](https://colab.research.google.com/drive/1NVZ07R0Eb-Xz6KBmMGRe3qmksYdeSBWc?usp=sharing)

### ObservableHQ

Explore Celldega as a standalone JavaScript library:

- [Celldega Landscape Xenium ObservableHQ](https://observablehq.com/@cornhundred/celldega-xenium_prime_mouse_brain_coronal_ff_outs)

## Next Steps

- [Installation](installation.md) - Detailed installation instructions
- [Usage](usage/index.md) - Notebook, web, and desktop options
- [Technologies](technologies/index.md) - Visualization and analysis foundations
- [File Formats](file_formats.md) - DegaFiles and AnnData Zarr format guide
- [Python API](../python/index.md) - Full Python API reference
- [JavaScript API](../javascript/index.md) - JavaScript API for web applications
- [Example Notebooks](../examples/index.md) - Jupyter notebook tutorials
