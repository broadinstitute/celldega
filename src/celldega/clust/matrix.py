from __future__ import annotations

import copy
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
    DEFAULT_MARKER_VIEW_LEVELS,
    DEFAULT_VIEW_LEVELS,
    DEFAULT_VIZ,
    ERRORS,
    MIN_VIEW_ROWS,
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


def _is_default_entity_pair(
    row_entity: str | dict | AxisEntity | None,
    col_entity: str | dict | AxisEntity | None,
) -> bool:
    """Return True when the caller is using Matrix's default entity pair."""
    return row_entity == "gene" and col_entity == "cell_cluster"


def _axis_entities_from_uns(adata: AnnData) -> tuple[AxisEntity, AxisEntity] | None:
    """Read Matrix row/column entities from AnnData metadata when available."""
    candidates = [
        adata.uns.get("axis_entities"),
        adata.uns.get("matrix_axis_entities"),
        adata.uns.get("celldega", {}).get("axis_entities")
        if isinstance(adata.uns.get("celldega"), dict)
        else None,
    ]

    for payload in candidates:
        if not isinstance(payload, dict):
            continue

        row_entity = payload.get("row_entity") or payload.get("row")
        col_entity = payload.get("col_entity") or payload.get("col")
        if row_entity is not None and col_entity is not None:
            return normalize_axis_entity(row_entity), normalize_axis_entity(col_entity)

    if "row_entity" in adata.uns and "col_entity" in adata.uns:
        return (
            normalize_axis_entity(adata.uns["row_entity"]),
            normalize_axis_entity(adata.uns["col_entity"]),
        )

    return None


def _infer_axis_entities_from_adata(adata: AnnData) -> tuple[AxisEntity, AxisEntity] | None:
    """Infer Matrix row/column entity specs for known AnnData modality shapes."""
    metadata_entities = _axis_entities_from_uns(adata)
    if metadata_entities is not None:
        return metadata_entities

    var_entity_type = adata.var.get("entity_type")
    if var_entity_type is None:
        return None

    var_entity_values = pd.Series(var_entity_type).dropna().astype(str).unique()
    category = adata.uns.get("category")

    if (
        len(var_entity_values) == 1
        and var_entity_values[0] == "cell_population"
        and category is not None
    ):
        row_entity: AxisEntity = {"entity": "cell", "attr": str(category)}

        if "dataset_col" in adata.uns:
            col_entity: AxisEntity = {"entity": "dataset", "attr": str(adata.uns["dataset_col"])}
        elif (
            "neighborhood_id" in adata.obs.columns
            or "neighborhood_type" in adata.obs.columns
            or adata.obs.index.name == "neighborhood_id"
        ):
            col_entity = {"entity": "nbhd", "attr": "name"}
        else:
            # Neighborhood population matrices may lack neighborhood obs metadata.
            col_entity = {"entity": "nbhd", "attr": "name"}

        return row_entity, col_entity

    return None


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


#: Columns of the tidy marker-rank frame, in the order scanpy's own
#: ``rank_genes_groups_df`` emits them (plus the explicit within-group rank).
_MARKER_RANK_COLUMNS = (
    "group",
    "names",
    "scores",
    "logfoldchanges",
    "pvals",
    "pvals_adj",
    "rank",
)


def marker_ranks_to_uns(markers: pd.DataFrame) -> dict[str, list]:
    """Serialize a tidy marker-rank frame for ``AnnData.uns``.

    Stored column-wise as plain lists so it survives an h5ad round trip, unlike
    a DataFrame.
    """
    return {column: markers[column].tolist() for column in markers.columns}


def marker_ranks_from_uns(payload: Any) -> pd.DataFrame | None:
    """Recover a tidy marker-rank frame from an ``uns`` payload.

    Accepts what :func:`marker_ranks_to_uns` wrote, and also scanpy's own
    in-place ``uns["rank_genes_groups"]`` structure (per-group columns in a
    structured array), so an AnnData that already had ``sc.tl.rank_genes_groups``
    run on it works without any celldega-specific preparation.

    Returns ``None`` for anything it doesn't recognize, so callers can probe
    ``uns`` keys without guarding each shape themselves.
    """
    if isinstance(payload, pd.DataFrame):
        return payload if "names" in payload.columns else None
    if not isinstance(payload, dict):
        return None

    # celldega's tidy form: already long, one row per (group, feature).
    if "group" in payload and "names" in payload:
        try:
            frame = pd.DataFrame({key: list(value) for key, value in payload.items()})
        except (TypeError, ValueError):
            return None
        return frame if "names" in frame.columns else None

    # scanpy's native form: `names`/`scores`/... are structured arrays whose
    # fields are the groups. Melt them into the same tidy shape.
    names = payload.get("names")
    fields = getattr(getattr(names, "dtype", None), "names", None)
    if not fields:
        return None

    frames = []
    for group in fields:
        columns = {"group": str(group), "names": list(np.asarray(names[group]))}
        for source, target in (
            ("scores", "scores"),
            ("logfoldchanges", "logfoldchanges"),
            ("pvals", "pvals"),
            ("pvals_adj", "pvals_adj"),
        ):
            values = payload.get(source)
            if values is not None and group in (
                getattr(getattr(values, "dtype", None), "names", None) or ()
            ):
                columns[target] = list(np.asarray(values[group]))
        group_frame = pd.DataFrame(columns)
        group_frame["rank"] = range(len(group_frame))
        frames.append(group_frame)

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _dense(values: Any) -> np.ndarray:
    return values.toarray() if hasattr(values, "toarray") else np.asarray(values)


# A clustered Matrix on disk is an AnnData Zarr store in ``Matrix(adata)``'s
# orientation (obs = Clustergram columns, var = rows). Dendrogram orders are
# ``obsm``/``varm`` frames; linkages, packed views, and a small JSON document
# with colors, attributes, and entities live in ``uns["celldega"]``.
_STORE_FORMAT = "celldega.matrix"
_STORE_VERSION = 1
_STORE_NODES_KEY = "celldega_nodes"
_STORE_NODE_ORDERS = ("ini", "clust", "rank", "rankvar")
_STORE_VIEW_SCALARS = ("view_type", "level", "level_unit", "n_rows")
_STORE_VIZ_KEYS = (
    "name",
    "row_attr_maxabs",
    "col_attr_maxabs",
    "cat_colors",
    "matrix_colors",
    "global_cat_colors",
    "links",
)
# X and the size layer are chunked in bands of whole columns of at most 16 MB.
_STORE_CHUNK_BYTES = 16 * 2**20


def _json_native(value: Any) -> Any:
    """Convert numpy scalars to Python and non-finite floats to ``None`` for JSON."""
    if isinstance(value, dict):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_native(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _nodes_frame(nodes: list[dict[str, Any]], names: pd.Index) -> pd.DataFrame:
    """Node records (orders, categories, numeric attributes) as an obsm/varm frame."""
    frame = pd.DataFrame(nodes).drop(columns="name")
    frame.index = names
    for column in frame.columns:
        if column in _STORE_NODE_ORDERS:
            frame[column] = frame[column].astype(np.int32)
        elif column.startswith("num-"):
            frame[column] = frame[column].astype(np.float64)
        else:
            frame[column] = frame[column].astype(str).astype(object)
    return frame


def _nodes_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Rebuild node records with the Python types the visualization export uses."""
    records = []
    for name, values in zip(frame.index, frame.itertuples(index=False, name=None), strict=True):
        node: dict[str, Any] = {"name": str(name)}
        for column, value in zip(frame.columns, values, strict=True):
            if column in _STORE_NODE_ORDERS:
                node[column] = int(value)
            elif column.startswith("num-"):
                node[column] = float(value)
            else:
                node[column] = str(value)
        records.append(node)
    return records


def _writable_meta(meta: pd.DataFrame, names: pd.Index) -> tuple[pd.DataFrame, list[str]]:
    """Make row/column metadata writable without loss; return its object columns.

    AnnData writes missing values in object columns as the string "None", so
    object columns are stored as categoricals, which keep them, and converted
    back on read.
    """
    frame = meta.reindex(names).copy()
    frame.index = names
    object_columns = []
    for column in frame.columns:
        series = frame[column]
        if series.dtype == object or isinstance(series.dtype, pd.StringDtype):
            object_columns.append(str(column))
            values = series.astype(object)
            frame[column] = pd.Categorical(values.where(values.isna(), values.astype(str)))
    frame.columns = [str(column) for column in frame.columns]
    return frame, object_columns


def _restored_meta(frame: pd.DataFrame, object_columns: list[str]) -> pd.DataFrame:
    """Undo :func:`_writable_meta`: turn stored categoricals back into object columns."""
    frame = frame.copy()
    for column in object_columns:
        values = frame[column].astype(object)
        frame[column] = values.where(values.notna(), np.nan)
    return frame


def _group_signature(
    adata: AnnData,
    groupby: str,
    *,
    layer: str | None = None,
    rank_genes_groups: bool | dict[str, Any] | None = None,
) -> tuple[AnnData, AnnData]:
    """Aggregate a cell-level AnnData into a groups x features signature.

    Uses ``scanpy.get.aggregate`` for the per-group mean (color) and the number
    of cells with expression > 0, divided by group size for the fraction
    expressing (dot size). Marker ranks come from ``adata.uns["rank_genes_groups"]`` when
    it was computed for the same ``groupby``, or from
    ``scanpy.tl.rank_genes_groups`` when ``rank_genes_groups`` asks for it.

    Returns:
        ``(signature, fraction)``: the groups x features mean expression (with
        group colors, sizes, marker ranks, and axis entities) and a same-shaped
        AnnData of the fraction of cells expressing each feature.
    """
    try:
        import scanpy as sc
    except ImportError:
        raise ImportError(ERRORS["missing_scanpy"]) from None

    from .utils import compute_marker_ranks

    if groupby not in adata.obs.columns:
        raise ValueError(ERRORS["missing_category"].format(groupby, list(adata.obs.columns)))

    labels = adata.obs[groupby]
    labelled = labels.notna().to_numpy()
    cells = adata if labelled.all() else adata[labelled]

    aggregated = sc.get.aggregate(cells, by=groupby, func="mean", layer=layer)
    group_names = pd.Index(aggregated.obs_names.astype(str))
    group_sizes = (
        cells.obs[groupby].astype(str).value_counts().reindex(group_names).fillna(0).to_numpy()
    )
    present = group_sizes > 0
    group_names = group_names[present]
    group_sizes = group_sizes[present]

    mean = _dense(aggregated.layers["mean"])[present]

    # Fraction of each group's cells with expression > 0 (scanpy's dot plot
    # convention), so scaled data with negative values doesn't count as expressing.
    source = cells.layers[layer] if layer is not None else cells.X
    detected = AnnData(
        X=(source > 0).astype(np.float32),
        obs=cells.obs[[groupby]].copy(),
        var=pd.DataFrame(index=cells.var_names),
    )
    expressing = sc.get.aggregate(detected, by=groupby, func="sum")
    n_expressing = pd.DataFrame(
        _dense(expressing.layers["sum"]), index=pd.Index(expressing.obs_names.astype(str))
    ).reindex(group_names)
    fraction = n_expressing.to_numpy() / group_sizes[:, None]

    obs = pd.DataFrame(index=group_names)
    obs[groupby] = group_names
    obs["n_cells"] = group_sizes.astype(int)
    var = cells.var.copy()
    var.index = pd.Index(cells.var_names.astype(str))
    signature = AnnData(X=mean, obs=obs, var=var)

    color_key = f"{groupby}_colors"
    if color_key in adata.uns:
        if isinstance(labels.dtype, pd.CategoricalDtype):
            categories = labels.cat.categories.astype(str)
        else:
            categories = pd.Index(pd.unique(labels.dropna())).astype(str)
        palette = dict(zip(categories, adata.uns[color_key], strict=False))
        signature.obs["color"] = [palette.get(name, "#808080") for name in group_names]
        signature.uns[color_key] = list(signature.obs["color"])

    markers = None
    existing = adata.uns.get("rank_genes_groups")
    existing_groupby = (
        existing.get("params", {}).get("groupby") if isinstance(existing, dict) else None
    )
    if rank_genes_groups is not False:
        if existing_groupby == groupby and not isinstance(rank_genes_groups, dict):
            markers = marker_ranks_from_uns(existing)
        elif rank_genes_groups or isinstance(rank_genes_groups, dict):
            kwargs = rank_genes_groups if isinstance(rank_genes_groups, dict) else None
            markers = compute_marker_ranks(cells, groupby, kwargs)
    if markers is not None:
        signature.uns["rank_genes_groups"] = marker_ranks_to_uns(markers)

    signature.uns["axis_entities"] = {
        "row_entity": {"entity": "gene", "attr": "name"},
        "col_entity": {"entity": "cell", "attr": groupby},
    }

    size = AnnData(X=fraction, obs=pd.DataFrame(index=group_names), var=var.copy())
    return signature, size


def _serialize_linkage(linkage_matrix: np.ndarray) -> list[list[float]]:
    """Compact JSON-ready linkage. Views ride along inside the viz metadata, so
    trim float noise rather than shipping full repr precision per merge."""
    return [[round(float(value), 6) for value in row] for row in linkage_matrix]


def _clustering_distances(data: np.ndarray, dist_type: str) -> np.ndarray:
    """Share distance handling between the full matrix and reduced views."""
    if dist_type == Distance.COSINE.value and (
        data.shape[1] > 1000 or np.any(~np.any(data, axis=1))
    ):
        # scipy's cosine metric is undefined for zero vectors. Use the same
        # explicit zero-vector convention at every matrix/view size.
        return fast_cosine_distance(data)
    distances = pdist(data, metric=dist_type)
    np.maximum(distances, 0.0, out=distances)
    return distances


class Matrix:
    """
    High-performance matrix class for explicit transformations and hierarchical clustering.

    Construction preserves supplied values. Filtering and normalization are
    explicit operations, followed by hierarchical clustering and visualization
    export. Uses intelligent caching for performance with large datasets.

    Examples:
        # Preserve an already-prepared matrix
        mat = Matrix(adata)
        mat.cluster()

        # Explicit preprocessing for a general dataset
        mat = Matrix(adata, global_colors={"high": "red", "low": "blue"})
        mat.filter("row", by="var", num=5000)
        mat.norm("row", by="qn")
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
        # Visualization parameters
        global_colors: dict[str, str] | pd.DataFrame | None = None,
        name: str | None = None,
        *,
        # Cell-level AnnData path: aggregate cells into groups (dot plot)
        groupby: str | None = None,
        layer: str | None = None,
        rank_genes_groups: bool | dict[str, Any] | None = None,
        # MuData path (alternative to `data`)
        mdata: Any = None,
        color_by: str | None = None,
        size_by: str | None = None,
        size_by_layer: str | None = None,
        dot_plot: str | None = None,
    ):
        """
        Create a Matrix while preserving the supplied values.

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
            global_colors: Global category color mapping (dict or DataFrame with 'color' column)
            name: Name for the matrix (default: None)
            groupby: With a cell-level AnnData ``data``, aggregate cells into
                groups by this ``obs`` column (e.g. ``"leiden"``, a sample or
                dataset column) with ``scanpy.get.aggregate``: columns become
                groups, color is the mean expression, and dot size is the
                fraction of cells expressing each feature (a dot plot). Group
                colors come from ``uns[f"{groupby}_colors"]``. Requires scanpy.
            layer: With ``groupby``, aggregate this layer instead of ``X``.
            rank_genes_groups: With ``groupby``, where marker ranks (for
                ``cluster(view="rank_genes_groups")``) come from. ``None``
                (default) reuses ``adata.uns["rank_genes_groups"]`` when it was
                computed for the same ``groupby``; ``True`` also runs
                ``scanpy.tl.rank_genes_groups`` when there are none; a dict runs
                it with these keyword arguments; ``False`` skips marker ranks.
            mdata: A ``MuData`` (or any object exposing ``.mod``) to build
                ``data`` from, in place of passing ``data`` directly —
                equivalent to ``data=mdata.mod[color_by]``. Requires `color_by`.
            color_by: Modality key on `mdata` driving color/opacity (the main
                matrix).
            size_by: Optional modality key on `mdata` driving the secondary
                *size* channel (dot-plot size, e.g. fraction of cells expressing —
                but any per-cell magnitude works, e.g. significance) — equivalent to
                calling ``.set_size_matrix(mdata.mod[size_by])`` after
                construction. Omit for a matrix with no size channel.
            size_by_layer: Optional layer driving the secondary size channel,
                on ``mdata.mod[color_by]`` or on an AnnData ``data``. Mutually
                exclusive with ``size_by`` and ``dot_plot``.
            dot_plot: Deprecated alias for `size_by` (pass either, not both).

        Examples:
            # Preserve already-prepared values (default)
            mat = Matrix(adata)

            # Explicit preprocessing for a general standalone dataset
            colors = {"Cancer": "#ff0000", "Normal": "#0000ff"}
            mat = Matrix(adata, global_colors=colors)
            mat.filter("row", by="var", num=5000)
            mat.norm("row", by="qn")

            # Marker dot plot straight from a cell-level AnnData
            sc.tl.rank_genes_groups(adata, groupby="leiden")
            mat = Matrix(adata, groupby="leiden")
            mat.cluster(view="rank_genes_groups")

            # Dot plot from MuData modalities
            mat = Matrix(mdata=mdata, color_by="expression", size_by="fraction")

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
        if dot_plot is not None:
            warnings.warn(
                "`dot_plot` is deprecated; use `size_by` for a modality or "
                "`size_by_layer` for a layer on the color modality.",
                DeprecationWarning,
                stacklevel=2,
            )
        if size_by is not None and dot_plot is not None:
            raise ValueError("pass either `size_by` or `dot_plot` (alias), not both")
        size_by = size_by if size_by is not None else dot_plot
        if size_by_layer is not None and size_by is not None:
            raise ValueError("pass either `size_by_layer` or `size_by`/`dot_plot`, not both")

        if mdata is not None:
            if data is not None:
                raise ValueError("pass either `data` or `mdata`, not both")
            if color_by is None:
                raise ValueError("`color_by` is required when constructing Matrix from `mdata`")
            if color_by not in mdata.mod:
                raise KeyError(
                    f"color_by '{color_by}' not found; available modalities: {list(mdata.mod)}"
                )
            data = mdata.mod[color_by]
        elif color_by is not None or size_by is not None:
            raise ValueError("`color_by`/`size_by` require `mdata`")
        elif size_by_layer is not None and not isinstance(data, AnnData):
            raise ValueError("`size_by_layer` requires an AnnData `data` or `mdata`")

        group_size: AnnData | None = None
        if groupby is not None:
            if mdata is not None or not isinstance(data, AnnData):
                raise ValueError("`groupby` requires a cell-level AnnData as `data`")
            data, group_size = _group_signature(
                data, groupby, layer=layer, rank_genes_groups=rank_genes_groups
            )
        elif layer is not None or rank_genes_groups is not None:
            raise ValueError("`layer`/`rank_genes_groups` require `groupby`")

        axis_entities_defaulted = _is_default_entity_pair(row_entity, col_entity)
        if isinstance(data, AnnData) and axis_entities_defaulted:
            inferred_entities = _infer_axis_entities_from_adata(data)
            if inferred_entities is not None:
                row_entity, col_entity = inferred_entities

        # Core data storage
        self.data: pd.DataFrame | None = None
        self.meta_col: pd.DataFrame = pd.DataFrame()
        self.meta_row: pd.DataFrame = pd.DataFrame()

        # Optional secondary matrix (aligned to the main matrix by row/col name)
        # used as a per-cell *size* channel for dot-plot style Clustergrams —
        # e.g. the fraction of cells in a cluster expressing each gene. See
        # :meth:`set_size_matrix`.
        self.size_matrix: pd.DataFrame | None = None

        # Differential-expression results carried by the input AnnData, as a
        # tidy frame with group/names/scores/logfoldchanges/pvals/pvals_adj.
        # Kept internal: scanpy (or `Matrix(adata, groupby=...)`) computes them; Matrix
        # only consumes the ranks for `cluster(view="rank_genes_groups")`.
        self._marker_ranks: pd.DataFrame | None = None

        # Precomputed dimensionality views (see `cluster(view=...)`). Each entry
        # is one re-biclustered filter level; exported in the viz metadata and
        # driven by the Clustergram's RANK slider.
        self.views: list[dict[str, Any]] = []

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

        # Visualization structure. Deep copy so each Matrix gets its own nested
        # ``linkage``/node dicts — a shallow copy would share them across instances.
        self.viz: dict[str, Any] = copy.deepcopy(DEFAULT_VIZ)
        # AnnData category palettes are collected in ``load_adata`` and take
        # precedence over auto-generated Matrix colors. This preserves a
        # shared annotation colors across separate views.
        self._source_global_cat_colors: dict[str, str] = {}

        # if name is None, generate a quick hash-based name from the data content
        if name is None:
            # Generate a quick hash-based name from the data content
            self._data_hash_name = quick_hash_data(data)
        else:
            self._data_hash_name = name

        # Load data without changing supplied values. Filtering and normalization
        # remain explicit Matrix operations via ``filter`` and ``norm``.
        if data is not None:
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

        # Always assign colors (auto-generated if not provided)
        self.set_global_cat_colors(global_colors)

        # Optional size channel from the same MuData / AnnData
        if size_by is not None:
            if mdata is None:
                raise ValueError("`size_by`/`dot_plot` require `mdata`")
            if size_by not in mdata.mod:
                raise KeyError(
                    f"size_by '{size_by}' not found; available modalities: {list(mdata.mod)}"
                )
            self.set_size_matrix(mdata.mod[size_by])
        elif size_by_layer is not None:
            color_modality = data
            if size_by_layer not in color_modality.layers:
                source = f"modality '{color_by}'" if mdata is not None else "data"
                raise KeyError(
                    f"size_by_layer '{size_by_layer}' not found in {source}; "
                    f"available layers: {list(color_modality.layers)}"
                )
            dot = AnnData(
                X=color_modality.layers[size_by_layer],
                obs=color_modality.obs.copy(),
                var=color_modality.var.copy(),
            )
            self.set_size_matrix(dot)
        elif group_size is not None:
            self.set_size_matrix(group_size)

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

    def clust(
        self,
        dist_type: DistanceType = "cosine",
        linkage_type: LinkageType = "average",
        force: bool = False,
        views: str | list[str] | None = None,
        levels: list[int] | None = None,
    ) -> Matrix:
        """Deprecated alias for :meth:`cluster`."""
        warnings.warn(
            "`Matrix.clust()` is deprecated; use `Matrix.cluster()` with the "
            "singular `view=` argument.",
            DeprecationWarning,
            stacklevel=2,
        )
        if isinstance(views, list):
            if len(views) != 1:
                raise ValueError(f"cluster(view=...) takes a single view type (got {views!r})")
            view = views[0]
        else:
            view = views
        return self.cluster(
            dist_type=dist_type,
            linkage_type=linkage_type,
            force=force,
            view=view,
            levels=levels,
        )

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

        for metadata, attributes in ((adata.obs, col_attr or []), (adata.var, row_attr or [])):
            for category in attributes:
                color_key = f"{category}_colors"
                if category not in metadata or color_key not in adata.uns:
                    continue
                source_colors = adata.uns[color_key]
                if isinstance(metadata[category].dtype, pd.CategoricalDtype):
                    categories = metadata[category].cat.categories.astype(str)
                else:
                    categories = pd.Index(metadata[category].dropna().astype(str).unique())
                for index, category_value in enumerate(categories):
                    if index < len(source_colors):
                        self._source_global_cat_colors.setdefault(
                            str(category_value), str(source_colors[index])
                        )

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

        # Differential expression carried on the AnnData -- written by
        # `Matrix(adata, groupby=..., rank_genes_groups=True)`, or by scanpy
        # itself -- makes `cluster(view="rank_genes_groups")` work with no
        # further setup. `load_df` above reset state, so this has to follow it.
        for key in ("rank_genes_groups", "marker_ranks"):
            markers = marker_ranks_from_uns(adata.uns.get(key))
            if markers is not None:
                self._marker_ranks = markers
                break

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

    def cluster(
        self,
        dist_type: DistanceType = "cosine",
        linkage_type: LinkageType = "average",
        force: bool = False,
        view: str | None = None,
        levels: list[int] | None = None,
        *,
        views: str | list[str] | None = None,
    ) -> Matrix:
        """
        Perform hierarchical clustering.

        Args:
            dist_type: Distance metric ('cosine', 'euclidean', 'correlation')
            linkage_type: Linkage method ('average', 'complete', 'ward')
            force: Override size limits for large matrices
            view: Precompute reduced-dimensionality views, each independently
                re-biclustered, and drive them from the Clustergram's RANK slider.
                One of:

                - ``"rank_genes_groups"``: each cluster's top markers, unioned.
                  Needs differential expression carried by the input AnnData,
                  normally from
                  ``scanpy.tl.rank_genes_groups`` (see ``Matrix(adata, groupby=...)``).
                - ``"var"`` / ``"sum"`` / ``"mean"``: rows ranked by a per-row
                  metric on the matrix itself — no differential expression needed,
                  which is the right fit for bulk or otherwise ungrouped matrices.
            levels: Slider stops to precompute. **The unit depends on the view**:

                - ``"rank_genes_groups"``: top markers **per cluster**, so level 10
                  means each cluster's 10 best markers unioned (deduplicated, so
                  the row count is at most ``n_clusters * 10``). Defaults to
                  :data:`~celldega.clust.constants.DEFAULT_MARKER_VIEW_LEVELS`.
                  Counting per cluster rather than in total means you don't have to
                  divide a row budget by however many clusters you happen to have.
                - metric views: total rows kept, since those rankings are global
                  with no groups to divide by. Defaults to
                  :data:`~celldega.clust.constants.DEFAULT_VIEW_LEVELS`.

                Levels that resolve to the whole matrix, to fewer than
                :data:`~celldega.clust.constants.MIN_VIEW_ROWS` rows, or to rows a
                finer level already covered are dropped. The full matrix is always
                available as the slider's "all" stop.

        Examples:
            >>> mat.cluster()                                        # no view
            >>> mat.cluster(view="rank_genes_groups")                # top K per cluster
            >>> mat.cluster(view="rank_genes_groups", levels=[3, 5]) # 3 and 5 per cluster
            >>> mat.cluster(view="var", levels=[10, 50, 200])        # 10/50/200 rows
        """
        if views is not None:
            warnings.warn(
                "`views=` is deprecated; use the singular `view=` argument.",
                DeprecationWarning,
                stacklevel=2,
            )
            if view is not None:
                raise ValueError("pass either `view` or deprecated `views`, not both")
            if isinstance(views, list):
                if len(views) != 1:
                    raise ValueError(f"cluster(view=...) takes a single view type (got {views!r})")
                view = views[0]
            else:
                view = views

        if view is not None and not isinstance(view, str):
            raise TypeError("`view` must be a single string")

        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        self._validate_clustering_size(force)

        for axis in [Axis.ROW.value, Axis.COL.value]:
            self._cluster_axis_cached(axis, dist_type, linkage_type)

        self.make_viz()
        self._clustered = True

        self.views = self._build_views(view, levels, dist_type, linkage_type) if view else []
        # `viz` is what `export_viz_parquet` serializes into the metadata blob, and
        # both the widget and DegaFiles readers spread that straight onto the
        # front-end network object — so views need no dedicated transport.
        self.viz["views"] = self.views
        return self

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
                distances = _clustering_distances(data, dist_type)

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

    @staticmethod
    def _subset_axis_linkage(
        data: np.ndarray, dist_type: str, linkage_type: str
    ) -> tuple[np.ndarray | None, list[int] | None]:
        """Linkage + dendrogram leaf order for one axis of a view's submatrix."""
        if data.shape[0] < 2:
            return None, None

        try:
            distances = _clustering_distances(data, dist_type)

            linkage_matrix = linkage(distances, method=linkage_type)
            leaves = dendrogram(linkage_matrix, no_plot=True)["leaves"]
        except Exception:
            return None, None

        return linkage_matrix, leaves

    def _cluster_subset(
        self,
        row_indices: list[int],
        dist_type: str,
        linkage_type: str,
    ) -> dict[str, Any] | None:
        """Re-bicluster a row subset, expressed in the full matrix's index space.

        ``row_indices`` must be ascending, so submatrix row ``j`` corresponds to
        full-matrix row ``row_indices[j]`` — the front end relies on exactly that
        mapping to translate this view's scipy leaf ids back to matrix rows.

        Order arrays are sized to the *full* matrix and pre-offset by 1 to match
        the front end's order convention, so they can be swapped straight into
        its state. Rows outside the view get 0; they're filtered out anyway.
        """
        sub_values = self.data.iloc[row_indices].values

        row_linkage, row_leaves = self._subset_axis_linkage(sub_values, dist_type, linkage_type)
        col_linkage, col_leaves = self._subset_axis_linkage(sub_values.T, dist_type, linkage_type)
        if row_linkage is None or col_linkage is None:
            return None

        n_rows, n_cols = self.data.shape

        row_position = {leaf: position for position, leaf in enumerate(row_leaves)}
        row_clust = [0] * n_rows
        for local_index, raw_index in enumerate(row_indices):
            row_clust[raw_index] = row_position.get(local_index, local_index) + 1

        col_position = {leaf: position for position, leaf in enumerate(col_leaves)}
        col_clust = [col_position.get(index, index) + 1 for index in range(n_cols)]

        return {
            "row_indices": list(row_indices),
            "row_clust": row_clust,
            "col_clust": col_clust,
            "row_linkage": _serialize_linkage(row_linkage),
            "col_linkage": _serialize_linkage(col_linkage),
        }

    def _build_views(
        self,
        view: str,
        levels: list[int] | None,
        dist_type: str,
        linkage_type: str,
    ) -> list[dict[str, Any]]:
        """Precompute one independently re-biclustered view per requested level."""
        view_type = view
        self._validate_view_type(view_type)

        is_marker_view = view_type == "rank_genes_groups"
        level_unit = "per_cluster" if is_marker_view else "rows"

        n_rows = self.data.shape[0]
        requested = list(levels) if levels is not None else self._default_levels_for(view_type)
        usable_levels = sorted({int(level) for level in requested if int(level) >= 1})

        position = {name: index for index, name in enumerate(self.data.index.astype(str))}

        built: list[dict[str, Any]] = []
        seen_row_sets: set[tuple[int, ...]] = set()

        for level in usable_levels:
            row_indices = tuple(
                sorted(
                    position[name]
                    for name in self._row_names_for_level(view_type, level)
                    if name in position
                )
            )

            # Too small to cluster, or already the whole matrix — which is the
            # slider's "all" stop and needs no precomputing.
            if len(row_indices) < MIN_VIEW_ROWS or len(row_indices) >= n_rows:
                continue

            # Levels can collapse onto the same rows — asking for 25 markers per
            # cluster when each cluster only has 12, say. Keep the finest level
            # that produced them instead of exporting duplicate slider stops.
            if row_indices in seen_row_sets:
                continue
            seen_row_sets.add(row_indices)

            view = self._cluster_subset(list(row_indices), dist_type, linkage_type)
            if view is None:
                warnings.warn(
                    f"Clustering failed for the '{view_type}' view at level {level}; skipping.",
                    UserWarning,
                    stacklevel=3,
                )
                continue

            view["view_type"] = view_type
            view["level"] = level
            view["level_unit"] = level_unit
            view["n_rows"] = len(row_indices)
            built.append(view)

        if not built:
            unit = "markers per cluster" if is_marker_view else "rows"
            warnings.warn(
                f"No requested view level ({unit}) yields a usable subset of this "
                f"{n_rows}-row matrix; skipping views.",
                UserWarning,
                stacklevel=3,
            )

        return built

    def make_viz(self) -> None:
        """Generate visualization data structure."""
        if self.data is None:
            raise ValueError(ERRORS["no_data"])

        # Rebuild node_info from current row_attr/col_attr and metadata. Without this,
        # cached dat can stay stale after mutating attr lists (e.g. appending a column
        # name after add_category), so exported row_nodes/col_nodes miss cat-* keys.
        self._dat_cache = None
        self._dirty_flags[CacheLevel.DATA.value] = True

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

    def cut_tree(
        self,
        axis: AxisInput = "row",
        n_clusters: int | None = None,
        threshold: float | None = None,
        criterion: str | None = None,
    ) -> pd.Series:
        """Cut the dendrogram into flat cluster labels.

        Cuts the hierarchical clustering linkage (computed by :meth:`cluster`) along
        one axis and returns a label per row/column. Use ``n_clusters`` to request
        a fixed number of clusters (``fcluster`` with ``criterion="maxclust"``) or
        ``threshold`` to cut at a linkage distance (``criterion="distance"``).
        Exactly one of the two must be given. ``criterion`` can override the
        inferred SciPy criterion, but it does not replace the cut value.

        This is the programmatic counterpart to the Clustergram's interactive
        dendrogram slider: it turns a clustered Matrix into discrete groups (e.g.
        consensus domains, meta-clusters) that can be attached back to an
        AnnData's ``obs`` / ``var``.

        Args:
            axis: ``"row"``/``"col"`` (or ``0``/``1``) — which dendrogram to cut.
            n_clusters: Target number of flat clusters (``maxclust`` criterion).
            threshold: Linkage-distance cutoff (``distance`` criterion).
            criterion: Explicit ``scipy`` ``fcluster`` criterion; overrides the
                ``n_clusters``/``threshold`` inference when given (paired with
                whichever of the two is supplied as ``t``).

        Returns:
            A ``pd.Series`` of integer cluster labels indexed by the axis names
            (``data.index`` for rows, ``data.columns`` for columns), in data order.

        Raises:
            ValueError: If the matrix is unclustered, the linkage is empty, or
                not exactly one of ``n_clusters`` or ``threshold`` is provided.
        """
        from scipy.cluster.hierarchy import fcluster

        if self.data is None:
            raise ValueError(ERRORS["no_data"])
        if (n_clusters is None) == (threshold is None):
            raise ValueError("provide exactly one of `n_clusters` or `threshold`")
        axis_enum = Axis.normalize(axis)
        linkage_data = self.viz["linkage"].get(axis_enum.value)
        if not linkage_data:
            raise ValueError(
                f"no linkage for axis '{axis_enum.value}'; call .cluster() before .cut_tree()"
            )

        linkage_matrix = np.array(linkage_data)
        if n_clusters is not None:
            labels = fcluster(linkage_matrix, t=n_clusters, criterion=criterion or "maxclust")
        elif threshold is not None:
            labels = fcluster(linkage_matrix, t=threshold, criterion=criterion or "distance")
        names = self.data.index if axis_enum == Axis.ROW else self.data.columns
        return pd.Series(labels, index=names.copy(), name="cluster")

    def to_cluster(
        self,
        axis: AxisInput = "row",
        n_clusters: int | None = None,
        threshold: float | None = None,
        criterion: str | None = None,
    ) -> pd.Series:
        """Deprecated alias for :meth:`cut_tree`."""
        warnings.warn(
            "`Matrix.to_cluster()` is deprecated; use `Matrix.cut_tree()`.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.cut_tree(
            axis=axis,
            n_clusters=n_clusters,
            threshold=threshold,
            criterion=criterion,
        )

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

        Examples:
            >>> mat = Matrix(adata)
            >>> mat.downsample_to("leiden")
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

    def _marker_groups(self) -> dict[str, list[str]]:
        """Each group's markers, best first, restricted to rows in the matrix."""
        available = set(self.data.index.astype(str))

        per_group: dict[str, list[str]] = {}
        for group, frame in self._marker_ranks.groupby("group", observed=True, sort=True):
            genes = [
                str(name)
                for name in frame.sort_values("rank")["names"].tolist()
                if str(name) in available
            ]
            if genes:
                per_group[str(group)] = genes

        return per_group

    def _marker_row_names(self, per_cluster: int) -> list[str]:
        """Union of each group's top `per_cluster` markers.

        Collected round-robin (every group's best, then every group's
        second-best, ...) and de-duplicated, so a gene that is a top marker for
        two clusters appears once and successive levels nest: raising the level
        only ever adds rows.
        """
        per_group = self._marker_groups()

        ordered: list[str] = []
        seen: set[str] = set()
        for index in range(per_cluster):
            for genes in per_group.values():
                if index >= len(genes):
                    continue
                gene = genes[index]
                if gene not in seen:
                    seen.add(gene)
                    ordered.append(gene)

        return ordered

    def _metric_row_names(self, by: FilterType, n_rows: int) -> list[str]:
        """Top `n_rows` row names by a per-row metric ('sum'/'mean'/'var')."""
        metric = compute_metric(self.data, by, axis=1)
        ranked = pd.Series(metric, index=self.data.index).sort_values(ascending=False)
        return [str(name) for name in ranked.index[:n_rows]]

    def _require_marker_ranks(self) -> None:
        if self._marker_ranks is None or self._marker_ranks.empty:
            raise ValueError(
                "view='rank_genes_groups' needs differential expression results. "
                "Build the Matrix with Matrix(adata, groupby=..., rank_genes_groups=True), "
                "or pass an AnnData carrying scanpy rank_genes_groups results -- "
                "or pick a view that needs no groups, e.g. view='var' / view='sum'."
            )

    def _validate_view_type(self, view_type: str) -> None:
        if view_type == "rank_genes_groups":
            self._require_marker_ranks()
            return
        if view_type not in {"var", "sum", "mean"}:
            raise ValueError(
                f"unknown view type {view_type!r}; expected one of "
                "'rank_genes_groups', 'var', 'sum', 'mean'"
            )

    def _row_names_for_level(self, view_type: str, level: int) -> list[str]:
        """Rows kept at one view level.

        `level` means top markers **per cluster** for ``rank_genes_groups`` and
        total rows for the metric rankings -- see `cluster`'s `levels` argument.
        """
        if view_type == "rank_genes_groups":
            return self._marker_row_names(level)
        return self._metric_row_names(view_type, level)

    def _default_levels_for(self, view_type: str) -> list[int]:
        return list(
            DEFAULT_MARKER_VIEW_LEVELS if view_type == "rank_genes_groups" else DEFAULT_VIEW_LEVELS
        )

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
                "Matrix not clustered. Call cluster() first.",
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

    def set_size_matrix(self, size: pd.DataFrame | np.ndarray | AnnData | Matrix) -> Matrix:
        """Attach a secondary matrix that drives size encoding.

        The values are interpreted as a per-cell size channel (typically the
        fraction of cells in a cluster expressing a gene, in ``[0, 1]``) that is
        rendered as square/dot size in a dot-plot :class:`~celldega.viz.Clustergram`,
        independently of the main matrix which continues to drive color/opacity
        and the clustering order.

        The size matrix is aligned to the main matrix **by row and column name** at
        export time, so it does not need to share the clustered ordering — only
        the same labels. Missing entries become ``0`` (no dot).

        Args:
            size: A ``DataFrame`` indexed by row names with columns of column
                names, a 2D array matching the main matrix shape/order, an
                ``AnnData`` (``X`` with ``obs_names`` rows / ``var_names`` cols),
                or another ``Matrix``.

        Returns:
            ``self`` (to allow chaining, e.g. ``Matrix(df).set_size_matrix(frac)``).
        """
        if isinstance(size, Matrix):
            size = pd.DataFrame(
                size.dat["mat"],
                index=size.dat["nodes"][Axis.ROW.value],
                columns=size.dat["nodes"][Axis.COL.value],
            )
        elif isinstance(size, AnnData):
            # Transposed to match `load_adata`'s convention for the main matrix
            # (features/var as rows, cells-or-sets/obs as columns) — without
            # this, `X`'s natural obs x var orientation is exactly backwards
            # from the main matrix's row/col names and `reindex` silently
            # aligns nothing (see `export_viz_parquet`).
            values = size.X.toarray() if hasattr(size.X, "toarray") else np.asarray(size.X)
            size = pd.DataFrame(
                values.T,
                index=size.var_names.astype(str),
                columns=size.obs_names.astype(str),
            )
        elif not isinstance(size, pd.DataFrame):
            arr = np.asarray(size)
            row_names = self.dat["nodes"][Axis.ROW.value]
            col_names = self.dat["nodes"][Axis.COL.value]
            if arr.shape != (len(row_names), len(col_names)):
                raise ValueError(
                    "dot array shape "
                    f"{arr.shape} does not match matrix shape "
                    f"{(len(row_names), len(col_names))}; pass a DataFrame to align by name"
                )
            size = pd.DataFrame(arr, index=row_names, columns=col_names)

        self.size_matrix = size
        return self

    def set_dot_matrix(self, dot: pd.DataFrame | np.ndarray | AnnData | Matrix) -> Matrix:
        """Deprecated alias for :meth:`set_size_matrix`."""
        warnings.warn(
            "`Matrix.set_dot_matrix()` is deprecated; use `Matrix.set_size_matrix()`.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.set_size_matrix(dot)

    @property
    def dot_mat(self) -> pd.DataFrame | None:
        """Deprecated alias for :attr:`size_matrix`."""
        warnings.warn(
            "`Matrix.dot_mat` is deprecated; use `Matrix.size_matrix`.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.size_matrix

    @dot_mat.setter
    def dot_mat(self, value: pd.DataFrame | None) -> None:
        warnings.warn(
            "`Matrix.dot_mat` is deprecated; use `Matrix.size_matrix`.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.size_matrix = value

    def export_viz_parquet(self) -> dict[str, bytes | str]:
        """Export visualization using Parquet encoded tables."""
        if not self._clustered:
            warnings.warn(
                "Matrix not clustered. Call cluster() first.",
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

        row_names = self.dat["nodes"][Axis.ROW.value]
        col_names = self.dat["nodes"][Axis.COL.value]

        mat_df = pd.DataFrame(
            self.dat["mat"],
            index=row_names,
            columns=col_names,
        ).reset_index(names="row")

        # Optional dot-size matrix, aligned to the main matrix order by name so it
        # lines up cell-for-cell in the front-end (fraction expressing, etc.).
        dot_bytes = b""
        if self.size_matrix is not None:
            dot_aligned = (
                self.size_matrix.reindex(index=row_names, columns=col_names)
                .astype("float32")
                .fillna(0.0)
            )
            dot_bytes = _to_bytes(dot_aligned.reset_index(names="row"))

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
            "dot_mat": dot_bytes,
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
        >>> mat.cluster()
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
        cgm_name = name or self._data_hash_name or "default"

        # Create output directory
        cgm_dir = PathLib(path) / "cgm" / cgm_name
        cgm_dir.mkdir(parents=True, exist_ok=True)

        # Get parquet data
        pq_data = self.export_viz_parquet()

        # Write parquet files
        (cgm_dir / "mat.parquet").write_bytes(pq_data["mat"])
        if pq_data.get("dot_mat"):
            (cgm_dir / "dot_mat.parquet").write_bytes(pq_data["dot_mat"])
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

    def to_clustered_adata(self, *, dtype: Any = None) -> AnnData:
        """Package the clustered Matrix as an AnnData, ready to write to Zarr.

        The AnnData has the Clustergram's columns as observations and its rows
        as variables (the orientation ``Matrix(adata)`` reads): matrix values in
        ``X``, the optional size matrix in ``layers["size"]``, dendrogram orders
        in ``obsm``/``varm["celldega_nodes"]``, and linkages, views, colors,
        attributes, and entities in ``uns["celldega"]``.
        :meth:`from_clustered_adata` restores the Matrix without re-clustering.

        Args:
            dtype: Data type of ``X`` and the size layer. Defaults to the
                Matrix's own.

        Raises:
            ValueError: If the Matrix has not been clustered.
        """
        if self.data is None or not self._clustered:
            raise ValueError("Call cluster() before saving the Matrix.")

        rows = pd.Index(self.data.index.astype(str))
        cols = pd.Index(self.data.columns.astype(str))
        x_dtype = np.dtype(dtype) if dtype is not None else self.data.values.dtype
        var, var_object_columns = _writable_meta(self.meta_row, rows)
        obs, obs_object_columns = _writable_meta(self.meta_col, cols)

        adata = AnnData(X=np.ascontiguousarray(self.data.values.T, dtype=x_dtype), obs=obs, var=var)
        if self.size_matrix is not None:
            size = self.size_matrix.reindex(index=self.data.index, columns=self.data.columns)
            adata.layers["size"] = np.ascontiguousarray(size.fillna(0.0).values.T, dtype=x_dtype)
        adata.varm[_STORE_NODES_KEY] = _nodes_frame(self.viz["row_nodes"], rows)
        adata.obsm[_STORE_NODES_KEY] = _nodes_frame(self.viz["col_nodes"], cols)

        meta = {
            "format": _STORE_FORMAT,
            "version": _STORE_VERSION,
            "row_entity": self.row_entity,
            "col_entity": self.col_entity,
            "row_attr": list(self.row_attr),
            "col_attr": list(self.col_attr),
            "row_cats": list(self.row_cats),
            "col_cats": list(self.col_cats),
            "var_object_columns": var_object_columns,
            "obs_object_columns": obs_object_columns,
            "is_downsampled": bool(self.is_downsampled),
            "has_size_matrix": self.size_matrix is not None,
            "source_global_cat_colors": dict(self._source_global_cat_colors),
            "viz": {key: self.viz.get(key) for key in _STORE_VIZ_KEYS},
            "views": [{key: view[key] for key in _STORE_VIEW_SCALARS} for view in self.views],
        }
        store: dict[str, Any] = {
            # One JSON document: AnnData's uns cannot hold lists of dicts, keys
            # containing "/" (category values such as "T/NK"), or key order.
            "meta_json": json.dumps(_json_native(meta)),
            # Lets a plain Matrix(adata) pick up the entities as well.
            "axis_entities": {
                "row_entity": dict(self.row_entity),
                "col_entity": dict(self.col_entity),
            },
            "linkage": {
                axis: np.asarray(self.viz["linkage"][axis], dtype=np.float64).reshape(-1, 4)
                for axis in ("row", "col")
            },
        }
        if self.views:
            # Five arrays for any number of views; each view's n_rows (in
            # meta_json) gives the split points of the concatenated row arrays.
            store["views"] = {
                "row_indices": np.concatenate(
                    [np.asarray(view["row_indices"], dtype=np.int32) for view in self.views]
                ),
                "row_clust": np.asarray([view["row_clust"] for view in self.views], dtype=np.int32),
                "col_clust": np.asarray([view["col_clust"] for view in self.views], dtype=np.int32),
                "row_linkage": np.concatenate(
                    [
                        np.asarray(view["row_linkage"], dtype=np.float64).reshape(-1, 4)
                        for view in self.views
                    ]
                ),
                "col_linkage": np.asarray(
                    [view["col_linkage"] for view in self.views], dtype=np.float64
                ),
            }
        adata.uns["celldega"] = store
        if self._marker_ranks is not None and not self._marker_ranks.empty:
            adata.uns["marker_ranks"] = marker_ranks_to_uns(self._marker_ranks)
        return adata

    @classmethod
    def from_clustered_adata(cls, adata: AnnData) -> Matrix:
        """Restore a clustered Matrix from :meth:`to_clustered_adata`'s AnnData.

        Nothing is re-clustered: dendrograms, orders, views, and colors are read
        back as saved, so the result can go straight to ``Clustergram(matrix=...)``.

        Raises:
            ValueError: If ``adata`` does not hold a supported clustered Matrix.
        """
        store = adata.uns.get("celldega", {})
        meta = json.loads(str(store["meta_json"])) if "meta_json" in store else {}
        if meta.get("format") != _STORE_FORMAT or int(meta.get("version", 0)) > _STORE_VERSION:
            raise ValueError(
                "adata does not hold a supported clustered Matrix (see Matrix.write_zarr)."
            )

        rows = pd.Index(adata.var_names.astype(str))
        cols = pd.Index(adata.obs_names.astype(str))
        mat = cls(
            name=meta["viz"]["name"],
            row_entity=meta["row_entity"],
            col_entity=meta["col_entity"],
        )
        mat.data = pd.DataFrame(_dense(adata.X).T, index=rows, columns=cols)
        mat.meta_row = _restored_meta(adata.var, meta["var_object_columns"])
        mat.meta_col = _restored_meta(adata.obs, meta["obs_object_columns"])
        mat.row_attr, mat.col_attr = meta["row_attr"], meta["col_attr"]
        mat.row_cats, mat.col_cats = meta["row_cats"], meta["col_cats"]
        mat.is_downsampled = bool(meta["is_downsampled"])
        mat._source_global_cat_colors = dict(meta["source_global_cat_colors"])
        if "size" in adata.layers:
            mat.size_matrix = pd.DataFrame(_dense(adata.layers["size"]).T, index=rows, columns=cols)
        markers = marker_ranks_from_uns(adata.uns.get("marker_ranks"))
        if markers is not None:
            # Zarr returns uns keys sorted; restore the frame's column order.
            first = [column for column in _MARKER_RANK_COLUMNS if column in markers.columns]
            markers = markers[first + [c for c in markers.columns if c not in first]]
        mat._marker_ranks = markers

        views = []
        packed = store.get("views", {})
        row_start = 0
        for index, description in enumerate(meta["views"]):
            n_rows = int(description["n_rows"])
            link_start = row_start - index  # previous views contribute n_rows - 1 merges each
            views.append(
                {
                    "row_indices": np.asarray(
                        packed["row_indices"][row_start : row_start + n_rows]
                    ).tolist(),
                    "row_clust": np.asarray(packed["row_clust"][index]).tolist(),
                    "col_clust": np.asarray(packed["col_clust"][index]).tolist(),
                    "row_linkage": np.asarray(
                        packed["row_linkage"][link_start : link_start + n_rows - 1]
                    ).tolist(),
                    "col_linkage": np.asarray(packed["col_linkage"][index]).tolist(),
                    **description,
                }
            )
            row_start += n_rows

        viz = copy.deepcopy(DEFAULT_VIZ)
        viz["linkage"] = {
            axis: np.asarray(store["linkage"][axis]).tolist() for axis in ("row", "col")
        }
        viz["row_nodes"] = _nodes_records(adata.varm[_STORE_NODES_KEY])
        viz["col_nodes"] = _nodes_records(adata.obsm[_STORE_NODES_KEY])
        # The same list objects as the Matrix attributes, as set_global_cat_colors leaves them.
        viz["row_cats"], viz["col_cats"] = mat.row_cats, mat.col_cats
        viz["row_attr"], viz["col_attr"] = mat.row_attr, mat.col_attr
        viz["views"] = mat.views = views
        mat.viz = viz

        # Building `dat` rewrites viz[*_attr_maxabs], so build it first and
        # restore the saved values after.
        mat._invalidate_cache(CacheLevel.DATA.value)
        dat = mat.dat
        for key in _STORE_VIZ_KEYS:
            viz[key] = copy.deepcopy(meta["viz"][key])
        viz["mat"] = dat["mat"].tolist()
        mat._clustered = True
        return mat

    def write_zarr(self, store: Any, *, dtype: Any = "float32", zarr_format: int = 3) -> None:
        """Write the clustered Matrix to an AnnData Zarr store (experimental).

        The store keeps everything a Clustergram needs: :meth:`read_zarr` loads
        it back without re-clustering for ``Clustergram(matrix=...)``, and the
        JavaScript ``matrix_from_zarr`` renders it in a browser. It is also a
        regular AnnData store that ``anndata.read_zarr`` opens.

        Args:
            store: Path or zarr store to write to.
            dtype: Data type of the matrix values and size layer. Defaults to
                float32, the precision the Clustergram displays; ``None``
                keeps the Matrix's own.
            zarr_format: Zarr format version, 3 (default) or 2.

        Examples:
            >>> mat.cluster(view="rank_genes_groups")
            >>> mat.write_zarr("pbmc_markers.zarr")
            >>> cgm = Clustergram(matrix=Matrix.read_zarr("pbmc_markers.zarr"))
        """
        import anndata as ad
        import zarr

        adata = self.to_clustered_adata(dtype=dtype)
        band_bytes = max(adata.n_vars * adata.X.dtype.itemsize, 1)
        chunk_rows = max(1, min(adata.n_obs, _STORE_CHUNK_BYTES // band_bytes))
        # Write chunks even when they hold only the fill value, so hosts that
        # answer 403 rather than 404 for missing files serve every chunk.
        with (
            ad.settings.override(zarr_write_format=zarr_format, auto_shard_zarr_v3=False),
            zarr.config.set({"array.write_empty_chunks": True}),
        ):
            ad.io.write_zarr(
                store,
                adata,
                chunks=(chunk_rows, adata.n_vars),
                convert_strings_to_categoricals=False,
            )

    @classmethod
    def read_zarr(cls, store: Any) -> Matrix:
        """Read a clustered Matrix written by :meth:`write_zarr` (experimental)."""
        import anndata as ad

        return cls.from_clustered_adata(ad.read_zarr(store))

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
            color_mapping = dict(self._source_global_cat_colors)

            for meta_df, cat_list in (
                (self.meta_row, self.row_cats),
                (self.meta_col, self.col_cats),
            ):
                if meta_df is not None and not meta_df.empty:
                    # If metadata has a 'color' column, use index -> color mapping
                    if "color" in meta_df.columns:
                        for idx, color in zip(meta_df.index, meta_df["color"], strict=False):
                            color_mapping.setdefault(str(idx), color)

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
