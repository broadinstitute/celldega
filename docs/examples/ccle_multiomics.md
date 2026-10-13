# CCLE multi-omics

This developing tutorial series uses curated CCLE and DepMap bulk cell-line
measurements to demonstrate Celldega's hierarchical Clustergram workflow on
multi-omics data. It is an analysis example rather than a single-cell workflow.

The preparation chapter builds a native `MuData` with one observation axis per
assay and wraps it in a `DatasetCollection`. RNA, RPPA, metabolomics, and CRISPR
therefore retain their genuine coverage. Cross-assay comparisons request an
explicit shared model cohort instead of treating an unmeasured assay as zero.

| Chapter | Focus |
| --- | --- |
| 00 | Build or load the local MuData/DatasetCollection archive |
| 01 | Independent global Ward Clustergrams plus an equal-feature RNA/RPPA/metabolomics stack |
| 02 | Pan-CCLE agreement among the independent spaces and an equal-feature stacked Clustergram |
| 03 | Tissue-specific hierarchies and recurring RNA programs |
| 04 | Lung SCLC/NSCLC concordance, direct RNA--RPPA checks, candidate metabolite associations, and stacked views |
| 05 | Coincident nearest-neighbor graph, empirical null, and a marker-selected stacked Clustergram |
| 06 | Hematologic Lymphoid/Myeloid coincident neighbors, contextual RNA--RPPA/RNA--metabolite checks, and selected-marker stacks |

The notebooks shown here are rendered as source and are not executed during a
documentation build. Download the raw CCLE/DepMap files locally, run chapter
00, and then execute the analysis chapters from the repository root. The raw
inputs, H5MU archive, and result tables reside under the gitignored
`data/ccle_multiomics/` directory.

The source notebooks are retained under `notebooks/` alongside their helper
module. The copies here make the evolving series convenient to preview in
MkDocs while it remains on this branch.
