"""
Optimized hierarchical clustering and visualization for high-dimensional biological data.

This module provides the main Network class for data clustering and the hc() convenience
function for quick clustering operations. Optimized for minimal time/space complexity.
"""

# Import main classes and functions
from .matrix import Matrix, hc2, matrix


# Export list
__all__ = [
    "Matrix",
    "hc2",
    "matrix",
]
