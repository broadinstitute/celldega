# %% [markdown]
# # CCLE multi-omics: consensus groups and marker-selected fusion
#
# This chapter adapts the multi-assay nearest-neighbor analysis from the
# smoldering-myeloma study to CCLE cell lines. Independent assay spaces first
# define local neighborhoods of the same matched cell lines. A pair receives a
# score from zero to three according to the number of assays in which it is a
# nearest-neighbor pair. Assay labels are then permuted to test whether the
# observed number of recurrent pairs exceeds the expectation from independent
# local graphs.
#
# The resulting consensus neighborhoods are descriptive, not a supervised
# cancer label. They provide common groups on which to call
# `rank_genes_groups` separately for RNA, RPPA, and metabolomics. Those
# assay-specific informative dimensions are then stacked into a second,
# provenance-preserving multi-omic Clustergram.

# %%
from __future__ import annotations

from pathlib import Path
import sys

from anndata import AnnData
import pandas as pd


PROJECT = next(parent for parent in (Path.cwd(), *Path.cwd().parents) if (parent / "pyproject.toml").exists())
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from celldega.clust import Matrix
from celldega.viz import Clustergram
from notebooks.ccle_multiomics import (
    HierarchicalConfig,
    hierarchical_clustergram,
    load_collection,
    marker_clustergram,
    rank_cluster_markers,
    shared_model_ids,
)
from notebooks.ccle_multiomics.coincidence import (
    coincident_pair_table,
    nearest_neighbor_coincidence,
    select_ranked_features,
    stack_selected_features,
)


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/05_nearest_neighbor_coincidence"
RESULTS.mkdir(parents=True, exist_ok=True)

MODALITIES = ("rna", "rppa", "metabolomics")
N_NEIGHBORS = 20
N_PERMUTATIONS = 250
MIN_COINCIDENT_MODALITIES = 2
N_CONSENSUS_NEIGHBORHOODS = 8
TOP_MARKERS_PER_NEIGHBORHOOD = 15
MAX_SELECTED_FEATURES_PER_MODALITY = 120

collection = load_collection(ARCHIVE)
matched_models = shared_model_ids(collection, MODALITIES)
print(f"Matched pan-CCLE cohort: {len(matched_models)} models")

# %% [markdown]
# ## Independent local neighborhoods and their recurrence across assays
#
# We retain the same feature scaling and Ward-ready matrices used in the global
# analysis, then calculate the twenty closest lines in each modality. Twenty is
# a fixed local neighborhood chosen for the 874-line complete-case cohort; it
# is intentionally not a clustering-resolution sweep.

# %%
tree_matrices: dict[str, Matrix] = {}
for modality in MODALITIES:
    _, tree_matrices[modality] = hierarchical_clustergram(
        collection.mod[modality][matched_models].copy(),
        HierarchicalConfig(
            n_top_features={"rna": 2_000, "rppa": 214, "metabolomics": 225}[modality],
            n_meta_clusters=N_CONSENSUS_NEIGHBORHOODS,
        ),
    )

relationship_values = {
    modality: tree_matrices[modality].data.T.reindex(matched_models) for modality in MODALITIES
}
coincidence, adjacency_by_modality, coincidence_summary, null_scores = nearest_neighbor_coincidence(
    relationship_values,
    n_neighbors=N_NEIGHBORS,
    min_modalities=MIN_COINCIDENT_MODALITIES,
    n_permutations=N_PERMUTATIONS,
    random_state=0,
)
coincidence_summary.to_csv(RESULTS / "nearest_neighbor_coincidence_summary.csv", index=False)
null_scores.to_csv(RESULTS / "nearest_neighbor_null_scores.csv", index=False)
coincidence.to_parquet(RESULTS / "coincident_neighbor_counts.parquet")

coincident_pairs = coincident_pair_table(
    coincidence,
    adjacency_by_modality,
    min_modalities=MIN_COINCIDENT_MODALITIES,
)
annotation_columns = [
    field
    for field in ("OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype")
    if field in collection.mod["rna"].obs
]
annotations = collection.mod["rna"].obs.loc[matched_models, annotation_columns].copy()
for side, column in (("1", "ModelID_1"), ("2", "ModelID_2")):
    renamed = annotations.add_suffix(f"_{side}").rename_axis(column).reset_index()
    coincident_pairs = coincident_pairs.merge(renamed, on=column, how="left", validate="many_to_one")
coincident_pairs.to_csv(RESULTS / "coincident_nearest_neighbor_pairs.csv", index=False)
print(coincidence_summary)
coincident_pairs.head(20)

# %% [markdown]
# ## Consensus neighborhoods from the coincidence graph
#
# This Clustergram follows the paper's subject-by-subject coincidence heatmap:
# a dark cell represents a pair that is local in two or three independent
# assays. The raw 0/1/2/3 counts are retained here rather than z-scoring the
# coincidence profiles, so edge intensity continues to mean the number of
# supporting assays. Ward clustering gives a fixed eight-way cut solely for
# naming groups and calling their assay-specific informative dimensions.

# %%
coincidence_adata = AnnData(
    X=coincidence.to_numpy(dtype="float32"),
    obs=annotations.copy(),
    var=annotations.copy(),
)
coincidence_adata.obs_names = matched_models
coincidence_adata.var_names = matched_models
for field in annotation_columns:
    color_key = f"{field}_colors"
    if color_key in collection.mod["rna"].uns:
        coincidence_adata.uns[color_key] = collection.mod["rna"].uns[color_key]
coincidence_matrix = Matrix(
    coincidence_adata,
    col_attr=annotation_columns,
    row_attr=annotation_columns,
    name="CCLE nearest-neighbor coincidence",
)
coincidence_matrix.cluster(dist_type="euclidean", linkage_type="ward")
consensus_labels = coincidence_matrix.cut_tree(axis="col", n_clusters=N_CONSENSUS_NEIGHBORHOODS).astype(str)
consensus_labels.name = "coincidence_neighborhood"
consensus_table = annotations.copy()
consensus_table.insert(0, "ModelID", consensus_table.index)
consensus_table["coincidence_neighborhood"] = consensus_labels.reindex(consensus_table.index).to_numpy()
consensus_table.to_csv(RESULTS / "coincidence_neighborhood_labels.csv", index=False)
consensus_table.groupby("coincidence_neighborhood").size().rename("n_models").to_csv(
    RESULTS / "coincidence_neighborhood_sizes.csv"
)

# %% [markdown]
# ## Rank informative dimensions in every assay, then stack only those features
#
# The consensus-neighborhood labels are supplied to `rank_genes_groups` one
# assay at a time. This deliberately gives RNA genes, RPPA proteins, and
# metabolites their own feature rankings. At most 120 significant top markers
# per assay are retained, together with their originating neighborhood and
# rank, before stacking. Thus each assay contributes evidence rather than RNA
# dominating merely because it has more measured dimensions.

# %%
ranked_marker_tables: list[pd.DataFrame] = []
selected_features: dict[str, pd.DataFrame] = {}
for modality in MODALITIES:
    assay = collection.mod[modality][matched_models].copy()
    assay.obs["coincidence_neighborhood"] = pd.Categorical(
        consensus_labels.reindex(assay.obs_names).to_numpy()
    )
    markers = rank_cluster_markers(
        assay,
        "coincidence_neighborhood",
        key_added="rank_genes_groups",
    )
    markers.insert(0, "modality", modality)
    ranked_marker_tables.append(markers)

    selected = select_ranked_features(
        markers.drop(columns="modality"),
        top_n_per_group=TOP_MARKERS_PER_NEIGHBORHOOD,
        max_features=MAX_SELECTED_FEATURES_PER_MODALITY,
    )
    selected.insert(0, "modality", modality)
    selected_features[modality] = selected

ranked_markers = pd.concat(ranked_marker_tables, ignore_index=True)
marker_selected_features = pd.concat(selected_features.values(), ignore_index=True)
ranked_markers.to_parquet(RESULTS / "consensus_neighborhood_ranked_markers.parquet", index=False)
marker_selected_features.to_csv(RESULTS / "marker_selected_features.csv", index=False)
marker_selected_features.groupby("modality").size().rename("n_selected_features").to_csv(
    RESULTS / "marker_selected_feature_counts.csv"
)

signature_stack = stack_selected_features(collection, selected_features, matched_models)
signature_stack.var["marker_group"] = signature_stack.var["marker_group"].astype(str)
signature_analysis, signature_clustergram = hierarchical_clustergram(
    signature_stack,
    HierarchicalConfig(
        n_top_features=signature_stack.n_vars,
        n_meta_clusters=N_CONSENSUS_NEIGHBORHOODS,
    ),
)
signature_key = signature_analysis.uns["hierarchical_clustergram"]["cluster_key"]
signature_markers = rank_cluster_markers(signature_analysis, signature_key, key_added="rank_genes_groups")
signature_marker_clustergram = marker_clustergram(signature_analysis)
signature_markers.to_parquet(RESULTS / "marker_selected_stack_ranked_markers.parquet", index=False)
signature_stack.var.to_csv(RESULTS / "marker_selected_stack_feature_provenance.csv")

print(marker_selected_features.groupby("modality").size())
marker_selected_features.groupby(["modality", "marker_group"], observed=True).head(3)[
    ["modality", "marker_group", "feature_id", "rank", "scores", "pvals_adj", "median_delta"]
]

# %% [markdown]
# ## Interactive coincidence graph and marker-selected multi-omics Clustergram
#
# The first widget identifies recurrent local cell-line relationships. The
# second shows only the assay-specific `rank_genes_groups` dimensions selected
# from those shared neighborhoods; `modality` marks each row's omic origin.

# %%
Clustergram(matrix=coincidence_matrix, width=1_100, height=700)

# %%
Clustergram(matrix=signature_marker_clustergram, width=1_100, height=700)
