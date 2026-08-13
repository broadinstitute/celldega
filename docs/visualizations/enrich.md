# Enrich

`Enrich` is an informational widget for gene set enrichment analysis: given a
list of genes (e.g. the top marker genes for a cluster), it looks up
enriched terms against public gene-set libraries via the
[Enrichr](https://maayanlab.cloud/Enrichr/) API.

## What it shows

- A **library selector** for choosing which Enrichr gene-set library to query
  (e.g. `CellMarker_2024`).
- A **bar chart** of the top enriched terms for the current gene list,
  ranked by score. Clicking a bar highlights the genes it's associated with.
- A **gene list panel** — clicking a gene shows detail about that gene and
  highlights it across the term bar chart.
- A link to view the full result set on Enrichr.

## Usage

```python
import celldega as dega

enrich = dega.viz.Enrich(width=650, height=650)
enrich.gene_list = ["BRCA1", "TP53", "EGFR"]
enrich
```

`Enrich` is commonly driven by a gene list derived from a `Clustergram` or
`Landscape` selection (e.g. marker genes for a clicked cluster). For the full
list of constructor arguments, see the
[Viz Module API reference](../python/viz/api.md).

!!! note
    Screenshots and an example video are coming soon.
