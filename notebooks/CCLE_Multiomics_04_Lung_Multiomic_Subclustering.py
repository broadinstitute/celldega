# %% [markdown]
# # CCLE lung cancer: multi-omic subclustering
#
# This is a matched-cohort follow-up to the global and within-tissue trees. It
# builds independent Ward trees for each assay, evaluates the agreement of their
# branch assignments, and makes a feature-stacked Clustergram with an explicit
# `modality` row annotation.

# %%
from __future__ import annotations

from itertools import combinations
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr
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
    split_stacked_feature_id,
    stack_modalities,
)
from notebooks.ccle_multiomics.coincidence import stack_selected_features


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/04_lung_multiomic_concordance"
RESULTS.mkdir(parents=True, exist_ok=True)

MODALITIES = ("rna", "rppa", "metabolomics")
N_BRANCHES = 3
FEATURES_PER_MODALITY = {"rna": 2_000, "rppa": 214, "metabolomics": 225}
# A stacked Euclidean tree should not be dominated simply because RNA has more
# assayed features. Keep independent trees source-appropriate above, then use
# the same number of high-variance rows from each assay in the integrated view.
STACKED_FEATURES_PER_MODALITY = {"rna": 214, "rppa": 214, "metabolomics": 214}

collection = load_collection(ARCHIVE)
shared = shared_model_ids(collection, MODALITIES)
rna = collection.mod["rna"]
lung_models = shared[rna.obs.loc[shared, "OncotreeLineage"].eq("Lung")]
print(f"Matched lung cohort: {len(lung_models)} models")

# %% [markdown]
# ## Independent per-assay trees
#
# The branches below are discovered independently. `marker_clustergrams` holds
# top-marker slider views for interactive inspection, while the tables retain
# rank statistics and source-scale median effects.

# %%
independent: dict[str, object] = {}
marker_clustergrams: dict[str, object] = {}
label_tables: list[pd.DataFrame] = []
marker_tables: list[pd.DataFrame] = []

for modality in MODALITIES:
    analysis, _ = hierarchical_clustergram(
        collection.mod[modality][lung_models].copy(),
        HierarchicalConfig(
            n_top_features=FEATURES_PER_MODALITY[modality],
            n_meta_clusters=N_BRANCHES,
        ),
    )
    cluster_key = analysis.uns["hierarchical_clustergram"]["cluster_key"]
    independent[modality] = analysis

    labels = analysis.obs[[
        field
        for field in ("OncotreePrimaryDisease", "OncotreeSubtype", cluster_key)
        if field in analysis.obs
    ]].copy()
    labels.insert(0, "ModelID", analysis.obs_names)
    labels.insert(1, "modality", modality)
    labels = labels.rename(columns={cluster_key: "hierarchical_cluster"})
    label_tables.append(labels)

    markers = rank_cluster_markers(analysis, cluster_key, key_added="rank_genes_groups")
    marker_clustergrams[modality] = marker_clustergram(analysis)
    markers.insert(0, "modality", modality)
    marker_tables.append(markers)

independent_labels = pd.concat(label_tables, ignore_index=True)
independent_markers = pd.concat(marker_tables, ignore_index=True)
independent_labels.to_parquet(RESULTS / "matched_lung_cluster_labels.parquet", index=False)
independent_markers.to_parquet(RESULTS / "matched_lung_hierarchical_markers.parquet", index=False)
independent_markers.query("rank <= 20 and pvals_adj <= 0.05").to_csv(
    RESULTS / "matched_lung_top20_markers.csv", index=False
)

# %% [markdown]
# ## Co-clustering coincidence on the same cell lines
#
# The adjusted Rand index compares branch membership without requiring an
# arbitrary relabeling. The contingency tables show which RNA branches coincide
# with an RPPA or metabolite branch on this explicit matched cohort.

# %%
labels_by_modality = {
    modality: independent[modality].obs["hierarchical_k3"].astype(str) for modality in MODALITIES
}
agreement_rows: list[dict[str, object]] = []

for left, right in combinations(MODALITIES, 2):
    table = pd.crosstab(labels_by_modality[left], labels_by_modality[right])
    table.index.name = f"{left}_cluster"
    table.columns.name = f"{right}_cluster"
    table.to_csv(RESULTS / f"{left}_by_{right}_branch_coincidence.csv")
    agreement_rows.append(
        {
            "left_modality": left,
            "right_modality": right,
            "n_models": len(lung_models),
            "adjusted_rand_index": adjusted_rand_score(
                labels_by_modality[left], labels_by_modality[right]
            ),
        }
    )

agreement = pd.DataFrame(agreement_rows)
agreement.to_csv(RESULTS / "independent_branch_agreement.csv", index=False)
print(agreement)

# %% [markdown]
# ## A stacked multi-omic Clustergram
#
# `stack_modalities` retains the matched cohort and appends a parseable
# ``::modality`` suffix only to keep feature IDs unique. Its `modality` row
# annotation distinguishes RNA genes, RPPA antibodies, and metabolites while
# the row z-score gives their patterns a
# common display scale. Equal feature counts prevent RNA from winning simply
# because it has a much larger measured feature space.

# %%
stacked = stack_modalities(
    collection,
    MODALITIES,
    lung_models,
    n_top_features=STACKED_FEATURES_PER_MODALITY,
)
stacked_analysis, stacked_clustergram = hierarchical_clustergram(
    stacked,
    HierarchicalConfig(n_top_features=stacked.n_vars, n_meta_clusters=N_BRANCHES),
)
stacked_key = stacked_analysis.uns["hierarchical_clustergram"]["cluster_key"]
stacked_markers = rank_cluster_markers(stacked_analysis, stacked_key, key_added="rank_genes_groups")
stacked_marker_clustergram = marker_clustergram(stacked_analysis)

stacked_labels = stacked_analysis.obs[[
    field
    for field in ("OncotreePrimaryDisease", "OncotreeSubtype", stacked_key)
    if field in stacked_analysis.obs
]].copy()
stacked_labels.insert(0, "ModelID", stacked_analysis.obs_names)
stacked_labels = stacked_labels.rename(columns={stacked_key: "hierarchical_cluster"})
stacked_labels.to_parquet(RESULTS / "stacked_lung_cluster_labels.parquet", index=False)
stacked_markers.to_parquet(RESULTS / "stacked_lung_hierarchical_markers.parquet", index=False)

stacked_agreement = []
for modality, labels in labels_by_modality.items():
    stacked_agreement.append(
        {
            "modality": modality,
            "n_models": len(lung_models),
            "adjusted_rand_index_with_stacked_tree": adjusted_rand_score(
                labels, stacked_analysis.obs[stacked_key].astype(str)
            ),
        }
    )
pd.DataFrame(stacked_agreement).to_csv(RESULTS / "stacked_branch_agreement.csv", index=False)

# %% [markdown]
# ## A neuroendocrine small-cell branch across omics
#
# The following interpretation is deliberately derived after the unsupervised
# tree. The branch with the largest fraction of annotated small-cell lung
# cancer (SCLC) models is used only as a readable label for the discovered
# branch. We first check direct RNA--RPPA target pairs that are actually
# present in the two assays, then ask which metabolite markers covary with a
# compact RNA neuroendocrine signature. This makes the metabolite results
# candidate associations rather than claims of a causal pathway.

# %%
SCLC_SUBTYPE = "Small Cell Lung Cancer"
SCLC_SIGNATURE_GENES = ("INSM1", "ASCL1", "CHGA", "CHGB", "SYP", "NCAM1", "HES6")
GENE_PROTEIN_PAIRS = (
    ("CDH1", "E-Cadherin"),
    ("BCL2", "Bcl-2"),
    ("IGFBP2", "IGFBP2"),
    ("KIT", "c-Kit"),
    ("EGFR", "EGFR"),
    ("CAV1", "Caveolin-1"),
    ("YAP1", "YAP_Caution"),
    ("ERBB2", "HER2"),
    ("NOTCH1", "Notch1"),
)

subtypes = stacked_analysis.obs["OncotreeSubtype"].astype("string")
branch_sclc_fraction = (
    pd.DataFrame({"branch": stacked_analysis.obs[stacked_key].astype(str), "is_sclc": subtypes.eq(SCLC_SUBTYPE)})
    .groupby("branch", observed=True)["is_sclc"]
    .agg(["sum", "count", "mean"])
    .sort_values(["mean", "sum"], ascending=False)
)
sclc_branch = str(branch_sclc_fraction.index[0])
is_sclc_branch = stacked_analysis.obs[stacked_key].astype(str).eq(sclc_branch)
stacked_analysis.obs["SCLC_neuroendocrine_branch"] = pd.Categorical(
    np.where(is_sclc_branch, "SCLC-enriched branch", "Other lung branches")
)
branch_sclc_fraction.to_csv(RESULTS / "sclc_branch_composition.csv")


def assay_frame(modality: str, features: list[str]) -> pd.DataFrame:
    """Return original-scale assay values in the shared lung-model order."""
    assay = collection.mod[modality][lung_models, features]
    return assay.to_df().reindex(lung_models)


rna_features = [gene for gene, _ in GENE_PROTEIN_PAIRS if gene in rna.var_names]
rppa_features = [protein for _, protein in GENE_PROTEIN_PAIRS if protein in collection.mod["rppa"].var_names]
rna_values = assay_frame("rna", rna_features)
rppa_values = assay_frame("rppa", rppa_features)
branch_mask = is_sclc_branch.reindex(lung_models).to_numpy()

gene_protein_rows: list[dict[str, object]] = []
for gene, protein in GENE_PROTEIN_PAIRS:
    if gene not in rna_values or protein not in rppa_values:
        continue
    rho, pvalue = spearmanr(rna_values[gene], rppa_values[protein])
    gene_protein_rows.append(
        {
            "gene": gene,
            "rppa_target": protein,
            "spearman_rho": rho,
            "spearman_pvalue": pvalue,
            "rna_branch_median_delta": rna_values.loc[branch_mask, gene].median() - rna_values.loc[~branch_mask, gene].median(),
            "rppa_branch_median_delta": rppa_values.loc[branch_mask, protein].median() - rppa_values.loc[~branch_mask, protein].median(),
        }
    )
gene_protein_pairs = pd.DataFrame(gene_protein_rows).sort_values("spearman_rho", ascending=False)
gene_protein_pairs.to_csv(RESULTS / "sclc_branch_gene_protein_pairs.csv", index=False)

signature_genes = [gene for gene in SCLC_SIGNATURE_GENES if gene in rna.var_names]
signature_values = assay_frame("rna", signature_genes)
signature_z = (signature_values - signature_values.mean()) / signature_values.std(ddof=0).replace(0, np.nan)
sclc_signature = signature_z.mean(axis=1)

metabolite_markers = (
    stacked_markers.loc[
        stacked_markers["group"].astype(str).eq(sclc_branch)
        & stacked_markers["names"].str.endswith("::metabolomics")
        & stacked_markers["pvals_adj"].le(0.05)
    ]
    .sort_values("rank")
    .head(8)
    .copy()
)
metabolite_markers["metabolite"] = metabolite_markers["names"].map(
    lambda feature_id: split_stacked_feature_id(feature_id)[0]
)
metabolite_values = assay_frame("metabolomics", metabolite_markers["metabolite"].tolist())

metabolite_rows: list[dict[str, object]] = []
for marker in metabolite_markers.itertuples(index=False):
    metabolite = marker.metabolite
    rho, pvalue = spearmanr(sclc_signature, metabolite_values[metabolite])
    _, branch_pvalue = mannwhitneyu(
        metabolite_values.loc[branch_mask, metabolite],
        metabolite_values.loc[~branch_mask, metabolite],
        alternative="greater",
    )
    metabolite_rows.append(
        {
            "metabolite": metabolite,
            "rank_genes_groups_rank": marker.rank,
            "rank_genes_groups_padj": marker.pvals_adj,
            "spearman_rho_with_rna_neuroendocrine_signature": rho,
            "spearman_pvalue": pvalue,
            "branch_median_delta": marker.median_delta,
            "one_sided_branch_test_pvalue": branch_pvalue,
        }
    )
metabolite_associations = pd.DataFrame(metabolite_rows).sort_values(
    "spearman_rho_with_rna_neuroendocrine_signature", ascending=False
)
metabolite_associations.to_csv(RESULTS / "sclc_branch_metabolite_associations.csv", index=False)

print(f"SCLC-enriched stacked branch: {sclc_branch}")
print(branch_sclc_fraction)
print("\nDirect RNA--RPPA target pairs")
print(gene_protein_pairs.round(3).to_string(index=False))
print("\nCandidate metabolite associations")
print(metabolite_associations.round(3).to_string(index=False))

# %% [markdown]
# The direct-pair table includes a useful epithelial anchor: RNA `CDH1` and the
# RPPA `E-Cadherin` target. They can be adjacent in the focused stacked view
# because their profiles agree across the lung panel. The row label is written
# as `CDH1::rna` or `E-Cadherin::rppa` so its assay origin remains visible;
# Celldega strips that explicit suffix before a gene-oriented UniProt lookup.
# The RPPA measurement remains an antibody target, so this is a cross-assay
# concordance observation rather than an independent protein-identification
# claim.

# %% [markdown]
# In this dataset the SCLC-enriched branch is supported strongly by the RNA and
# RPPA trees, while the metabolite tree is more heterogeneous. The exported
# tables above make that distinction auditable: direct gene--protein agreement
# is reported separately from metabolite covariation with the RNA signature.
# In particular, the metabolite panel is a compact readout for follow-up, not a
# marker set used to name the branch.

# %% [markdown]
# ## Focused SCLC cross-omic readout
#
# This small view stacks only the RNA neuroendocrine signature, the direct
# RNA--RPPA target pairs, and the rank-derived metabolite candidates above.
# It is a post-clustering explanatory panel: it is not used to discover the
# primary Ward tree or to calculate agreement. A row z-score is used solely to
# put the three assay scales on a common display scale.

# %%
sclc_focus = stack_selected_features(
    collection,
    {
        "rna": pd.DataFrame({"feature_id": signature_genes}),
        "rppa": pd.DataFrame({"feature_id": gene_protein_pairs["rppa_target"].tolist()}),
        "metabolomics": pd.DataFrame({"feature_id": metabolite_associations["metabolite"].tolist()}),
    },
    lung_models,
)
sclc_focus.obs["SCLC_neuroendocrine_branch"] = pd.Categorical(
    np.where(branch_mask, "SCLC-enriched branch", "Other lung branches"),
    categories=["SCLC-enriched branch", "Other lung branches"],
)
sclc_focus.uns["SCLC_neuroendocrine_branch_colors"] = ["#E45756", "#BAB0AC"]
sclc_focus_matrix = Matrix(
    sclc_focus,
    col_attr=("SCLC_neuroendocrine_branch", "OncotreePrimaryDisease", "OncotreeSubtype"),
    row_attr=("modality",),
    name="CCLE lung SCLC candidate cross-omic readout",
)
sclc_focus_matrix.norm("row", by="zscore")
sclc_focus_matrix.cluster(dist_type="euclidean", linkage_type="ward")

Clustergram(matrix=sclc_focus_matrix, width=1_100, height=700)

# %% [markdown]
# ## Interactive lung stacked Clustergram
#
# This view places the matched lung lines on one shared dendrogram. Its
# `modality` track distinguishes RNA genes, RPPA antibodies, and metabolites;
# the RANK control shows top features for each of the three dendrogram branches.

# %%
Clustergram(matrix=stacked_marker_clustergram, width=1_100, height=700)
