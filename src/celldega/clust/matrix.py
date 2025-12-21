from __future__ import annotations

import hashlib
import json
from typing import Any
import warnings
import weakref

from anndata import AnnData
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
from sklearn.preprocessing import QuantileTransformer

from .constants import (
    _COLOR_PALETTE,
    CACHE_HIERARCHY,
    CONFIG,
    DEFAULT_VIZ,
    ERRORS,
    Axis,
    AxisEntity,
    AxisInput,
    AxisType,
    CacheLevel,
    Distance,
    DistanceType,
    FilterType,
    LinkageType,
    Normalization,
    NormType,
    normalize_axis_entity,
)
from .utils import (
    add_mixed_attributes_to_node_info,
    compute_metric,
    create_node_info_base,
    fast_cosine_distance,
    get_data_hash,
    validate_metadata,
    validate_metadata_types,
    zscore_normalize_inplace,
)


# Global caches with size limits
_distance_cache = weakref.WeakKeyDictionary()
_ranking_cache = weakref.WeakKeyDictionary()


def quick_hash_data(data: pd.DataFrame | AnnData, max_rows=100, max_cols=100) -> str:
    try:
        if isinstance(data, pd.DataFrame):
            df = data.select_dtypes(include=[np.number])  # drop object/string columns
            row_means = df.mean(axis=1).values[:max_rows]
            col_means = df.mean(axis=0).values[:max_cols]
        elif isinstance(data, AnnData):
            import scipy.sparse

            x = data.X
            if scipy.sparse.issparse(x):
                row_means = x.mean(axis=1).A1[:max_rows]  # Use sparse matrix operations
                col_means = x.mean(axis=0).A1[:max_cols]  # Use sparse matrix operations
            else:
                x = np.asarray(x, dtype=np.float32)
                row_means = x.mean(axis=1)[:max_rows]
                col_means = x.mean(axis=0)[:max_cols]
        else:
            return f"cgm_{id(data)}"

        sig = np.concatenate([row_means, col_means])
        sig_bytes = sig.astype(np.float32).tobytes()
        return f"cgm_{hashlib.md5(sig_bytes).hexdigest()[:12]}"
    except Exception:
        return f"cgm_{id(data)}"


class Matrix:
    """
    High-performance matrix class for single-cell genomics data processing.

    Features automatic processing pipeline, hierarchical clustering, and visualization export.
    Uses intelligent caching for performance with large datasets.

    Examples:
        # Basic usage - applies norm_col='total', norm_row='zscore'
        mat = Matrix(adata)
        viz_data = mat.cluster()

        # Custom processing with colors
        mat = Matrix(adata, filter_genes=5000, norm_row='qn',
                    global_colors={"high": "red", "low": "blue"})

        # No processing
        mat = Matrix(adata, disable_processing=True)
    """

    def __init__(
        self,
        data: pd.DataFrame | AnnData | None = None,
        meta_col: pd.DataFrame | None = None,
        meta_row: pd.DataFrame | None = None,
        col_attr: list[str] | None = None,
        row_attr: list[str] | None = None,
        row_entity: str | dict | AxisEntity | None = "gene",
        col_entity: str | dict | AxisEntity | None = "cell_cluster",
        # Processing parameters
        filter_genes: int | None = None,
        norm_col: str | None = "total",
        norm_row: str | None = "zscore",
        # Control flag
        disable_processing: bool = True,
        # Visualization parameters
        global_colors: dict[str, str] | pd.DataFrame | None = None,
        name: str | None = None,
    ):
        """
        Create Matrix with automatic processing unless disabled.

        Args:
            data: DataFrame or AnnData object
            meta_col: Column metadata (for DataFrame input)
            meta_row: Row metadata (for DataFrame input)
            col_attr: Column attribute names (categorical or numeric)
            row_attr: Row attribute names (categorical or numeric)
            row_entity: Entity specification for rows. Accepted formats:
                - str: Shorthand with implicit attr mapping:
                    - "gene" → {"entity": "gene", "attr": "name"}
                    - "nbhd" → {"entity": "nbhd", "attr": "name"}
                    - "cell" → {"entity": "cell", "attr": "name"}
                    - "hextile" → {"entity": "hextile", "attr": "name"}
                    - "cell_cluster" or "cluster" → {"entity": "cell", "attr": "leiden"}
                - tuple: Compact format, e.g., ("nbhd", "name")
                - dict: Full format, e.g., {"entity": "nbhd", "attr": "name"}
            col_entity: Entity specification for columns (same formats as row_entity)
            filter_genes: Number of top variable genes to keep (None = no filtering)
            norm_col: Column normalization ('total', 'zscore', 'qn', None)
            norm_row: Row normalization ('total', 'zscore', 'qn', None)
            disable_processing: Skip automatic processing (default: False)
            global_colors: Global category color mapping (dict or DataFrame with 'color' column)
            name: Name for the matrix (default: None)

        Examples:
            # Automatic processing (recommended)
            mat = Matrix(adata)  # Applies norm_col='total', norm_row='zscore'

            # Custom processing with colors
            colors = {"Cancer": "#ff0000", "Normal": "#0000ff"}
            mat = Matrix(adata, filter_genes=5000, norm_row='qn', global_colors=colors)

            # No processing
            mat = Matrix(adata, disable_processing=True)

            # Raw matrix without data
            mat = Matrix()  # Empty matrix for manual loading

            # With entity specifications for widget interaction:
            # Genes (rows) by cell clusters (columns) - typical gene expression heatmap
            mat = Matrix(df, row_entity="gene", col_entity="cell_cluster")
            # Or equivalently with new format:
            mat = Matrix(df,
                row_entity={"entity": "gene", "attr": "name"},
                col_entity={"entity": "cell", "attr": "leiden"})

            # Neighborhoods by cell types
            mat = Matrix(df,
                row_entity={"entity": "cell", "attr": "leiden"},
                col_entity={"entity": "nbhd", "attr": "name"})
        """
        # Core data storage
        self.data: pd.DataFrame | None = None
        self.meta_col: pd.DataFrame = pd.DataFrame()
        self.meta_row: pd.DataFrame = pd.DataFrame()

        self.col_attr = col_attr or list(self.meta_col.columns)
        self.row_attr = row_attr or list(self.meta_row.columns)

        self.col_cats = [
            attr
            for attr in self.col_attr
            if attr in self.meta_col.columns
            and not pd.api.types.is_numeric_dtype(self.meta_col[attr])
        ]
        self.row_cats = [
            attr
            for attr in self.row_attr
            if attr in self.meta_row.columns
            and not pd.api.types.is_numeric_dtype(self.meta_row[attr])
        ]

        # Normalize entity specifications to the new AxisEntity format
        self.row_entity: AxisEntity = normalize_axis_entity(row_entity)
        self.col_entity: AxisEntity = normalize_axis_entity(col_entity)

        # State tracking
        self._clustered: bool = False
        self.is_downsampled: bool = False

        # Optimized caching
        self._dat_cache: dict[str, Any] | None = None
        self._data_hash: int | None = None
        self._dirty_flags: dict[str, bool] = dict.fromkeys(CACHE_HIERARCHY, True)

        # Visualization structure
        self.viz: dict[str, Any] = DEFAULT_VIZ.copy()

        # if name is None, generate a quick hash-based name from the data content
        if name is None:
            # Generate a quick hash-based name from the data content
            self._data_hash_name = quick_hash_data(data)
        else:
            self._data_hash_name = name

        # Load data and optionally apply processing
        if data is not None:
            # Step 1: Always load data
            if isinstance(data, AnnData):
                # by default no metadata should be visualized for AnnDatas
                if col_attr is None:
                    col_attr = []
                if row_attr is None:
                    row_attr = []

                self.load_adata(data, col_attr=col_attr, row_attr=row_attr)
            else:
                self.load_df(
                    data,
                    meta_col,
                    meta_row,
                    col_attr,
                    row_attr,
                )

            # Step 2: Apply processing unless disabled
            if not disable_processing:
                self.process(filter_genes=filter_genes, norm_col=norm_col, norm_row=norm_row)

        # Step 3: Always assign colors (auto-generated if not provided)
        self.set_global_cat_colors(global_colors)

    @property
    def dat(self) -> dict[str, Any]:
        """Lazy dat structure with intelligent caching."""
        current_hash = get_data_hash(self.data)

        if (
            self._dat_cache is None
            or self._data_hash != current_hash
            or self._dirty_flags[CacheLevel.DATA.value]
        ):
            self._dat_cache = self._build_dat_structure()
            self._data_hash = current_hash
            self._dirty_flags[CacheLevel.DATA.value] = False

        return self._dat_cache

    def process(
        self,
        filter_genes: int | None = None,
        norm_col: str | None = "total",
        norm_row: str | None = "zscore",
    ) -> None:
        """
        Apply processing pipeline to the matrix.

        Args:
            filter_genes: Number of top variable genes to keep
            norm_col: Column normalization method ('total', 'zscore', 'qn', None)
            norm_row: Row normalization method ('total', 'zscore', 'qn', None)

        Examples:
            mat = Matrix(adata, disable_processing=True)  # Raw data
            mat.process(filter_genes=5000, norm_row='qn')  # Custom processing
        """
        if filter_genes:
            self.filter(axis=Axis.ROW, by="var", num=filter_genes)
        if norm_col:
            self.norm(axis=Axis.COL, by=norm_col)
        if norm_row:
            self.norm(axis=Axis.ROW, by=norm_row)

    def cluster(self, **cluster_kwargs: Any) -> dict[str, Any]:
        """
        Perform clustering and return visualization data.

        Args:
            **cluster_kwargs: Clustering parameters (dist_type, linkage_type, force)

        Returns:
            dict: Visualization-ready JSON structure

        Examples:
            mat = Matrix(adata)
            viz_data = mat.cluster()  # Use defaults
            viz_data = mat.cluster(dist_type='euclidean', linkage_type='ward')
        """
        self.clust(**cluster_kwargs)

    def load_df(
        self,
        df: pd.DataFrame,
        meta_col: pd.DataFrame | None = None,
        meta_row: pd.DataFrame | None = None,
        col_attr: list[str] | None = None,
        row_attr: list[str] | None = None,
    ) -> None:
        """
        Load DataFrame with metadata.

        Args:
            df: Data matrix
            meta_col: Column metadata (must match df.columns)
            meta_row: Row metadata (must match df.index)
            col_attr: Column attribute names for viz (categorical or numeric)
            row_attr: Row attribute names for viz (categorical or numeric)
        """
        self.data = df.copy()

        self.meta_col = meta_col.copy() if meta_col is not None else pd.DataFrame(index=df.columns)
        self.meta_row = meta_row.copy() if meta_row is not None else pd.DataFrame(index=df.index)

        validate_metadata(df, self.meta_col, self.meta_row)
        validate_metadata_types(self.meta_col, self.meta_row)

        self.col_attr = list(self.meta_col.columns) if col_attr is None else col_attr
        self.row_attr = list(self.meta_row.columns) if row_attr is None else row_attr

        self.col_cats = [
            attr
            for attr in self.col_attr
            if attr in self.meta_col.columns
            and not pd.api.types.is_numeric_dtype(self.meta_col[attr])
        ]
        self.row_cats = [
            attr
            for attr in self.row_attr
            if attr in self.meta_row.columns
            and not pd.api.types.is_numeric_dtype(self.meta_row[attr])
        ]

        self._clustered = self.is_downsampled = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def load_adata(
        self, adata: AnnData, col_attr: list[str] | None = None, row_attr: list[str] | None = None
    ) -> None:
        """
        Load AnnData object.

        Args:
            adata: AnnData object (will be transposed to genes x cells)
        """
        matrix_data = (adata.X.todense() if hasattr(adata.X, "todense") else adata.X).T

        if adata.n_obs * adata.n_vars > CONFIG["matrix_cell_threshold"]:
            warnings.warn(
                f"Large matrix ({adata.n_obs} x {adata.n_vars}). Consider filtering.",
                UserWarning,
                stacklevel=2,
            )

        df = pd.DataFrame(matrix_data, index=adata.var.index, columns=adata.obs.index)

        # Copy metadata to avoid mutating the original AnnData object
        meta_col = adata.obs.copy()
        meta_row = adata.var.copy()

        # convert categorical columns to string
        for col in meta_col.select_dtypes(include=["category"]).columns:
            meta_col[col] = meta_col[col].astype(str)

        for col in meta_row.select_dtypes(include=["category"]).columns:
            meta_row[col] = meta_row[col].astype(str)

        self.load_df(
            df,
            meta_col,
            meta_row,
            col_attr,
            row_attr,
        )

        # Note: row_entity and col_entity are already set in __init__ based on user input
        # Don't overwrite them here - user may have specified entities for non-gene-expression data

    def filter(self, axis: AxisInput, by: FilterType, num: int) -> None:
        """
        Filter features by specified metric.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum (0/ROW=rows, 1/COL=columns)
            by: Metric ('var' for variance, 'mean' for mean)
            num: Number of top features to keep
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_enum = Axis.normalize(axis)
        axis_data = self.data if axis_enum == Axis.ROW else self.data.T
        metric = compute_metric(axis_data, by, axis=1)
        top_features = pd.Series(metric, index=axis_data.index).nlargest(num).index

        if axis_enum == Axis.ROW:
            self.data = self.data.loc[top_features]
            self.meta_row = self.meta_row.loc[top_features]
        else:
            self.data = self.data[top_features]
            self.meta_col = self.meta_col.loc[top_features]

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def subset(self, axis: AxisInput, by: list[str]) -> None:
        """
        Subset data by feature list.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum (0/ROW=rows, 1/COL=columns)
            by: List of feature names to keep
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_enum = Axis.normalize(axis)
        available = set(self.data.index if axis_enum == Axis.ROW else self.data.columns)
        valid_features = [f for f in by if f in available]

        if not valid_features:
            raise ValueError(ERRORS["no_valid_features"].format(axis_enum.value))

        if axis_enum == Axis.ROW:
            self.data = self.data.loc[valid_features]
            self.meta_row = self.meta_row.loc[valid_features]
        else:
            self.data = self.data[valid_features]
            self.meta_col = self.meta_col.loc[valid_features]

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def random_subsample(self, axis: AxisInput, num: int, seed: int = 42) -> None:
        """
        Randomly subsample features.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum (0/ROW=rows, 1/COL=columns)
            num: Number of features to sample
            seed: Random seed for reproducibility
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_enum = Axis.normalize(axis)
        features = self.data.index if axis_enum == Axis.ROW else self.data.columns
        if num >= len(features):
            return

        np.random.seed(seed)
        sampled = np.random.choice(features, size=num, replace=False)

        if axis_enum == Axis.ROW:
            self.data = self.data.loc[sampled]
            self.meta_row = self.meta_row.loc[sampled]
        else:
            self.data = self.data[sampled]
            self.meta_col = self.meta_col.loc[sampled]

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def norm(self, axis: AxisInput, by: NormType) -> None:
        """
        Normalize data along specified axis.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum (0/ROW=rows, 1/COL=columns)
            by: Normalization method ('total', 'zscore', 'qn')
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_enum = Axis.normalize(axis)

        if by == Normalization.TOTAL.value:
            pandas_axis = axis_enum.pandas_axis
            axis_sum = self.data.sum(axis=pandas_axis)
            axis_sum = axis_sum.replace(0, 1)  # Avoid division by zero
            div_axis = 0 if axis_enum == Axis.ROW else 1
            self.data = self.data.div(axis_sum, axis=div_axis)

        elif by == Normalization.ZSCORE.value:
            data_values = (
                self.data.values.T.copy() if axis_enum == Axis.ROW else self.data.values.copy()
            )
            zscore_normalize_inplace(data_values, axis=0)

            if axis_enum == Axis.ROW:
                self.data = pd.DataFrame(
                    data_values.T, index=self.data.index, columns=self.data.columns
                )
            else:
                self.data = pd.DataFrame(
                    data_values, index=self.data.index, columns=self.data.columns
                )

        elif by == Normalization.QN.value:
            qt = QuantileTransformer(output_distribution="uniform", random_state=42)
            if axis_enum == Axis.COL:
                normalized_data = qt.fit_transform(self.data)
            else:
                normalized_data = qt.fit_transform(self.data.T).T

            self.data = pd.DataFrame(
                normalized_data, index=self.data.index, columns=self.data.columns
            )
        else:
            raise ValueError(ERRORS["invalid_norm"])

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def clust(
        self,
        dist_type: DistanceType = "cosine",
        linkage_type: LinkageType = "average",
        force: bool = False,
    ) -> None:
        """
        Perform hierarchical clustering.

        Args:
            dist_type: Distance metric ('cosine', 'euclidean', 'correlation')
            linkage_type: Linkage method ('average', 'complete', 'ward')
            force: Override size limits for large matrices
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        self._validate_clustering_size(force)

        for axis in [Axis.ROW.value, Axis.COL.value]:
            self._cluster_axis_cached(axis, dist_type, linkage_type)

        self.make_viz()
        self._clustered = True

    def _cluster_axis_cached(self, axis: AxisType, dist_type: str, linkage_type: str) -> None:
        """Cached clustering computation."""
        cache_key = (axis, dist_type, get_data_hash(self.data))

        if self not in _distance_cache:
            _distance_cache[self] = {}

        if cache_key in _distance_cache[self]:
            distances = _distance_cache[self][cache_key]
        else:
            data = self.data.values if axis == Axis.ROW.value else self.data.values.T

            if data.shape[0] < 2:
                self.viz["linkage"][axis] = []
                return

            try:
                if dist_type == Distance.COSINE.value and data.shape[1] > 1000:
                    distances = fast_cosine_distance(data)
                else:
                    distances = pdist(data, metric=dist_type)
                    np.maximum(distances, 0.0, out=distances)

                # Cache with size limit
                if len(_distance_cache[self]) < CONFIG["cache_size_limit"]:
                    _distance_cache[self][cache_key] = distances

            except Exception as e:
                warnings.warn(f"Clustering failed for {axis}: {e}", UserWarning, stacklevel=2)
                self.viz["linkage"][axis] = []
                return

        try:
            linkage_matrix = linkage(distances, method=linkage_type)
            self.viz["linkage"][axis] = linkage_matrix.tolist()
        except Exception as e:
            warnings.warn(f"Clustering failed for {axis}: {e}", UserWarning, stacklevel=2)
            self.viz["linkage"][axis] = []

    def make_viz(self) -> None:
        """Generate visualization data structure."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        # Use cached dat structure (triggers lazy loading)
        _ = self.dat

        # Update rankings
        self._update_rankings_cached()

        # Update clustering order
        for axis in [Axis.ROW.value, Axis.COL.value]:
            linkage_data = self.viz["linkage"][axis]
            if linkage_data:
                try:
                    linkage_array = np.array(linkage_data)
                    dendro = dendrogram(linkage_array, no_plot=True)
                    self.dat["node_info"][axis]["clust"] = dendro["leaves"]
                except Exception:
                    pass

        self._viz_json(dendro=self._clustered)
        self._dirty_flags[CacheLevel.VIZ.value] = False

    def downsample_to(
        self,
        category: str = "leiden",
        axis: AxisInput = "col",
        propagate_metadata: bool | list[str] = False,
    ) -> None:
        """
        Downsample data by aggregating categories using scanpy.get.aggregate.

        Args:
            category: Metadata column to aggregate by
            axis: Which axis to aggregate ('col'/1/COL for cells, 'row'/0/ROW for genes)
            propagate_metadata: Whether to propagate other metadata columns to the
                aggregated result using the modal (most frequent) value per group.
                - False: Skip metadata propagation (fast, default)
                - True: Propagate all metadata columns (slow for large datasets)
                - list[str]: Propagate only specified columns

        Requires:
            scanpy for aggregation functionality

        Note:
            Uses scanpy.get.aggregate under the hood for fast mean aggregation.
            See: https://scanpy.readthedocs.io/en/stable/generated/scanpy.get.aggregate.html
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        try:
            import scanpy as sc
        except ImportError:
            raise ImportError(ERRORS["missing_scanpy"]) from None

        axis_enum = Axis.normalize(axis)
        meta_df = self.meta_col if axis_enum == Axis.COL else self.meta_row
        if category not in meta_df.columns:
            raise ValueError(ERRORS["missing_category"].format(category, list(meta_df.columns)))

        adata = (
            self.to_adata()
            if axis_enum == Axis.COL
            else AnnData(X=self.data.T, obs=self.meta_row, var=self.meta_col)
        )

        # Use scanpy's fast aggregate function
        adata_agg = sc.get.aggregate(adata, by=category, func="mean")
        if adata_agg.X is None and "mean" in adata_agg.layers:
            adata_agg.X = adata_agg.layers["mean"]

        # Add count column
        count_col = "n_cells" if axis_enum == Axis.COL else "n_genes"
        group_sizes = adata.obs.groupby(category, observed=True).size()
        adata_agg.obs[count_col] = group_sizes.reindex(adata_agg.obs.index).values

        # Optionally propagate metadata columns using modal values
        if propagate_metadata:
            cols_to_propagate = (
                [c for c in meta_df.columns if c != category and c not in adata_agg.obs.columns]
                if propagate_metadata is True
                else [
                    c
                    for c in propagate_metadata
                    if c in meta_df.columns and c not in adata_agg.obs.columns
                ]
            )

            if cols_to_propagate:
                # Vectorized mode computation using value_counts
                grouped = adata.obs.groupby(category, observed=True)
                for col in cols_to_propagate:
                    try:
                        # Get the most frequent value per group
                        mode_series = grouped[col].agg(
                            lambda x: x.value_counts().index[0] if len(x) > 0 else None
                        )
                        adata_agg.obs[col] = mode_series.reindex(adata_agg.obs.index).values
                    except Exception:
                        pass  # Skip columns that fail

        self.data = pd.DataFrame(
            adata_agg.X.T if axis_enum == Axis.COL else adata_agg.X,
            index=adata_agg.var.index if axis_enum == Axis.COL else adata_agg.obs.index,
            columns=adata_agg.obs.index if axis_enum == Axis.COL else adata_agg.var.index,
        )

        # Add category column to the aggregated metadata
        meta_agg = adata_agg.obs.copy()
        meta_agg[category] = meta_agg.index.astype(str)

        # Add colors from source adata if available
        color_key = f"{category}_colors"
        if color_key in adata.uns:
            src_colors = adata.uns[color_key]
            if hasattr(adata.obs[category], "cat"):
                src_categories = list(adata.obs[category].cat.categories.astype(str))
            else:
                src_categories = list(adata.obs[category].unique().astype(str))

            color_dict = {
                str(cat): src_colors[i]
                for i, cat in enumerate(src_categories)
                if i < len(src_colors)
            }
            meta_agg["color"] = [color_dict.get(str(c), "#808080") for c in meta_agg.index]

        setattr(self, f"meta_{axis_enum.value}", meta_agg)
        self.is_downsampled, self._clustered = True, False
        self._invalidate_cache(CacheLevel.DATA.value)

        # Update entity specification for the downsampled axis
        # The entity type stays the same, but the attribute changes to the aggregation category
        current_entity = self.col_entity if axis_enum == Axis.COL else self.row_entity
        new_entity: AxisEntity = {
            "entity": current_entity.get("entity", "cell"),
            "attr": category,
        }

        if axis_enum == Axis.COL:
            self.col_entity = new_entity
        else:
            self.row_entity = new_entity

    def to_df(self) -> pd.DataFrame:
        """Return DataFrame copy of data."""
        return self.data.copy() if self.data is not None else pd.DataFrame()

    def to_adata(self) -> AnnData:
        """Convert to AnnData object."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])
        return AnnData(X=self.data.values.T, obs=self.meta_col, var=self.meta_row)

    def export_viz_json(self) -> dict[str, Any]:
        """Export visualization as JSON dict.

        .. deprecated:: 0.10
           Use :meth:`export_viz_parquet` instead.
        """
        warnings.warn(
            "`export_viz_json` is deprecated and will be removed in a future "
            "release. Use `export_viz_parquet` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not self._clustered:
            warnings.warn(
                "Matrix not clustered. Call clust() first.",
                UserWarning,
                stacklevel=2,
            )
        return self.viz.copy()

    def export_viz_json_string(self) -> str:
        """Export visualization as JSON string.

        .. deprecated:: 0.10
           Use :meth:`export_viz_parquet` instead.
        """
        warnings.warn(
            "`export_viz_json_string` is deprecated and will be removed in a "
            "future release. Use `export_viz_parquet` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return json.dumps(self.export_viz_json())

    def export_viz_to_widget(self, which_viz: str = "viz") -> str:
        """Export visualization for widget.

        .. deprecated:: 0.10
           Use :class:`celldega.viz.Clustergram` with ``matrix`` instead.
        """
        warnings.warn(
            "`export_viz_to_widget` is deprecated. Instantiate `Clustergram` "
            "with `matrix` or `parquet_data` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.export_viz_json_string()

    def export_viz_parquet(self) -> dict[str, bytes | str]:
        """Export visualization using Parquet encoded tables."""
        if not self._clustered:
            warnings.warn(
                "Matrix not clustered. Call clust() first.",
                UserWarning,
                stacklevel=2,
            )

        import io

        import pyarrow as pa
        import pyarrow.parquet as pq

        def _to_bytes(df: pd.DataFrame) -> bytes:
            # Build a dtype mapping for all applicable columns
            dtype_map = {}
            for col in df.select_dtypes(include=["int64"]).columns:
                dtype_map[col] = "int32"
            for col in df.select_dtypes(include=["float64"]).columns:
                dtype_map[col] = "float32"

            # Perform a single bulk cast
            df_casted = df.astype(dtype_map, copy=False)

            # Serialize to Parquet
            buf = io.BytesIO()
            pq.write_table(pa.Table.from_pandas(df_casted), buf, compression="zstd")
            return buf.getvalue()

        viz = self.viz

        mat_df = pd.DataFrame(
            self.dat["mat"],
            index=self.dat["nodes"][Axis.ROW.value],
            columns=self.dat["nodes"][Axis.COL.value],
        ).reset_index(names="row")

        row_nodes_df = pd.DataFrame(viz.get("row_nodes", []))
        col_nodes_df = pd.DataFrame(viz.get("col_nodes", []))
        row_link_df = pd.DataFrame(viz.get("linkage", {}).get(Axis.ROW.value, []))
        col_link_df = pd.DataFrame(viz.get("linkage", {}).get(Axis.COL.value, []))

        meta_json = viz.copy()
        meta_json.pop("mat", None)
        meta_json.pop("row_nodes", None)
        meta_json.pop("col_nodes", None)
        meta_json["linkage"] = {}

        return {
            "mat": _to_bytes(mat_df),
            "row_nodes": _to_bytes(row_nodes_df),
            "col_nodes": _to_bytes(col_nodes_df),
            "row_linkage": _to_bytes(row_link_df),
            "col_linkage": _to_bytes(col_link_df),
            "meta": meta_json,
            # Entity info as dicts with entity and attr keys
            "row_entity": self.row_entity,
            "col_entity": self.col_entity,
        }

    def write_dega_files(
        self,
        path: str,
        name: str | None = None,
    ) -> None:
        """
        Write Clustergram visualization data to a DegaFiles directory.

        This creates a `cgm/` subdirectory containing the parquet files needed
        to load the Clustergram in JavaScript without a Python backend.

        Parameters
        ----------
        path : str or Path
            Path to the DegaFiles directory (the same directory used for
            Landscape and Yearbook data).
        name : str, optional
            Name for this Clustergram. If provided, files are saved to
            ``cgm/{name}/``. If None, uses the matrix's name attribute,
            or "default" if no name is set.

        Examples
        --------
        >>> mat = Matrix(adata)
        >>> mat.clust()
        >>> mat.write_dega_files("./my_dega_files", name="skin_cancer_clusters")
        >>>
        >>> # JavaScript can then load from:
        >>> # base_url + '/cgm/skin_cancer_clusters/'

        Notes
        -----
        The following files are created:
        - ``mat.parquet``: The matrix data
        - ``row_nodes.parquet``: Row node information
        - ``col_nodes.parquet``: Column node information
        - ``row_linkage.parquet``: Row dendrogram linkage
        - ``col_linkage.parquet``: Column dendrogram linkage
        - ``meta.json``: Metadata including colors and config
        """
        from pathlib import Path as PathLib

        # Determine the name for the subdirectory
        cgm_name = name or self.name or "default"

        # Create output directory
        cgm_dir = PathLib(path) / "cgm" / cgm_name
        cgm_dir.mkdir(parents=True, exist_ok=True)

        # Get parquet data
        pq_data = self.export_viz_parquet()

        # Write parquet files
        (cgm_dir / "mat.parquet").write_bytes(pq_data["mat"])
        (cgm_dir / "row_nodes.parquet").write_bytes(pq_data["row_nodes"])
        (cgm_dir / "col_nodes.parquet").write_bytes(pq_data["col_nodes"])
        (cgm_dir / "row_linkage.parquet").write_bytes(pq_data["row_linkage"])
        (cgm_dir / "col_linkage.parquet").write_bytes(pq_data["col_linkage"])

        # Write metadata JSON
        meta = pq_data["meta"].copy()
        meta["row_entity"] = pq_data["row_entity"]
        meta["col_entity"] = pq_data["col_entity"]
        (cgm_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        print(f"Clustergram data saved to {cgm_dir}")

    def add_category(self, axis: AxisInput, name: str, data: pd.Series) -> None:
        """
        Add category to metadata.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum (0/ROW=rows, 1/COL=columns)
            name: Category name
            data: Category values (must match axis length)
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_enum = Axis.normalize(axis)
        meta_df = self.meta_col if axis_enum == Axis.COL else self.meta_row
        meta_df[name] = data

        cats_list = self.col_cats if axis_enum == Axis.COL else self.row_cats
        if name not in cats_list:
            cats_list.append(name)

        self._invalidate_cache(CacheLevel.DATA.value)
        if self._clustered:
            self.make_viz()

    # =========================================================================
    # CATEGORY METHODS
    # =========================================================================

    def add_cats(self, axis: AxisInput, cat_data: dict[str, Any]) -> None:
        """
        Add multiple categories to metadata.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum
            cat_data: Dict with category name as key, values as list/Series/dict

        Examples:
            # Add multiple categories at once
            mat.add_cats('col', {
                'cell_type': ['T-cell', 'B-cell', 'NK-cell'],
                'treatment': ['control', 'treated', 'control']
            })

            # From existing metadata
            mat.add_cats('col', meta_df.to_dict('series'))
        """
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_enum = Axis.normalize(axis)
        meta_df = self.meta_col if axis_enum == Axis.COL else self.meta_row
        cats_list = self.col_cats if axis_enum == Axis.COL else self.row_cats

        for cat_name, cat_values in cat_data.items():
            # Handle different input types
            if isinstance(cat_values, dict):
                # Dict mapping feature names to values
                cat_series = pd.Series(cat_values)
                cat_series = cat_series.reindex(meta_df.index, fill_value=None)
            elif isinstance(cat_values, list):
                # List of values in same order as features
                if len(cat_values) != len(meta_df):
                    raise ValueError(
                        f"Category '{cat_name}' length ({len(cat_values)}) "
                        f"doesn't match {axis_enum.value} count ({len(meta_df)})"
                    )
                cat_series = pd.Series(cat_values, index=meta_df.index)
            elif isinstance(cat_values, pd.Series):
                # Pandas Series - reindex to match metadata
                cat_series = cat_values.reindex(meta_df.index, fill_value=None)
            else:
                raise ValueError(f"Unsupported category data type: {type(cat_values)}")

            meta_df[cat_name] = cat_series

            if cat_name not in cats_list:
                cats_list.append(cat_name)

        self._invalidate_cache(CacheLevel.DATA.value)
        if self._clustered:
            self.make_viz()

    def set_global_cat_colors(
        self, color_mapping: dict[str, str] | pd.DataFrame | None = None
    ) -> None:
        """
        Set global category color mapping that applies across all categories.

        Args:
            color_mapping: Dict mapping category values to colors,
                        DataFrame with 'color' column, or None to auto-generate

        Note:
            If metadata has a 'color' column, those colors will be used automatically.
        """
        # Ensure viz structure exists
        if "global_cat_colors" not in self.viz:
            self.viz["global_cat_colors"] = {}

        if color_mapping is None:
            # First, try to extract colors from metadata 'color' columns
            color_mapping = {}

            for meta_df, cat_list in (
                (self.meta_row, self.row_cats),
                (self.meta_col, self.col_cats),
            ):
                if meta_df is not None and not meta_df.empty:
                    # If metadata has a 'color' column, use index -> color mapping
                    if "color" in meta_df.columns:
                        for idx, color in zip(meta_df.index, meta_df["color"], strict=False):
                            color_mapping[str(idx)] = color

                    # Also check each categorical column for matching color columns
                    for cat_col in cat_list:
                        if cat_col in meta_df.columns and "color" in meta_df.columns:
                            for cat_val, color in zip(
                                meta_df[cat_col].astype(str), meta_df["color"], strict=False
                            ):
                                if cat_val not in color_mapping:
                                    color_mapping[cat_val] = color

            # Fill in missing colors with auto-generated palette
            all_cats: set[str] = set()
            for meta_df, cat_list in (
                (self.meta_row, self.row_cats),
                (self.meta_col, self.col_cats),
            ):
                if meta_df is not None and not meta_df.empty:
                    for cat_col in cat_list:
                        if cat_col in meta_df.columns:
                            all_cats.update(meta_df[cat_col].dropna().astype(str).unique().tolist())

            # Add row/col index values as potential categories (for nbhd-by-nbhd matrices)
            if self.meta_row is not None:
                all_cats.update(str(x) for x in self.meta_row.index)
            if self.meta_col is not None:
                all_cats.update(str(x) for x in self.meta_col.index)

            for i, cat in enumerate(sorted(all_cats)):
                if cat not in color_mapping:
                    color_mapping[cat] = _COLOR_PALETTE[i % len(_COLOR_PALETTE)]

        elif isinstance(color_mapping, pd.DataFrame):
            if "color" in color_mapping.columns:
                color_mapping = color_mapping["color"].to_dict()
            else:
                raise ValueError("DataFrame must have 'color' column")

        else:
            color_mapping = dict(color_mapping)

        # save the row and column categories and attributes
        self.viz["row_cats"] = self.row_cats
        self.viz["col_cats"] = self.col_cats
        self.viz["row_attr"] = self.row_attr
        self.viz["col_attr"] = self.col_attr

        self.viz["row_attr_maxabs"] = self._compute_attr_maxabs(Axis.ROW.value)
        self.viz["col_attr_maxabs"] = self._compute_attr_maxabs(Axis.COL.value)

        self.viz["global_cat_colors"].update(color_mapping)

    def _compute_attr_maxabs(self, axis: str) -> list[float | None]:
        """Return max absolute values for numeric attributes on an axis."""
        meta_df = self.meta_row if axis == Axis.ROW.value else self.meta_col
        attr = self.row_attr if axis == Axis.ROW.value else self.col_attr

        maxabs: list[float | None] = []
        for inst_attr in attr:
            if inst_attr in meta_df.columns and pd.api.types.is_numeric_dtype(meta_df[inst_attr]):
                maxabs.append(float(meta_df[inst_attr].abs().max()))
            else:
                maxabs.append(None)
        return maxabs

    def set_matrix_colors(self, pos: str = "red", neg: str = "blue") -> None:
        """
        Set matrix color scheme for positive and negative values.

        Args:
            pos: Color for positive values (hex or named color)
            neg: Color for negative values (hex or named color)

        Example:
            mat.set_matrix_colors(pos="#ff0000", neg="#0000ff")
        """
        if "matrix_colors" not in self.viz:
            self.viz["matrix_colors"] = {}
        self.viz["matrix_colors"].update({"pos": pos, "neg": neg})

    def set_cat_color(self, axis: AxisInput, cat_index: int, cat_name: str, color: str) -> None:
        """
        Set color for specific category value in a specific category column.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum
            cat_index: Category column index (1-based, like original Network)
            cat_name: Category value name to color
            color: Hex color string or named color

        Example:
            # Set color for 'Cancer' in the first column category
            mat.set_cat_color('col', 1, 'Cancer', '#ff0000')
        """
        axis_enum = Axis.normalize(axis)

        # Ensure viz structure exists
        if "cat_colors" not in self.viz:
            self.viz["cat_colors"] = {Axis.ROW.value: {}, Axis.COL.value: {}}

        axis_str = axis_enum.value
        cat_key = f"cat-{cat_index - 1}"  # Convert 1-based to 0-based

        if axis_str not in self.viz["cat_colors"]:
            self.viz["cat_colors"][axis_str] = {}
        if cat_key not in self.viz["cat_colors"][axis_str]:
            self.viz["cat_colors"][axis_str][cat_key] = {}

        self.viz["cat_colors"][axis_str][cat_key][cat_name] = color

    def set_cat_colors(
        self, axis: AxisInput, cat_index: int, color_mapping: dict[str, str]
    ) -> None:
        """
        Set colors for multiple category values in a specific category column.

        Args:
            axis: 'row'/'col', 0/1, or Axis enum
            cat_index: Category column index (1-based)
            color_mapping: Dict mapping category values to colors

        Example:
            # Set colors for multiple values in tissue type category
            mat.set_cat_colors('col', 1, {
                'Liver': '#00ff00',
                'Brain': '#ffff00',
                'Heart': '#ff00ff'
            })
        """
        for cat_name, color in color_mapping.items():
            self.set_cat_color(axis, cat_index, cat_name, color)

    ###########################################################################

    # NOTE: Internal helpers

    ###########################################################################

    def _invalidate_cache(self, level: str) -> None:
        """Hierarchical cache invalidation."""
        self._dirty_flags[level] = True
        for dependent in CACHE_HIERARCHY.get(level, []):
            self._dirty_flags[dependent] = True

        if level == CacheLevel.DATA.value:
            self._dat_cache = None
            if self in _ranking_cache:
                del _ranking_cache[self]

    def _build_dat_structure(self) -> dict[str, Any]:
        """Build dat structure efficiently."""
        if self.data is None:
            return {
                "nodes": {Axis.ROW.value: [], Axis.COL.value: []},
                "mat": np.array([]),
                "node_info": {Axis.ROW.value: {}, Axis.COL.value: {}},
            }

        return {
            "nodes": {
                Axis.ROW.value: list(self.data.index),
                Axis.COL.value: list(self.data.columns),
            },
            "mat": self.data.values,
            "node_info": {
                Axis.ROW.value: self._create_node_info(Axis.ROW.value),
                Axis.COL.value: self._create_node_info(Axis.COL.value),
            },
        }

    def _create_node_info(self, axis: str) -> dict[str, Any]:
        """Create node info for specified axis."""
        nodes = list(self.data.index if axis == Axis.ROW.value else self.data.columns)
        meta_df = self.meta_row if axis == Axis.ROW.value else self.meta_col
        attr = self.row_attr if axis == Axis.ROW.value else self.col_attr
        linkage_data = self.viz["linkage"][axis]

        node_info = create_node_info_base(len(nodes), linkage_data)
        max_abs = add_mixed_attributes_to_node_info(node_info, nodes, meta_df, attr)
        self.viz[f"{axis}_attr_maxabs"] = max_abs

        return node_info

    def _update_rankings_cached(self) -> None:
        """Update rankings with caching."""
        if self in _ranking_cache and not self._dirty_flags[CacheLevel.CLUSTERING.value]:
            # Use cached rankings
            for axis, rankings in _ranking_cache[self].items():
                self.dat["node_info"][axis]["rank"] = rankings["rank"]
                self.dat["node_info"][axis]["rankvar"] = rankings["rankvar"]
            return

        matrix = self.dat["mat"]
        rankings = {}

        for axis in [Axis.ROW.value, Axis.COL.value]:
            nodes = self.dat["nodes"][axis]
            n_nodes = len(nodes)

            if n_nodes == 0 or (
                (axis == Axis.ROW.value and matrix.shape[0] != n_nodes)
                or (axis == Axis.COL.value and matrix.shape[1] != n_nodes)
            ):
                continue

            data = matrix if axis == Axis.ROW.value else matrix.T

            # Vectorized ranking
            sum_values = np.sum(data, axis=1)
            var_values = np.var(data, axis=1)

            sum_ranks = np.empty(n_nodes, dtype=np.int32)
            var_ranks = np.empty(n_nodes, dtype=np.int32)

            sum_ranks[np.argsort(sum_values)] = np.arange(n_nodes)
            var_ranks[np.argsort(var_values)] = np.arange(n_nodes)

            rank_data = {"rank": sum_ranks.tolist(), "rankvar": var_ranks.tolist()}

            self.dat["node_info"][axis]["rank"] = rank_data["rank"]
            self.dat["node_info"][axis]["rankvar"] = rank_data["rankvar"]
            rankings[axis] = rank_data

        _ranking_cache[self] = rankings
        self._dirty_flags[CacheLevel.CLUSTERING.value] = False

    def _viz_json(self, dendro: bool = True, links: bool = False) -> None:
        """Generate visualization JSON structure."""
        dat, viz = self.dat, self.viz

        # add name
        viz["name"] = self._data_hash_name

        viz["linkage"] = {
            axis: dat["node_info"][axis]["Y"].tolist() for axis in (Axis.ROW.value, Axis.COL.value)
        }

        viz["row_attr_maxabs"] = self.viz.get("row_attr_maxabs", [])
        viz["col_attr_maxabs"] = self.viz.get("col_attr_maxabs", [])

        for axis in dat["nodes"]:
            self._process_axis_nodes(axis, dat, viz)

        if links:
            viz["links"] = [
                {
                    "source": i,
                    "target": j,
                    "value": float(dat["mat"][i, j]) if not np.isnan(dat["mat"][i, j]) else 0,
                    **({"value_orig": "NaN"} if np.isnan(dat["mat"][i, j]) else {}),
                }
                for i in range(len(dat["nodes"][Axis.ROW.value]))
                for j in range(len(dat["nodes"][Axis.COL.value]))
            ]
        else:
            viz["mat"] = dat["mat"].tolist()

    def _process_axis_nodes(self, axis: str, dat: dict[str, Any], viz: dict[str, Any]) -> None:
        """Process nodes for visualization."""
        node_info = dat["node_info"][axis]
        axis_nodes = viz[f"{axis}_nodes"]
        axis_nodes.clear()

        cluster_lookup = {v: k for k, v in enumerate(node_info["clust"])}
        cat_keys = [k for k in node_info if k.startswith("cat-")]
        num_keys = [k for k in node_info if k.startswith("num-")]

        # Pre-fetch arrays
        arrays = {
            "ini": node_info.get("ini", []),
            "rank": node_info.get("rank", []),
            "rankvar": node_info.get("rankvar", []),
        }

        for i, name in enumerate(dat["nodes"][axis]):
            node = {
                "name": name,
                "ini": arrays["ini"][i] if i < len(arrays["ini"]) else i,
                "clust": cluster_lookup.get(i, i),
                "rank": arrays["rank"][i] if i < len(arrays["rank"]) else i,
            }

            if i < len(arrays["rankvar"]):
                node["rankvar"] = arrays["rankvar"][i]

            # Add categories
            for cat_key in cat_keys:
                cat_data = node_info.get(cat_key, [])
                if i < len(cat_data):
                    node[cat_key] = cat_data[i]

            # Add numeric attributes
            for num_key in num_keys:
                num_data = node_info.get(num_key, [])
                if i < len(num_data):
                    node[num_key] = num_data[i]

            axis_nodes.append(node)

    def _validate_clustering_size(self, force: bool = False) -> None:
        """Validate matrix size for clustering."""
        if self.data is None:
            return
        n_rows, n_cols = self.data.shape
        # if n_cols > CONFIG["large_matrix_threshold"] and not force:
        #     raise ValueError(ERRORS["clustering_size"].format(n_cols))
        if n_rows * n_cols > CONFIG["matrix_cell_threshold"]:
            # raise and error if the matrix is too large
            if not force:
                raise ValueError(
                    ERRORS["clustering_size"].format(
                        n_rows, n_cols, CONFIG["matrix_cell_threshold"]
                    )
                )
            # otherwise, just warn
            warnings.warn(
                f"Large matrix ({n_rows} x {n_cols}) may cause memory issues.",
                UserWarning,
                stacklevel=2,
            )
