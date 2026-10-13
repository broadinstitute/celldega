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
from .prepare import (
    apply_modality_colors,
    build_collection,
    harmonize_annotation_colors,
    inherit_annotation_colors,
    load_collection,
    shared_model_ids,
)


__all__ = [
    "HierarchicalConfig",
    "apply_modality_colors",
    "build_collection",
    "gene_modules_from_clustergram",
    "harmonize_annotation_colors",
    "hierarchical_clustergram",
    "inherit_annotation_colors",
    "load_collection",
    "marker_clustergram",
    "marker_jaccard",
    "rank_cluster_markers",
    "representative_module_features",
    "shared_model_ids",
    "stack_modalities",
]
