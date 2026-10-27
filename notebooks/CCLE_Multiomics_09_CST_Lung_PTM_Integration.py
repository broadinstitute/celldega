# %% [markdown]
# # CCLE lung cancer: CST TMT post-translational-modification integration
#
# This focused sub-chapter updates the published Clustergrammer lung case study
# with current CCLE/DepMap model identifiers and annotations. It retains the
# original CST Tandem Mass Tag (TMT) PTM matrix exactly as distributed: 1,730
# phosphorylation, arginine-methylation, lysine-methylation, and lysine-
# acetylation features across 37 lung cancer cell lines.
#
# The PTM values are cancer-cell-line-to-normal-lung ratios that were column
# quantile normalized and row z-scored in the original work. Current DepMap
# RNA, RPPA, and metabolite measurements have different experimental contexts
# and scales. They are therefore separate native MuData modalities. The stacked
# panel uses only within-assay selected markers and row z-scores for display;
# it does not treat a cross-assay correlation as a mechanistic claim.

# %%
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score


PROJECT = next(
    parent for parent in (Path.cwd(), *Path.cwd().parents) if (parent / "pyproject.toml").exists()
)
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from celldega.viz import Clustergram
from notebooks.ccle_multiomics import (
    HierarchicalConfig,
    build_cst_lung_ptm_mudata,
    hierarchical_clustergram,
    rank_cluster_markers,
)
from notebooks.ccle_multiomics.coincidence import (
    select_ranked_features,
    stack_selected_features,
)


DATA = PROJECT / "data/ccle_multiomics"
RAW = DATA / "raw"
ARCHIVE = DATA / "processed/cst_lung_ptm_multiomics.h5mu"
RESULTS = DATA / "results/09_cst_lung_ptm_integration"
RESULTS.mkdir(parents=True, exist_ok=True)

# Rebuild from the exact local Figshare download and the current main archive.
# Both archives reside under ignored data/ and are reproducible from their
# documented sources.
mdata = build_cst_lung_ptm_mudata(
    RAW,
    base_archive=DATA / "processed/ccle_multiomics.h5mu",
    output=ARCHIVE,
    overwrite=True,
)
models = pd.Index(mdata.obs_names.astype(str), name="ModelID")
print({name: (adata.n_obs, adata.n_vars) for name, adata in mdata.mod.items()})
print(mdata.obs["CSTHistology"].value_counts())

# %% [markdown]
# ## The separate CST lung MuData
#
# All 37 published PTM/RNA-matched cell lines map unambiguously to current
# DepMap ModelIDs. The archive preserves the historical CST SCLC/NSCLC,
# sub-histology, and mutation annotations alongside modern OncoTree metadata.
# It contains current RNA, RPPA, and metabolomics layers for the same models
# where they are measured, plus the original `cst_ptm` layer.

# %%
historical_annotations = [
    "CSTCellLineName",
    "CSTHistology",
    "CSTSubHistology",
    "CSTTP53Mutation",
    "CSTEGFRMutation",
    "CSTRB1Mutation",
    "CSTKRASMutation",
]
mapping = mdata.obs[[field for field in historical_annotations if field in mdata.obs]].copy()
mapping.insert(0, "ModelID", mapping.index)
mapping.to_csv(RESULTS / "cst_to_current_model_mapping.csv", index=False)
print(mdata.uns["cst_lung_ptm"])

# %% [markdown]
# ## Independent RNA and site-resolved PTM hierarchies
#
# Each assay gets its own Ward tree. We then use the published SCLC/NSCLC
# labels only to rank marker dimensions, with `rank_genes_groups`, and to
# quantify how the data-driven two-way cut agrees with that known histology.
# This mirrors the original case study while avoiding an assumption that its
# labels are the clustering input.

# %%
DISCOVERY = {"rna": 2_000, "cst_ptm": 500}
COL_ATTRIBUTES = (
    "CSTHistology",
    "CSTSubHistology",
    "OncotreeSubtype",
    "CSTTP53Mutation",
    "CSTEGFRMutation",
    "CSTRB1Mutation",
    "CSTKRASMutation",
)
analyses: dict[str, object] = {}
matrices: dict[str, object] = {}
marker_tables: list[pd.DataFrame] = []
agreement_rows: list[dict[str, object]] = []

for modality, n_features in DISCOVERY.items():
    analysis, matrix = hierarchical_clustergram(
        mdata.mod[modality][models].copy(),
        HierarchicalConfig(n_top_features=n_features, n_meta_clusters=2),
        col_attributes=COL_ATTRIBUTES,
        row_attributes=("modality", "ptm_type"),
    )
    markers = rank_cluster_markers(
        analysis,
        "CSTHistology",
        key_added="rank_genes_groups",
    )
    markers.insert(0, "modality", modality)
    marker_tables.append(markers)
    analyses[modality], matrices[modality] = analysis, matrix

    cluster_key = analysis.uns["hierarchical_clustergram"]["cluster_key"]
    contingency = pd.crosstab(
        analysis.obs[cluster_key],
        analysis.obs["CSTHistology"],
        rownames=["ward_cluster"],
        colnames=["CST_histology"],
    )
    contingency.to_csv(RESULTS / f"{modality}_ward_by_histology.csv")
    agreement_rows.append(
        {
            "modality": modality,
            "n_models": len(models),
            "n_features_for_tree": n_features,
            "adjusted_rand_index_vs_historical_histology": adjusted_rand_score(
                analysis.obs[cluster_key].astype(str), analysis.obs["CSTHistology"].astype(str)
            ),
        }
    )

markers_by_histology = pd.concat(marker_tables, ignore_index=True)
markers_by_histology.to_parquet(RESULTS / "rna_and_cst_ptm_histology_markers.parquet", index=False)
top_markers = markers_by_histology.query("rank <= 25 and pvals_adj <= 0.05")
top_markers.to_csv(RESULTS / "rna_and_cst_ptm_top_histology_markers.csv", index=False)
agreement = pd.DataFrame(agreement_rows)
agreement.to_csv(RESULTS / "independent_tree_histology_agreement.csv", index=False)
print(agreement)

outlier_rows: list[dict[str, object]] = []
for modality, analysis in analyses.items():
    cluster_key = analysis.uns["hierarchical_clustergram"]["cluster_key"]
    cluster_histology = pd.crosstab(
        analysis.obs[cluster_key].astype(str), analysis.obs["CSTHistology"].astype(str)
    )
    dominant_histology = cluster_histology.idxmax(axis=1)
    for model_id, row in analysis.obs.iterrows():
        ward_cluster = str(row[cluster_key])
        expected_histology = dominant_histology.loc[ward_cluster]
        if str(row["CSTHistology"]) != expected_histology:
            outlier_rows.append(
                {
                    "modality": modality,
                    "ModelID": model_id,
                    "CellLineName": row["CellLineName"],
                    "CSTHistology": row["CSTHistology"],
                    "ward_cluster": ward_cluster,
                    "dominant_histology_of_ward_cluster": expected_histology,
                }
            )
branch_outliers = pd.DataFrame(outlier_rows)
branch_outliers.to_csv(RESULTS / "independent_tree_histology_outliers.csv", index=False)
print(branch_outliers)

# %% [markdown]
# ## RNA plus PTM marker stack
#
# The row selection is balanced: at most 80 ranked RNA markers and 80 ranked
# site-resolved PTM markers. Thus RNA's larger feature space cannot dominate
# the display. `modality`, `ptm_type`, and the SCLC/NSCLC annotations remain
# visible in the interactive Clustergram.

# %% [markdown]
# The current RNA and the published PTM tree both place the historical NSCLC
# line H2106 in their SCLC-dominant branch. This reproduces the original
# cross-assay observation as a robust review candidate. It does not establish
# a mislabel: its modern OncoTree subtype is large-cell lung carcinoma, and a
# branch assignment should be followed by provenance and molecular review.

# %%
selections: dict[str, pd.DataFrame] = {}
for modality in DISCOVERY:
    assay_markers = markers_by_histology.query("modality == @modality").drop(columns="modality")
    selections[modality] = select_ranked_features(
        assay_markers,
        top_n_per_group=40,
        max_features=80,
    )
    selections[modality].insert(0, "modality", modality)

stacked = stack_selected_features(mdata, selections, models)
# PTM feature metadata adds another useful row category to the stacked panel.
stacked_ptm_type = stacked.var["original_feature_id"].map(mdata.mod["cst_ptm"].var["ptm_type"])
stacked.var["ptm_type"] = stacked_ptm_type.astype("string").fillna("not_applicable")
stacked_analysis, stacked_matrix = hierarchical_clustergram(
    stacked,
    HierarchicalConfig(n_top_features=stacked.n_vars, n_meta_clusters=2),
    col_attributes=COL_ATTRIBUTES,
    row_attributes=("modality", "ptm_type", "marker_group"),
)
stacked_key = stacked_analysis.uns["hierarchical_clustergram"]["cluster_key"]
stacked_contingency = pd.crosstab(
    stacked_analysis.obs[stacked_key],
    stacked_analysis.obs["CSTHistology"],
    rownames=["ward_cluster"],
    colnames=["CST_histology"],
)
stacked_contingency.to_csv(RESULTS / "stacked_ward_by_histology.csv")
stacked.var.to_csv(RESULTS / "stacked_marker_feature_provenance.csv")
pd.DataFrame(
    {
        "modality": list(selections),
        "n_selected_markers": [len(selection) for selection in selections.values()],
    }
).to_csv(RESULTS / "stacked_marker_counts.csv", index=False)

# %% [markdown]
# ## Interactive PTM and RNA--PTM views
#
# The PTM tree is the direct modernized reproduction view. The second panel
# combines independently histology-ranked RNA and PTM dimensions. Look for
# site-level PTM rows adjacent to their corresponding RNA genes, then use the
# metadata tracks to assess whether the pattern follows SCLC/NSCLC, a mutation,
# or a more specific lineage state.

# %%
Clustergram(matrix=matrices["cst_ptm"], width=1_100, height=780)

# %%
Clustergram(matrix=stacked_matrix, width=1_100, height=820)
