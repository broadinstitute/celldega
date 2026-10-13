# %% [markdown]
# # CCLE hematologic cancers: multi-omic coincident neighbors
#
# This focused follow-up asks whether local cell-line relationships recur across
# RNA, RPPA, and metabolomics *within* a combined Lymphoid/Myeloid cohort. It
# therefore tests subtypes of related hematologic cancers instead of allowing
# broad epithelial-versus-hematologic differences to dominate the analysis.
#
# Coincident local neighborhoods define shared groups without using the
# Oncotree labels. `rank_genes_groups` then calls markers for those groups in
# each assay separately. The final Clustergram contains only this selected
# multi-omic marker union and retains the source assay as a row category.

# %%
from __future__ import annotations

from pathlib import Path
import sys

from anndata import AnnData
import pandas as pd
from sklearn.metrics import adjusted_rand_score


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
RESULTS = DATA / "results/06_hematologic_neighbor_coincidence"
RESULTS.mkdir(parents=True, exist_ok=True)

MODALITIES = ("rna", "rppa", "metabolomics")
LINEAGES = ("Lymphoid", "Myeloid")
FEATURES_PER_MODALITY = {"rna": 2_000, "rppa": 214, "metabolomics": 225}
N_NEIGHBORS = 10
MIN_COINCIDENT_MODALITIES = 2
N_PERMUTATIONS = 250
N_CONSENSUS_NEIGHBORHOODS = 6
TOP_MARKERS_PER_NEIGHBORHOOD = 15
MAX_SELECTED_FEATURES_PER_MODALITY = 120

collection = load_collection(ARCHIVE)
matched_models = shared_model_ids(collection, MODALITIES)
reference = collection.mod["rna"]
hematologic_models = matched_models[
    reference.obs.loc[matched_models, "OncotreeLineage"].isin(LINEAGES)
]
print(
    f"Matched hematologic cohort: {len(hematologic_models)} models\n",
    reference.obs.loc[hematologic_models, "OncotreeLineage"]
    .value_counts()
    .loc[lambda counts: counts > 0],
)

# %% [markdown]
# ## Recurrent local relationships across three assay spaces
#
# Ten is a fixed local-neighborhood size for this 151-model cohort. Each assay
# uses its own high-variance feature space and the same feature z-score used by
# its Ward Clustergram. No additional z-score is applied to the 0/1/2/3
# coincidence counts: those counts preserve the number of assays supporting a
# cell-line pair.

# %%
tree_matrices: dict[str, Matrix] = {}
for modality in MODALITIES:
    _, tree_matrices[modality] = hierarchical_clustergram(
        collection.mod[modality][hematologic_models].copy(),
        HierarchicalConfig(
            n_top_features=FEATURES_PER_MODALITY[modality],
            n_meta_clusters=N_CONSENSUS_NEIGHBORHOODS,
        ),
    )

relationship_values = {
    modality: matrix.data.T.reindex(hematologic_models)
    for modality, matrix in tree_matrices.items()
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

annotation_columns = [
    field
    for field in ("OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype")
    if field in reference.obs
]
annotations = reference.obs.loc[hematologic_models, annotation_columns].copy()
coincident_pairs = coincident_pair_table(
    coincidence,
    adjacency_by_modality,
    min_modalities=MIN_COINCIDENT_MODALITIES,
)
for side, column in (("1", "ModelID_1"), ("2", "ModelID_2")):
    renamed = annotations.add_suffix(f"_{side}").rename_axis(column).reset_index()
    coincident_pairs = coincident_pairs.merge(renamed, on=column, how="left", validate="many_to_one")
coincident_pairs.to_csv(RESULTS / "coincident_nearest_neighbor_pairs.csv", index=False)
print(coincidence_summary)

# %% [markdown]
# ## Consensus neighborhoods and their assay-specific markers
#
# Ward clustering of the raw coincidence profiles makes a fixed six-way cut for
# naming groups and marker testing. This number supports a compact comparison
# of myeloid, plasma-cell, mature B-cell, B-lymphoblastic, and T/NK-like
# programs. It is not a Leiden-resolution search.

# %%
coincidence_adata = AnnData(
    X=coincidence.to_numpy(dtype="float32"),
    obs=annotations.copy(),
    var=annotations.copy(),
)
coincidence_adata.obs_names = hematologic_models
coincidence_adata.var_names = hematologic_models
for field in annotation_columns:
    color_key = f"{field}_colors"
    if color_key in reference.uns:
        coincidence_adata.uns[color_key] = reference.uns[color_key]

coincidence_matrix = Matrix(
    coincidence_adata,
    col_attr=annotation_columns,
    row_attr=annotation_columns,
    name="CCLE hematologic nearest-neighbor coincidence",
)
coincidence_matrix.cluster(dist_type="euclidean", linkage_type="ward")
consensus_labels = coincidence_matrix.cut_tree(
    axis="col",
    n_clusters=N_CONSENSUS_NEIGHBORHOODS,
).astype(str)
consensus_labels.name = "coincidence_neighborhood"
coincidence_matrix.add_category("col", "coincidence_neighborhood", consensus_labels)
coincidence_matrix.add_category("row", "coincidence_neighborhood", consensus_labels)
coincidence_matrix.set_global_cat_colors()

consensus_table = annotations.copy()
consensus_table.insert(0, "ModelID", consensus_table.index)
consensus_table["coincidence_neighborhood"] = consensus_labels.reindex(consensus_table.index).to_numpy()
consensus_table.to_csv(RESULTS / "coincidence_neighborhood_labels.csv", index=False)
consensus_table.groupby("coincidence_neighborhood").size().rename("n_models").to_csv(
    RESULTS / "coincidence_neighborhood_sizes.csv"
)
pd.crosstab(
    consensus_table["coincidence_neighborhood"],
    consensus_table["OncotreePrimaryDisease"],
).to_csv(RESULTS / "coincidence_neighborhood_by_primary_disease.csv")


def top_annotations(frame: pd.DataFrame, field: str, n: int = 3) -> str:
    """Render the most frequent post-hoc annotations without fitting on them."""
    counts = frame[field].value_counts().head(n)
    return ", ".join(f"{name} ({count})" for name, count in counts.items())


consensus_summary = pd.DataFrame(
    [
        {
            "coincidence_neighborhood": group,
            "n_models": len(frame),
            "lineages": top_annotations(frame, "OncotreeLineage", n=2),
            "top_subtypes": top_annotations(frame, "OncotreeSubtype"),
        }
        for group, frame in consensus_table.groupby("coincidence_neighborhood", observed=True)
    ]
)
consensus_summary.to_csv(RESULTS / "coincidence_neighborhood_summary.csv", index=False)
consensus_summary  # noqa: B018 - intentional Jupyter table output

# %% [markdown]
# ## Select markers per assay, then visualize their union
#
# The same consensus labels are passed to `rank_genes_groups` separately for
# RNA, RPPA, and metabolites. Each assay gets up to 120 significant markers,
# selected from its own top fifteen dimensions per consensus group. This keeps
# the final stack interpretable and prevents the much larger RNA feature space
# from deciding the feature count.

# %%
ranked_marker_tables: list[pd.DataFrame] = []
selected_features: dict[str, pd.DataFrame] = {}
for modality in MODALITIES:
    assay = collection.mod[modality][hematologic_models].copy()
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
selected_marker_features = pd.concat(selected_features.values(), ignore_index=True)
ranked_markers.to_parquet(RESULTS / "consensus_neighborhood_ranked_markers.parquet", index=False)
selected_marker_features.to_csv(RESULTS / "marker_selected_features.csv", index=False)
selected_marker_features.groupby("modality").size().rename("n_selected_features").to_csv(
    RESULTS / "marker_selected_feature_counts.csv"
)
top_assay_markers = (
    ranked_markers.loc[(ranked_markers["rank"] <= 15) & (ranked_markers["pvals_adj"] <= 0.05)]
    .sort_values(["modality", "group", "rank"])
    .groupby(["modality", "group"], observed=True)
    .head(3)
)
top_assay_markers.to_csv(RESULTS / "top_consensus_markers_by_modality.csv", index=False)

signature_stack = stack_selected_features(collection, selected_features, hematologic_models)
signature_stack.obs["coincidence_neighborhood"] = pd.Categorical(
    consensus_labels.reindex(signature_stack.obs_names).to_numpy()
)
signature_attributes = ("coincidence_neighborhood", *annotation_columns)
signature_analysis, _ = hierarchical_clustergram(
    signature_stack,
    HierarchicalConfig(
        n_top_features=signature_stack.n_vars,
        n_meta_clusters=N_CONSENSUS_NEIGHBORHOODS,
    ),
    col_attributes=signature_attributes,
)
signature_key = signature_analysis.uns["hierarchical_clustergram"]["cluster_key"]
signature_markers = rank_cluster_markers(
    signature_analysis,
    "coincidence_neighborhood",
    key_added="rank_genes_groups",
)
signature_marker_clustergram = marker_clustergram(
    signature_analysis,
    col_attributes=signature_attributes,
)
signature_markers.to_parquet(RESULTS / "marker_selected_stack_consensus_markers.parquet", index=False)
signature_stack.var.to_csv(RESULTS / "marker_selected_stack_feature_provenance.csv")

signature_labels = signature_analysis.obs[["coincidence_neighborhood", signature_key]].copy()
signature_labels.insert(0, "ModelID", signature_analysis.obs_names)
signature_labels.to_csv(RESULTS / "marker_selected_stack_labels.csv", index=False)
pd.DataFrame(
    [
        {
            "n_models": len(signature_analysis),
            "adjusted_rand_index_consensus_vs_marker_stack_tree": adjusted_rand_score(
                signature_analysis.obs["coincidence_neighborhood"].astype(str),
                signature_analysis.obs[signature_key].astype(str),
            ),
        }
    ]
).to_csv(RESULTS / "marker_selected_stack_agreement.csv", index=False)

print(selected_marker_features.groupby("modality").size())
top_assay_markers[["modality", "group", "rank", "names", "scores", "pvals_adj", "median_delta"]]

# %% [markdown]
# ## Interactive coincidence and selected-marker Clustergrams
#
# The coincidence map preserves the number of assays supporting each local
# relationship. The marker stack then tests whether the assay-specific markers
# of those consensus groups recover an interpretable combined hierarchy. The
# `coincidence_neighborhood` column category lets the two views be compared
# without claiming that the second Ward tree created the groups.

# %%
Clustergram(matrix=coincidence_matrix, width=1_100, height=760)

# %%
Clustergram(matrix=signature_marker_clustergram, width=1_100, height=760)
