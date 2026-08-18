# Jupyter Notebook Examples

These example notebooks demonstrate how to use Celldega for spatial transcriptomics analysis and visualization. Each notebook is designed to be run in a Jupyter environment and showcases different features of the library.

## Tutorials

Comprehensive tutorials that walk through complete workflows:

<<<<<<< HEAD:docs/tutorials/index.md
- [Scanpy-Squidpy Xenium Pancreas](guided_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb) - Full analysis workflow using Scanpy and Squidpy with Xenium data
- [Chromium Pre-process](guided_notebooks/Scanpy_Chromium.ipynb) - Pre-processing Chromium single-cell RNA-seq data
- [Single-cell Clustergram Chromium](guided_notebooks/Single-Cell_Clustergram_Chromium.ipynb) - Creating clustergram visualizations for single-cell data
- [Visium-HD Landscape Pre-process](guided_notebooks/Visium-HD_Landscape_Pre-process.ipynb) - Pre-processing Visium HD data for Landscape visualization
- [Comparison of domain identification algorithms in Celldega](guided_notebooks/domain_comparison-Celldega_w_external_algorithms.ipynb) - Comparison of domain identification algorithms in Celldega's Landscape visualization
=======
- [Scanpy-Squidpy Xenium Pancreas](tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb) - Full analysis workflow using Scanpy and Squidpy with Xenium data
- [Preprocess DegaFiles and Viz Pancreas](tutorial_notebooks/Preprocess_DegaFiles_and_Viz_Pancreas.ipynb) - Preprocessing raw Xenium Pancreas data into DegaFiles and visualizing the result in a Landscape widget
- [Chromium Pre-process](tutorial_notebooks/Scanpy_Chromium.ipynb) - Pre-processing Chromium single-cell RNA-seq data
- [Single-cell Clustergram Chromium](tutorial_notebooks/Single-Cell_Clustergram_Chromium.ipynb) - Creating clustergram visualizations for single-cell data
>>>>>>> origin/main:docs/examples/index.md

## Brief Notebooks

Focused examples demonstrating specific features:

<<<<<<< HEAD:docs/tutorials/index.md
- [Landscape View Xenium](quick_notebooks/Landscape_View_Xenium.ipynb) - Basic Landscape visualization of Xenium data
- [Landscape-Heatmap Visium-HD](quick_notebooks/Landscape-Heatmap-Visium-HD.ipynb) - Combined Landscape and heatmap visualization
- [UMAP-Cluster Pancreas Xenium](quick_notebooks/UMAP-Cluster_Pancreas_Xenium.ipynb) - UMAP clustering with Xenium pancreas data
- [Visium-HD Landscape Mouse Lung](quick_notebooks/Visium-HD_Landscape_Mouse_Lung_FF.ipynb) - Visium HD visualization example
- [Custom Segmentation](quick_notebooks/Custom_Segmentation.ipynb) - Using custom cell segmentation with Celldega
- [Yearbook-Query](quick_notebooks/Yearbook_Query.ipynb) - Using single-cell Yearbook view
=======
- [Landscape View Xenium](brief_notebooks/Landscape_View_Xenium.ipynb) - Basic Landscape visualization of Xenium data
- [Atera Viz](brief_notebooks/Atera_viz.ipynb) - Linked Landscape and Clustergram visualization of a Xenium breast cancer dataset
- [Yearbook-Query](brief_notebooks/Yearbook_Query.ipynb) - Using single-cell Yearbook view
- [CellCloud Thick MERFISH](brief_notebooks/Landscape-3D_thick_MERFISH.ipynb) - 3D orbit-camera CellCloud view of thick-tissue MERFISH data
- [Landscape-Heatmap Visium-HD](brief_notebooks/Landscape-Heatmap-Visium-HD.ipynb) - Combined Landscape and heatmap visualization
- [UMAP-Cluster Pancreas Xenium](brief_notebooks/UMAP-Cluster_Pancreas_Xenium.ipynb) - UMAP clustering with Xenium pancreas data
- [Custom Segmentation](brief_notebooks/Custom_Segmentation.ipynb) - Using custom cell segmentation with Celldega
- [NeighborhoodCollection Population Space](brief_notebooks/NeighborhoodCollection_Population_Space.ipynb) - Creating a neighborhood collection and calculating a neighborhood-by-population modality
- [Gradient Neighborhood Pancreas Islets](brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb) - Building inward/outward gradient rings around pancreatic islets and profiling cell-type proportion and hormone expression with distance from the islet edge
- [DatasetCollection Population Space](brief_notebooks/DatasetCollection_Population_Space.ipynb) - Creating toy dataset-level data and calculating dataset-by-population modalities
- [SetCollection Cluster Space](brief_notebooks/SetCollection_Cluster_Space.ipynb) - Building a SetCollection from a Xenium clustering and clustering its per-set gene-expression signature
>>>>>>> origin/main:docs/examples/index.md

## Running the Notebooks

### Prerequisites

Install Celldega and its dependencies:

```bash
pip install celldega
```

For full analysis workflows, you may also need:

```bash
pip install scanpy squidpy
```

### Embedding interactive widgets in the docs

The docs are rendered statically by `mkdocs-jupyter`, which **displays saved widget state but does
not execute notebooks**. For an interactive `Landscape` / `Clustergram` (anywidget) to appear on the
docs site, the notebook's saved widget state must be complete and its model IDs must match the cell
outputs.

A plain "Run All + Save" in Jupyter Lab is unreliable for this: each `Landscape` streams a large
message (the embedded JS bundle plus the data parquet), and the state is only captured if the widget
has *fully* finished rendering in the browser before you save. Editing a cell and saving without a
full re-execution leaves stale or missing state, and the widgets render blank.

The reliable way to (re)build a docs notebook so its widgets embed is to execute it headless with a
raised `iopub_timeout` so those large messages aren't dropped:

```bash
jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=900 \
  --ExecutePreprocessor.iopub_timeout=120 \
  docs/examples/brief_notebooks/<Notebook>.ipynb
```

Tips:

- Put each widget as the **only expression in its own cell** (separate from its construction) —
  anywidget embeds most reliably that way.
- Don't add `%env ANYWIDGET_HMR=1` to a docs notebook. That dev-time hot-reload watches and reloads
  the widget's frontend module; running it while the frontend bundle is being rebuilt can desync the
  saved model IDs from the cell outputs.
- To confirm a notebook is good, check that every `application/vnd.jupyter.widget-view+json`
  `model_id` in the cell outputs also exists in `metadata.widgets["application/vnd.jupyter.widget-state+json"].state`.

### Online Resources

You can also run Celldega notebooks in the cloud:

- [Google Colab - Xenium Landscape Visualizations](https://colab.research.google.com/drive/1NVZ07R0Eb-Xz6KBmMGRe3qmksYdeSBWc?usp=sharing)
- [ObservableHQ - Celldega Landscape Xenium](https://observablehq.com/@cornhundred/celldega-xenium_prime_mouse_brain_coronal_ff_outs)
- [![Open in molab](https://molab.marimo.io/molab-shield.svg)](https://molab.marimo.io/notebooks/nb_NQM2YhNLyow8N56cit7xvC)
