"""
This module provides the main Matrix class for hierarchical data clustering and visualization.
"""

# Import main classes and functions
from .constants import AxisEntity, EntityType, normalize_axis_entity
from .matrix import Matrix, marker_ranks_from_uns, marker_ranks_to_uns
from .utils import compute_marker_ranks


# Export list
__all__ = [
    "AxisEntity",
    "EntityType",
    "Matrix",
    "compute_marker_ranks",
    "marker_ranks_from_uns",
    "marker_ranks_to_uns",
    "normalize_axis_entity",
]
