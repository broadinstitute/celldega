# %% [markdown]
# # CCLE multi-omics: tissue hierarchies and recurring RNA programs
#
# The global RNA dendrogram establishes the broad tissue structure.  This
# notebook then holds `OncotreeLineage` constant, builds a smaller Ward tree
# within each adequately represented lineage, and compares the marker sets of
# the resulting branches.  The row-side dendrogram is also cut into
# co-varying gene modules and scored in every cell line.
#
# A flat cut is used only to name a few branches for marker ranking.  The full
# Clustergram tree remains the primary result; no resolution sweep is used.

# %%
from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


PROJECT = next(parent for parent in (Path.cwd(), *Path.cwd().parents) if (parent / "pyproject.toml").exists())
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from celldega.viz import Clustergram
from notebooks.ccle_multiomics import (
    HierarchicalConfig,
    gene_modules_from_clustergram,
    hierarchical_clustergram,
    load_collection,
    marker_clustergram,
    marker_jaccard,
    rank_cluster_markers,
    representative_module_features,
)


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/03_tissue_gene_programs"
RESULTS.mkdir(parents=True, exist_ok=True)

collection = load_collection(ARCHIVE)
rna = collection.mod["rna"]

LINEAGE_FIELD = "OncotreeLineage"
MIN_MODELS_PER_LINEAGE = 30
WITHIN_LINEAGE_BRANCHES = 3
N_GENE_MODULES = 30

# %% [markdown]
# ## The row tree defines descriptive gene programs
#
# `global_clustergram` uses the 2,000 most variable RNA genes.  Cutting its
# *row* tree defines co-varying modules.  Module scores are simply mean gene
# z-scores from that same Clustergram, not separately fitted latent factors.

# %%
global_rna, global_clustergram = hierarchical_clustergram(
    rna,
    HierarchicalConfig(n_top_features=2_000, n_meta_clusters=8),
)
global_cluster_key = global_rna.uns["hierarchical_clustergram"]["cluster_key"]
rank_cluster_markers(global_rna, global_cluster_key, key_added="rank_genes_groups")
global_marker_clustergram = marker_clustergram(global_rna)
gene_modules, gene_program_scores = gene_modules_from_clustergram(
    global_clustergram, n_modules=N_GENE_MODULES
)

gene_modules.to_parquet(RESULTS / "rna_gene_modules.parquet", index=False)
gene_program_scores.reset_index().to_parquet(RESULTS / "rna_gene_program_scores.parquet", index=False)
representative_module_features(
    global_clustergram, gene_modules, gene_program_scores
).to_parquet(RESULTS / "rna_gene_module_representatives.parquet", index=False)

lineage = global_rna.obs[LINEAGE_FIELD].replace("unknown", pd.NA)
program_by_lineage = (
    gene_program_scores.join(lineage)
    .dropna(subset=[LINEAGE_FIELD])
    .groupby(LINEAGE_FIELD, observed=True)
    .mean()
)
program_by_lineage.to_parquet(RESULTS / "rna_gene_programs_by_lineage.parquet")

top_lineages_per_program = (
    program_by_lineage.reset_index()
    .melt(id_vars=LINEAGE_FIELD, var_name="gene_module", value_name="mean_zscore")
    .sort_values(["gene_module", "mean_zscore"], ascending=[True, False])
    .groupby("gene_module", observed=True)
    .head(5)
)
top_lineages_per_program.to_csv(RESULTS / "top_lineages_per_gene_program.csv", index=False)

# %% [markdown]
# ## Rebuild the hierarchy inside each tissue lineage
#
# The global dendrogram is expected to separate many tissue lineages first.
# Within-lineage trees reveal sub-histology and state variation that are hidden
# by that broad separation.  Three is a fixed, small initial cut for marker
# tables.  Inspect `tissue_clustergrams` to select different branches from the
# complete trees.

# %%
lineage_counts = (
    rna.obs[LINEAGE_FIELD]
    .replace("unknown", pd.NA)
    .value_counts()
    .rename_axis(LINEAGE_FIELD)
    .rename("n_models")
)
eligible_lineages = lineage_counts.loc[lambda count: count >= MIN_MODELS_PER_LINEAGE].index.tolist()
lineage_counts.to_csv(RESULTS / "rna_lineage_sizes.csv")

tissue_clustergrams: dict[str, object] = {}
tissue_labels: list[pd.DataFrame] = []
tissue_markers: list[pd.DataFrame] = []

for lineage_name in eligible_lineages:
    within_lineage = rna[rna.obs[LINEAGE_FIELD] == lineage_name].copy()
    analysis, clustergram = hierarchical_clustergram(
        within_lineage,
        HierarchicalConfig(
            n_top_features=min(1_000, within_lineage.n_vars),
            n_meta_clusters=WITHIN_LINEAGE_BRANCHES,
        ),
    )
    cluster_key = analysis.uns["hierarchical_clustergram"]["cluster_key"]
    tissue_clustergrams[str(lineage_name)] = clustergram

    labels = analysis.obs[[
        field
        for field in (LINEAGE_FIELD, "OncotreePrimaryDisease", "OncotreeSubtype", cluster_key)
        if field in analysis.obs
    ]].copy()
    labels.insert(0, "ModelID", analysis.obs_names)
    labels = labels.rename(columns={cluster_key: "hierarchical_cluster"})
    tissue_labels.append(labels)

    markers = rank_cluster_markers(analysis, cluster_key)
    markers.insert(0, LINEAGE_FIELD, str(lineage_name))
    tissue_markers.append(markers)

within_lineage_labels = pd.concat(tissue_labels, ignore_index=True)
within_lineage_markers = pd.concat(tissue_markers, ignore_index=True)
within_lineage_labels.to_parquet(RESULTS / "within_lineage_cluster_labels.parquet", index=False)
within_lineage_markers.to_parquet(RESULTS / "within_lineage_hierarchical_markers.parquet", index=False)

top_within_lineage_markers = within_lineage_markers.query("rank <= 20 and pvals_adj <= 0.05")
top_within_lineage_markers.to_csv(RESULTS / "within_lineage_top20_markers.csv", index=False)

# %% [markdown]
# ## Repeated marker programs across tissue lineages
#
# High Jaccard overlap between the independently derived top-marker sets is a
# compact starting point for programs that recur outside one tissue lineage.
# These candidates should be inspected in the global Clustergram and confirmed
# with their effect sizes before being called a biological program.

# %%
marker_overlap = marker_jaccard(
    within_lineage_markers,
    group_columns=[LINEAGE_FIELD, "group"],
    top_n=20,
)
marker_overlap = marker_overlap.loc[
    marker_overlap[f"left_{LINEAGE_FIELD}"] != marker_overlap[f"right_{LINEAGE_FIELD}"]
].copy()
marker_overlap.to_csv(RESULTS / "cross_lineage_marker_overlap.csv", index=False)

marker_overlap.head(20)

# %% [markdown]
# ## Interactive RNA program Clustergram
#
# The row-side dendrogram contains the co-varying programs summarized above.
# The RANK control reduces this global RNA tree to the strongest branch markers,
# while tissue and subtype tracks provide biological context after clustering.

# %%
Clustergram(matrix=global_marker_clustergram, width=1_100, height=700)
