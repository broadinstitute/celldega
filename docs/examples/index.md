# Jupyter Notebook Examples

These example notebooks demonstrate how to use Celldega for spatial transcriptomics and multi-omics analysis and visualization. Each notebook is designed to be run in a Jupyter environment and showcases different features of the library.

## Spatial Transcriptomics Tutorials

Comprehensive tutorials that walk through complete workflows:

- [Atera Kidney Landscape-Clustergram](tutorial_notebooks/Atera_Kidney_Landscape-Clustergram.ipynb) - Direct Scanpy and AnnData steps for default clusters, linked dotplot Clustergrams, and cell-type composition across podocyte-defined glomerular gradients
- [Atera Breast Cancer Landscape-Clustergram](tutorial_notebooks/Atera_Breast_Cancer_Landscape-Clustergram.ipynb) - Loads a precomputed Scanpy clustering (or optionally recomputes it) and creates linked Landscape, Clustergram, and Enrich widgets
- [Atera Breast Cancer Neighborhood Exploration](tutorial_notebooks/Atera_Breast_Cancer_Neighborhood_Exploration.ipynb) - Continues the Atera tutorial with hextile niches linked to cell-type composition and alpha-shape overlap linked to a separate Landscape
- [Visium HD Human CRC Landscape-Clustergram-Enrich](tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb) - Uses Scanpy and plain AnnData to summarize a clustered Visium HD colorectal cancer sample (signatures, fraction expressing, marker genes) and explores it in linked Landscape, Clustergram, and Enrich widgets, ready for interactive annotation
- [Scanpy-Squidpy Xenium Pancreas](tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb) - Full analysis workflow using Scanpy and Squidpy with Xenium data
- [Preprocess DegaFiles and Viz Pancreas](tutorial_notebooks/Preprocess_DegaFiles_and_Viz_Pancreas.ipynb) - Preprocessing raw Xenium Pancreas data into DegaFiles and visualizing the result in a Landscape widget
- [Broad-Allen Dev Mouse Brain E15.5 Viz](tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb) - Visualizes the aligned E15.5 brain as a 3D CellCloud linked to the cluster composition of every slice and to a gene-expression Clustergram

## Single Cell Tutorials

Tutorials for single-cell data without spatial coordinates:

- [Chromium PBMC Landscape-Clustergram-Enrich](tutorial_notebooks/Scanpy_Chromium.ipynb) - Downloads a 10x PBMC count matrix, clusters cells with Scanpy, and uses plain AnnData for expression signatures, fraction expressing, and marker-ranked Clustergram views linked to a UMAP Landscape and Enrich, plus a single-cell Clustergram linked to Enrich

## Multi-Omic Tutorials

Tutorials that combine several omics measured on the same samples:

- [Flex CITE-seq PBMC Landscape-Clustergram-Enrich](tutorial_notebooks/Flex_CITE-seq_PBMC_Landscape-Clustergram-Enrich.ipynb) - Explores RNA and 184 surface proteins in 12,242 PBMCs across levels of the cell hierarchy: QC-guided filtering with a UMAP linked to a cluster Clustergram, cell types compared across RNA and protein, and single-cell Clustergrams of B-cell subtypes and suspected B + T doublets
- [CST Lung Cancer PTM Clustergram-Enrich](tutorial_notebooks/CST_Lung_Cancer_PTM_Clustergram-Enrich.ipynb) - Reproduces the Clustergrammer lung cancer case study with a MuData of phosphorylation, methylation, acetylation, and gene expression across 37 cell lines: a Clustergram for each PTM type, stacked PTM, gene expression (linked to Enrich), and merged PTM-expression Clustergrams, plus a comparison of the cell line clusters found by each omic

## Brief Notebooks

Focused examples demonstrating specific features:

- [Landscape View Xenium](brief_notebooks/Landscape_View_Xenium.ipynb) - Basic Landscape visualization of Xenium data
- [Landscape from a Local Server](brief_notebooks/Landscape_Local_Server.ipynb) - Viewing locally stored DegaFiles in a Landscape with `dega.viz.get_local_server()`
- [Atera Viz](brief_notebooks/Atera_viz.ipynb) - Linked Landscape and Clustergram visualization of a Xenium breast cancer dataset
- [Atera Pre-process](brief_notebooks/Atera_Pre-process.ipynb) - Making DegaFiles from a 10x Atera output bundle with `dega.pre.main` and viewing them in a Landscape
- [Yearbook-Query](brief_notebooks/Yearbook_Query.ipynb) - Using single-cell Yearbook view
- [CellCloud Thick MERFISH](brief_notebooks/Landscape-3D_thick_MERFISH.ipynb) - 3D orbit-camera CellCloud view of thick-tissue MERFISH data
- [Landscape-Heatmap Visium-HD](brief_notebooks/Landscape-Heatmap-Visium-HD.ipynb) - Combined Landscape and heatmap visualization
- [UMAP-Cluster Pancreas Xenium](brief_notebooks/UMAP-Cluster_Pancreas_Xenium.ipynb) - UMAP clustering with Xenium pancreas data
- [Custom Segmentation](brief_notebooks/Custom_Segmentation.ipynb) - Using custom cell segmentation with Celldega
- [Gradient Neighborhood Pancreas Islets](brief_notebooks/Gradient_Neighborhood_Pancreas_Islets.ipynb) - Building inward/outward gradient rings around pancreatic islets and profiling cell-type proportion and hormone expression with distance from the islet edge

<!-- CCLE multi-omics tutorials temporarily hidden

## CCLE Multi-omics Tutorials

This numbered series demonstrates coverage-preserving `MuData` workflows for
bulk cancer cell lines. It begins with a
global hierarchical map, compares independent RNA, RPPA, and metabolomics
spaces, then examines recurring programs and a lung SCLC/NSCLC example.

- [CCLE multi-omics overview](ccle_multiomics.md)
- [00: Prepare archive](tutorial_notebooks/CCLE_Multiomics_00_Prepare.ipynb)
- [01: Global hierarchy](tutorial_notebooks/CCLE_Multiomics_01_Global_Hierarchy.ipynb)
- [02: Cross-omic concordance](tutorial_notebooks/CCLE_Multiomics_02_Cross_Omic_Concordance.ipynb)
- [03: Tissue gene programs](tutorial_notebooks/CCLE_Multiomics_03_Tissue_Gene_Programs.ipynb)
- [04: Lung multi-omic subclustering](tutorial_notebooks/CCLE_Multiomics_04_Lung_Multiomic_Subclustering.ipynb)
- [05: Pan-CCLE multi-omic consensus](tutorial_notebooks/CCLE_Multiomics_05_Pan_CCLE_Multiomic_Consensus.ipynb)
- [06: Hematologic multi-omic subclustering](tutorial_notebooks/CCLE_Multiomics_06_Hematologic_Multiomic_Subclustering.ipynb)
- [07: Tissue mixing and provenance review](tutorial_notebooks/CCLE_Multiomics_07_Tissue_Mixing_and_Provenance_Review.ipynb)
- [08: RNA-anchored multi-omic characterization](tutorial_notebooks/CCLE_Multiomics_08_RNA_Anchored_Multiomic_Characterization.ipynb)
- [09: CST lung TMT PTM integration](tutorial_notebooks/CCLE_Multiomics_09_CST_Lung_PTM_Integration.ipynb)

-->

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
