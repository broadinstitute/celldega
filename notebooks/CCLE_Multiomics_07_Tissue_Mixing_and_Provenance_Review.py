# %% [markdown]
# # CCLE multi-omics: tissue mixing and provenance review
#
# The pan-CCLE map should primarily recover tissue lineage. When a recurrent
# local relationship crosses two lineages, however, it can be useful evidence
# for a shared cancer-state program, an anatomic continuum, a metastatic or
# dedifferentiated model, a provenance issue, or occasionally a label error.
# This chapter turns those cross-lineage edges into a transparent review queue.
# It is **not** an automated relabeling procedure.
#
# The analysis repeats the fixed, three-assay nearest-neighbor recurrence from
# Chapter 05 on the complete RNA/RPPA/metabolomics cohort. It reports edge
# counts *and densities*, displays the strongest three-assay relationships, and
# makes an interactive Clustergram for the selected review candidates. External
# model metadata and primary literature are required before making any identity
# claim.

# %%
from __future__ import annotations

from itertools import combinations
from pathlib import Path
import sys

from anndata import AnnData
import numpy as np
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
    shared_model_ids,
)
from notebooks.ccle_multiomics.coincidence import (
    coincident_pair_table,
    nearest_neighbor_coincidence,
)


DATA = PROJECT / "data/ccle_multiomics"
ARCHIVE = DATA / "processed/ccle_multiomics.h5mu"
RESULTS = DATA / "results/07_tissue_mixing_and_provenance_review"
RESULTS.mkdir(parents=True, exist_ok=True)

MODALITIES = ("rna", "rppa", "metabolomics")
FEATURES_PER_MODALITY = {"rna": 2_000, "rppa": 214, "metabolomics": 225}
N_NEIGHBORS = 20
MIN_COINCIDENT_MODALITIES = 2
N_PERMUTATIONS = 250
MIN_POSSIBLE_PAIRS_FOR_HIGHLIGHT = 50
N_DISPLAY_MODELS = 50

collection = load_collection(ARCHIVE)
matched_models = shared_model_ids(collection, MODALITIES)
reference = collection.mod["rna"]
print(f"Matched pan-CCLE cohort: {len(matched_models)} models")

# %% [markdown]
# ## Recurrent local relationships across three assay spaces
#
# As in Chapter 05, each assay first has its own Ward-ready feature space. The
# raw 0/1/2/3 recurrence count is intentionally retained after the local graphs
# are intersected: it means how many assays support a model pair, not a scaled
# expression value. The label-permutation null tests global recurrence only;
# the lineage labels are withheld from all graph construction.

# %%
tree_matrices: dict[str, Matrix] = {}
for modality in MODALITIES:
    _, tree_matrices[modality] = hierarchical_clustergram(
        collection.mod[modality][matched_models].copy(),
        HierarchicalConfig(
            n_top_features=FEATURES_PER_MODALITY[modality],
            n_meta_clusters=8,
        ),
    )

relationship_values = {
    modality: matrix.data.T.reindex(matched_models)
    for modality, matrix in tree_matrices.items()
}
coincidence, adjacency_by_modality, coincidence_summary, null_scores = nearest_neighbor_coincidence(
    relationship_values,
    n_neighbors=N_NEIGHBORS,
    min_modalities=MIN_COINCIDENT_MODALITIES,
    n_permutations=N_PERMUTATIONS,
    random_state=0,
)
coincidence_summary.to_csv(RESULTS / "recurrence_summary.csv", index=False)
null_scores.to_csv(RESULTS / "recurrence_null_scores.csv", index=False)
coincidence.to_parquet(RESULTS / "recurrent_neighbor_counts.parquet")
print(coincidence_summary)

# %% [markdown]
# ## Which lineage pairs recur more often than their cohort sizes predict?
#
# Raw edge counts favor lineages with many models, so each count is paired with
# the number of possible cross-lineage model pairs and an edge density. The
# table is a prioritization device rather than a significance test per tissue
# pair. It highlights shared biology for interpretation and records worth
# checking, not asserted misannotations.

# %%
annotation_columns = [
    field
    for field in ("OncotreeLineage", "OncotreePrimaryDisease", "OncotreeSubtype")
    if field in reference.obs
]
annotations = reference.obs.loc[matched_models, annotation_columns].copy()
annotations["OncotreeLineage"] = (
    annotations["OncotreeLineage"].astype("string").fillna("unknown")
)

coincident_pairs = coincident_pair_table(
    coincidence,
    adjacency_by_modality,
    min_modalities=MIN_COINCIDENT_MODALITIES,
)
for side, column in (("1", "ModelID_1"), ("2", "ModelID_2")):
    renamed = annotations.add_suffix(f"_{side}").rename_axis(column).reset_index()
    coincident_pairs = coincident_pairs.merge(renamed, on=column, how="left", validate="many_to_one")


def lineage_pair(left: object, right: object) -> str:
    """Create a stable, unordered lineage-pair label."""
    return " | ".join(sorted((str(left), str(right))))


cross_lineage_pairs = coincident_pairs.loc[
    coincident_pairs["OncotreeLineage_1"].ne(coincident_pairs["OncotreeLineage_2"])
].copy()
cross_lineage_pairs["lineage_pair"] = [
    lineage_pair(left, right)
    for left, right in zip(
        cross_lineage_pairs["OncotreeLineage_1"],
        cross_lineage_pairs["OncotreeLineage_2"],
        strict=True,
    )
]

lineage_sizes = annotations["OncotreeLineage"].value_counts().sort_index()
possible_pair_rows = [
    {
        "lineage_pair": lineage_pair(left, right),
        "n_possible_pairs": int(lineage_sizes[left] * lineage_sizes[right]),
    }
    for left, right in combinations(lineage_sizes.index, 2)
]
possible_pairs = pd.DataFrame(possible_pair_rows)
observed_pairs = (
    cross_lineage_pairs.groupby("lineage_pair", observed=True)["n_coincident_modalities"]
    .agg(
        n_recurrent_2_or_3="size",
        n_recurrent_3=lambda values: int(values.eq(3).sum()),
    )
    .reset_index()
)
lineage_pair_summary = possible_pairs.merge(
    observed_pairs,
    on="lineage_pair",
    how="left",
    validate="one_to_one",
).fillna({"n_recurrent_2_or_3": 0, "n_recurrent_3": 0})
lineage_pair_summary[["n_recurrent_2_or_3", "n_recurrent_3"]] = lineage_pair_summary[
    ["n_recurrent_2_or_3", "n_recurrent_3"]
].astype(int)
lineage_pair_summary["recurrence_density_2_or_3"] = (
    lineage_pair_summary["n_recurrent_2_or_3"] / lineage_pair_summary["n_possible_pairs"]
)
lineage_pair_summary["recurrence_density_3"] = (
    lineage_pair_summary["n_recurrent_3"] / lineage_pair_summary["n_possible_pairs"]
)
global_three_assay_density = (
    lineage_pair_summary["n_recurrent_3"].sum() / lineage_pair_summary["n_possible_pairs"].sum()
)
lineage_pair_summary["three_assay_density_enrichment"] = (
    lineage_pair_summary["recurrence_density_3"] / global_three_assay_density
)
lineage_pair_summary = lineage_pair_summary.sort_values(
    ["n_recurrent_3", "recurrence_density_3", "n_possible_pairs"],
    ascending=[False, False, False],
).reset_index(drop=True)
lineage_pair_summary.to_csv(RESULTS / "cross_lineage_recurrence.csv", index=False)

highlighted_lineage_pairs = lineage_pair_summary.loc[
    (lineage_pair_summary["n_possible_pairs"] >= MIN_POSSIBLE_PAIRS_FOR_HIGHLIGHT)
    & (lineage_pair_summary["n_recurrent_3"] > 0)
].head(8)
highlighted_lineage_pairs.to_csv(RESULTS / "highlighted_cross_lineage_pairs.csv", index=False)
highlighted_lineage_pairs  # noqa: B018 - intentional Jupyter table output

# %% [markdown]
# ## Three-assay examples and a model-level review queue
#
# A model is placed in the review queue only when it has at least ten recurrent
# relationships, at least half of them cross its annotated lineage, and at
# least one of those cross-lineage edges is supported by all three assays. That
# makes the interactive panel compact; the CSV retains every model's metrics.
# A high score indicates a review opportunity, not a wrong tissue label.

# %%
three_assay_examples = cross_lineage_pairs.loc[
    cross_lineage_pairs["n_coincident_modalities"].eq(3)
    & cross_lineage_pairs["lineage_pair"].isin(highlighted_lineage_pairs["lineage_pair"])
].copy()
three_assay_examples = three_assay_examples.merge(
    highlighted_lineage_pairs[["lineage_pair", "n_recurrent_3"]],
    on="lineage_pair",
    how="left",
    validate="many_to_one",
).sort_values(
    ["n_recurrent_3", "lineage_pair", "ModelID_1", "ModelID_2"],
    ascending=[False, True, True, True],
)
three_assay_examples.to_csv(RESULTS / "highlighted_three_assay_examples.csv", index=False)
three_assay_examples.groupby("lineage_pair", observed=True).head(3)[
    [
        "lineage_pair",
        "ModelID_1",
        "OncotreePrimaryDisease_1",
        "OncotreeSubtype_1",
        "ModelID_2",
        "OncotreePrimaryDisease_2",
        "OncotreeSubtype_2",
    ]
]

left_edges = cross_lineage_pairs[["ModelID_1", "OncotreeLineage_2", "n_coincident_modalities"]].rename(
    columns={"ModelID_1": "ModelID", "OncotreeLineage_2": "other_lineage"}
)
right_edges = cross_lineage_pairs[["ModelID_2", "OncotreeLineage_1", "n_coincident_modalities"]].rename(
    columns={"ModelID_2": "ModelID", "OncotreeLineage_1": "other_lineage"}
)
cross_edge_endpoints = pd.concat((left_edges, right_edges), ignore_index=True)
total_degree = pd.concat(
    (
        coincident_pairs[["ModelID_1"]].rename(columns={"ModelID_1": "ModelID"}),
        coincident_pairs[["ModelID_2"]].rename(columns={"ModelID_2": "ModelID"}),
    ),
    ignore_index=True,
).groupby("ModelID").size().rename("total_recurrent_degree")


def dominant_label(values: pd.Series) -> str:
    """Return a deterministic dominant partner lineage."""
    counts = values.astype(str).value_counts()
    return sorted(counts[counts.eq(counts.max())].index)[0]


cross_metrics = cross_edge_endpoints.groupby("ModelID", observed=True).agg(
    cross_lineage_degree=("other_lineage", "size"),
    cross_lineage_degree_3=("n_coincident_modalities", lambda values: int(values.eq(3).sum())),
    dominant_other_lineage=("other_lineage", dominant_label),
)
review_metrics = pd.DataFrame(index=matched_models).join(total_degree).join(cross_metrics).fillna(
    {
        "total_recurrent_degree": 0,
        "cross_lineage_degree": 0,
        "cross_lineage_degree_3": 0,
        "dominant_other_lineage": "none",
    }
)
review_metrics[["total_recurrent_degree", "cross_lineage_degree", "cross_lineage_degree_3"]] = review_metrics[
    ["total_recurrent_degree", "cross_lineage_degree", "cross_lineage_degree_3"]
].astype(int)
review_metrics["cross_lineage_fraction"] = (
    review_metrics["cross_lineage_degree"] / review_metrics["total_recurrent_degree"].replace(0, np.nan)
).fillna(0.0)
model_metadata = reference.obs.loc[
    matched_models,
    [
        field
        for field in (
            "CellLineName",
            "CCLEName",
            "OncotreeLineage",
            "OncotreePrimaryDisease",
            "OncotreeSubtype",
            "PrimaryOrMetastasis",
            "SampleCollectionSite",
        )
        if field in reference.obs
    ],
].copy()
model_metadata = model_metadata.rename_axis("ModelID")
review_metrics = review_metrics.join(model_metadata)
review_queue = review_metrics.loc[
    (review_metrics["total_recurrent_degree"] >= 10)
    & (review_metrics["cross_lineage_fraction"] >= 0.5)
    & (review_metrics["cross_lineage_degree_3"] >= 1)
].sort_values(
    ["cross_lineage_degree_3", "cross_lineage_fraction", "cross_lineage_degree"],
    ascending=False,
)
review_metrics.to_csv(RESULTS / "all_model_cross_lineage_metrics.csv")
review_queue.to_csv(RESULTS / "cross_lineage_review_queue.csv")
review_queue.head(N_DISPLAY_MODELS)

# %% [markdown]
# ## Interactive recurrence Clustergram for review candidates
#
# This panel uses the unscaled count matrix. A nonzero cell means that two
# models are local neighbors in two or three independent assay spaces. Cluster
# colors show the reference annotations, while `dominant_other_lineage` records
# the most common lineage among a selected model's recurrent cross-lineage
# partners. It is useful for choosing small sets of models to follow up with
# lineage markers, origin metadata, and external registry records.

# %%
display_models = review_queue.head(N_DISPLAY_MODELS).index
display_metadata = review_metrics.loc[display_models].copy()
display_metadata["dominant_other_lineage"] = display_metadata["dominant_other_lineage"].astype(str)
display_metadata["review_candidate"] = "cross-lineage recurrent neighbor"
model_id_labels = pd.Series(
    display_metadata.index.astype(str),
    index=display_metadata.index,
    dtype="string",
)
display_labels = display_metadata["CCLEName"].astype("string").fillna(model_id_labels)
if display_labels.duplicated().any():
    display_labels = pd.Index(
        [f"{label} ({model_id})" for label, model_id in zip(display_labels, display_metadata.index, strict=True)]
    )
else:
    display_labels = pd.Index(display_labels.astype(str))
display_metadata.index = display_labels

review_adata = AnnData(
    X=coincidence.loc[display_models, display_models].to_numpy(dtype="float32"),
    obs=display_metadata,
    var=display_metadata.copy(),
)
review_adata.obs_names = display_labels
review_adata.var_names = display_labels
for field in annotation_columns:
    color_key = f"{field}_colors"
    if color_key in reference.uns:
        review_adata.uns[color_key] = reference.uns[color_key]
review_matrix = Matrix(
    review_adata,
    col_attr=("OncotreeLineage", "OncotreePrimaryDisease", "dominant_other_lineage"),
    row_attr=("OncotreeLineage", "OncotreePrimaryDisease", "dominant_other_lineage"),
    name="CCLE recurrent cross-lineage neighborhood review",
)
review_matrix.cluster(dist_type="euclidean", linkage_type="ward")

Clustergram(matrix=review_matrix, width=1_100, height=800)
