"""Configuration constants and string literals for Matrix module."""

from enum import Enum
from typing import Literal


# Enum definitions for better type safety and IDE support
class Axis(Enum):
    ROW = "row"
    COL = "col"


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


# Type definitions for backward compatibility
AxisType = Literal["row", "col"]
NormType = Literal["zscore", "total", "qn"]
FilterType = Literal["sum", "var", "mean", "median"]
DistanceType = Literal["cosine", "euclidean", "correlation", "manhattan"]
LinkageType = Literal["average", "single", "complete", "ward"]

# Performance configuration
CONFIG = {
    "chunk_size": 2000,
    "memory_threshold": 2e9,  # 2GB for memory mapping
    "cache_size_limit": 5,
    "large_matrix_threshold": 10000,
    "memory_warning_threshold": 50_000_000,
    "sample_hash_size": 100,
}

# Cache hierarchy for invalidation
CACHE_HIERARCHY = {
    CacheLevel.DATA.value: [CacheLevel.CLUSTERING.value, CacheLevel.VIZ.value],
    CacheLevel.CLUSTERING.value: [CacheLevel.VIZ.value],
    CacheLevel.VIZ.value: [],
}

# Metric function mappings
METRIC_FUNCTIONS = {
    Filter.SUM.value: "sum",
    Filter.VAR.value: "var",
    Filter.MEAN.value: "mean",
    Filter.MEDIAN.value: "median",
}

# Default visualization structure
DEFAULT_VIZ = {
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

# Error messages
ERRORS = {
    "no_data": "No data loaded",
    "invalid_filter": "Filter type '{}' not supported. Use: {}",
    "invalid_norm": "Normalization '{}' not supported. Use: total, zscore, qn",
    "missing_category": "Category '{}' not found in {}",
    "no_valid_features": "No valid {} features found",
    "clustering_size": "Matrix has {} columns. Use force=True to override.",
    "missing_scanpy": "scanpy required: pip install scanpy",
    "missing_metadata": "{} metadata missing for: {}...",
}
