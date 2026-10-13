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
from scipy.stats import spearmanr
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
consensus_categories = sorted(consensus_labels.unique(), key=int)
consensus_colors = dict(
    zip(
        consensus_categories,
        ("#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2"),
        strict=True,
    )
)
coincidence_matrix.add_category("col", "coincidence_neighborhood", consensus_labels)
coincidence_matrix.add_category("row", "coincidence_neighborhood", consensus_labels)
coincidence_matrix.set_global_cat_colors(consensus_colors)

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
    counts = frame[field].astype("string").dropna().value_counts().head(n)
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
    consensus_labels.reindex(signature_stack.obs_names).to_numpy(),
    categories=consensus_categories,
)
signature_stack.uns["coincidence_neighborhood_colors"] = [
    consensus_colors[group] for group in consensus_categories
]
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
# ## Reading recurrent hematologic neighborhoods across assays
#
# The summary below remains an exploratory description of unsupervised groups:
# the lineage and disease names were not used to build the coincidence graph.
# It collects the leading rank-tested dimensions from each assay so that a
# group can be followed from its recurrent neighbors to RNA, RPPA, and
# metabolite measurements without collapsing the three assay types into one
# generic feature list.

# %%
neighborhood_marker_summary = (
    top_assay_markers.groupby(["group", "modality"], observed=True)["names"]
    .agg(lambda names: ", ".join(names.astype(str)))
    .unstack("modality")
    .rename(columns={"rna": "top_rna", "rppa": "top_rppa", "metabolomics": "top_metabolites"})
    .reset_index()
    .rename(columns={"group": "coincidence_neighborhood"})
    .merge(consensus_summary, on="coincidence_neighborhood", how="left", validate="one_to_one")
)
neighborhood_marker_summary.to_csv(RESULTS / "coincidence_neighborhood_marker_summary.csv", index=False)
print(neighborhood_marker_summary.to_string(index=False))

# %% [markdown]
# Several compact cross-assay readouts are worth checking directly. The table
# below only includes a target when an RNA gene and the corresponding RPPA
# antibody feature are both measured. Its correlations are descriptive across
# the 151 matched hematologic models; the group-specific deltas tell whether a
# target contributes to the indicated recurrent neighborhood. The `Caution`
# suffix is retained exactly where it appears in the source RPPA panel.
#
# In the current run, neighborhood 1 is CML/AML-heavy and highlights
# STAT5A--STAT5-alpha and KIT--c-Kit alongside phosphocreatine and
# 1-methylnicotinamide. Its SLC6A8--phosphocreatine RNA--metabolite pairing is
# shown separately below. Neighborhood 4 is mature-B-cell-heavy with the
# CD20/SYK axis and lysophospholipids. Neighborhood 6 includes a T-ALL-rich
# component with GATA3/NOTCH1 and GABA/NAD. These are useful hypotheses for
# follow-up, not externally validated clinical classifiers.

# %%
GENE_PROTEIN_CONTEXTS = (
    ("1", "STAT5A", "STAT5-alpha"),
    ("1", "KIT", "c-Kit"),
    ("2", "MAPK14", "p38 alpha MAPK"),
    ("4", "MS4A1", "CD20 _Caution"),
    ("4", "SYK", "Syk"),
    ("5", "GAB2", "Gab2"),
    ("5", "PRDX1", "PRDX1"),
    ("6", "GATA3", "GATA3"),
    ("6", "NOTCH1", "Notch1"),
)


def assay_values(modality: str, features: list[str]) -> pd.DataFrame:
    """Return original-scale matched-cohort values for direct comparisons."""
    return collection.mod[modality][hematologic_models, features].to_df().reindex(hematologic_models)


rna_targets = [gene for _, gene, _ in GENE_PROTEIN_CONTEXTS if gene in collection.mod["rna"].var_names]
rppa_targets = [target for _, _, target in GENE_PROTEIN_CONTEXTS if target in collection.mod["rppa"].var_names]
rna_values = assay_values("rna", rna_targets)
rppa_values = assay_values("rppa", rppa_targets)
consensus_by_model = consensus_labels.reindex(hematologic_models).astype(str)


def marker_rank(group: str, modality: str, feature: str) -> float | None:
    """Look up the within-assay rank without converting it into a new test."""
    found = ranked_markers.loc[
        ranked_markers["group"].astype(str).eq(group)
        & ranked_markers["modality"].eq(modality)
        & ranked_markers["names"].eq(feature),
        "rank",
    ]
    return None if found.empty else float(found.iloc[0])


pair_rows: list[dict[str, object]] = []
for group, gene, target in GENE_PROTEIN_CONTEXTS:
    if gene not in rna_values or target not in rppa_values:
        continue
    in_group = consensus_by_model.eq(group)
    rho, pvalue = spearmanr(rna_values[gene], rppa_values[target])
    pair_rows.append(
        {
            "coincidence_neighborhood": group,
            "gene": gene,
            "rppa_target": target,
            "spearman_rho_all_hematologic_models": rho,
            "spearman_pvalue": pvalue,
            "rna_marker_rank_in_neighborhood": marker_rank(group, "rna", gene),
            "rppa_marker_rank_in_neighborhood": marker_rank(group, "rppa", target),
            "rna_neighborhood_median_delta": rna_values.loc[in_group, gene].median() - rna_values.loc[~in_group, gene].median(),
            "rppa_neighborhood_median_delta": rppa_values.loc[in_group, target].median() - rppa_values.loc[~in_group, target].median(),
        }
    )

gene_protein_context = pd.DataFrame(pair_rows).sort_values(
    ["coincidence_neighborhood", "spearman_rho_all_hematologic_models"],
    ascending=[True, False],
)
gene_protein_context.to_csv(RESULTS / "contextual_gene_protein_pairs.csv", index=False)
print("\nContextual RNA--RPPA target pairs")
print(gene_protein_context.round(3).to_string(index=False))

# %%
GENE_METABOLITE_CONTEXTS = (("1", "SLC6A8", "phosphocreatine"),)
gene_metabolite_rows: list[dict[str, object]] = []
for group, gene, metabolite in GENE_METABOLITE_CONTEXTS:
    if gene not in collection.mod["rna"].var_names or metabolite not in collection.mod["metabolomics"].var_names:
        continue
    gene_values = assay_values("rna", [gene])[gene]
    metabolite_values = assay_values("metabolomics", [metabolite])[metabolite]
    in_group = consensus_by_model.eq(group)
    rho, pvalue = spearmanr(gene_values, metabolite_values)
    gene_metabolite_rows.append(
        {
            "coincidence_neighborhood": group,
            "gene": gene,
            "metabolite": metabolite,
            "spearman_rho_all_hematologic_models": rho,
            "spearman_pvalue": pvalue,
            "rna_marker_rank_in_neighborhood": marker_rank(group, "rna", gene),
            "metabolite_marker_rank_in_neighborhood": marker_rank(group, "metabolomics", metabolite),
            "rna_neighborhood_median_delta": gene_values.loc[in_group].median() - gene_values.loc[~in_group].median(),
            "metabolite_neighborhood_median_delta": metabolite_values.loc[in_group].median() - metabolite_values.loc[~in_group].median(),
        }
    )
gene_metabolite_context = pd.DataFrame(gene_metabolite_rows)
gene_metabolite_context.to_csv(RESULTS / "contextual_gene_metabolite_pairs.csv", index=False)
print("\nContextual RNA--metabolite pairs")
print(gene_metabolite_context.round(3).to_string(index=False))

# %% [markdown]
# ## Focused hematologic cross-omic readout
#
# The compact panel below is an explanatory companion to the full
# marker-selected Clustergram. It contains the contextual RNA--RPPA and
# RNA--metabolite pairs above, plus the two strongest rank-tested metabolites
# from each recurrent neighborhood. The original coincidence labels appear as
# a shared column category with the same colors as the full views.

# %%
focus_metabolites = (
    top_assay_markers.loc[top_assay_markers["modality"].eq("metabolomics")]
    .sort_values(["group", "rank"])
    .groupby("group", observed=True)
    .head(2)["names"]
    .drop_duplicates()
    .tolist()
)
hematologic_focus = stack_selected_features(
    collection,
    {
        "rna": pd.DataFrame(
            {
                "feature_id": pd.concat(
                    [gene_protein_context["gene"], gene_metabolite_context["gene"]]
                ).drop_duplicates()
            }
        ),
        "rppa": pd.DataFrame({"feature_id": gene_protein_context["rppa_target"].drop_duplicates()}),
        "metabolomics": pd.DataFrame({"feature_id": focus_metabolites}),
    },
    hematologic_models,
)
hematologic_focus.obs["coincidence_neighborhood"] = pd.Categorical(
    consensus_labels.reindex(hematologic_focus.obs_names).to_numpy(),
    categories=consensus_categories,
)
hematologic_focus.uns["coincidence_neighborhood_colors"] = [
    consensus_colors[group] for group in consensus_categories
]
hematologic_focus_matrix = Matrix(
    hematologic_focus,
    col_attr=["coincidence_neighborhood", *annotation_columns],
    row_attr=["modality"],
    name="CCLE hematologic contextual cross-omic readout",
)
hematologic_focus_matrix.norm("row", by="zscore")
hematologic_focus_matrix.cluster(dist_type="euclidean", linkage_type="ward")

Clustergram(matrix=hematologic_focus_matrix, width=1_100, height=760)

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
