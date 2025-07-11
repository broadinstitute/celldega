"""Configuration constants and string literals for Matrix module."""

from enum import Enum
from typing import Any, Literal, Union


# Enhanced Axis enum that supports both string and numeric values
class Axis(Enum):
    ROW = "row"
    COL = "col"

    @classmethod
    def normalize(cls, axis: Union["Axis", str, int]) -> "Axis":
        """
        Convert axis input to Axis enum.

        Args:
            axis: Axis enum, string ('row', 'col'), or numeric (0, 1)

        Returns:
            Axis: Normalized Axis enum

        Examples:
            Axis.normalize(0) -> Axis.ROW
            Axis.normalize(1) -> Axis.COL
            Axis.normalize('row') -> Axis.ROW
            Axis.normalize('col') -> Axis.COL
            Axis.normalize(Axis.ROW) -> Axis.ROW
        """
        if isinstance(axis, cls):
            return axis
        if axis == 0 or axis == "row":
            return cls.ROW
        if axis == 1 or axis == "col":
            return cls.COL
        raise ValueError(f"Invalid axis: {axis}. Use 0/'row'/Axis.ROW or 1/'col'/Axis.COL")

    @property
    def numeric(self) -> int:
        """Return numeric representation (0 for ROW, 1 for COL)."""
        return 0 if self == Axis.ROW else 1

    @property
    def pandas_axis(self) -> int:
        """Return pandas axis for operations (1 for ROW operations, 0 for COL operations)."""
        return 1 if self == Axis.ROW else 0


class Normalization(Enum):
    ZSCORE = "zscore"
    TOTAL = "total"
    QN = "qn"


class Filter(Enum):
    SUM = "sum"
    VAR = "var"
    MEAN = "mean"
    MEDIAN = "median"


class Distance(Enum):
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    CORRELATION = "correlation"
    MANHATTAN = "manhattan"


class Linkage(Enum):
    AVERAGE = "average"
    SINGLE = "single"
    COMPLETE = "complete"
    WARD = "ward"


class CacheLevel(Enum):
    DATA = "data"
    CLUSTERING = "clustering"
    VIZ = "viz"


# Type definitions - now unified around the enhanced Axis enum
AxisType = Literal["row", "col"]
AxisInput = Axis | str | int  # Support enum, string, and numeric inputs
NormType = Literal["zscore", "total", "qn"]
FilterType = Literal["sum", "var", "mean", "median"]
DistanceType = Literal["cosine", "euclidean", "correlation", "manhattan"]
LinkageType = Literal["average", "single", "complete", "ward"]

_COLOR_PALETTE = [
    "#393b79",
    "#aec7e8",
    "#ff7f0e",
    "#ffbb78",
    "#98df8a",
    "#bcbd22",
    "#404040",
    "#ff9896",
    "#c5b0d5",
    "#8c5648",
    "#1f77b4",
    "#5254a3",
    "#FFDB58",
    "#c49c94",
    "#e377c2",
    "#7f7f7f",
    "#2ca02c",
    "#9467bd",
    "#dbdb8d",
    "#17becf",
    "#637939",
    "#6b6ecf",
    "#9c9ede",
    "#d62728",
    "#8ca252",
    "#8c6d31",
    "#bd9e39",
    "#e7cb94",
    "#843c39",
    "#ad494a",
    "#d6616b",
    "#7b4173",
    "#a55194",
    "#ce6dbd",
    "#de9ed6",
]


# Legacy function for backward compatibility
def normalize_axis(axis: AxisInput) -> str:
    """
    Convert axis input to standard string format.

    Args:
        axis: Axis enum, string ('row', 'col'), or numeric (0, 1)

    Returns:
        str: Normalized axis string ('row' or 'col')

    Note:
        This function is deprecated. Use Axis.normalize() instead.
    """
    return Axis.normalize(axis).value


# Performance configuration
CONFIG: dict[str, Any] = {
    "chunk_size": 2000,
    "memory_threshold": 2e9,  # 2GB for memory mapping
    "cache_size_limit": 5,
    "large_matrix_threshold": 10000,
    "memory_warning_threshold": 50_000_000,
    "sample_hash_size": 100,
}

# Cache hierarchy for invalidation
CACHE_HIERARCHY: dict[str, list[str]] = {
    CacheLevel.DATA.value: [CacheLevel.CLUSTERING.value, CacheLevel.VIZ.value],
    CacheLevel.CLUSTERING.value: [CacheLevel.VIZ.value],
    CacheLevel.VIZ.value: [],
}

# Metric function mappings
METRIC_FUNCTIONS: dict[str, str] = {
    Filter.SUM.value: "sum",
    Filter.VAR.value: "var",
    Filter.MEAN.value: "mean",
    Filter.MEDIAN.value: "median",
}

# Default visualization structure
DEFAULT_VIZ: dict[str, Any] = {
    "row_nodes": [],
    "col_nodes": [],
    "mat": [],
    "linkage": {Axis.ROW.value: [], Axis.COL.value: []},
    "cat_colors": {Axis.ROW.value: {}, Axis.COL.value: {}},
    "matrix_colors": {"pos": "red", "neg": "blue"},
    "views": [],
    "global_cat_colors": {},
    "links": [],
}

ERRORS: dict[str, str] = {
    "no_data": "No data loaded",
    "invalid_filter": "Filter type '{}' not supported. Use: {}",
    "invalid_norm": "Normalization '{}' not supported. Use: total, zscore, qn",
    "missing_category": "Category '{}' not found in {}",
    "no_valid_features": "No valid {} features found",
    "clustering_size": "Matrix has {} columns. Use force=True to override.",
    "missing_scanpy": "scanpy required: pip install scanpy",
    "missing_metadata": "{} metadata missing for: {}...",
}
