# Tabula Sapiens atlas

Explore the authors' UMAP of 1,136,218 cells from 28 organs, colored by cell type.
Select a gene to color cells by its expression, or use **XY** to compare two genes.
Zooming updates the cell-type counts and signature-based gene estimates in view;
**purple TRX** marks an estimate.

<div class="tabula-gallery" data-tabula-gallery="atlas">
  <div class="tabula-landscape-panel">
    <p data-tabula-status="landscape" role="status">Loading the atlas… The first load may take a moment.</p>
    <div data-tabula-landscape aria-label="Tabula Sapiens UMAP"></div>
  </div>
</div>

[Explore the UMAP with its linked Clustergram](gallery_tabula_sapiens_clustergram.md)
· [Tutorial and data preparation](../examples/tutorial_notebooks/Tabula_Sapiens_Landscape-Clustergram-Enrich.ipynb)

**Data:** Tabula Sapiens Consortium, Tabula Sapiens 2.0, distributed by
[CZ CELLxGENE Discover](https://cellxgene.cziscience.com/collections/e5f58829-1a66-40b5-a624-9046778e74f5)
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Expression is normalized to 10,000 counts per cell and log1p-transformed;
cell-type signatures are derived analyses.
[Source, processing details, citations and data release policy](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/blob/main/Tabula_Sapiens/README.md).
