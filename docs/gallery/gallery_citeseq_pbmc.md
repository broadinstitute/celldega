# CITE-seq PBMC Cell Types: RNA and Protein

Compare 20 cell types of human peripheral blood mononuclear cells (PBMCs) across
gene expression and surface proteins measured in the same cells with 10x Genomics
Flex and TotalSeq-C antibodies. Rows stack each cell type's top marker genes and
proteins (`rna` or `prot` data type); columns are cell types, colored by cell type
and lineage. The Clustergram loads a clustered Matrix, saved in Python with
`Matrix.write_zarr`, directly from Hugging Face.

<div id="clustergram-citeseq-pbmc" style="width: 100%; min-height: 900px;"></div>

<!-- The CITE-seq tutorial is temporarily hidden (see exclude_docs in
mkdocs.yaml); restore this link with it.
Open the [CITE-seq tutorial](../examples/tutorial_notebooks/Flex_CITE-seq_PBMC_Landscape-Clustergram-Enrich.ipynb)
to build this Clustergram, link it to a UMAP, and zoom in on B cells at
single-cell resolution.
-->

[Clustered Matrix (Zarr) on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/main/Flex_16k_PBMC_CITE-seq/matrices/cell_types.zarr)
· [MuData on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/blob/main/Flex_16k_PBMC_CITE-seq/Flex_16k_PBMC_CITE-seq.h5mu)
· [DegaFiles on GitHub](https://github.com/broadinstitute/Celldega_16k_Human_PBMCs_TotalseqC_4plex_PBMC_TotalSeqC)
