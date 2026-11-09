# Atera Breast Cancer FF

Explore 485,850 cells in a human breast cancer section (Atera v1 whole-transcriptome, fresh
frozen), colored by the dataset's 26 default Leiden clusters, next to a
Clustergram of their marker genes. Click a Clustergram gene to color the cells by its
expression, or a cluster column to select its cells. Use the Clustergram's marker-level
control to show more or fewer markers per cluster.

For the Python workflow, open the [breast cancer tutorial](../examples/tutorial_notebooks/Atera_Breast_Cancer_Landscape-Matrix.ipynb),
which includes aligned H&E, a cell Yearbook, and a linked Landscape, Clustergram and Enrich.

<div class="linked-gallery" data-atera-gallery="breast">
  <div class="linked-landscape-panel">
    <p data-atera-status="landscape" role="status">Loading the tissue… The first load may take a moment.</p>
    <div data-atera-landscape aria-label="Atera Breast Cancer FF tissue view"></div>
  </div>
  <div class="linked-clustergram-panel">
    <p data-atera-status="clustergram" role="status">Loading the cluster signatures…</p>
    <div data-atera-clustergram aria-label="Atera Breast Cancer FF cluster Clustergram"></div>
  </div>
</div>

The tissue view streams images, cell boundaries, transcripts, and gene expression from
[DegaFiles on GitHub](https://github.com/broadinstitute/celldega_atera-wta-ff-human-breast-cancer).
The Clustergram reads the default clusters' signatures and ranked marker genes from a
[clustered Matrix AnnData-Zarr on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/main/Atera/Atera_v1_WTA_S4C_Breast_Cancer_FF/cgm/default_clusters.zarr).
