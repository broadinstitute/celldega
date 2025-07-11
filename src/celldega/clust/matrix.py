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
    AxisInput,
    AxisType,
    CacheLevel,
    Distance,
    DistanceType,
    FilterType,
    LinkageType,
    Normalization,
    NormType,
)
from .utils import (
    add_categories_to_node_info,
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
        col_cats: list[str] | None = None,
        row_cats: list[str] | None = None,
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
            col_cats: Column categories (for DataFrame input)
            row_cats: Row categories (for DataFrame input)
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
        """
        # Core data storage
        self.data: pd.DataFrame | None = None
        self.meta_col: pd.DataFrame = pd.DataFrame()
        self.meta_row: pd.DataFrame = pd.DataFrame()
        self.col_cats: list[str] = []
        self.row_cats: list[str] = []

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
                self.load_adata(data)
            else:
                self.load_df(data, meta_col, meta_row, col_cats, row_cats)

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
        return self.export_viz_json()

    def load_df(
        self,
        df: pd.DataFrame,
        meta_col: pd.DataFrame | None = None,
        meta_row: pd.DataFrame | None = None,
        col_cats: list[str] | None = None,
        row_cats: list[str] | None = None,
    ) -> None:
        """
        Load DataFrame with metadata.

        Args:
            df: Data matrix
            meta_col: Column metadata (must match df.columns)
            meta_row: Row metadata (must match df.index)
            col_cats: Column category names for viz
            row_cats: Row category names for viz
        """
        self.data = df.copy()

        self.meta_col = meta_col.copy() if meta_col is not None else pd.DataFrame(index=df.columns)
        self.meta_row = meta_row.copy() if meta_row is not None else pd.DataFrame(index=df.index)

        validate_metadata(df, self.meta_col, self.meta_row)
        validate_metadata_types(self.meta_col, self.meta_row)

        self.col_cats = col_cats or list(self.meta_col.columns)
        self.row_cats = row_cats or list(self.meta_row.columns)

        self._clustered = self.is_downsampled = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def load_adata(self, adata: AnnData) -> None:
        """
        Load AnnData object.

        Args:
            adata: AnnData object (will be transposed to genes x cells)
        """
        matrix_data = (adata.X.todense() if hasattr(adata.X, "todense") else adata.X).T

        if adata.n_obs * adata.n_vars > CONFIG["memory_warning_threshold"]:
            warnings.warn(
                f"Large matrix ({adata.n_obs} x {adata.n_vars}). Consider filtering.",
                UserWarning,
                stacklevel=2,
            )

        df = pd.DataFrame(matrix_data, index=adata.var.index, columns=adata.obs.index)
        self.load_df(
            df, adata.obs.copy(), adata.var.copy(), list(adata.obs.columns), list(adata.var.columns)
        )

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

    def downsample_to(self, category: str = "leiden", axis: AxisInput = "col") -> None:
        """
        Downsample data by aggregating categories.

        Args:
            category: Metadata column to aggregate by
            axis: Which axis to aggregate ('col'/1/COL for cells, 'row'/0/ROW for genes)

        Requires:
            scanpy for aggregation functionality
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
        adata_agg = sc.get.aggregate(adata, by=category, func="mean")

        count_col = "n_cells" if axis_enum == Axis.COL else "n_genes"
        adata_agg.obs[count_col] = adata.obs.groupby(category).size().values

        modal_cols = {
            col: adata.obs.groupby(category)[col]
            .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None)
            .values
            for col in meta_df.columns
            if col != category and col not in adata_agg.obs.columns
        }

        for col, values in modal_cols.items():
            adata_agg.obs[col] = values

        self.data = pd.DataFrame(
            adata_agg.X.T if axis_enum == Axis.COL else adata_agg.X,
            index=adata_agg.var.index if axis_enum == Axis.COL else adata_agg.obs.index,
            columns=adata_agg.obs.index if axis_enum == Axis.COL else adata_agg.var.index,
        )
        setattr(self, f"meta_{axis_enum.value}", adata_agg.obs)
        self.is_downsampled, self._clustered = True, False
        self._invalidate_cache(CacheLevel.DATA.value)

    def to_df(self) -> pd.DataFrame:
        """Return DataFrame copy of data."""
        return self.data.copy() if self.data is not None else pd.DataFrame()

    def to_adata(self) -> AnnData:
        """Convert to AnnData object."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])
        return AnnData(X=self.data.values.T, obs=self.meta_col, var=self.meta_row)

    def export_viz_json(self) -> dict[str, Any]:
        """Export visualization as JSON dict."""
        if not self._clustered:
            warnings.warn("Matrix not clustered. Call clust() first.", UserWarning, stacklevel=2)
        return self.viz.copy()

    def export_viz_json_string(self) -> str:
        """Export visualization as JSON string."""
        return json.dumps(self.export_viz_json())

    def export_viz_to_widget(self, which_viz: str = "viz") -> str:
        """Export visualization for widget."""
        return self.export_viz_json_string()

    def export_viz_parquet(self) -> dict[str, bytes]:
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
        }

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
        """
        # Ensure viz structure exists
        if "global_cat_colors" not in self.viz:
            self.viz["global_cat_colors"] = {}

        if color_mapping is None:
            # Build color mapping from all unique category values
            all_cats = set()

            for df in [self.meta_row, self.meta_col]:
                if df is not None and not df.empty:
                    for col in df.columns:
                        all_cats.update(df[col].dropna().unique())

            color_mapping = {
                str(cat): _COLOR_PALETTE[i % len(_COLOR_PALETTE)]
                for i, cat in enumerate(sorted(all_cats))
            }

        elif isinstance(color_mapping, pd.DataFrame):
            if "color" in color_mapping.columns:
                color_mapping = color_mapping["color"].to_dict()
            else:
                raise ValueError("DataFrame must have 'color' column")

        else:
            color_mapping = dict(color_mapping)

        # save the row and column categories as a list
        self.viz["row_cats"] = self.row_cats
        self.viz["col_cats"] = self.col_cats

        self.viz["global_cat_colors"].update(color_mapping)

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
        cats = self.row_cats if axis == Axis.ROW.value else self.col_cats
        linkage_data = self.viz["linkage"][axis]

        node_info = create_node_info_base(len(nodes), linkage_data)
        add_categories_to_node_info(node_info, nodes, meta_df, cats)

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

            axis_nodes.append(node)

    def _validate_clustering_size(self, force: bool = False) -> None:
        """Validate matrix size for clustering."""
        if self.data is None:
            return
        n_rows, n_cols = self.data.shape
        if n_cols > CONFIG["large_matrix_threshold"] and not force:
            raise ValueError(ERRORS["clustering_size"].format(n_cols))
        if n_rows * n_cols > CONFIG["memory_warning_threshold"]:
            warnings.warn(
                f"Large matrix ({n_rows} x {n_cols}) may cause memory issues.",
                UserWarning,
                stacklevel=2,
            )
