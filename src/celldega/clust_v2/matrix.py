"""
Optimized Matrix class with improved maintainability and time/space complexity.
"""

from __future__ import annotations

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
    CACHE_HIERARCHY,
    CONFIG,
    DEFAULT_VIZ,
    ERRORS,
    Axis,
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


class Matrix:
    """Optimized Matrix class with improved time and space complexity."""

    def __init__(
        self,
        data: pd.DataFrame | AnnData | None = None,
        meta_col: pd.DataFrame | None = None,
        meta_row: pd.DataFrame | None = None,
        col_cats: list[str] | None = None,
        row_cats: list[str] | None = None,
    ):
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
        self._dirty_flags = dict.fromkeys(CACHE_HIERARCHY, True)

        # Visualization structure
        self.viz: dict[str, Any] = DEFAULT_VIZ.copy()

        if data is not None:
            if isinstance(data, AnnData):
                self.load_adata(data)
            else:
                self.load_df(data, meta_col, meta_row, col_cats, row_cats)

    def _invalidate_cache(self, level: str) -> None:
        """Hierarchical cache invalidation."""
        self._dirty_flags[level] = True
        for dependent in CACHE_HIERARCHY.get(level, []):
            self._dirty_flags[dependent] = True

        if level == CacheLevel.DATA.value:
            self._dat_cache = None
            if self in _ranking_cache:
                del _ranking_cache[self]

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

    def load_df(self, df: pd.DataFrame, meta_col=None, meta_row=None, col_cats=None, row_cats=None):
        """Load DataFrame with metadata."""
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
        """Load AnnData object."""
        matrix_data = (adata.X.todense() if hasattr(adata.X, "todense") else adata.X).T

        if adata.n_obs * adata.n_vars > CONFIG["memory_warning_threshold"]:
            warnings.warn(f"Large matrix ({adata.n_obs} x {adata.n_vars}). Consider filtering.")

        df = pd.DataFrame(matrix_data, index=adata.var.index, columns=adata.obs.index)
        self.load_df(
            df, adata.obs.copy(), adata.var.copy(), list(adata.obs.columns), list(adata.var.columns)
        )

    def filter(self, axis: AxisType, by: FilterType, num: int) -> None:
        """Filter features by specified metric."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        axis_data = self.data if axis == Axis.ROW.value else self.data.T
        metric = compute_metric(axis_data, by, axis=1)
        top_features = pd.Series(metric, index=axis_data.index).nlargest(num).index

        if axis == Axis.ROW.value:
            self.data = self.data.loc[top_features]
            self.meta_row = self.meta_row.loc[top_features]
        else:
            self.data = self.data[top_features]
            self.meta_col = self.meta_col.loc[top_features]

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def subset(self, axis: AxisType, by: list[str]) -> None:
        """Subset data by feature list."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        available = set(self.data.index if axis == Axis.ROW.value else self.data.columns)
        valid_features = [f for f in by if f in available]

        if not valid_features:
            raise ValueError(ERRORS["no_valid_features"].format(axis))

        if axis == Axis.ROW.value:
            self.data = self.data.loc[valid_features]
            self.meta_row = self.meta_row.loc[valid_features]
        else:
            self.data = self.data[valid_features]
            self.meta_col = self.meta_col.loc[valid_features]

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def random_subsample(self, axis: AxisType, num: int, seed: int = 42) -> None:
        """Randomly subsample features."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        features = self.data.index if axis == Axis.ROW.value else self.data.columns
        if num >= len(features):
            return

        np.random.seed(seed)
        sampled = np.random.choice(features, size=num, replace=False)

        if axis == Axis.ROW.value:
            self.data = self.data.loc[sampled]
            self.meta_row = self.meta_row.loc[sampled]
        else:
            self.data = self.data[sampled]
            self.meta_col = self.meta_col.loc[sampled]

        self._clustered = False
        self._invalidate_cache(CacheLevel.DATA.value)

    def norm(self, axis: AxisType, by: NormType) -> None:
        """Normalize data along specified axis."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        if by == Normalization.TOTAL.value:
            axis_sum = self.data.sum(axis=1 if axis == Axis.ROW.value else 0)
            axis_sum = axis_sum.replace(0, 1)  # Avoid division by zero
            self.data = self.data.div(axis_sum, axis=0 if axis == Axis.ROW.value else 1)

        elif by == Normalization.ZSCORE.value:
            data_values = (
                self.data.values.T.copy() if axis == Axis.ROW.value else self.data.values.copy()
            )
            zscore_normalize_inplace(data_values, axis=0)

            if axis == Axis.ROW.value:
                self.data = pd.DataFrame(
                    data_values.T, index=self.data.index, columns=self.data.columns
                )
            else:
                self.data = pd.DataFrame(
                    data_values, index=self.data.index, columns=self.data.columns
                )

        elif by == Normalization.QN.value:
            qt = QuantileTransformer(output_distribution="uniform", random_state=42)
            if axis == Axis.COL.value:
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
    ):
        """Perform hierarchical clustering."""
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
                warnings.warn(f"Clustering failed for {axis}: {e}")
                self.viz["linkage"][axis] = []
                return

        try:
            linkage_matrix = linkage(distances, method=linkage_type)
            self.viz["linkage"][axis] = linkage_matrix.tolist()
        except Exception as e:
            warnings.warn(f"Clustering failed for {axis}: {e}")
            self.viz["linkage"][axis] = []

    def make_viz(self) -> None:
        """Generate visualization data structure."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        # Use cached dat structure
        dat_structure = self.dat

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

    def _process_axis_nodes(self, axis: str, dat: dict, viz: dict) -> None:
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

    def downsample_to(self, category: str = "leiden", axis: AxisType = "col") -> None:
        """Downsample data by aggregating categories."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        try:
            import scanpy as sc
        except ImportError:
            raise ImportError(ERRORS["missing_scanpy"])

        meta_df = self.meta_col if axis == Axis.COL.value else self.meta_row
        if category not in meta_df.columns:
            raise ValueError(ERRORS["missing_category"].format(category, list(meta_df.columns)))

        adata = (
            self.to_adata()
            if axis == Axis.COL.value
            else AnnData(X=self.data.T, obs=self.meta_row, var=self.meta_col)
        )
        adata_agg = sc.get.aggregate(adata, by=category, func="mean")

        count_col = "n_cells" if axis == Axis.COL.value else "n_genes"
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
            adata_agg.X.T if axis == Axis.COL.value else adata_agg.X,
            index=adata_agg.var.index if axis == Axis.COL.value else adata_agg.obs.index,
            columns=adata_agg.obs.index if axis == Axis.COL.value else adata_agg.var.index,
        )
        setattr(self, f"meta_{axis}", adata_agg.obs)
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
            warnings.warn("Matrix not clustered. Call clust() first.", UserWarning)
        return self.viz.copy()

    def export_viz_json_string(self) -> str:
        """Export visualization as JSON string."""
        return json.dumps(self.export_viz_json())

    def export_viz_to_widget(self, which_viz: str = "viz") -> str:
        """Export visualization for widget."""
        return self.export_viz_json_string()

    def add_category(self, axis: AxisType, name: str, data: pd.Series) -> None:
        """Add category to metadata."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        meta_df = self.meta_col if axis == Axis.COL.value else self.meta_row
        meta_df[name] = data

        cats_list = self.col_cats if axis == Axis.COL.value else self.row_cats
        if name not in cats_list:
            cats_list.append(name)

        self._invalidate_cache(CacheLevel.DATA.value)
        if self._clustered:
            self.make_viz()

    def _validate_clustering_size(self, force: bool = False) -> None:
        """Validate matrix size for clustering."""
        if self.data is None:
            return
        n_rows, n_cols = self.data.shape
        if n_cols > CONFIG["large_matrix_threshold"] and not force:
            raise ValueError(ERRORS["clustering_size"].format(n_cols))
        if n_rows * n_cols > CONFIG["memory_warning_threshold"]:
            warnings.warn(
                f"Large matrix ({n_rows} x {n_cols}) may cause memory issues.", UserWarning
            )


def matrix(data, filter_genes=None, norm_col="total", norm_row="zscore", **kwargs) -> Matrix:
    """Create and process Matrix with defaults."""
    mat = Matrix(data)

    if filter_genes:
        mat.filter(axis=Axis.ROW.value, by="var", num=filter_genes)

    if norm_col:
        mat.norm(axis=Axis.COL.value, by=norm_col)
    if norm_row:
        mat.norm(axis=Axis.ROW.value, by=norm_row)

    mat.clust(**kwargs)
    return mat


def hc2(df: pd.DataFrame, **kwargs) -> dict[str, Any]:
    """Hierarchical clustering convenience function."""
    return matrix(df, **kwargs).export_viz_json()
