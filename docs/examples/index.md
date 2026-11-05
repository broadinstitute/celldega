# Jupyter Notebook Examples

These example notebooks demonstrate how to use Celldega to analyze and visualize spatial and single-cell data. Each notebook is designed to be run in a Jupyter environment and showcases different features of the library.

## Spatial Transcriptomics Tutorials

Comprehensive tutorials that walk through complete workflows:

- [Atera Kidney Landscape-Clustergram](tutorial_notebooks/Atera_Kidney_Landscape-Clustergram.ipynb) - Direct Scanpy and AnnData steps for default clusters, linked dotplot Clustergrams, and cell-type composition across podocyte-defined glomerular gradients
- [Atera Breast Cancer Landscape-Clustergram](tutorial_notebooks/Atera_Breast_Cancer_Landscape-Clustergram.ipynb) - Loads a precomputed Scanpy clustering (or optionally recomputes it) and creates linked Landscape, Clustergram, and Enrich widgets
- [Atera Breast Cancer Neighborhood Exploration](tutorial_notebooks/Atera_Breast_Cancer_Neighborhood_Exploration.ipynb) - Continues the Atera tutorial with hextile niches linked to cell-type composition and alpha-shape overlap linked to a separate Landscape
- [Visium HD Human CRC Landscape-Clustergram-Enrich](tutorial_notebooks/Visium_HD_Human_CRC_Landscape-Clustergram-Enrich.ipynb) - Uses Scanpy and plain AnnData to summarize a clustered Visium HD colorectal cancer sample (signatures, fraction expressing, marker genes) and explores it in linked Landscape, Clustergram, and Enrich widgets, ready for interactive annotation
- [Scanpy-Squidpy Xenium Pancreas](tutorial_notebooks/Scanpy-Squidpy_Xenium_Pancreas.ipynb) - Full analysis workflow using Scanpy and Squidpy with Xenium data

### 3D Spatial Transcriptomics

Explore the Broad–Allen E15.5 developing mouse brain across 43 aligned Xenium
sections. Follow these notebooks in order, or open the visualization notebook
directly to use the already hosted DegaFiles:

1. [Broad–Allen Mouse Brain: Preprocessing and Alignment](tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Align.ipynb)
   — align sections using cluster-centroid landmarks and neighborhood overlap,
   compare the results, and write named CellCloud DegaFiles variants.
2. [Broad–Allen Mouse Brain: Visualization](tutorial_notebooks/Broad-Allen_Dev-Mouse-Brain_E15.5_Viz.ipynb)
   — explore a 2D section, compare cluster composition across slices, and link
   the 3D CellCloud to a gene-expression Clustergram.

## Single Cell Tutorials

Tutorials that explore single-cell RNA-seq data with UMAP Landscapes linked to Clustergrams:

- [Chromium PBMC Landscape-Clustergram-Enrich](tutorial_notebooks/Scanpy_Chromium.ipynb) - Clusters the 10x Chromium PBMC 3k dataset with Scanpy and explores it from Hugging Face: a UMAP Landscape that reads the AnnData Zarr store in the browser, a Clustergram of each cluster's `rank_genes_groups` markers loaded from a Matrix Zarr store, and a single-cell Clustergram of the same markers linked to its own Landscape, each with Enrich
<!-- Shared as an unlisted page while revised (see not_in_nav in mkdocs.yaml):
- [MIX-seq Drug Screen Landscape-Clustergram-Enrich](tutorial_notebooks/MIX-seq_Drug_Screen_Landscape-Clustergram-Enrich.ipynb) - Explores the McFarland et al. 2020 screen of 13 drugs across about 170 pooled cancer cell lines: cell line identity, the drug responses within one cell line, and the response to the BRAF inhibitor dabrafenib across 94 cell lines, the analysis behind Fig. 3 of the pertpy paper
-->

<!-- New multi-omic tutorials temporarily hidden while they are revised (see
exclude_docs and not_in_nav in mkdocs.yaml).

## Multi-Omic Tutorials

Tutorials that combine several omics measured on the same samples:

- [Flex CITE-seq PBMC Landscape-Clustergram-Enrich](tutorial_notebooks/Flex_CITE-seq_PBMC_Landscape-Clustergram-Enrich.ipynb) - Explores RNA and 184 surface proteins in 12,242 PBMCs across levels of the cell hierarchy: QC-guided filtering with a UMAP linked to a cluster Clustergram, cell types compared across RNA and protein, and single-cell Clustergrams of B-cell subtypes and suspected B + T doublets
- [CST Lung Cancer PTM Clustergram-Enrich](tutorial_notebooks/CST_Lung_Cancer_PTM_Clustergram-Enrich.ipynb) - Reproduces the Clustergrammer lung cancer case study with a MuData of phosphorylation, methylation, acetylation, and gene expression across 37 cell lines: a Clustergram for each PTM type, stacked PTM, gene expression (linked to Enrich), and merged PTM-expression Clustergrams, plus a comparison of the cell line clusters found by each omic
-->

## Brief Notebooks

Focused examples demonstrating specific features:

- [Landscape View Xenium](brief_notebooks/Landscape_View_Xenium.ipynb) - Basic Landscape visualization of Xenium data
- [Landscape from a Local Server](brief_notebooks/Landscape_Local_Server.ipynb) - Viewing locally stored DegaFiles in a Landscape with `dega.viz.get_local_server()`
- [Atera Pre-process](brief_notebooks/Atera_Pre-process.ipynb) - Making DegaFiles from a 10x Atera output bundle with `dega.pre.main` and viewing them in a Landscape
- [Atera Kidney Yearbook Review](brief_notebooks/Atera_Kidney_Yearbook_Review.ipynb) - Find large endothelial cells with podocyte (NPHS2) transcripts using `dega.select`, review their portraits, and get the selected IDs
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

### Online Resources

You can also run Celldega notebooks in the cloud:

- [Google Colab - Xenium Landscape Visualizations](https://colab.research.google.com/drive/1NVZ07R0Eb-Xz6KBmMGRe3qmksYdeSBWc?usp=sharing)
- [ObservableHQ - Celldega Landscape Xenium](https://observablehq.com/@cornhundred/celldega-xenium_prime_mouse_brain_coronal_ff_outs)
- [![Open in molab](https://molab.marimo.io/molab-shield.svg)](https://molab.marimo.io/notebooks/nb_NQM2YhNLyow8N56cit7xvC)

## Contributing examples

Instructions for publishing notebooks with saved widget state are in
[Contributing](https://github.com/broadinstitute/celldega/blob/main/CONTRIBUTING.md).
