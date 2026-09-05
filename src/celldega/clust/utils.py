"""Utility functions for Matrix operations."""

from typing import Any
import warnings

from anndata import AnnData
import numpy as np
import pandas as pd

from .constants import CONFIG, ERRORS, METRIC_FUNCTIONS


def get_data_hash(data: pd.DataFrame | None) -> int:
    """Fast hash computation for cache invalidation."""
    if data is None:
        return 0

    shape_hash = hash(data.shape)
    if data.size > CONFIG["large_matrix_threshold"]:
        # Sample-based hash for large matrices
        sample_size = min(CONFIG["sample_hash_size"], data.shape[0])
        sample_data = data.iloc[:sample_size, : min(10, data.shape[1])]
        content_hash = hash(sample_data.values.tobytes())
    else:
        content_hash = hash(data.values.tobytes())

    return hash((shape_hash, content_hash))


def validate_metadata(df: pd.DataFrame, meta_col: pd.DataFrame, meta_row: pd.DataFrame) -> None:
    """Validate metadata alignment with data."""
    missing_cols = set(df.columns) - set(meta_col.index)
    missing_rows = set(df.index) - set(meta_row.index)

    if missing_cols:
        raise ValueError(ERRORS["missing_metadata"].format("Column", list(missing_cols)[:5]))
    if missing_rows:
        raise ValueError(ERRORS["missing_metadata"].format("Row", list(missing_rows)[:5]))


def validate_metadata_types(meta_col: pd.DataFrame, meta_row: pd.DataFrame) -> None:
    """Check for mixed data types in metadata."""
    for df_name, meta_df in [("meta_col", meta_col), ("meta_row", meta_row)]:
        for col in meta_df.columns:
            dtypes = meta_df[col].dropna().apply(type).unique()
            if len(dtypes) > 1:
                warnings.warn(f"Mixed data types in {df_name}['{col}'].", UserWarning, stacklevel=2)


def compute_metric(data: pd.DataFrame | np.ndarray, metric: str, axis: int = 1) -> np.ndarray:
    """Compute specified metric along axis."""
    if metric not in METRIC_FUNCTIONS:
        raise ValueError(ERRORS["invalid_filter"].format(metric, list(METRIC_FUNCTIONS.keys())))

    if isinstance(data, pd.DataFrame):
        return getattr(data, METRIC_FUNCTIONS[metric])(axis=axis).values

    # Handle numpy array cases
    if metric == "sum":
        return np.sum(data, axis=axis)
    if metric == "var":
        return np.var(data, axis=axis)
    if metric == "mean":
        return np.mean(data, axis=axis)
    if metric == "median":
        return np.median(data, axis=axis)
    raise ValueError(f"Unsupported metric: {metric}")


def fast_cosine_distance(data: np.ndarray) -> np.ndarray:
    """Optimized cosine distance computation."""
    norms = np.linalg.norm(data, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized_data = data / norms

    similarity_matrix = np.dot(normalized_data, normalized_data.T)
    distance_matrix = 1 - similarity_matrix

    # Extract upper triangle
    n = distance_matrix.shape[0]
    indices = np.triu_indices(n, k=1)
    return distance_matrix[indices]


def zscore_normalize_inplace(data: np.ndarray, axis: int = 0) -> np.ndarray:
    """Memory-efficient in-place z-score normalization."""
    means = np.mean(data, axis=axis, keepdims=True)
    stds = np.std(data, axis=axis, keepdims=True)

    zero_std_mask = stds == 0
    if zero_std_mask.any():
        warnings.warn(
            f"Found {zero_std_mask.sum()} constant features. "
            "Replacing zero std with small value to avoid inf/NaN.",
            UserWarning,
            stacklevel=2,
        )
        stds[zero_std_mask] = 1e-10

    data -= means
    data /= stds
    return data


def compute_marker_ranks(
    adata: Any,
    groupby: str,
    rank_genes_groups_kwargs: dict[str, Any] | None = None,
    stacklevel: int = 3,
) -> pd.DataFrame | None:
    """Run ``scanpy.tl.rank_genes_groups`` and return tidy, rank-annotated results.

    Shared by ``Matrix.downsample_to``/``set_marker_ranks`` and
    ``SetCollection.calc_signature`` so marker rankings mean the same thing
    regardless of which one produced them.

    Cost is dominated by scanpy: the default ``"wilcoxon"`` test runs at roughly
    30 ms per gene on 200k cells (``"t-test"`` is about 3x faster), scaling
    linearly in genes. Restricting `adata` to the genes you actually intend to
    display is the most effective lever.

    Args:
        adata: Cell-level ``AnnData`` carrying ``groupby`` in ``obs``.
        groupby: ``obs`` column defining the groups to compare.
        rank_genes_groups_kwargs: Extra keyword arguments for
            ``scanpy.tl.rank_genes_groups``; ``method`` defaults to ``"wilcoxon"``.
        stacklevel: Warning stacklevel, so the too-few-groups warning points at
            the caller's caller rather than in here.

    Returns:
        A tidy frame with ``group``/``names``/``scores``/``logfoldchanges``/
        ``pvals``/``pvals_adj``/``rank``, or ``None`` when there are fewer than
        two groups to compare.
    """
    try:
        import scanpy as sc
    except ImportError:
        raise ImportError(ERRORS["missing_scanpy"]) from None

    if groupby not in adata.obs.columns:
        raise ValueError(f"'{groupby}' not found in obs; available: {list(adata.obs.columns)}")

    n_groups = adata.obs[groupby].astype(str).nunique()
    if n_groups < 2:
        warnings.warn(
            f"'{groupby}' has {n_groups} group(s); skipping rank_genes_groups.",
            UserWarning,
            stacklevel=stacklevel,
        )
        return None

    kwargs = dict(rank_genes_groups_kwargs or {})
    kwargs.setdefault("method", "wilcoxon")

    # A minimal shell rather than `adata.copy()`: it references X instead of
    # duplicating it, and leaves behind layers/obsm/varm/obsp, none of which
    # differential expression reads — a real saving on the several-hundred-
    # thousand-cell objects this runs against. It also absorbs scanpy's `uns`
    # side effects and keeps the categorical coercion off the caller's object.
    # `rank_genes_groups` only reads X, so sharing it is safe.
    working = AnnData(
        X=adata.X,
        obs=pd.DataFrame(
            {groupby: pd.Categorical(adata.obs[groupby].astype(str))},
            index=adata.obs_names.astype(str),
        ),
        var=pd.DataFrame(index=adata.var_names.astype(str)),
    )
    sc.tl.rank_genes_groups(working, groupby=groupby, **kwargs)

    markers = sc.get.rank_genes_groups_df(working, group=None)
    markers["group"] = markers["group"].astype(str)
    # scanpy emits each group already sorted best-first; make that explicit so
    # the ordering survives any downstream sort, merge, or serialization.
    markers["rank"] = markers.groupby("group", observed=True).cumcount()

    return markers.reset_index(drop=True)


def create_node_info_base(n_nodes: int, linkage_data: list[Any]) -> dict[str, Any]:
    """Create base node info structure."""
    linkage_array = np.array(linkage_data) if linkage_data else np.array([]).reshape(0, 4)

    return {
        "ini": list(range(n_nodes, 0, -1)),
        "clust": list(range(n_nodes)),
        "rank": list(range(n_nodes)),
        "Y": linkage_array,
    }


def add_categories_to_node_info(
    node_info: dict[str, Any], nodes: list[str], meta_df: pd.DataFrame, cats: list[str]
) -> None:
    """Add category information to node info."""
    if not cats or meta_df.empty:
        return

    valid_cats = [cat for cat in cats if cat in meta_df.columns]
    if not valid_cats:
        return

    try:
        cat_data = meta_df.reindex(nodes)[valid_cats].fillna("Unknown").astype(str)
        for idx, cat_name in enumerate(valid_cats):
            node_info[f"cat-{idx}"] = cat_data[cat_name].tolist()
    except Exception:
        pass  # Skip failed category processing


def add_mixed_attributes_to_node_info(
    node_info: dict[str, Any], nodes: list[str], meta_df: pd.DataFrame, attr: list[str]
) -> list[float | None]:
    """Add categorical and numeric attributes to node info.

    Returns a list of max absolute values for numeric attributes (``None`` for
    categorical attributes).
    """
    if not attr or meta_df.empty:
        return []

    valid_attr = [attr for attr in attr if attr in meta_df.columns]
    if not valid_attr:
        return []

    max_abs: list[float | None] = []

    try:
        attr_data = meta_df.reindex(nodes)[valid_attr]
        for idx, attr_name in enumerate(valid_attr):
            series = attr_data[attr_name]
            if pd.api.types.is_numeric_dtype(series):
                node_info[f"num-{idx}"] = series.astype(float).tolist()
                max_abs_val = float(series.abs().max())
                max_abs.append(max_abs_val)
            else:
                node_info[f"cat-{idx}"] = series.fillna("Unknown").astype(str).tolist()
                max_abs.append(None)
    except Exception:
        return []

    return max_abs
