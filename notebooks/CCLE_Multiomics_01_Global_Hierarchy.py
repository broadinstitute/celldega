# %% [markdown]
# # CCLE multi-omics: unsupervised exploration
#
# This notebook source begins from the native MuData/DatasetCollection archive.
# It builds an independent Ward Clustergram for each assay before comparing
# modalities. Tissue and subtype annotations interpret, not create, the groups.

# %%
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


PROJECT = next(parent for parent in (Path.cwd(), *Path.cwd().parents) if (parent / "pyproject.toml").exists())
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from celldega.viz import Clustergram
from notebooks.ccle_multiomics import (
    HierarchicalConfig,
    hierarchical_clustergram,
    load_collection,
    marker_clustergram,
    rank_cluster_markers,
    shared_model_ids,
    stack_modalities,
)
from notebooks.ccle_multiomics.clustering import annotation_table


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/01_global_hierarchy"
RESULTS.mkdir(parents=True, exist_ok=True)

collection = load_collection(ARCHIVE)
print(type(collection).__name__)
for modality, adata in collection.mod.items():
    print(f"{modality:14s} {adata.n_obs:4d} models x {adata.n_vars:6d} features")

# %% [markdown]
# The initial atlas uses measurements without missing values. CRISPR is present
# in the archive but has missing calls, so it will receive an explicit
# missingness strategy in the functional-dependency notebook rather than being
# silently imputed here.

# %%
EXPLORATION_MODALITIES = ("rna", "rppa", "metabolomics")
CONFIG_BY_MODALITY = {
    "rna": HierarchicalConfig(n_top_features=2_000, n_meta_clusters=8),
    "rppa": HierarchicalConfig(n_top_features=214, n_meta_clusters=8),
    "metabolomics": HierarchicalConfig(n_top_features=225, n_meta_clusters=8),
}
STACKED_FEATURES_PER_MODALITY = {"rna": 214, "rppa": 214, "metabolomics": 214}


def cluster_summary(adata, cluster_key: str) -> pd.DataFrame:
    """Keep interpretation separate from label-free discovery."""
    keep = [field for field in ("OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype") if field in adata.obs]
    counts = adata.obs[[*keep, cluster_key]].copy()
    counts.insert(0, "ModelID", adata.obs_names)
    return counts


def annotation_agreement(adata, cluster_key: str, annotation: str) -> dict[str, object]:
    """Summarize an annotation after a label-free dendrogram cut.

    Purity gives the fraction of models in a branch sharing its most common
    annotation. ARI and NMI are descriptive agreement scores, not optimized
    because the dendrogram was never fitted against the annotation.
    """
    labels = adata.obs[[cluster_key, annotation]].dropna()
    branch = labels[cluster_key].astype(str)
    known = labels[annotation].astype(str)
    contingency = pd.crosstab(branch, known)
    return {
        "annotation": annotation,
        "n_models": len(labels),
        "n_annotation_categories": known.nunique(),
        "adjusted_rand_index": adjusted_rand_score(branch, known),
        "normalized_mutual_information": normalized_mutual_info_score(branch, known),
        "branch_purity": contingency.max(axis=1).sum() / contingency.to_numpy().sum(),
    }


# %% [markdown]
# The Clustergram contains the full hierarchy. Eight is only the initial cut
# used to define groups for marker ranking; change `n_meta_clusters` in one
# place after inspecting the dendrogram rather than sweeping a graph resolution.

# %%
analyses: dict[str, object] = {}
clustergrams: dict[str, object] = {}
all_cluster_tables: list[pd.DataFrame] = []
marker_tables: list[pd.DataFrame] = []
composition_tables: list[pd.DataFrame] = []
agreement_tables: list[dict[str, object]] = []

for modality in EXPLORATION_MODALITIES:
    adata, clustergram = hierarchical_clustergram(collection.mod[modality], CONFIG_BY_MODALITY[modality])
    analyses[modality] = adata
    clustergrams[modality] = clustergram
    cluster_key = adata.uns["hierarchical_clustergram"]["cluster_key"]
    labels = cluster_summary(adata, cluster_key)
    labels.insert(1, "modality", modality)
    labels = labels.rename(columns={cluster_key: "hierarchical_cluster"})
    all_cluster_tables.append(labels)

    markers = rank_cluster_markers(adata, cluster_key, key_added="rank_genes_groups")
    markers.insert(0, "modality", modality)
    marker_tables.append(markers)

    # The RANK slider is now driven by top markers from this exact dendrogram cut.
    clustergrams[modality] = marker_clustergram(adata)

    for annotation in ("OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype"):
        if annotation not in adata.obs:
            continue
        composition = annotation_table(adata, cluster_key, annotation).reset_index(names="hierarchical_cluster")
        composition.insert(0, "modality", modality)
        composition.insert(1, "annotation", annotation)
        composition_tables.append(composition)
        agreement = annotation_agreement(adata, cluster_key, annotation)
        agreement_tables.append({"modality": modality, **agreement})

cluster_labels = pd.concat(all_cluster_tables, ignore_index=True)
cluster_labels.to_parquet(RESULTS / "cluster_labels.parquet", index=False)
cluster_labels.groupby(["modality", "hierarchical_cluster"]).size().rename("n_models").to_csv(
    RESULTS / "cluster_sizes.csv"
)
markers = pd.concat(marker_tables, ignore_index=True)
markers.to_parquet(RESULTS / "hierarchical_markers.parquet", index=False)
top_markers = markers.query("rank <= 20 and pvals_adj <= 0.05").copy()
top_markers.to_csv(RESULTS / "top20_markers.csv", index=False)
pd.concat(composition_tables, ignore_index=True).to_csv(RESULTS / "cluster_annotation_composition.csv", index=False)
pd.DataFrame(agreement_tables).to_csv(RESULTS / "cluster_annotation_agreement.csv", index=False)

top_markers.groupby(["modality", "group"]).head(5)[
    ["modality", "group", "rank", "names", "scores", "pvals_adj", "median_delta"]
]

# %% [markdown]
# ## Matched, equal-feature stacked multi-omic hierarchy
#
# The individual trees above retain each assay's full model coverage. This
# complementary view asks whether the complete-case cell lines form a useful
# shared hierarchy once every feature is put on the same z-score display scale.
# It takes the same number of variable rows from RNA, RPPA, and metabolomics so
# RNA does not dominate simply because it measures many more features. The
# `modality` row track marks the origin of every feature.

# %%
stacked_models = shared_model_ids(collection, EXPLORATION_MODALITIES)
stacked = stack_modalities(
    collection,
    EXPLORATION_MODALITIES,
    stacked_models,
    n_top_features=STACKED_FEATURES_PER_MODALITY,
)
stacked_analysis, _ = hierarchical_clustergram(
    stacked,
    HierarchicalConfig(n_top_features=stacked.n_vars, n_meta_clusters=8),
)
stacked_key = stacked_analysis.uns["hierarchical_clustergram"]["cluster_key"]
stacked_markers = rank_cluster_markers(
    stacked_analysis,
    stacked_key,
    key_added="rank_genes_groups",
)
stacked_marker_clustergram = marker_clustergram(stacked_analysis)

stacked_labels = cluster_summary(stacked_analysis, stacked_key)
stacked_labels.insert(1, "modality", "stacked_rna_rppa_metabolomics")
stacked_labels = stacked_labels.rename(columns={stacked_key: "hierarchical_cluster"})
stacked_labels.to_parquet(RESULTS / "stacked_cluster_labels.parquet", index=False)
stacked_markers.to_parquet(RESULTS / "stacked_hierarchical_markers.parquet", index=False)
stacked.var.to_csv(RESULTS / "stacked_feature_provenance.csv")
print(
    stacked.var["modality"].value_counts().rename("n_features").to_frame().T,
    f"\nMatched models: {len(stacked_models)}",
)

# %% [markdown]
# ## Interactive global marker Clustergrams
#
# Each view is an independent Ward tree for its own assay. The RANK control
# shows the five, ten, or twenty top `rank_genes_groups` markers for each
# branch. The column annotations are retained for interpretation but were not
# used to build any tree.

# %%
Clustergram(matrix=clustergrams["rna"], width=1_100, height=700)

# %% [markdown]
# ### RPPA proteins

# %%
Clustergram(matrix=clustergrams["rppa"], width=1_100, height=700)

# %% [markdown]
# ### Metabolomics

# %%
Clustergram(matrix=clustergrams["metabolomics"], width=1_100, height=700)

# %% [markdown]
# ### Equal-feature stacked RNA + RPPA + metabolomics
#
# This fourth view is a single matched-cell-line hierarchy. Its `modality` row
# category separates the contributing RNA, RPPA, and metabolite features, and
# the RANK control presents marker features for its dendrogram-derived groups.

# %%
Clustergram(matrix=stacked_marker_clustergram, width=1_100, height=700)

# %% [markdown]
# The next notebook will subset a tissue such as lung *after* this global map,
# repeat the same independent clustering workflow, and then assess which marker
# patterns agree across RNA, RPPA, and metabolites on explicitly matched lines.
