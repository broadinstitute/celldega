"""
Main Network class for hierarchical clustering and visualization of high-dimensional biological data.

This module contains the core Network class that provides comprehensive functionality
for data clustering, normalization, filtering, and visualization generation.

This is part of the core module as Network is the fundamental data structure that
coordinates all other components of the clustering system.
"""

from __future__ import annotations

import contextlib
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import random
from typing import Any, Literal
import weakref

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist
from scipy.stats import mannwhitneyu, ttest_ind
from sklearn.metrics import auc, confusion_matrix, pairwise_distances, roc_curve
import statsmodels.stats.multitest as smm

from ..analysis import enrichr_functions as enr_fun
from ..categories import categories
from ..clustering import make_clust_fun
from ..data import export_data, load_data, load_vect_post
from ..preprocessing import downsample_fun, normalize_fun, run_filter
from . import data_formats, initialize_net


# Type aliases for better readability
MatrixData = np.ndarray | list[list[float]]
AxisType = Literal["row", "col"]
NormType = Literal["zscore", "qn", "umi"]
DistanceType = Literal["cosine", "euclidean", "correlation", "manhattan", "chebyshev"]
LinkageType = Literal["average", "single", "complete", "ward"]
ClusterLibrary = Literal["scipy", "hdbscan", "fastcluster"]
VizDict = dict[str, Any]
CatData = dict[str, str | dict[str, list[str]]]

# Optimized constants
_AXIS_MAP = {"row": 0, "col": 1}
_DEFAULT_CLUSTERING_PARAMS = {
    "dist_type": "cosine",
    "linkage_type": "average",
    "clust_library": "scipy",
    "min_samples": 1,
    "min_cluster_size": 2,
}

# Global cache for distance matrices to avoid memory leaks from instance methods
_distance_cache = weakref.WeakKeyDictionary()


def _compute_distance_matrix_cached(
    instance, dist_type: DistanceType, data_hash: int
) -> np.ndarray:
    """Cached distance matrix computation using global cache with weak references."""
    if instance not in _distance_cache:
        _distance_cache[instance] = {}

    cache_key = (dist_type, data_hash)
    if cache_key not in _distance_cache[instance]:
        df = instance.cached_df
        _distance_cache[instance][cache_key] = 1 - pdist(df.T, metric=dist_type)

    return _distance_cache[instance][cache_key]


class Network:
    """
    Main clustering and visualization class for high-dimensional data.

    Provides hierarchical clustering, data normalization, filtering, and visualization
    generation for biological data analysis. Supports both data and visualization states.

    Attributes:
        dat: Internal data representation with matrix and metadata
        viz: Visualization data structure for frontend rendering
        meta_cat: Whether metadata categories are present
        is_downsampled: Whether data has been downsampled
    """

    # Use __slots__ for memory efficiency while maintaining all attributes
    __slots__ = (
        "_cached_df",
        "_distance_cache",
        "col_cats",
        "dat",
        "ds_name",
        "is_downsampled",
        "meta_cat",
        "meta_col",
        "meta_ds_col",
        "meta_ds_row",
        "meta_row",
        "persistent_cat_colors",
        "row_cats",
        "sim",
        "umap",
        "viz",
        "widget_class",
        "widget_instance",
    )

    def __init__(self, widget: Any | None = None) -> None:
        """Initialize Network with optional widget integration."""
        self.dat: dict[str, Any] = {}
        self.viz: VizDict = {}
        self.meta_cat: bool = False
        self.is_downsampled: bool = False
        self._cached_df = None
        self._distance_cache = {}
        self.sim = {}
        # Conditionally initialize umap if not present
        if not hasattr(self, "umap"):
            self.umap = {"row": None, "col": None}
        initialize_net.main(self, widget)

    def reset(self) -> None:
        """Re-initialize the Network object to clean state."""
        self._cached_df = None
        self._distance_cache.clear()
        initialize_net.main(self)

    # Data Loading Methods

    def load_file(self, filename: str | Path) -> None:
        """Load data from TSV file."""
        load_data.load_file(self, filename)

    def load_file_as_string(self, file_string: str, filename: str = "") -> None:
        """Load data from string content."""
        load_data.load_file_as_string(self, file_string, filename=filename)

    def load_stdin(self) -> None:
        """Load TSV-formatted data from standard input."""
        load_data.load_stdin(self)

    def load_tsv_to_net(self, file_buffer: Any, filename: str | None = None) -> None:
        """Load TSV data from file buffer."""
        load_data.load_tsv_to_net(self, file_buffer, filename)

    def load_vect_post_to_net(self, vect_post: dict[str, Any]) -> None:
        """Load data in vector format JSON."""
        load_vect_post.main(self, vect_post)

    def load_data_file_to_net(self, filename: str | Path) -> None:
        """Load Clustergrammer's internal data format."""
        inst_dat = self.load_json_to_dict(filename)
        load_data.load_data_to_net(self, inst_dat)

    def load_df(
        self,
        df_ini: pd.DataFrame,
        meta_col: pd.DataFrame | None = None,
        meta_row: pd.DataFrame | None = None,
        col_cats: list[str] | None = None,
        row_cats: list[str] | None = None,
        is_downsampled: bool = False,
        meta_ds_row: pd.DataFrame | None = None,
        meta_ds_col: pd.DataFrame | None = None,
    ) -> None:
        """
        Load DataFrame with optional metadata.

        Args:
            df_ini: Input DataFrame
            meta_col: Column metadata DataFrame
            meta_row: Row metadata DataFrame
            col_cats: Column category names
            row_cats: Row category names
            is_downsampled: Whether data is downsampled
            meta_ds_row: Downsampled row metadata
            meta_ds_col: Downsampled column metadata
        """
        self.reset()
        df = deepcopy(df_ini)

        self.is_downsampled = is_downsampled
        if is_downsampled:
            if meta_ds_col is not None:
                self.meta_ds_col = meta_ds_col
            if meta_ds_row is not None:
                self.meta_ds_row = meta_ds_row

        self._setup_metadata_flags()
        self._load_metadata(meta_col, meta_row, col_cats, row_cats)
        data_formats.df_to_dat(self, df, define_cat_colors=True)

    def _setup_metadata_flags(self) -> None:
        """Initialize metadata flags if not present."""
        if not hasattr(self, "meta_col") and not hasattr(self, "meta_row"):
            self.meta_cat = False

    def _load_metadata(
        self,
        meta_col: pd.DataFrame | None,
        meta_row: pd.DataFrame | None,
        col_cats: list[str] | None,
        row_cats: list[str] | None,
    ) -> None:
        """Load column and row metadata if provided."""
        if isinstance(meta_col, pd.DataFrame):
            self.meta_col = meta_col
            self.col_cats = meta_col.columns.tolist() if col_cats is None else col_cats
            self.meta_cat = True

        if isinstance(meta_row, pd.DataFrame):
            self.meta_row = meta_row
            self.row_cats = meta_row.columns.tolist() if row_cats is None else row_cats
            self.meta_cat = True

    @property
    def cached_df(self) -> pd.DataFrame:
        """Lazy-loaded cached DataFrame to avoid redundant conversions."""
        if self._cached_df is None:
            self._cached_df = data_formats.dat_to_df(self)
            if self.is_downsampled:
                self._cached_df.columns = self.dat["nodes"]["col"]
                self._cached_df.index = self.dat["nodes"]["row"]
        return self._cached_df

    def export_df(self) -> pd.DataFrame:
        """Export internal data as pandas DataFrame."""
        return self.cached_df.copy()

    # Clustering Methods

    def cluster(
        self,
        dist_type: DistanceType = "cosine",
        run_clustering: bool = True,
        dendro: bool = True,
        views: list[str] | None = None,
        linkage_type: LinkageType = "average",
        sim_mat: bool | str = False,
        filter_sim: float = 0.0,
        calc_cat_pval: bool = False,
        run_enrichr: str | None = None,
        enrichrgram: bool | None = None,
        clust_library: ClusterLibrary = "scipy",
        min_samples: int = 1,
        min_cluster_size: int = 2,
    ) -> None:
        """
        Perform hierarchical clustering and generate visualization.

        Args:
            dist_type: Distance metric for clustering
            run_clustering: Whether to perform actual clustering
            dendro: Whether to generate dendrogram
            views: List of view types to generate
            linkage_type: Hierarchical clustering linkage method
            sim_mat: Generate similarity matrices (bool or "row"/"col")
            filter_sim: Similarity filtering threshold
            calc_cat_pval: Calculate category p-values
            run_enrichr: Enrichr library for gene enrichment
            enrichrgram: Enable enrichrgram visualization
            clust_library: Clustering library to use
            min_samples: Minimum samples for HDBSCAN
            min_cluster_size: Minimum cluster size for HDBSCAN
        """
        if views is None:
            views = []

        self._cached_df = None  # Invalidate cache
        initialize_net.viz(self)
        make_clust_fun.make_clust(
            self,
            dist_type=dist_type,
            run_clustering=run_clustering,
            dendro=dendro,
            requested_views=views,
            linkage_type=linkage_type,
            sim_mat=sim_mat,
            filter_sim=filter_sim,
            calc_cat_pval=calc_cat_pval,
            run_enrichr=run_enrichr,
            enrichrgram=enrichrgram,
            clust_library=clust_library,
            min_samples=min_samples,
            min_cluster_size=min_cluster_size,
        )

    # Data Processing Methods

    def swap_nan_for_zero(self) -> None:
        """Replace all NaN values with zeros in the data matrix."""
        self.dat["mat"][np.isnan(self.dat["mat"])] = 0
        self._cached_df = None

    def normalize(
        self,
        df: pd.DataFrame | None = None,
        norm_type: NormType = "zscore",
        axis: AxisType = "row",
        z_clip: float | None = None,
    ) -> None:
        """
        Normalize matrix data.

        Args:
            df: Optional DataFrame to normalize (uses internal data if None)
            norm_type: Normalization method
            axis: Axis to normalize along
            z_clip: Z-score clipping threshold
        """
        self._cached_df = None
        normalize_fun.run_norm(self, df, norm_type, axis, z_clip)

    def clip(self, lower: float | None = None, upper: float | None = None) -> None:
        """Clip values to specified thresholds."""
        df = self.export_df()
        df = df.clip(lower=lower, upper=upper)
        self._cached_df = None
        self.load_df(df)

    # Filtering Methods

    def filter_sum(
        self,
        threshold: float,
        take_abs: bool = True,
        axis: AxisType | None = None,
        inst_rc: AxisType | None = None,
    ) -> None:
        """Filter based on sum threshold across axis."""
        axis = self._resolve_axis(axis, inst_rc)
        inst_df = self.dat_to_df()

        if axis == "row":
            inst_df = run_filter.df_filter_row_sum(inst_df, threshold, take_abs)
        elif axis == "col":
            inst_df = run_filter.df_filter_col_sum(inst_df, threshold, take_abs)

        self._cached_df = None
        self.df_to_dat(inst_df)

    def filter_n_top(
        self,
        n_top: int,
        rank_type: Literal["sum", "var"] = "sum",
        inst_rc: AxisType | None = None,
        axis: AxisType | None = None,
    ) -> None:
        """Keep only top N features by ranking metric."""
        axis = self._resolve_axis(axis, inst_rc)
        inst_df = self.dat_to_df()
        inst_df = run_filter.filter_n_top(axis, inst_df, n_top, rank_type)
        self._cached_df = None
        self.df_to_dat(inst_df)

    def filter_threshold(
        self,
        threshold: float,
        num_occur: int = 1,
        inst_rc: AxisType | None = None,
        axis: AxisType | None = None,
    ) -> None:
        """Filter based on number of values above threshold."""
        axis = self._resolve_axis(axis, inst_rc)
        inst_df = self.dat_to_df()
        inst_df = run_filter.filter_threshold(inst_df, axis, threshold, num_occur)
        self._cached_df = None
        self.df_to_dat(inst_df)

    def filter_cat(self, axis: AxisType, cat_index: int, cat_name: str) -> None:
        """Filter by category membership."""
        run_filter.filter_cat(self, axis, cat_index, cat_name)
        self._cached_df = None

    def filter_names(self, axis: AxisType, names: list[str]) -> None:
        """Filter by specific feature names."""
        run_filter.filter_names(self, axis, names)
        self._cached_df = None

    def _resolve_axis(self, axis: AxisType | None, inst_rc: AxisType | None) -> AxisType:
        """Resolve axis parameter with backward compatibility."""
        resolved_axis = axis or inst_rc
        if resolved_axis is None:
            raise ValueError("Must provide axis argument")
        return resolved_axis

    # Downsampling Methods

    def downsample(
        self,
        df: pd.DataFrame | None = None,
        ds_type: str = "kmeans",
        axis: AxisType = "row",
        num_samples: int = 100,
        random_state: int = 1000,
        ds_name: str = "Downsample",
        ds_cluster_name: str = "cluster",
    ) -> pd.Series | None:
        """Downsample data using clustering."""
        self._cached_df = None
        return downsample_fun.main(
            self, df, ds_type, axis, num_samples, random_state, ds_name, ds_cluster_name
        )

    def random_sample(
        self,
        num_samples: int,
        df: pd.DataFrame | None = None,
        replace: bool = False,
        weights: np.ndarray | None = None,
        random_state: int = 100,
        axis: AxisType = "row",
    ) -> None:
        """Random sample from matrix."""
        if df is None:
            df = self.dat_to_df()

        axis_int = 0 if axis == "row" else 1
        df = self.export_df()
        df = df.sample(
            n=num_samples,
            replace=replace,
            weights=weights,
            random_state=random_state,
            axis=axis_int,
        )
        self._cached_df = None
        self.load_df(df)

    # Category Methods

    def add_cats(self, axis: AxisType, cat_data: CatData) -> None:
        """Add categories to features."""
        categories.add_cats(self, axis, cat_data)
        self._cached_df = None

    def set_matrix_colors(self, pos: str = "red", neg: str = "blue") -> None:
        """Set matrix color scheme."""
        self.viz["matrix_colors"] = {"pos": pos, "neg": neg}

    def set_global_cat_colors(self, df_meta: pd.DataFrame) -> None:
        """Set global category color mapping."""
        color_mapping = {name: df_meta.loc[name, "color"] for name in df_meta.index.tolist()}
        self.viz["global_cat_colors"].update(color_mapping)

    def set_cat_color(
        self, axis: int | AxisType, cat_index: int, cat_name: str, inst_color: str
    ) -> None:
        """Set color for specific category."""
        # Convert numeric axis to string
        axis_str = {0: "row", 1: "col"}.get(axis, axis)

        with contextlib.suppress(KeyError, TypeError, IndexError):
            cat_key = f"cat-{cat_index - 1}"
            self.viz["cat_colors"][axis_str][cat_key][cat_name] = inst_color

    # Export Methods

    def export_net_json(self, net_type: str = "viz", indent: str = "no-indent") -> str:
        """Export network data as JSON string."""
        return export_data.export_net_json(self, net_type, indent)

    def export_viz_to_widget(self, which_viz: str = "viz") -> str:
        """Export visualization JSON for widget use."""
        return export_data.export_net_json(self, which_viz, "no-indent")

    def write_json_to_file(
        self, net_type: str, filename: str | Path, indent: str = "no-indent"
    ) -> None:
        """Save network data as JSON file."""
        export_data.write_json_to_file(self, net_type, filename, indent)

    def write_matrix_to_tsv(
        self, filename: str | Path | None = None, df: pd.DataFrame | None = None
    ) -> str:
        """Export data matrix to TSV file."""
        return export_data.write_matrix_to_tsv(self, filename, df)

    # Widget Methods

    def widget(
        self,
        which_viz: str = "viz",
        link_net: Network | None = None,
        link_net_js: Network | None = None,
        clust_library: ClusterLibrary = "scipy",
        min_samples: int = 1,
        min_cluster_size: int = 2,
    ) -> Any:
        """Generate widget visualization."""
        self._ensure_clustered(clust_library, min_samples, min_cluster_size)
        self._validate_widget_class()

        widget_instance = self.widget_class(network=self.export_viz_to_widget(which_viz))

        self._setup_manual_category(widget_instance)
        self._setup_widget_links(widget_instance, link_net, link_net_js)

        self.widget_instance = widget_instance
        return widget_instance

    def _ensure_clustered(
        self, clust_library: ClusterLibrary, min_samples: int, min_cluster_size: int
    ) -> None:
        """Ensure clustering is performed before widget creation."""
        if len(self.viz["row_nodes"]) == 0:
            self.cluster(
                clust_library=clust_library,
                min_samples=min_samples,
                min_cluster_size=min_cluster_size,
            )

            # Transfer additional data to viz
            if "manual_category" in self.dat:
                self.viz["manual_category"] = self.dat["manual_category"]
            if "pre_zscore" in self.dat:
                self.viz["pre_zscore"] = self.dat["pre_zscore"]

    def _validate_widget_class(self) -> None:
        """Validate widget class is available."""
        if not hasattr(self, "widget_class"):
            raise AttributeError(
                "Network has no widget_class. Initialize with Network(widget_instance)"
            )

    def _setup_manual_category(self, widget_instance: Any) -> None:
        """Setup manual category for widget."""
        if "manual_category" not in self.dat:
            return

        manual_cat = {"col": {"col_cat_colors": self.viz["cat_colors"]["col"]["cat-0"]}}
        man_cat_name = self.dat["manual_category"]["col"]
        manual_cat["col"][man_cat_name] = self.meta_col[man_cat_name].to_dict()

        widget_instance.manual_cat = json.dumps(manual_cat)
        widget_instance.observe(self.get_manual_category, names="manual_cat")

    def _setup_widget_links(
        self, widget_instance: Any, link_net: Network | None, link_net_js: Network | None
    ) -> None:
        """Setup widget links to other networks."""
        if link_net is not None:
            widget_instance.link = widgets.link(
                (widget_instance, "manual_cat"), (link_net.widget_instance, "manual_cat")
            )

        if link_net_js is not None:
            widget_instance.link = widgets.jslink(
                (widget_instance, "manual_cat"), (link_net_js.widget_instance, "manual_cat")
            )

    def widget_df(self) -> pd.DataFrame | None:
        """Export DataFrame from widget visualization."""
        if hasattr(self, "widget_instance"):
            if self.widget_instance.mat_string != "":
                tmp_net = deepcopy(Network())
                tmp_net.load_file_as_string(self.widget_instance.mat_string)
                return tmp_net.export_df()
            return self.export_df()

        if hasattr(self, "widget_class"):
            print("Please make the widget before exporting the widget DataFrame.")
            print("Do this using the widget method: net.widget()")
            return None

        print("Can not make widget because Network has no attribute widget_class")
        print(
            "Please instantiate Network with clustergrammer_widget using: Network(clustergrammer_widget)"
        )
        return None

    # Visualization and Analysis Methods

    def enrichrgram(self, lib: str, axis: AxisType = "row") -> None:
        """Add Enrichr gene enrichment results."""
        df = self.export_df()
        df, bar_info = enr_fun.add_enrichr_cats(df, axis, lib)
        self._cached_df = None
        self.load_df(df)
        self.dat["enrichrgram_lib"] = lib
        self.dat["row_cat_bars"] = bar_info

    # Statistical Analysis Methods

    def _compute_distance_matrix(self, dist_type: DistanceType, data_hash: int) -> np.ndarray:
        """Compute distance matrix using global cache to avoid memory leaks."""
        return _compute_distance_matrix_cached(self, dist_type, data_hash)

    def sim_same_and_diff_category_samples(
        self,
        df: pd.DataFrame,
        cat_index: int = 1,
        dist_type: DistanceType = "cosine",
        equal_var: bool = False,
        plot_roc: bool = True,
        precalc_dist: bool | np.ndarray = False,
        calc_roc: bool = True,
    ) -> dict[str, Any]:
        """Calculate similarity within and between categories."""
        cols = df.columns.tolist()

        dist_arr = (
            1 - pdist(df.transpose(), metric=dist_type)
            if isinstance(precalc_dist, bool)
            else precalc_dist
        )

        sample_combos = list(combinations(range(df.shape[1]), 2))
        sample_names = [
            f"{ind}_same" if cols[x[0]][cat_index] == cols[x[1]][cat_index] else f"{ind}_different"
            for ind, x in enumerate(sample_combos)
        ]

        ser_dist = pd.Series(data=dist_arr, index=sample_names)

        # Separate same vs different category comparisons
        same_cat = [x for x in sample_names if x.split("_")[1] == "same"]
        diff_cat = [x for x in sample_names if x.split("_")[1] == "different"]

        ser_same = ser_dist[same_cat]
        ser_same.name = "Same Category"
        ser_diff = ser_dist[diff_cat]
        ser_diff.name = "Different Category"

        sim_dict = {"same": ser_same, "diff": ser_diff}

        # Statistical tests
        _, pval_ttest = ttest_ind(ser_diff, ser_same, equal_var=equal_var)
        _, pval_mann = mannwhitneyu(ser_diff, ser_same)
        pval_dict = {"ttest": pval_ttest, "mannwhitney": pval_mann}

        # ROC analysis
        roc_data = {}
        if calc_roc:
            roc_data = self._calculate_roc_analysis(sim_dict, plot_roc)

        return {"sim_dict": sim_dict, "pval_dict": pval_dict, "roc_data": roc_data}

    def _calculate_roc_analysis(
        self, sim_dict: dict[str, pd.Series], plot_roc: bool
    ) -> dict[str, Any]:
        """Calculate ROC curve analysis for similarity data."""
        true_labels = list(np.ones(sim_dict["same"].shape[0]))
        false_labels = list(np.zeros(sim_dict["diff"].shape[0]))
        y_true = true_labels + false_labels

        true_scores = list(sim_dict["same"].values)
        false_scores = list(sim_dict["diff"].values)
        y_score = true_scores + false_scores

        fpr, tpr, thresholds = roc_curve(y_true, y_score)
        inst_auc = auc(fpr, tpr)

        if plot_roc:
            plt.figure()
            plt.plot(fpr, tpr)
            plt.plot([0, 1], [0, 1], color="navy", linestyle="--")
            plt.figure(figsize=(10, 10))
            print("AUC", inst_auc)

        return {
            "true": y_true,
            "score": y_score,
            "fpr": fpr,
            "tpr": tpr,
            "thresholds": thresholds,
            "auc": inst_auc,
        }

    def generate_signatures(
        self,
        df_data: pd.DataFrame,
        df_meta: pd.DataFrame,
        category_name: str,
        pval_cutoff: float = 0.05,
        num_top_dims: bool | int = False,
        verbose: bool = True,
        equal_var: bool = False,
    ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        """Generate differential signatures for categories."""
        df_t = df_data.transpose()

        # Remove constant columns
        orig_num_cols = df_t.shape[1]
        df_t = df_t.loc[:, (df_t != df_t.iloc[0]).any()]
        if df_t.shape[1] < orig_num_cols and verbose:
            print("dropped columns with constant values")

        # Add category information
        df_t.index = [(x, df_meta.loc[x, category_name]) for x in df_t.index.tolist()]
        df = self.row_tuple_to_multiindex(df_t)

        cell_types = sorted(set(df.index.get_level_values(1).tolist()))

        return self._compute_differential_signatures(
            df, cell_types, pval_cutoff, num_top_dims, equal_var, verbose
        )

    def _compute_differential_signatures(
        self,
        df: pd.DataFrame,
        cell_types: list[str],
        pval_cutoff: float,
        num_top_dims: bool | int,
        equal_var: bool,
        verbose: bool,
    ) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
        """Compute differential expression signatures."""
        keep_genes = []
        gene_pval_dict = {}
        all_fold_info = {}

        for cell_type in cell_types:
            ct_mat = df.xs(key=cell_type, level=1)
            other_mat = df.drop(cell_type, level=1)

            # Calculate fold changes and statistics
            fold_info = self._calculate_fold_changes(ct_mat, other_mat)
            all_fold_info[cell_type] = fold_info

            _, pvals = ttest_ind(ct_mat, other_mat, axis=0, equal_var=equal_var)
            ser_pval = pd.Series(data=pvals, index=df.columns.tolist()).sort_values()

            # Filter by p-value or top N
            ser_pval_keep = (
                ser_pval[:num_top_dims] if num_top_dims else ser_pval[ser_pval < pval_cutoff]
            )

            gene_pval_dict[cell_type] = ser_pval_keep
            keep_genes.extend(ser_pval_keep.index.tolist())

        keep_genes = sorted(set(keep_genes))

        if len(keep_genes) == 0 and verbose:
            print("found no informative dimensions")

        # Generate signature matrix and differential results
        df_gbm = df.groupby(level=1).mean().transpose()
        df_sig = df_gbm.loc[keep_genes] if keep_genes else df_gbm.iloc[:0]

        df_diff = self._generate_differential_results(gene_pval_dict, all_fold_info, keep_genes)

        return df_sig, df_diff

    def _calculate_fold_changes(
        self, ct_mat: pd.DataFrame, other_mat: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """Calculate fold changes between cluster and other samples."""
        cluster_mean = ct_mat.mean()
        other_mean = other_mat.mean()
        log2_fold = (cluster_mean / other_mean).apply(np.log2)

        return {"cluster_mean": cluster_mean, "other_mean": other_mean, "log2_fold": log2_fold}

    def _generate_differential_results(
        self,
        gene_pval_dict: dict[str, pd.Series],
        all_fold_info: dict[str, dict[str, pd.Series]],
        keep_genes: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Generate differential expression results with multiple testing correction."""
        df_gene_pval = pd.concat(gene_pval_dict, axis=1, sort=False)
        df_diff = {}

        for col in df_gene_pval.columns:
            pvals = df_gene_pval[col].dropna().sort_values()
            if pvals.shape[0] == 0:
                continue

            genes = pvals.index.tolist()
            _, pval_corr = smm.multipletests(pvals, 0.05, method="fdr_bh")[:2]

            # Combine all statistics
            fold_info = all_fold_info[col]
            df_diff[col] = pd.DataFrame(
                {
                    "P-values": pvals,
                    "BH P-values": pd.Series(pval_corr, index=genes),
                    "Log2 Fold Change": fold_info["log2_fold"].loc[genes],
                    "Cluster Mean": fold_info["cluster_mean"].loc[genes],
                    "All Other Mean": fold_info["other_mean"].loc[genes],
                }
            )

        return df_diff

    def predict_cats_from_sigs(
        self,
        df_data_ini: pd.DataFrame,
        df_meta: pd.DataFrame,
        df_sig_ini: pd.DataFrame,
        predict: str = "Predicted Category",
        dist_type: DistanceType = "cosine",
        unknown_thresh: float = -1,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Predict categories using signature similarity."""
        common_rows = list(set(df_data_ini.index.tolist()).intersection(df_sig_ini.index.tolist()))

        df_data = deepcopy(df_data_ini.loc[common_rows])
        df_sig = deepcopy(df_sig_ini.loc[common_rows])

        # Calculate similarity matrix
        sim_mat = 1 - pairwise_distances(df_sig.transpose(), df_data.transpose(), metric=dist_type)

        cell_types = df_sig.columns.tolist()
        barcodes = df_data.columns.tolist()
        df_sim = pd.DataFrame(data=sim_mat, index=cell_types, columns=barcodes).transpose()

        # Assign predictions based on highest similarity
        predictions = df_sim.idxmax(axis=1)
        max_similarities = df_sim.max(axis=1)

        # Handle unknown predictions below threshold
        unknown_mask = max_similarities < unknown_thresh
        predictions[unknown_mask] = "Unknown"

        df_meta[predict] = predictions
        return df_sim.transpose(), df_meta

    def assess_prediction(
        self, df_meta: pd.DataFrame, truth: str, pred: str
    ) -> tuple[pd.DataFrame, pd.Series, float]:
        """Generate confusion matrix and accuracy metrics."""
        y_true = df_meta[truth].values.tolist()
        y_pred = df_meta[pred].values.tolist()

        sorted_cats = sorted(set(y_true + y_pred))
        conf_mat = confusion_matrix(y_true, y_pred, labels=sorted_cats)

        # Create confusion DataFrame (pred as rows, true as cols)
        df_conf = pd.DataFrame(conf_mat, index=sorted_cats, columns=sorted_cats).transpose()

        # Calculate overall accuracy
        total_correct = np.trace(df_conf)
        total_pred = df_conf.sum().sum()
        fraction_correct = total_correct / float(total_pred)

        # Calculate per-category accuracy
        cat_counts = df_conf.sum(axis=0)
        ser_correct = pd.Series(
            [df_conf.loc[cat, cat] / cat_counts[cat] for cat in df_conf.columns],
            index=df_conf.columns,
        )

        return df_conf, ser_correct, fraction_correct

    def compare_performance_to_shuffled_labels(
        self,
        df_data: pd.DataFrame,
        category_level: int,
        num_shuffles: int = 100,
        random_seed: int = 99,
        pval_cutoff: float = 0.05,
        dist_type: DistanceType = "cosine",
        num_top_dims: bool | int = False,
        predict_level: str = "Predict Category",
        truth_level: int = 1,
        unknown_thresh: float = -1,
        equal_var: bool = False,
        performance_type: Literal["prediction", "cat_sim_auc"] = "prediction",
    ) -> pd.Series:
        """Compare performance against shuffled label baseline."""
        random.seed(random_seed)
        performance_list = []

        # Pre-calculate distance matrix for similarity analysis
        dist_arr = None
        if performance_type == "cat_sim_auc":
            dist_arr = 1 - pdist(df_data.transpose(), metric=dist_type)

        for run_idx in range(num_shuffles + 1):
            df_shuffle = self._create_shuffled_data(df_data, run_idx)

            # Generate signatures on shuffled data
            df_sig, _ = self.generate_signatures(
                df_shuffle,
                self.meta_col,
                list(self.meta_col.columns)[category_level],
                pval_cutoff=pval_cutoff,
                num_top_dims=num_top_dims,
                equal_var=equal_var,
            )

            performance = self._evaluate_performance(
                df_shuffle,
                df_sig,
                performance_type,
                predict_level,
                truth_level,
                dist_type,
                unknown_thresh,
                equal_var,
                dist_arr,
            )

            if run_idx == 0:
                real_performance = performance
                print(f"performance of unshuffled: {real_performance}")
            else:
                performance_list.append(performance)

        perform_ser = pd.Series(performance_list)
        top_fraction = (perform_ser > real_performance).sum() / num_shuffles
        print(f"real data performs in the top {top_fraction * 100}% of shuffled labels\n")

        return perform_ser

    def _create_shuffled_data(self, df_data: pd.DataFrame, run_idx: int) -> pd.DataFrame:
        """Create shuffled version of data for baseline comparison."""
        if run_idx == 0:
            return deepcopy(df_data)

        cols = df_data.columns.tolist()
        shuffled_cols = deepcopy(cols)
        random.shuffle(shuffled_cols)

        return pd.DataFrame(
            data=df_data.values, columns=shuffled_cols, index=df_data.index.tolist()
        )

    def _evaluate_performance(
        self,
        df_shuffle: pd.DataFrame,
        df_sig: pd.DataFrame,
        performance_type: str,
        predict_level: str,
        truth_level: int,
        dist_type: DistanceType,
        unknown_thresh: float,
        equal_var: bool,
        dist_arr: np.ndarray | None,
    ) -> float:
        """Evaluate performance using specified metric."""
        if performance_type == "prediction":
            _, df_meta_updated = self.predict_cats_from_sigs(
                df_shuffle,
                self.meta_col,
                df_sig,
                predict=predict_level,
                dist_type=dist_type,
                unknown_thresh=unknown_thresh,
            )

            _, _, fraction_correct = self.assess_prediction(
                df_meta_updated, list(self.meta_col.columns)[truth_level], predict_level
            )
            return fraction_correct

        if performance_type == "cat_sim_auc":
            sim_data = self.sim_same_and_diff_category_samples(
                df_shuffle, cat_index=1, plot_roc=False, equal_var=equal_var, precalc_dist=dist_arr
            )
            return sim_data["roc_data"]["auc"]

        return 0.0

    # Utility Methods
    def row_tuple_to_multiindex(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert tuple-based row index to pandas MultiIndex."""
        df_mi = deepcopy(df)
        rows = df_mi.index.tolist()

        # Extract titles from first row
        titles = [part.split(": ")[0] if ": " in part else "Name" for part in rows[0]]

        # Clean up row data
        new_rows = [
            tuple(part.split(": ")[1] if ": " in part else part for part in row) for row in rows
        ]

        df_mi.index = pd.MultiIndex.from_tuples(new_rows, names=titles)
        return df_mi

    def set_cat_colors(
        self,
        cat_colors: dict[str, str],
        axis: AxisType,
        cat_index: int,
        cat_title: bool | str = False,
    ) -> None:
        """Set colors for multiple categories."""
        for category_name, color in cat_colors.items():
            display_name = f"{cat_title}: {category_name}" if cat_title else category_name
            self.set_cat_color(
                axis=axis, cat_index=cat_index, cat_name=display_name, inst_color=color
            )

    def set_manual_category(
        self,
        col: str | None = None,
        row: str | None = None,
        preferred_cats: pd.DataFrame | None = None,
    ) -> None:
        """Set manual category for interactive dendrogram definition."""
        self.dat["manual_category"] = {"col": col, "row": row}

        if preferred_cats is not None:
            pref_cats = [
                {"name": name, "color": preferred_cats.loc[name, "color"]}
                for name in preferred_cats.index.tolist()
            ]

            if col is not None:
                self.dat["manual_category"]["col_cats"] = pref_cats
            if row is not None:
                self.dat["manual_category"]["row_cats"] = pref_cats

    def ds_to_original_meta(self, axis: AxisType) -> None:
        """Transfer downsampled metadata to original metadata."""
        if not (hasattr(self, "meta_ds_col") and hasattr(self, "ds_name")):
            return

        clusters = self.meta_ds_col.index.tolist()
        man_cat_title = self.dat["manual_category"][axis]

        for cluster in clusters:
            cluster_cat = self.meta_ds_col.loc[cluster, man_cat_title]
            matching_labels = self.meta_col[self.meta_col[self.ds_name] == cluster].index.tolist()
            self.meta_col.loc[matching_labels, man_cat_title] = cluster_cat

    def get_manual_category(self, tmp: Any) -> None:
        """Extract manual category data from widget."""
        for axis in ["col"]:
            with contextlib.suppress(Exception):
                nodes = self.dat["nodes"][axis]
                cat_title = self.dat["manual_category"][axis]

                manual_cat_data = json.loads(self.widget_instance.manual_cat)
                cat_series = pd.Series(manual_cat_data[axis][cat_title])

                if hasattr(self, "meta_cat"):
                    self._update_metadata_categories(axis, nodes, cat_title, cat_series)

    def _update_metadata_categories(
        self, axis: AxisType, nodes: list[str], cat_title: str, cat_series: pd.Series
    ) -> None:
        """Update metadata with manual category assignments."""
        if axis == "row":
            target_meta = self.meta_ds_row if self.is_downsampled else self.meta_row
            target_meta.loc[nodes, cat_title] = cat_series
            if self.is_downsampled:
                self.ds_to_original_meta(axis)

        elif axis == "col":
            if self.is_downsampled:
                self.meta_ds_col.loc[nodes, cat_title] = cat_series
                self.ds_to_original_meta(axis)
            else:
                for node in cat_series.index.tolist():
                    self.meta_col.loc[node, cat_title] = cat_series[node]

    # Deprecated Methods (maintained for backward compatibility)

    def df_to_dat(self, df: pd.DataFrame, define_cat_colors: bool = False) -> None:
        """Load DataFrame (deprecated - use load_df instead)."""
        self._cached_df = None
        data_formats.df_to_dat(self, df, define_cat_colors)

    def dat_to_df(self) -> pd.DataFrame:
        """Export DataFrame (deprecated - use export_df instead)."""
        return data_formats.dat_to_df(self)

    # Static Methods

    @staticmethod
    def load_gmt(filename: str | Path) -> dict[str, list[str]]:
        """Load GMT format pathway file."""
        return load_data.load_gmt(filename)

    @staticmethod
    def load_json_to_dict(filename: str | Path) -> dict[str, Any]:
        """Load JSON file to dictionary."""
        return load_data.load_json_to_dict(filename)

    @staticmethod
    def save_dict_to_json(
        inst_dict: dict[str, Any], filename: str | Path, indent: str = "no-indent"
    ) -> None:
        """Save dictionary to JSON file."""
        export_data.save_dict_to_json(inst_dict, filename, indent)

    @staticmethod
    def save_list_to_tsv(inst_list: list[str], filename: str | Path) -> None:
        """Save list of strings to TSV file."""
        with Path(filename).open("w") as f:
            for line in inst_list:
                f.write(f"{line}\n")

    @staticmethod
    def load_gene_exp_to_df(inst_path: str | Path) -> pd.DataFrame:
        """Load 10x Genomics gene expression data to DataFrame."""
        from ast import literal_eval as make_tuple

        from scipy import io

        path_str = str(inst_path)

        # Load matrix
        matrix = io.mmread(f"{path_str}matrix.mtx")
        mat = matrix.todense()

        # Load and process genes
        genes = Network._load_genes_file(f"{path_str}genes.tsv")

        # Load and process barcodes
        barcodes = Network._load_barcodes_file(f"{path_str}barcodes.tsv")

        # Try to parse as tuples if needed
        for data_list in [barcodes, genes]:
            with contextlib.suppress(Exception):
                data_list[:] = [make_tuple(x) for x in data_list]

        return pd.DataFrame(mat, index=genes, columns=barcodes)

    @staticmethod
    def _load_genes_file(filename: str) -> list[str]:
        """Load and process genes file with duplicate handling."""
        with Path(filename).open() as f:
            lines = f.readlines()

        # Extract gene names
        raw_genes = [
            line.strip().split()[1] if len(line.strip().split()) > 1 else line.strip().split()[0]
            for line in lines
        ]

        # Handle duplicates by adding numeric suffixes
        gene_counts = pd.Series(raw_genes).value_counts()
        duplicates = set(gene_counts[gene_counts > 1].index)

        processed_genes = []
        dup_counters = {}

        for gene in raw_genes:
            if gene in duplicates:
                dup_counters[gene] = dup_counters.get(gene, 0) + 1
                processed_genes.append(f"{gene}_{dup_counters[gene]}")
            else:
                processed_genes.append(gene)

        return processed_genes

    @staticmethod
    def _load_barcodes_file(filename: str) -> list[str]:
        """Load and process barcodes file."""
        with Path(filename).open() as f:
            lines = f.readlines()

        barcodes = []
        for line in lines:
            barcode = line.strip().split("\t")[0]
            # Remove dash suffix if present
            if "-" in barcode:
                barcode = barcode.split("-")[0]
            barcodes.append(barcode)

        return barcodes

    @staticmethod
    def save_gene_exp_to_mtx_dir(inst_path: str | Path, df: pd.DataFrame) -> None:
        """Save DataFrame as 10x Genomics format files."""
        from scipy import io, sparse

        path_obj = Path(inst_path)
        path_obj.mkdir(exist_ok=True)

        genes = df.index.tolist()
        barcodes = df.columns.tolist()

        # Save genes and barcodes
        Network.save_list_to_tsv(genes, path_obj / "genes.tsv")
        Network.save_list_to_tsv(barcodes, path_obj / "barcodes.tsv")

        # Save matrix in sparse format
        mat_sparse = sparse.coo_matrix(df.values)
        io.mmwrite(path_obj / "matrix.mtx", mat_sparse)

    @staticmethod
    def umi_norm(df: pd.DataFrame) -> pd.DataFrame:
        """Perform UMI normalization (divide by column sums)."""
        return df.div(df.sum(axis=0), axis=1)

    @staticmethod
    def make_df_from_cols(cols: list[tuple[str, ...]]) -> pd.DataFrame:
        """Create DataFrame from column tuples with category information."""
        if not cols:
            return pd.DataFrame()

        # Extract category titles from first column
        cat_titles = [info.split(": ")[0] for info in cols[0][1:]]

        # Clean column data
        clean_cols = [
            tuple(info.split(": ", 1)[1] if ": " in info else info for info in col) for col in cols
        ]

        # Create DataFrame with first element as index
        df_data = pd.DataFrame(clean_cols).set_index(0)

        return pd.DataFrame(data=df_data.values, index=df_data.index.tolist(), columns=cat_titles)

    @staticmethod
    def box_scatter_plot(
        df: pd.DataFrame,
        group: str,
        columns: bool | list[str] = False,
        rand_seed: int = 100,
        alpha: float = 0.5,
        dot_color: str = "red",
        num_row: int | None = None,
        num_col: int = 1,
        figsize: tuple[int, int] = (10, 10),
        start_title: str = "Variable Measurements Across",
        end_title: str = "Groups",
    ) -> dict[str, pd.DataFrame]:
        """Create box plots with scatter overlay for grouped data."""

        plot_columns = columns if columns else df.columns.tolist()

        plt.figure(figsize=figsize)
        plt.suptitle(f"{start_title} {group} {end_title}", fontsize=20)

        result_dfs = {}

        for col_idx, column in enumerate(plot_columns):
            plot_id = col_idx + 1

            # Group data
            grouped = df.groupby(group) if group in df.columns else df.groupby(level=group)

            names, values = [], []
            col_title = column[0] if isinstance(column, tuple) else column

            for name, subdf in grouped:
                names.append(name)
                series = subdf[column]
                series.name = f"{col_title}-{name}"
                values.append(series)

            # Create plot
            np.random.seed(rand_seed)
            ax = plt.subplot(num_row, num_col, plot_id)
            plt.boxplot(values, labels=names)

            # Add scatter points
            Network._add_scatter_points(values, dot_color, alpha, num_row, num_col, plot_id)

            # Statistical analysis and title
            df_arranged = pd.concat(values, axis=1)
            pval = Network._calculate_anova_pvalue(df_arranged)

            title_text = (
                f"{col_title} P-val: {pval:.2e}"
                if pval < 0.01
                else f"{col_title} P-val: {pval:.5f}"
            )
            ax.set_title(title_text)

            result_dfs[column] = df_arranged

        return result_dfs

    @staticmethod
    def _add_scatter_points(
        values: list[pd.Series],
        dot_color: str,
        alpha: float,
        num_row: int | None,
        num_col: int,
        plot_id: int,
    ) -> None:
        """Add scatter points to box plot."""
        n_groups = len(values)
        group_positions = np.linspace(0.0, 1.0, n_groups)

        for i, (_, series) in enumerate(zip(group_positions, values, strict=False)):
            x_scatter = np.random.normal(i + 1, 0.04, len(series))
            plt.subplot(num_row, num_col, plot_id)
            plt.scatter(x_scatter, series, c=dot_color, alpha=alpha)

    @staticmethod
    def _calculate_anova_pvalue(df_arranged: pd.DataFrame) -> float:
        """Calculate ANOVA p-value for grouped data."""
        from scipy import stats

        anova_data = [df_arranged[col].dropna() for col in df_arranged.columns]
        _, pval = stats.f_oneway(*anova_data)
        return pval

    @staticmethod
    def rank_cols_by_anova_pval(
        df: pd.DataFrame, group: str, columns: bool | list[str] = False
    ) -> pd.Series:
        """Rank columns by ANOVA p-values for group differences."""
        plot_columns = columns if columns else df.columns.tolist()
        pval_list = []

        for column in plot_columns:
            # Group data
            grouped = df.groupby(group) if group in df.columns else df.groupby(level=group)

            values = []
            col_title = column[0] if isinstance(column, tuple) else column

            for name, subdf in grouped:
                series = subdf[column]
                series.name = f"{col_title}-{name}"
                values.append(series)

            # Calculate ANOVA
            df_arranged = pd.concat(values, axis=1)
            pval = Network._calculate_anova_pvalue(df_arranged)
            pval_list.append(pval)

        return pd.Series(pval_list, index=plot_columns).sort_values()


def save_list_to_tsv(inst_list: list[str], filename: str | Path) -> None:
    """Save list of strings to TSV file."""
    with Path(filename).open("w") as f:
        for line in inst_list:
            f.write(f"{line}\n")
