"""
This module provides the main Matrix class for hierarchical data clustering and visualization.
"""

# Import main classes and functions
from .constants import AxisEntity, EntityType, normalize_axis_entity
from .matrix import Matrix


# Export list
__all__ = [
    "AxisEntity",
    "EntityType",
    "Matrix",
    "normalize_axis_entity",
]
