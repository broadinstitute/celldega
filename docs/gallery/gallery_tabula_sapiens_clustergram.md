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

## Data source and license

**Source:** [Tabula Sapiens – All Cells](https://cellxgene.cziscience.com/e/53d208b0-2cfd-4366-9866-c3c6114081bc.cxg/)
from the **Tabula Sapiens Consortium**, curated and distributed by
[CZ CELLxGENE Discover in the Tabula Sapiens collection](https://cellxgene.cziscience.com/collections/e5f58829-1a66-40b5-a624-9046778e74f5).
This example uses Tabula Sapiens 2.0, dataset version
`1c88f927-bcbb-4bb1-9881-281842945a2d`: 1,136,218 cells from 28 organs.

**License:** The source data and the derived files used here are available under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

**Processing:** We retain the authors' UMAP, normalize expression to 10,000 counts
per cell, apply log1p, and store the data as Zarr for browser access. Cell-type
signatures, marker rankings, and hierarchical clustering are analyses prepared
for this visualization. The Clustergram shows mean expression scaled per gene
and the fraction of cells expressing each gene.
[Processing details and the bundled data release policy](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/blob/main/Tabula_Sapiens/README.md)
accompany the hosted files; see also the
[Tabula Sapiens data release policy](https://tabula-sapiens.sf.czbiohub.org/whereisthedata).

**Citation:** The Tabula Sapiens Consortium. *Tabula Sapiens 2.0: A comprehensive
transcriptomic atlas of human cell types.* Cell 189, 7212–7227 (2026).
[doi:10.1016/j.cell.2026.08.010](https://doi.org/10.1016/j.cell.2026.08.010).
