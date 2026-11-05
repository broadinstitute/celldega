# Getting Started

Celldega is a spatial and single-cell analysis and visualization library developed by the [Spatial Technology Platform](https://www.broadinstitute.org/spatial-technology-platform) at the [Broad Institute of MIT and Harvard](https://www.broadinstitute.org). Use its linked views to explore spatial tissue data, single-cell UMAP/XY landscapes, expression patterns, and gene-set enrichment.

## Video Tutorial

This narrated tutorial links a Landscape, Clustergram, and Enrich to analyze a Visium HD human colorectal cancer dataset. Follow along in the [Visium HD Human CRC Landscape-Clustergram-Enrich](../examples/tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb) notebook.

<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;">
    <iframe src="https://www.youtube.com/embed/IjGsIykVIUE" title="Visium HD human colorectal cancer tutorial in Celldega" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe>
</div>

## Visualization and supporting analysis

Celldega has two parts that work together:

1. **Interactive visualizations** for human-in-the-loop analysis. Explore tissue,
   cells, and gene expression; select, draw, and annotate what you find; and
   bring those selections back into your analysis. See
   [Visualizations](../visualizations/index.md).
2. **A Python back-end** that performs the analysis behind the visualizations:
    - hierarchical bi-clustering of genes and cell groups for Clustergrams
      ([`clust`](../python/clust/api.md));
    - creating tissue neighborhoods and calculating their attributes, such as
      cell-type composition and gene expression ([`nbhd`](../python/nbhd/api.md));
    - Collections: data structures for higher-level biological entities, such as
      neighborhoods, samples, and sets of cells, that keep several feature spaces
      together ([`collection`](../python/collection/api.md),
      [`dataset`](../python/dataset/api.md), [`set`](../python/set/api.md));
    - choosing and ranking cells to review in Yearbook
      ([`select`](../python/select/api.md));
    - fast alignment of serial sections into 3D for CellCloud and
      NeighborhoodCloud ([`align`](../python/align/api.md));
    - preparing instrument output as DegaFiles for the browser
      ([`pre`](../python/pre/api.md)).

The [Python API overview](../python/index.md) shows how the modules feed the
visualizations.

## What you can explore

Celldega provides:

- **[Landscape](../visualizations/landscape.md)**: Explore tissue images, cells, transcripts, and neighborhoods, or switch to UMAP and gene-expression XY views
- **[Matrix/Clustergram Visualization](../visualizations/clustergram.md)**: View hierarchical clustering heatmaps linked to spatial data
- **[Yearbook View](../visualizations/yearbook.md)**: Visualize individual cells as "portraits" in a grid layout
- **[CellCloud](../visualizations/cell-cloud.md)**: Explore cells in 3D, from thick tissue or aligned serial sections
- **[Neighborhood Analysis](../python/nbhd/api.md)**: Define and analyze tissue neighborhoods with alpha shapes and hextiles
- **[Multi-dataset Support](../visualizations/landscape.md#what-it-shows)**: Compare multiple datasets side-by-side

## Interacting with the Visualizations

Every Celldega visualization is interactive: scroll to zoom, drag to pan, hover
for details, and click to select clusters, genes, or regions. Selections can
also update other views. For example, clicking a gene in a Clustergram colors
the cells that express it in a linked Landscape.

The [Visualizations](../visualizations/index.md) overview introduces the
[control panel](../visualizations/index.md#the-control-panel) that most
visualizations share, and the
[two ways to use them](../visualizations/index.md#two-ways-to-use-a-visualization):
as notebook widgets with a Python back-end, or as JavaScript on a web page.
Each visualization's page then describes its interactions in detail. The
Celldega logo in every control panel opens that page:
[Landscape](../visualizations/landscape.md) ·
[Yearbook](../visualizations/yearbook.md) ·
[CellCloud](../visualizations/cell-cloud.md) ·
[NeighborhoodCloud](../visualizations/neighborhood-cloud.md) ·
[Clustergram](../visualizations/clustergram.md) ·
[Composition](../visualizations/composition.md) ·
[Enrich](../visualizations/enrich.md).

## Performance

Celldega provides responsive exploration of spatial transcriptomics datasets
with over 1 billion transcripts. Landscape loads data in spatial tiles: as you
zoom in, it fetches and draws every transcript in view, so you can move from a
whole tissue section to individual transcripts without waiting for the full
dataset to load. The [Celldega preprint](https://doi.org/10.64898/2026.08.13.744672)
benchmarks loading, transcript display, and interactive exploration on datasets
of 10 million to 1 billion transcripts; Celldega displayed transcripts without
delay and completed the exploration task at every size. See
[Technologies](technologies/index.md) for the visualization approach.

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

### Visualizations

Each visualization is a notebook widget in `dega.viz`. Landscape and Clustergram
also have [JavaScript entry points](../javascript/index.md) for web pages.

| Visualization | What you explore |
|--------|-------------|
| `Landscape` | Tissue images, cells, transcripts, and neighborhoods, or UMAP and gene-expression XY views |
| `Yearbook` | A grid of individual cell portraits |
| `CellCloud` | Cells in 3D, from thick tissue or aligned serial sections |
| `NeighborhoodCloud` | Tissue neighborhoods across slices in 3D |
| `Clustergram` | Hierarchically clustered heatmaps and dot plots |
| `Composition` | Cell-type proportions across groups |
| `Enrich` | Gene-set enrichment through Enrichr |

See [Visualizations](../visualizations/index.md) for all views and how to
use them together.

### Supported Technologies

Celldega works with spatial and single-cell data:

- **Spatial transcriptomics**: **Xenium**, including Atera (10x Genomics);
  **MERSCOPE** (Vizgen); **Visium HD** (10x Genomics); and **CosMx** (NanoString).
  3D data, such as aligned serial sections and thick-tissue MERFISH, display as
  point clouds.
- **Single-cell**: any AnnData, such as 10x **Chromium** RNA-seq
  ([PBMC 3k tutorial](../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)), a
  cell atlas ([Tabula Sapiens](../gallery/gallery_tabula_sapiens.md)), or RNA and
  surface protein measured in the same cells with CITE-seq
  ([PBMC cell types](../gallery/gallery_citeseq_pbmc.md)).

## Quick Start

### 1. Install Celldega

```bash
pip install celldega
```

### 2. Explore a public Xenium dataset

Open a prepared Xenium human pancreas dataset, hosted as DegaFiles on GitHub,
and link it to a Clustergram of each default cluster's mean gene expression:

```python
import ipywidgets as widgets
import pandas as pd
import celldega as dega

base_url = (
    "https://raw.githubusercontent.com/broadinstitute/celldega_Xenium_human_Pancreas_FFPE/"
    "main/Landscape_Xenium_V1_human_Pancreas_FFPE_outs_webp"
)

# Tissue image, cells, and transcripts, with neighborhood drawing turned on.
landscape = dega.viz.Landscape(base_url=base_url, height=600, nbhd_edit=True)

# Genes by default clusters (mean counts per cell), from the same DegaFiles.
df_sig = pd.read_parquet(f"{base_url}/df_sig.parquet")
mat = dega.clust.Matrix(df_sig)
mat.norm(axis="col", by="total")
mat.norm(axis="row", by="zscore")
mat.cluster()
cgm = dega.viz.Clustergram(matrix=mat, width=500, height=500)

# Clicking a gene or cluster in the Clustergram updates the Landscape.
widgets.jslink((cgm, "click_info"), (landscape, "update_trigger"))
widgets.HBox([landscape, cgm])
```

Click **NBHD**, then **SKTCH** (or press ++s++ over the tissue), and drag to
outline a region. The drawn neighborhood and its cells are then available in
Python:

```python
landscape.nbhd  # a GeoDataFrame of drawn neighborhoods
```

In Jupyter, `dega.viz.spatial_clustergram(landscape, cgm)` builds the same
linked layout; the explicit `jslink` above also works in Google Colab.

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

- [Celldega 0.28.0 Xenium pancreas Landscape and Clustergram](https://colab.research.google.com/drive/1HE7sa5Ju43fbVepF7YEhixjqWo5tRwpD?usp=sharing),
  the Quick Start example above
- [Celldega Xenium Landscape Visualizations](https://colab.research.google.com/drive/1NVZ07R0Eb-Xz6KBmMGRe3qmksYdeSBWc?usp=sharing)

### marimo molab

Open a prepared Atera dataset in a Landscape in marimo's cloud notebooks:

[![Open in molab](https://molab.marimo.io/molab-shield.svg)](https://molab.marimo.io/notebooks/nb_QLzYVa6S9nBApCwvw9vzni)

### ObservableHQ

Explore Celldega as a standalone JavaScript library:

- [Celldega Landscape Xenium ObservableHQ](https://observablehq.com/@cornhundred/celldega-xenium_prime_mouse_brain_coronal_ff_outs)

## Next Steps

- [Installation](installation.md) - Detailed installation instructions
- [Usage](usage/index.md) - Notebook, web, and desktop options
- [Visualizations](../visualizations/index.md) - The control panel and each visualization's interactions
- [Technologies](technologies/index.md) - Visualization and analysis foundations
- [File Formats](file_formats.md) - DegaFiles and AnnData Zarr format guide
- [Python API](../python/index.md) - Full Python API reference
- [JavaScript API](../javascript/index.md) - JavaScript API for web applications
- [Example Notebooks](../examples/index.md) - Jupyter notebook tutorials
