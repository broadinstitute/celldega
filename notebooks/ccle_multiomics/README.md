# CCLE multi-omics notebook support

The files in this directory support exploratory notebooks at the repository
root. They are not part of the installed Celldega API.

`prepare.py` constructs a coverage-preserving native `MuData` from the core
source-scale assays and wraps it in a `DatasetCollection`:

| Modality | Matrix values | First analytical role |
| --- | --- | --- |
| `rna` | DepMap batch-corrected log2(TPM + 1) | tissue and subtype discovery; gene programs |
| `rppa` | CCLE targeted antibody measurements | protein-level interpretation |
| `proteomics_ms` | CCLE normalized MS relative protein abundance | broad protein-level comparison with RNA and RPPA |
| `metabolomics` | CCLE calibrated log10 peak areas | metabolic structure and enzyme/metabolite concordance |
| `crispr` | DepMap Chronos gene effect | dependency structure, kept separate from abundance |

All data remain beneath the ignored `data/ccle_multiomics/` directory:

```text
data/ccle_multiomics/
  raw/                         # source CSVs (not tracked)
  processed/ccle_multiomics.h5mu
  processed/ccle_multiomics.qc.json
  results/                     # generated tables (not tracked)
```

The preparation notebook expects the following raw filenames:

- `Model.csv`
- `OmicsExpressionProteinCodingGenesTPMLogp1BatchCorrected.csv`
- `CRISPRGeneEffect.csv`
- `CCLE_RPPA_20181003.csv`
- `CCLE_metabolomics_20190502.csv`

The optional CCLE MS-proteomics file,
`protein_quant_current_normalized.csv`, is detected automatically when placed
in the same raw directory. Its bridge-sample columns are mapped through
`StrippedCellLineName`, technical replicates and duplicate gene rows are
median-collapsed, and the result remains the separate `proteomics_ms` modality.
It is intentionally not combined with RPPA in a multi-assay consensus graph:
the two technologies should first be compared, rather than counted as two
independent votes for the same broad protein layer.

RNA, model metadata, and CRISPR values come from the [DepMap 24Q2 public
release](https://plus.figshare.com/articles/dataset/DepMap_24Q2_Public/25880521).
The RPPA and metabolomics files come from the CCLE archival endpoints recorded
in `prepare.py`.  The archive purposefully keeps native model axes: call
`shared_model_ids()` only at the point where a cross-assay comparison needs a
matched cohort.

Run the notebook sources with the optional Scanpy dependency installed:

```bash
pip install -e '.[scanpy]'
```
