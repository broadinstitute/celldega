# Celldega File Formats
While there has been tremendous progress in developing standardized data formats and architectures for spatial-omics data, namely [SpatialData](https://spatialdata.scverse.org/en/stable/) and the related [AnnData](https://anndata.readthedocs.io/en/stable/), these approaches currently lack support for interactive cloud-based visualization of large (>100M transcripts) Spatial Transcriptomics (ST) data. Furthermore, all-in-one data format approaches preclude the development of more efficient visualization-specific data formats.

The Celldega project addresses these challenges with the development of a new ST data format called LandscapeFiles, specifically built for cloud-based visualization. LandscapeFiles support Celldega's Landscape visualization method by leveraging compact [image formats](../technologies/index.md/#webp) and [cloud-native data formats](../technologies/index.md/#apache-parquet) to enable efficient storage and visualization of image (e.g., microscopy images) and vectorized data (e.g., transcript coordinates). This approach is highly scalable, enabling the visualization of very large ST datasets (>400M transcripts), while remaining compact enough that LandscapeFiles for an entire Xenium dataset can be hosted in a [public GitHub repository](https://github.com/broadinstitute/celldega_Xenium_Prime_Human_Skin_FFPE_outs/).


## LandscapeFiles
LandscapeFiles are first generated using the Celldega [pre](../python/pre/api.md) module (see example Google Colab notebook [Celldega-Landscape-Pre-Process_Xenium-Pancreas-Dataset](https://colab.research.google.com/drive/1guUFhXP3nlZ4Es2-tsnraFKlAKHZSCZC?usp=sharing)). LandscapeFiles are read by Celldega's JavaScript front-end to interactively visualize ST data. Users have several options for hosting LandscapeFiles both locally on the cloud (e.g., Terra.bio buckets) or locally (e.g., running a local server to locally host LandscapeFiles).

An example directory structure for a Xenium Prime LandscapeFiles is shown below:

```
.
├── cbg
├── cell_clusters
├── cell_metadata.parquet
├── cell_segmentation
├── df_sig.parquet
├── landscape_parameters.json
├── meta_gene.parquet
├── pyramid_images
│   ├── bound_files
│   ├── dapi_files
│   ├── prot_files
│   └── rna_files
│── transcript_tiles
└── xenium_transform.csv

```

### Cell-by-Gene

### Cell Clusters

### Cell Metadata

### Cell Segmentation

### Cell Cluster Gene Expression Signatures

### Landscape Parameters

### Gene Metadata

### Pyramid Images

### Transcript Tiles

### Image Transformation