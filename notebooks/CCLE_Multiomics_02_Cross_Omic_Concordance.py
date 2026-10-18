# %% [markdown]
# # CCLE multi-omics: global cross-omic concordance
#
# Cell lines can agree across assays because tissue identity is shared, or they
# can differ because each assay measures a distinct biological layer. This
# chapter compares full cell-line relationship spaces without selecting clusters,
# then uses one fixed dendrogram cut for readable coincidence and marker tables.
#
# It also creates an equal-feature stacked Clustergram with `modality` as a row
# annotation. Equal feature counts prevent RNA from dominating merely because it
# has many more measured features than RPPA or metabolomics.

# %%
from __future__ import annotations

from itertools import combinations
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score


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


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/02_cross_omic_concordance"
RESULTS.mkdir(parents=True, exist_ok=True)

MODALITIES = ("rna", "rppa", "metabolomics")
LINEAGE = "OncotreeLineage"
N_MARKER_BRANCHES = 12
INDEPENDENT_FEATURES = {"rna": 2_000, "rppa": 214, "metabolomics": 225}
STACKED_FEATURES = {"rna": 200, "rppa": 200, "metabolomics": 200}

collection = load_collection(ARCHIVE)
matched_models = shared_model_ids(collection, MODALITIES)
print(f"Matched pan-CCLE cohort: {len(matched_models)} models")

# %% [markdown]
# ## Independent trees on the explicit matched cohort
#
# Each assay keeps its native values and is clustered independently. The Ward
# matrix normalizes each feature for display and clustering, while marker tables
# report source-scale group-versus-rest median effects.

# %%
independent: dict[str, object] = {}
tree_matrices: dict[str, object] = {}
marker_clustergrams: dict[str, object] = {}
label_tables: list[pd.DataFrame] = []
marker_tables: list[pd.DataFrame] = []

for modality in MODALITIES:
    analysis, tree_matrix = hierarchical_clustergram(
        collection.mod[modality][matched_models].copy(),
        HierarchicalConfig(
            n_top_features=INDEPENDENT_FEATURES[modality],
            n_meta_clusters=N_MARKER_BRANCHES,
        ),
    )
    cluster_key = analysis.uns["hierarchical_clustergram"]["cluster_key"]
    independent[modality] = analysis
    tree_matrices[modality] = tree_matrix

    markers = rank_cluster_markers(analysis, cluster_key, key_added="rank_genes_groups")
    marker_clustergrams[modality] = marker_clustergram(analysis)
    markers.insert(0, "modality", modality)
    marker_tables.append(markers)

    labels = analysis.obs[[
        field
        for field in (LINEAGE, "OncotreePrimaryDisease", "OncotreeSubtype", cluster_key)
        if field in analysis.obs
    ]].copy()
    labels.insert(0, "ModelID", analysis.obs_names)
    labels.insert(1, "modality", modality)
    labels = labels.rename(columns={cluster_key: "hierarchical_cluster"})
    label_tables.append(labels)

independent_labels = pd.concat(label_tables, ignore_index=True)
independent_markers = pd.concat(marker_tables, ignore_index=True)
independent_labels.to_parquet(RESULTS / "matched_global_cluster_labels.parquet", index=False)
independent_markers.to_parquet(RESULTS / "matched_global_hierarchical_markers.parquet", index=False)
independent_markers.query("rank <= 20 and pvals_adj <= 0.05").to_csv(
    RESULTS / "matched_global_top20_markers.csv", index=False
)

# %% [markdown]
# ## Full-space agreement, globally and within tissue lineage
#
# The vector of every pairwise cell-line distance represents one omics space.
# Spearman correlation compares the rank order of those relationships without a
# dendrogram cut. Repeating it only for same-lineage pairs reveals how much of a
# pan-cancer association survives once the broad tissue split is held constant.

# %%
pair_distances = {
    modality: pdist(tree_matrices[modality].data.T.to_numpy(), metric="euclidean")
    for modality in MODALITIES
}
lineage = independent["rna"].obs[LINEAGE].astype("string").fillna("unknown").to_numpy()
upper_i, upper_j = np.triu_indices(len(matched_models), k=1)
within_lineage_pairs = (lineage[upper_i] == lineage[upper_j]) & (lineage[upper_i] != "unknown")

distance_rows: list[dict[str, object]] = []
for left, right in combinations(MODALITIES, 2):
    distance_rows.append(
        {
            "left_modality": left,
            "right_modality": right,
            "n_all_model_pairs": len(pair_distances[left]),
            "spearman_all_pairs": spearmanr(pair_distances[left], pair_distances[right]).statistic,
            "n_within_lineage_pairs": int(within_lineage_pairs.sum()),
            "spearman_within_lineage_pairs": spearmanr(
                pair_distances[left][within_lineage_pairs],
                pair_distances[right][within_lineage_pairs],
            ).statistic,
        }
    )

distance_agreement = pd.DataFrame(distance_rows)
distance_agreement.to_csv(RESULTS / "global_distance_agreement.csv", index=False)
print(distance_agreement)

# %% [markdown]
# ## Branch coincidence and a balanced stacked Clustergram
#
# Twelve branches are a pre-specified, readable cut for coincidence and marker
# tables. The full dendrograms remain available in `tree_matrices`. The stacked
# view is an integrated third tree, not a substitute for the independent ones.

# %%
labels_by_modality = {
    modality: independent[modality].obs[f"hierarchical_k{N_MARKER_BRANCHES}"].astype(str)
    for modality in MODALITIES
}
branch_rows: list[dict[str, object]] = []
for left, right in combinations(MODALITIES, 2):
    coincidence = pd.crosstab(labels_by_modality[left], labels_by_modality[right])
    coincidence.index.name = f"{left}_branch"
    coincidence.columns.name = f"{right}_branch"
    coincidence.to_csv(RESULTS / f"{left}_by_{right}_branch_coincidence.csv")
    branch_rows.append(
        {
            "left_modality": left,
            "right_modality": right,
            "n_models": len(matched_models),
            "adjusted_rand_index": adjusted_rand_score(
                labels_by_modality[left], labels_by_modality[right]
            ),
        }
    )

branch_agreement = pd.DataFrame(branch_rows)
branch_agreement.to_csv(RESULTS / "global_branch_agreement.csv", index=False)
for modality, labels in labels_by_modality.items():
    pd.crosstab(labels, independent[modality].obs[LINEAGE], normalize="index").to_csv(
        RESULTS / f"{modality}_branch_by_lineage.csv"
    )

stacked = stack_modalities(
    collection,
    MODALITIES,
    matched_models,
    n_top_features=STACKED_FEATURES,
)
stacked.var.groupby("modality", observed=True).size().rename("n_features").to_csv(
    RESULTS / "stacked_feature_counts.csv"
)
stacked_analysis, stacked_clustergram = hierarchical_clustergram(
    stacked,
    HierarchicalConfig(n_top_features=stacked.n_vars, n_meta_clusters=N_MARKER_BRANCHES),
)
stacked_key = stacked_analysis.uns["hierarchical_clustergram"]["cluster_key"]
stacked_markers = rank_cluster_markers(stacked_analysis, stacked_key, key_added="rank_genes_groups")
stacked_marker_clustergram = marker_clustergram(stacked_analysis)

stacked_labels = stacked_analysis.obs[[
    field
    for field in (LINEAGE, "OncotreePrimaryDisease", "OncotreeSubtype", stacked_key)
    if field in stacked_analysis.obs
]].copy()
stacked_labels.insert(0, "ModelID", stacked_analysis.obs_names)
stacked_labels = stacked_labels.rename(columns={stacked_key: "hierarchical_cluster"})
stacked_labels.to_parquet(RESULTS / "stacked_global_cluster_labels.parquet", index=False)
stacked_markers.to_parquet(RESULTS / "stacked_global_hierarchical_markers.parquet", index=False)

stacked_agreement = pd.DataFrame(
    [
        {
            "modality": modality,
            "n_models": len(matched_models),
            "adjusted_rand_index_with_stacked_tree": adjusted_rand_score(
                labels, stacked_analysis.obs[stacked_key].astype(str)
            ),
        }
        for modality, labels in labels_by_modality.items()
    ]
)
stacked_agreement.to_csv(RESULTS / "stacked_global_branch_agreement.csv", index=False)
print(branch_agreement)
print(stacked_agreement)

# %% [markdown]
# ## Interactive balanced stacked Clustergram
#
# Rows are balanced across RNA, RPPA, and metabolomics before the Ward tree is
# built. The `modality` row annotation makes the assay origin of each
# discriminating feature visible, and RANK exposes branch markers from the
# pre-specified 12-way cut.

# %%
Clustergram(matrix=stacked_marker_clustergram, width=1_100, height=700)
