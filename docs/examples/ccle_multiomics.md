# CCLE multi-omics

This developing tutorial series uses curated CCLE and DepMap bulk cell-line
measurements to demonstrate Celldega's hierarchical Clustergram workflow on
multi-omics data. It is an analysis example rather than a single-cell workflow.

The preparation chapter builds a native `MuData` with one observation axis per
assay and wraps it in a `DatasetCollection`. RNA, RPPA, metabolomics, CRISPR,
and optional mass-spectrometry proteomics therefore retain their genuine
coverage. Cross-assay comparisons request an explicit shared model cohort
instead of treating an unmeasured assay as zero.

| Chapter | Focus |
| --- | --- |
| 00 | Build or load the local MuData/DatasetCollection archive |
| 01 | Independent global Ward Clustergrams plus an equal-feature RNA/RPPA/metabolomics stack |
| 02 | Pan-CCLE agreement among the independent spaces and an equal-feature stacked Clustergram |
| 03 | Tissue-specific hierarchies and recurring RNA programs |
| 04 | Lung multi-omic subclustering, direct RNA--RPPA checks including CDH1/E-Cadherin, candidate metabolite associations, and stacked views |
| 05 | Pan-CCLE multi-omic consensus groups, an empirical recurrence null, and a marker-selected stacked Clustergram |
| 06 | Hematologic Lymphoid/Myeloid multi-omic subclustering, contextual RNA--RPPA/RNA--metabolite checks, and selected-marker stacks |
| 07 | Cross-lineage recurrence densities, three-assay examples, and a provenance-review Clustergram that does not infer label corrections |
| 08 | RNA-defined primary hierarchy with RPPA and metabolite rank_genes_groups characterizations and a balanced, RNA-ordered explanatory stack |
| 09 | Published CST lung TMT PTM subset mapped to current DepMap models, with independent RNA/PTM hierarchies and a balanced marker stack |

The notebooks shown here are rendered as source and are not executed during a
documentation build. Download the raw CCLE/DepMap files locally, run chapter
00, and then execute the analysis chapters from the repository root. The raw
inputs, H5MU archive, and result tables reside under the gitignored
`data/ccle_multiomics/` directory.

The source notebooks are retained under `notebooks/` alongside their helper
module. The copies here make the evolving series convenient to preview in
MkDocs while it remains on this branch.

## Gallery follow-up

Celldega's existing `Matrix.write_dega_files(...)` exporter and
`matrix_from_dega_files(...)` browser loader are sufficient for a tissue and
assay selector page. The analysis should first settle the exact tissue cohorts
and marker policy. A small exporter can then write one named DegaFiles bundle
per tissue/assay view, plus a manifest with the model and feature counts. The
gallery page only needs to fetch the currently selected bundle; hosting those
bundles outside the source repository avoids committing large matrices.
