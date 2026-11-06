# %% [markdown]
# # CCLE multi-omics: RNA-anchored cluster characterization
#
# This complementary route makes one assay the discovery space. RNA defines the
# primary Ward hierarchy on the complete RNA/RPPA/metabolomics cohort; its
# dendrogram cut is then transferred unchanged to RPPA and metabolomics.
# rank_genes_groups therefore asks a focused question in every layer:
# which genes, antibody targets, and metabolites characterize these
# RNA-defined cell-line groups?
#
# This avoids interpreting a stacked dendrogram as consensus evidence. The
# final balanced stacked panel is explanatory: its columns retain the original
# RNA dendrogram, and its rows are independently selected markers from all
# three assays.

# %%
from __future__ import annotations

from pathlib import Path
import sys

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
    select_ranked_features,
    stack_selected_features,
)


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/08_rna_anchored_multiomic_characterization"
RESULTS.mkdir(parents=True, exist_ok=True)

MODALITIES = ("rna", "rppa", "metabolomics")
N_RNA_CLUSTERS = 8
RNA_FEATURES = 2_000
TOP_MARKERS_PER_CLUSTER = 15
MAX_SELECTED_FEATURES_PER_MODALITY = 120
RNA_CLUSTER_COLORS = (
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#E45756",
    "#B279A2",
    "#72B7B2",
    "#FF9DA6",
    "#9D755D",
)

collection = load_collection(ARCHIVE)
matched_models = shared_model_ids(collection, MODALITIES)
print(f"Matched RNA/RPPA/metabolomics cohort: {len(matched_models)} models")

# %% [markdown]
# ## Discover the primary groups in RNA
#
# The eight-way cut merely provides stable groups for the per-assay marker
# tests. The full Ward dendrogram, built from the 2,000 most variable RNA
# features after per-feature z-scoring, remains the primary object to inspect.
# Tissue labels appear only as post-hoc column annotations.

# %%
rna_analysis, rna_matrix = hierarchical_clustergram(
    collection.mod["rna"][matched_models].copy(),
    HierarchicalConfig(
        n_top_features=RNA_FEATURES,
        n_meta_clusters=N_RNA_CLUSTERS,
    ),
)
rna_cluster_key = rna_analysis.uns["hierarchical_clustergram"]["cluster_key"]
rna_cluster_labels = rna_analysis.obs[rna_cluster_key].astype(str)
rna_categories = sorted(rna_cluster_labels.unique(), key=int)
rna_cluster_color_map = dict(
    zip(rna_categories, RNA_CLUSTER_COLORS[: len(rna_categories)], strict=True)
)
rna_analysis.obs["rna_hierarchical_cluster"] = pd.Categorical(
    rna_cluster_labels,
    categories=rna_categories,
)
rna_analysis.uns["rna_hierarchical_cluster_colors"] = [
    rna_cluster_color_map[group] for group in rna_categories
]
rna_markers = rank_cluster_markers(
    rna_analysis,
    rna_cluster_key,
    key_added="rank_genes_groups",
)
rna_marker_clustergram = marker_clustergram(rna_analysis)

rna_labels = rna_analysis.obs[
    [
        field
        for field in (
            "OncotreeLineage",
            "OncotreePrimaryDisease",
            "OncotreeSubtype",
            "rna_hierarchical_cluster",
        )
        if field in rna_analysis.obs
    ]
].copy()
rna_labels.insert(0, "ModelID", rna_analysis.obs_names)
rna_labels.to_csv(RESULTS / "rna_primary_cluster_labels.csv", index=False)
pd.crosstab(
    rna_labels["rna_hierarchical_cluster"],
    rna_labels["OncotreeLineage"],
).to_csv(RESULTS / "rna_primary_cluster_by_lineage.csv")
rna_markers.to_parquet(RESULTS / "rna_primary_ranked_markers.parquet", index=False)

# %% [markdown]
# ## Characterize those fixed RNA groups in every assay
#
# The RNA-derived labels are copied to each native assay before calling
# rank_genes_groups. No protein or metabolite value can change a cell line's
# primary group. Each assay has its own Wilcoxon statistic and source-scale
# median effect, so the results remain interpretable in their original
# measurement units.

# %%
ranked_marker_tables: list[pd.DataFrame] = []
selected_features: dict[str, pd.DataFrame] = {}

for modality in MODALITIES:
    assay = collection.mod[modality][matched_models].copy()
    assay.obs["rna_hierarchical_cluster"] = pd.Categorical(
        rna_cluster_labels.reindex(assay.obs_names).to_numpy(),
        categories=rna_categories,
    )
    assay.uns["rna_hierarchical_cluster_colors"] = [
        rna_cluster_color_map[group] for group in rna_categories
    ]
    markers = rank_cluster_markers(
        assay,
        "rna_hierarchical_cluster",
        key_added="rank_genes_groups",
    )
    markers.insert(0, "modality", modality)
    ranked_marker_tables.append(markers)

    selected = select_ranked_features(
        markers.drop(columns="modality"),
        top_n_per_group=TOP_MARKERS_PER_CLUSTER,
        max_features=MAX_SELECTED_FEATURES_PER_MODALITY,
    )
    selected.insert(0, "modality", modality)
    selected_features[modality] = selected

ranked_markers = pd.concat(ranked_marker_tables, ignore_index=True)
marker_selected_features = pd.concat(selected_features.values(), ignore_index=True)
ranked_markers.to_parquet(RESULTS / "rna_group_ranked_markers_by_modality.parquet", index=False)
marker_selected_features.to_csv(RESULTS / "rna_group_marker_selected_features.csv", index=False)
marker_selected_features.groupby("modality").size().rename("n_selected_features").to_csv(
    RESULTS / "rna_group_marker_selected_feature_counts.csv"
)

top_markers_by_group = (
    ranked_markers.loc[
        (ranked_markers["rank"] <= 15)
        & (ranked_markers["pvals_adj"] <= 0.05)
    ]
    .sort_values(["group", "modality", "rank"])
    .groupby(["group", "modality"], observed=True)
    .head(5)
)
top_markers_by_group.to_csv(RESULTS / "top_rna_group_markers_by_modality.csv", index=False)
top_markers_by_group[
    ["group", "modality", "rank", "names", "scores", "pvals_adj", "median_delta"]
]

# %% [markdown]
# In the current archive, RNA group 2 gives a compact example of the value of
# this route. Its leading RNA markers include epithelial-junction genes such as
# `MPZL2`, `GJB3`, `PPL`, `SCEL`, and `LAMC2`, while its independent RPPA
# characterization includes the E-Cadherin, Claudin-7, alpha-Catenin, and EGFR
# targets. This broad group spans several epithelial tissues, so it is best
# read as an epithelial-state program rather than a tissue-label correction.
# The metabolite rows are retained as testable associations instead of being
# used to define that program.

# %% [markdown]
# ## Balanced explanatory stack, ordered by the RNA dendrogram
#
# Marker unions have the same cap in every assay, preventing RNA's larger
# feature space from filling the panel. The row dendrogram is newly calculated
# on those selected cross-assay dimensions. The column linkage is then replaced
# with the RNA discovery linkage, preserving the primary hierarchy used to
# assign rna_hierarchical_cluster.

# %%
marker_stack = stack_selected_features(collection, selected_features, matched_models)
marker_stack.obs["rna_hierarchical_cluster"] = pd.Categorical(
    rna_cluster_labels.reindex(marker_stack.obs_names).to_numpy(),
    categories=rna_categories,
)
marker_stack.uns["rna_hierarchical_cluster_colors"] = [
    rna_cluster_color_map[group] for group in rna_categories
]
marker_stack.var["marker_group"] = marker_stack.var["marker_group"].astype(str)

stack_col_attributes = (
    "rna_hierarchical_cluster",
    "OncotreeLineage",
    "OncotreePrimaryDisease",
    "OncotreeSubtype",
)
anchored_stack = Matrix(
    marker_stack,
    col_attr=[field for field in stack_col_attributes if field in marker_stack.obs],
    row_attr=["modality", "marker_group"],
    name="CCLE RNA-anchored multi-omic marker stack",
)
anchored_stack.norm("row", by="zscore")
anchored_stack.cluster(dist_type="euclidean", linkage_type="ward")
# Both matrices use the same complete-case ModelID order. Replacing only the
# column linkage retains a newly derived row dendrogram while making the cell
# line order and branches faithful to the RNA discovery analysis.
anchored_stack.viz["linkage"]["col"] = rna_matrix.viz["linkage"]["col"]
anchored_stack.make_viz()

marker_stack.var.to_csv(RESULTS / "rna_group_marker_stack_feature_provenance.csv")
print(marker_selected_features.groupby("modality").size())

# %% [markdown]
# ## Interactive RNA discovery tree and RNA-anchored multi-omic characterization
#
# The first widget is the RNA discovery hierarchy. The second retains that
# cell-line dendrogram while annotating its fixed groups with marker-selected
# RNA, RPPA, and metabolite rows. Switch between the modality and marker_group
# row annotations to follow which assay and RNA group supplied a displayed
# dimension.

# %%
Clustergram(matrix=rna_marker_clustergram, width=1_100, height=760)

# %%
Clustergram(matrix=anchored_stack, width=1_100, height=800)
