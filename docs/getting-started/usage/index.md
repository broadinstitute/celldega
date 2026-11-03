# Usage

Use Celldega in local or cloud notebooks, in a standalone web page, or
through the publicly available Celldega-App alpha.

## In a notebook

Use Celldega downstream of single-cell and spatial analysis workflows, such as
Scanpy and Squidpy, to interactively visualize the results. Bring cluster
annotations, UMAP coordinates, gene expression, and neighborhood summaries from
your analysis into linked Landscape, Clustergram, and Enrich widgets.

### Example workflows

- **[Chromium PBMC: Landscape–Clustergram–Enrich](../../examples/tutorial_notebooks/Scanpy_Chromium.ipynb)**
  — analyze single-cell RNA-seq data with Scanpy, then explore clusters, UMAP/XY
  landscapes, marker-gene dot plots, and gene-set enrichment in linked views.
- **[Scanpy–Squidpy Xenium Pancreas](../../examples/tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb)**
  — explore Scanpy clusters and expression patterns alongside Squidpy spatial
  neighborhood-enrichment results using Landscapes and Clustergrams.

See [Example Notebooks](../../examples/index.md) for more workflows.

### Notebook options

- **Local Jupyter** — JupyterLab or Jupyter Notebook running on your own
  machine, following the standard [Installation](../installation.md)
  and [Getting Started](../index.md) guides.
- **Cloud notebook services** — hosted notebook environments such as
  [Manifold.ai](https://www.manifold.ai/),
  [Google Colab](https://colab.research.google.com/),
  [marimo](https://marimo.io/), and [molab](https://molab.marimo.io/).
  Celldega installs like any other PyPI package (`pip install celldega`); widget rendering depends on the
  service supporting the Jupyter Widgets protocol.

## On a web page

Celldega's visualizations also run outside of a notebook entirely, as a
stand-alone JavaScript library against publicly hosted data — see the
[JavaScript API](../../javascript/index.md). The [Gallery](../../gallery/index.md)
is a collection of such stand-alone web pages showcasing datasets across
technologies (Xenium, CosMx, Visium HD, and more).

## Desktop app (alpha)

[Celldega-App](https://github.com/broadinstitute/celldega-app) is publicly
available as an alpha desktop app for opening local or remote DegaFiles.
It provides linked Landscape, Clustergram, and Yearbook windows, with no
notebook required for viewing prepared data.

[Download an alpha build](https://github.com/broadinstitute/celldega-app/releases)
and follow the app's
[installation instructions](https://github.com/broadinstitute/celldega-app#install).
