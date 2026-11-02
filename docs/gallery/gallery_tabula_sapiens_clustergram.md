# Tabula Sapiens: UMAP and cell-type signatures

Explore the atlas alongside marker expression across 180 cell types.
Click a Clustergram gene to color the UMAP, or a cell-type column to select its
cells. Use the Clustergram's marker-level control to adjust the number of markers
per cell type. Zoom into the UMAP to explore local cell-type counts and estimated
expression (**purple TRX**).

<div class="tabula-gallery tabula-gallery-linked" data-tabula-gallery="linked">
  <div class="tabula-landscape-panel">
    <p data-tabula-status="landscape" role="status">Loading the atlas… The first load may take a moment.</p>
    <div data-tabula-landscape aria-label="Tabula Sapiens UMAP"></div>
  </div>
  <div class="tabula-clustergram-panel">
    <p data-tabula-status="clustergram" role="status">Loading cell-type signatures…</p>
    <div data-tabula-clustergram aria-label="Tabula Sapiens cell-type Clustergram"></div>
  </div>
</div>

[Open the UMAP alone](gallery_tabula_sapiens.md)
· [Tutorial and data preparation](../examples/tutorial_notebooks/Tabula_Sapiens_Landscape-Clustergram-Enrich.ipynb)

**Data:** Tabula Sapiens Consortium, Tabula Sapiens 2.0, distributed by
[CZ CELLxGENE Discover](https://cellxgene.cziscience.com/collections/e5f58829-1a66-40b5-a624-9046778e74f5)
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The authors' UMAP contains 1,136,218 cells from 28 organs. Expression is normalized
to 10,000 counts per cell and log1p-transformed; signatures and marker rankings
are derived analyses.
[Source, processing details, citations and data release policy](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/blob/main/Tabula_Sapiens/README.md).
