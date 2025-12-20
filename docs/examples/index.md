# Jupyter Notebook Examples

These example notebooks demonstrate how to use Celldega for spatial transcriptomics analysis and visualization. Each notebook is designed to be run in a Jupyter environment and showcases different features of the library.

## Tutorials

Comprehensive tutorials that walk through complete workflows:

- [Scanpy-Squidpy Xenium Pancreas](tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb) - Full analysis workflow using Scanpy and Squidpy with Xenium data
- [Chromium Pre-process](tutorial_notebooks/Scanpy_Chromium.ipynb) - Pre-processing Chromium single-cell RNA-seq data
- [Single-cell Clustergram Chromium](tutorial_notebooks/Single-Cell_Clustergram_Chromium.ipynb) - Creating clustergram visualizations for single-cell data
- [Visium-HD Landscape Pre-process](tutorial_notebooks/Visium-HD_Landscape_Pre-process.ipynb) - Pre-processing Visium HD data for Landscape visualization

## Brief Notebooks

Focused examples demonstrating specific features:

- [Landscape View Xenium](brief_notebooks/Landscape_View_Xenium.ipynb) - Basic Landscape visualization of Xenium data
- [Landscape-Heatmap Visium-HD](brief_notebooks/Landscape-Heatmap-Visium-HD.ipynb) - Combined Landscape and heatmap visualization
- [UMAP-Cluster Pancreas Xenium](brief_notebooks/UMAP-Cluster_Pancreas_Xenium.ipynb) - UMAP clustering with Xenium pancreas data
- [Visium-HD Landscape Mouse Lung](brief_notebooks/Visium-HD_Landscape_Mouse_Lung_FF.ipynb) - Visium HD visualization example
- [Custom Segmentation](brief_notebooks/Custom_Segmentation.ipynb) - Using custom cell segmentation with Celldega

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

### Online Resources

You can also run Celldega notebooks in the cloud:

- [Google Colab - Xenium Landscape Visualizations](https://colab.research.google.com/drive/1NVZ07R0Eb-Xz6KBmMGRe3qmksYdeSBWc?usp=sharing)
- [ObservableHQ - Celldega Landscape Xenium](https://observablehq.com/@cornhundred/celldega-landscape-xenium-observablehq)
