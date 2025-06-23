"""
Optimized Matrix class with improved time and space complexity.
"""

from __future__ import annotations

import json
from typing import Any, Literal
import warnings
import weakref

from anndata import AnnData
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
from sklearn.preprocessing import QuantileTransformer


AxisType = Literal["row", "col"]
NormType = Literal["zscore", "total", "qn"]
FilterType = Literal["sum", "var", "mean", "median"]
DistanceType = Literal["cosine", "euclidean", "correlation", "manhattan"]
LinkageType = Literal["average", "single", "complete", "ward"]

# Global weak reference cache for distance matrices and computations
_distance_cache = weakref.WeakKeyDictionary()
_ranking_cache = weakref.WeakKeyDictionary()


class Matrix:
    def __init__(
        self,
        data: pd.DataFrame | AnnData | None = None,
        meta_col: pd.DataFrame | None = None,
        meta_row: pd.DataFrame | None = None,
        col_cats: list[str] | None = None,
        row_cats: list[str] | None = None,
    ):
        self.data: pd.DataFrame | None = None
        self.meta_col: pd.DataFrame = pd.DataFrame()
        self.meta_row: pd.DataFrame = pd.DataFrame()
        self.col_cats: list[str] = []
        self.row_cats: list[str] = []

        self._clustered: bool = False
        self.is_downsampled: bool = False

        # Lazy evaluation with caching
        self._dat_cache: dict[str, Any] | None = None
        self._data_hash: int | None = None
        self._dirty_flags = {"data": True, "clustering": True, "viz": True}

        self.viz: dict[str, Any] = {
            "row_nodes": [],
            "col_nodes": [],
            "mat": [],
            "linkage": {"row": [], "col": []},
            "cat_colors": {"row": {}, "col": {}},
            "matrix_colors": {"pos": "red", "neg": "blue"},
            "views": [],
            "global_cat_colors": {},
            "links": [],
        }

        if data is not None:
            (self.load_adata if isinstance(data, AnnData) else self.load_df)(
                data,
                *([] if isinstance(data, AnnData) else [meta_col, meta_row, col_cats, row_cats]),
            )

    def _get_data_hash(self) -> int:
        """Fast hash computation using shape and sample for large matrices."""
        if self.data is None:
            return 0

        shape_hash = hash(self.data.shape)
        if self.data.size > 10000:
            # Sample-based hash for large matrices
            sample_size = min(100, self.data.shape[0])
            sample_data = self.data.iloc[:sample_size, : min(10, self.data.shape[1])]
            content_hash = hash(sample_data.values.tobytes())
        else:
            content_hash = hash(self.data.values.tobytes())

        return hash((shape_hash, content_hash))

    def _invalidate_cache(self, level: str) -> None:
        """Hierarchical cache invalidation."""
        hierarchy = {"data": ["clustering", "viz"], "clustering": ["viz"], "viz": []}

        self._dirty_flags[level] = True
        for dependent in hierarchy.get(level, []):
            self._dirty_flags[dependent] = True

        if level == "data":
            self._dat_cache = None
            if self in _ranking_cache:
                del _ranking_cache[self]

    @property
    def dat(self) -> dict[str, Any]:
        """Lazy dat structure with intelligent caching."""
        current_hash = self._get_data_hash()

        if self._dat_cache is None or self._data_hash != current_hash or self._dirty_flags["data"]:
            self._dat_cache = self._build_dat_structure()
            self._data_hash = current_hash
            self._dirty_flags["data"] = False

        return self._dat_cache

    def _build_dat_structure(self) -> dict[str, Any]:
        """Optimized dat structure creation."""
        if self.data is None:
            return {
                "nodes": {"row": [], "col": []},
                "mat": np.array([]),
                "node_info": {"row": {}, "col": {}},
            }

        return {
            "nodes": {"row": list(self.data.index), "col": list(self.data.columns)},
            "mat": self.data.values,
            "node_info": {axis: self._create_node_info_optimized(axis) for axis in ["row", "col"]},
        }

    def _create_node_info_optimized(self, axis: str) -> dict[str, Any]:
        """Vectorized node info creation eliminating nested loops."""
        nodes = list(self.data.index if axis == "row" else self.data.columns)
        meta_df = self.meta_row if axis == "row" else self.meta_col
        cats = self.row_cats if axis == "row" else self.col_cats

        linkage_data = self.viz["linkage"][axis]
        linkage_array = np.array(linkage_data) if linkage_data else np.array([]).reshape(0, 4)

        node_info = {
            "ini": list(range(len(nodes), -1, -1)),
            "clust": list(range(len(nodes))),
            "rank": list(range(len(nodes))),
            "Y": linkage_array,
        }

        # Vectorized category processing - single operation
        if cats and not meta_df.empty:
            valid_cats = [cat for cat in cats if cat in meta_df.columns]
            if valid_cats:
                try:
                    cat_data = meta_df.reindex(nodes)[valid_cats].fillna("Unknown").astype(str)
                    for idx, cat_name in enumerate(valid_cats):
                        node_info[f"cat-{idx}"] = cat_data[cat_name].tolist()
                except Exception:
                    pass

        return node_info

    def load_df(self, df: pd.DataFrame, meta_col=None, meta_row=None, col_cats=None, row_cats=None):
        self.data = df.copy()

        self.meta_col, self.meta_row = map(
            lambda x, idx: x.copy() if x is not None else pd.DataFrame(index=idx),
            [meta_col, meta_row],
            [df.columns, df.index],
        )

        [
            self._validate_metadata(df, self.meta_col, self.meta_row),
            self._validate_metadata_types(self.meta_col, self.meta_row),
        ]

        self.col_cats = col_cats or list(self.meta_col.columns)
        self.row_cats = row_cats or list(self.meta_row.columns)
        self._clustered = self.is_downsampled = False
        self._invalidate_cache("data")

    def load_adata(self, adata: AnnData) -> None:
        matrix_data = (adata.X.todense() if hasattr(adata.X, "todense") else adata.X).T

        if adata.n_obs * adata.n_vars > 2_500_000_000:
            warnings.warn(
                f"Large matrix ({adata.n_obs} x {adata.n_vars}). Consider filtering.", UserWarning
            )

        df = pd.DataFrame(matrix_data, index=adata.var.index, columns=adata.obs.index)
        self.load_df(
            df, adata.obs.copy(), adata.var.copy(), list(adata.obs.columns), list(adata.var.columns)
        )

    def downsample_to(self, category: str = "leiden", axis: AxisType = "col") -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        try:
            import scanpy as sc
        except ImportError:
            raise ImportError("scanpy required: pip install scanpy")

        meta_df = self.meta_col if axis == "col" else self.meta_row
        if category not in meta_df.columns:
            raise ValueError(f"Category '{category}' not found in {list(meta_df.columns)}")

        adata = (
            self.to_adata()
            if axis == "col"
            else AnnData(X=self.data.T, obs=self.meta_row, var=self.meta_col)
        )
        adata_agg = sc.get.aggregate(adata, by=category, func="mean")

        count_col = "n_cells" if axis == "col" else "n_genes"
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
            adata_agg.X.T if axis == "col" else adata_agg.X,
            index=adata_agg.var.index if axis == "col" else adata_agg.obs.index,
            columns=adata_agg.obs.index if axis == "col" else adata_agg.var.index,
        )
        setattr(self, f"meta_{axis}", adata_agg.obs)
        self.is_downsampled, self._clustered = True, False
        self._invalidate_cache("data")

    def filter(self, axis: AxisType, by: FilterType, num: int) -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        metric_funcs = {"sum": "sum", "var": "var", "mean": "mean", "median": "median"}
        if by not in metric_funcs:
            raise ValueError(f"Filter type '{by}' not supported. Use: {list(metric_funcs.keys())}")

        axis_data = self.data if axis == "row" else self.data.T
        metric = getattr(axis_data, metric_funcs[by])(axis=1)
        top_features = metric.nlargest(num).index

        self.data = self.data.loc[top_features] if axis == "row" else self.data[top_features]
        setattr(self, f"meta_{axis}", getattr(self, f"meta_{axis}").loc[top_features])
        self._clustered = False
        self._invalidate_cache("data")

    def subset(self, axis: AxisType, by: list[str]) -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        available = set(self.data.index if axis == "row" else self.data.columns)
        valid_features = [f for f in by if f in available]

        if not valid_features:
            raise ValueError(f"No valid {axis} features found")

        self.data = self.data.loc[valid_features] if axis == "row" else self.data[valid_features]
        setattr(self, f"meta_{axis}", getattr(self, f"meta_{axis}").loc[valid_features])
        self._clustered = False
        self._invalidate_cache("data")

    def random_subsample(self, axis: AxisType, num: int, seed: int = 42) -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        np.random.seed(seed)
        features = self.data.index if axis == "row" else self.data.columns

        if num >= len(features):
            return

        sampled = np.random.choice(features, size=num, replace=False)
        self.data = self.data.loc[sampled] if axis == "row" else self.data[sampled]
        setattr(self, f"meta_{axis}", getattr(self, f"meta_{axis}").loc[sampled])
        self._clustered = False
        self._invalidate_cache("data")

    def norm(self, axis: AxisType, by: NormType) -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        if by == "total":
            axis_sum = self.data.sum(axis=1 if axis == "row" else 0)
            axis_sum = axis_sum.replace(0, 1)  # Avoid division by zero
            self.data = self.data.div(axis_sum, axis=0 if axis == "row" else 1)

        elif by == "zscore":
            # Memory-optimized z-score
            self._zscore_normalize_inplace(axis)

        elif by == "qn":
            qt = QuantileTransformer(output_distribution="uniform", random_state=42)
            if axis == "col":
                normalized_data = qt.fit_transform(self.data)
            else:
                normalized_data = qt.fit_transform(self.data.T).T

            self.data = pd.DataFrame(
                normalized_data, index=self.data.index, columns=self.data.columns
            )
        else:
            raise ValueError(f"Normalization '{by}' not supported. Use: total, zscore, qn")

        self._clustered = False
        self._invalidate_cache("data")

    def _zscore_normalize_inplace(self, axis: AxisType) -> None:
        """Memory-optimized in-place z-score normalization."""
        data_values = self.data.values.T.copy() if axis == "row" else self.data.values.copy()

        means = np.mean(data_values, axis=0, keepdims=True)
        stds = np.std(data_values, axis=0, keepdims=True)

        zero_std_mask = stds == 0
        if zero_std_mask.any():
            warnings.warn(
                f"Found {zero_std_mask.sum()} constant features. "
                "Replacing zero std with small value to avoid inf/NaN.",
                UserWarning,
                stacklevel=2,
            )
            stds[zero_std_mask] = 1e-10

        # In-place normalization
        data_values -= means
        data_values /= stds

        if axis == "row":
            self.data = pd.DataFrame(
                data_values.T, index=self.data.index, columns=self.data.columns
            )
        else:
            self.data = pd.DataFrame(data_values, index=self.data.index, columns=self.data.columns)

    def clust(
        self,
        dist_type: DistanceType = "cosine",
        linkage_type: LinkageType = "average",
        force: bool = False,
    ):
        if self.data is None:
            raise ValueError("No data loaded")

        self._validate_clustering_size(force)

        # Optimized clustering with caching
        for axis in ["row", "col"]:
            self._cluster_axis_cached(axis, dist_type, linkage_type)

        self.make_viz()
        self._clustered = True

    def _cluster_axis_cached(self, axis: AxisType, dist_type: str, linkage_type: str) -> None:
        """Cached distance computation with weak references."""
        cache_key = (axis, dist_type, self._get_data_hash())

        if self not in _distance_cache:
            _distance_cache[self] = {}

        if cache_key in _distance_cache[self]:
            distances = _distance_cache[self][cache_key]
        else:
            data = self.data.values if axis == "row" else self.data.values.T

            if data.shape[0] < 2:
                self.viz["linkage"][axis] = []
                return

            try:
                # Optimized distance calculation
                if dist_type == "cosine" and data.shape[1] > 1000:
                    distances = self._fast_cosine_distance(data)
                else:
                    distances = pdist(data, metric=dist_type)
                    np.maximum(distances, 0.0, out=distances)

                # Cache with size limit
                if len(_distance_cache[self]) < 5:
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

    def _fast_cosine_distance(self, data: np.ndarray) -> np.ndarray:
        """Optimized cosine distance using matrix multiplication."""
        norms = np.linalg.norm(data, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized_data = data / norms

        similarity_matrix = np.dot(normalized_data, normalized_data.T)
        distance_matrix = 1 - similarity_matrix

        # Extract upper triangle efficiently
        n = distance_matrix.shape[0]
        indices = np.triu_indices(n, k=1)
        return distance_matrix[indices]

    def make_viz(self) -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        # Use cached dat structure
        dat_structure = self.dat

        # Cached ranking computation
        self._update_rankings_cached()

        # Update clustering order
        for axis in ["row", "col"]:
            linkage_data = self.viz["linkage"][axis]
            if linkage_data and len(linkage_data) > 0:
                try:
                    linkage_array = np.array(linkage_data)
                    dendro = dendrogram(linkage_array, no_plot=True)
                    self.dat["node_info"][axis]["clust"] = dendro["leaves"]
                except Exception:
                    pass

        self._viz_json(dendro=self._clustered)
        self._dirty_flags["viz"] = False

    def _update_rankings_cached(self) -> None:
        """Cached ranking calculations."""
        if self in _ranking_cache and not self._dirty_flags["clustering"]:
            # Use cached rankings
            for axis, rankings in _ranking_cache[self].items():
                self.dat["node_info"][axis]["rank"] = rankings["rank"]
                self.dat["node_info"][axis]["rankvar"] = rankings["rankvar"]
            return

        matrix = self.dat["mat"]
        rankings = {}

        for axis in ["row", "col"]:
            nodes = self.dat["nodes"][axis]
            n_nodes = len(nodes)

            if n_nodes == 0 or (
                (axis == "row" and matrix.shape[0] != n_nodes)
                or (axis == "col" and matrix.shape[1] != n_nodes)
            ):
                continue

            data = matrix if axis == "row" else matrix.T

            # Vectorized ranking computation
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

        # Cache rankings
        _ranking_cache[self] = rankings
        self._dirty_flags["clustering"] = False

    def _viz_json(self, dendro: bool = True, links: bool = False) -> None:
        if not all(hasattr(self, attr) for attr in ("viz", "dat")):
            raise AttributeError("Network missing required attributes")
        if missing := {"nodes", "node_info", "mat"} - self.dat.keys():
            raise KeyError(f"Missing keys: {missing}")

        dat, viz = self.dat, self.viz

        viz["linkage"] = {axis: dat["node_info"][axis]["Y"].tolist() for axis in ("row", "col")}

        # Optimized node processing
        for axis in dat["nodes"]:
            self._process_axis_nodes_optimized(axis, dat, viz)

        if links:
            viz["links"] = [
                {
                    "source": i,
                    "target": j,
                    "value": (val := float(dat["mat"][i, j])),
                    **({} if not np.isnan(val) else {"value_orig": "NaN"}),
                }
                for i in range(len(dat["nodes"]["row"]))
                for j in range(len(dat["nodes"]["col"]))
            ]
        else:
            viz["mat"] = dat["mat"].tolist()

    def _process_axis_nodes_optimized(self, axis: str, dat: dict, viz: dict) -> None:
        """Optimized node processing with pre-computed lookups."""
        node_info = dat["node_info"][axis]
        axis_nodes = viz[f"{axis}_nodes"]
        axis_nodes.clear()

        # Pre-compute all lookups for O(1) access
        cluster_lookup = {v: k for k, v in enumerate(node_info["clust"])}
        cat_keys = [k for k in node_info if k.startswith("cat-")]

        # Pre-fetch all arrays
        ini_values = node_info.get("ini", [])
        rank_values = node_info.get("rank", [])
        rankvar_values = node_info.get("rankvar", [])
        value_values = node_info.get("value", [])
        info_values = node_info.get("info", [])

        for i, name in enumerate(dat["nodes"][axis]):
            try:
                node = {
                    "name": name,
                    "ini": ini_values[i] if i < len(ini_values) else i,
                    "clust": cluster_lookup.get(i, i),
                    "rank": rank_values[i] if i < len(rank_values) else i,
                }

                # Add optional fields efficiently
                if i < len(rankvar_values):
                    node["rankvar"] = rankvar_values[i]
                if i < len(value_values):
                    node["value"] = value_values[i]
                if i < len(info_values):
                    node["info"] = info_values[i]

                # Add categories with pre-computed lookups
                for cat_key in cat_keys:
                    cat_data = node_info.get(cat_key, [])
                    if i < len(cat_data):
                        cat_value = cat_data[i]
                        node[cat_key] = cat_value
                        base_key = cat_key.replace("-", "_")

                        # Add p-value and index efficiently
                        if (
                            pval_data := node_info.get(f"pval_{base_key}")
                        ) and cat_value in pval_data:
                            node[f"{base_key}_pval"] = pval_data[cat_value]
                        if (idx_data := node_info.get(f"{base_key}_index")) and i < len(idx_data):
                            node[f"{base_key}_index"] = idx_data[i]

                axis_nodes.append(node)

            except IndexError as e:
                raise IndexError(f"Index {i} out of bounds in {axis} node_info") from e

    def to_df(self) -> pd.DataFrame:
        return self.data.copy() if self.data is not None else pd.DataFrame()

    def to_adata(self) -> AnnData:
        if self.data is None:
            raise ValueError("No data loaded")
        return AnnData(X=self.data.values.T, obs=self.meta_col, var=self.meta_row)

    def export_viz_json(self) -> dict[str, Any]:
        if not self._clustered:
            warnings.warn("Matrix not clustered. Call clust() first.", UserWarning)
        return self.viz.copy()

    def export_viz_json_string(self) -> str:
        return json.dumps(self.export_viz_json())

    def export_viz_to_widget(self, which_viz: str = "viz") -> str:
        return self.export_viz_json_string()

    def add_category(self, axis: AxisType, name: str, data: pd.Series) -> None:
        if self.data is None:
            raise ValueError("No data loaded")

        meta_df = self.meta_col if axis == "col" else self.meta_row
        meta_df[name] = data

        cats_list = self.col_cats if axis == "col" else self.row_cats
        if name not in cats_list:
            cats_list.append(name)

        self._invalidate_cache("data")
        if self._clustered:
            self.make_viz()

    def _validate_clustering_size(self, force: bool = False) -> None:
        if self.data is None:
            return
        n_rows, n_cols = self.data.shape
        if n_cols > 10000 and not force:
            raise ValueError(f"Matrix has {n_cols} columns. Use force=True to override.")
        if n_rows * n_cols > 50_000_000:
            warnings.warn(
                f"Large matrix ({n_rows} x {n_cols}) may cause memory issues.", UserWarning
            )

    def _validate_metadata(
        self, df: pd.DataFrame, meta_col: pd.DataFrame, meta_row: pd.DataFrame
    ) -> None:
        missing_cols = set(df.columns) - set(meta_col.index)
        missing_rows = set(df.index) - set(meta_row.index)
        if missing_cols:
            raise ValueError(f"Column metadata missing: {list(missing_cols)[:5]}...")
        if missing_rows:
            raise ValueError(f"Row metadata missing: {list(missing_rows)[:5]}...")

    def _validate_metadata_types(self, meta_col: pd.DataFrame, meta_row: pd.DataFrame) -> None:
        for df_name, meta_df in [("meta_col", meta_col), ("meta_row", meta_row)]:
            for col in meta_df.columns:
                dtypes = meta_df[col].dropna().apply(type).unique()
                if len(dtypes) > 1:
                    warnings.warn(f"Mixed data types in {df_name}['{col}'].", UserWarning)


def matrix(data, filter_genes=None, norm_col="total", norm_row="zscore", **kwargs) -> Matrix:
    mat = Matrix(data)

    if filter_genes:
        mat.filter(axis="row", by="var", num=filter_genes)

    if norm_col:
        mat.norm(axis="col", by=norm_col)
    if norm_row:
        mat.norm(axis="row", by=norm_row)

    mat.clust(**kwargs)
    return mat


def hc2(df: pd.DataFrame, **kwargs) -> dict[str, Any]:
    return matrix(df, **kwargs).export_viz_json()
