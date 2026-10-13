"""Reproducible preparation and exploration helpers for CCLE multi-omics."""

from .clustering import (
    HierarchicalConfig,
    gene_modules_from_clustergram,
    hierarchical_clustergram,
    marker_clustergram,
    marker_jaccard,
    rank_cluster_markers,
    representative_module_features,
    stack_modalities,
)
from .cst_lung_ptm import (
    CST_LUNG_PTM_FILE,
    DEFAULT_CST_LUNG_OUTPUT,
    build_cst_lung_ptm_mudata,
    read_cst_lung_ptm,
)
from .features import MODALITY_SUFFIX_SEPARATOR, split_stacked_feature_id, stacked_feature_id
from .prepare import (
    apply_modality_colors,
    build_collection,
    harmonize_annotation_colors,
    inherit_annotation_colors,
    load_collection,
    shared_model_ids,
)


__all__ = [
    "CST_LUNG_PTM_FILE",
    "DEFAULT_CST_LUNG_OUTPUT",
    "MODALITY_SUFFIX_SEPARATOR",
    "HierarchicalConfig",
    "apply_modality_colors",
    "build_collection",
    "build_cst_lung_ptm_mudata",
    "gene_modules_from_clustergram",
    "harmonize_annotation_colors",
    "hierarchical_clustergram",
    "inherit_annotation_colors",
    "load_collection",
    "marker_clustergram",
    "marker_jaccard",
    "rank_cluster_markers",
    "read_cst_lung_ptm",
    "representative_module_features",
    "shared_model_ids",
    "split_stacked_feature_id",
    "stack_modalities",
    "stacked_feature_id",
]
