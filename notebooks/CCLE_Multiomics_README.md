# CCLE / DepMap multi-omics notebook series

These Jupytext notebook sources demonstrate Celldega on a curated bulk
cell-line dataset. They deliberately keep the one-time data preparation apart
from the analysis notebooks. Generated `.ipynb` counterparts are ignored like
the rest of the local notebook workspace; the `.py` sources are the reviewable
versions.

Run in this order:

1. `CCLE_Multiomics_00_Prepare.py` creates or loads the native MuData archive and
   its DatasetCollection wrapper.
2. `CCLE_Multiomics_01_Global_Hierarchy.py` creates global RNA, RPPA, and
   metabolomics Ward Clustergrams plus an equal-feature matched multi-omic
   stack and marker tables.
3. `CCLE_Multiomics_02_Cross_Omic_Concordance.py` compares global matched-cohort
   cell-line relationships across the independent omics trees and builds an
   equal-feature stacked Clustergram with modality row annotations.
4. `CCLE_Multiomics_03_Tissue_Gene_Programs.py` cuts the RNA row tree into gene
   programs, analyzes each sufficiently represented tissue lineage, and finds
   repeated top-marker sets across lineages.
5. `CCLE_Multiomics_04_Lung_Multiomic_Concordance.py` tests a focused SCLC/NSCLC example
   across independent RNA/RPPA/metabolite trees and an equal-feature stacked
   multi-omic Clustergram.
6. `CCLE_Multiomics_05_Nearest_Neighbor_Coincidence.py` finds cell-line pairs
   that recur as nearest neighbors across assays, tests the recurrence against
   permuted assay labels, then stacks the `rank_genes_groups` dimensions of
   the resulting consensus neighborhoods.
7. `CCLE_Multiomics_06_Hematologic_Neighbor_Coincidence.py` applies the same
   workflow to the combined Lymphoid/Myeloid cohort, where consensus groups
   can reveal hematologic subtypes and cross-lineage relationships.

All raw data, the H5MU archive, and generated result tables reside in ignored
`data/ccle_multiomics/`. The reusable preparation and clustering helpers live
in `notebooks/ccle_multiomics/`; they are intentionally notebook support code,
not a public Celldega API.

## Rendering the documentation widgets

The copies under `docs/examples/tutorial_notebooks/` are committed rendered
notebooks, not plain conversions of these sources. Each visual chapter contains
one or more standalone `Clustergram(...)` expressions and must be re-executed with the
[documented widget-embedding command](../CONTRIBUTING.md#-rendering-docs-notebooks-widget-embedding)
before `mkdocs build`:

```bash
CELLDEGA_ESM_VERSION=0.26.1 jupyter nbconvert \
  --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=900 \
  --ExecutePreprocessor.iopub_timeout=120 \
  docs/examples/tutorial_notebooks/CCLE_Multiomics_01_Global_Hierarchy.ipynb
```

Use the matching release version from `package.json`. The CDN ESM shim keeps
the front-end bundle small; `mkdocs-jupyter` reads the saved state and does not
run the notebook itself.

## Follow-up work

1. Add CCLE mass-spectrometry proteomics as a distinct `proteomics_ms`
   modality, then compare its matched-cohort tree with RPPA rather than merging
   the two assays.
2. Prioritize cross-lineage programs that recur in independent tissue trees,
   annotate them with pathway enrichment, and retain the supporting effect-size
   tables alongside each biological claim.
3. Export selected `Matrix` views as static DegaFiles for a gallery after the
   analysis and curation choices stabilize.
