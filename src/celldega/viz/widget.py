"""Widget module for interactive visualization components."""

from collections.abc import Sequence
import colorsys
from contextlib import suppress
from copy import deepcopy
import importlib.metadata
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Literal
import urllib.error
from urllib.parse import urlparse
import uuid
import warnings

import anywidget
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.affinity import affine_transform
import traitlets


_clustergram_registry = {}  # maps names to widget instances
_enrich_registry = {}  # maps names to widget instances

_LOCAL_ESM = Path(__file__).parent / "../static" / "celldega.js"
_ESM_CDN = "https://cdn.jsdelivr.net/npm/celldega@{version}/src/celldega/static/celldega.js"


def _resolve_widget_esm() -> "Path | str":
    """Front-end module for the celldega anywidgets.

    Returns the local ``celldega.js`` for development (anywidget inlines it into
    the widget state on save), or a tiny ESM shim that imports the published
    bundle from jsdelivr otherwise. The shim is what lets saved widget state stay
    small: instead of embedding the ~10 MB bundle once per widget, each widget
    stores ~80 bytes and the browser fetches/caches the CDN bundle a single time,
    reused across every widget and notebook.

    Resolution order:
      1. ``CELLDEGA_LOCAL_ESM`` or ``ANYWIDGET_HMR`` set -> local file (dev / HMR).
      2. ``CELLDEGA_ESM_VERSION`` env var               -> CDN at that version.
      3. installed version, if a clean ``X.Y.Z`` release -> CDN at that version.
      4. otherwise (dev / unpublished, e.g. ``0.16.0a1``) -> local file (safe,
         self-contained, since that version may not be on the CDN).
    """
    if os.environ.get("CELLDEGA_LOCAL_ESM") or os.environ.get("ANYWIDGET_HMR"):
        return _LOCAL_ESM
    version = os.environ.get("CELLDEGA_ESM_VERSION", "")
    if not version:
        try:
            candidate = importlib.metadata.version("celldega")
        except importlib.metadata.PackageNotFoundError:
            candidate = ""
        version = candidate if re.fullmatch(r"\d+\.\d+\.\d+", candidate) else ""
    if not version:
        return _LOCAL_ESM
    return f"export {{ default }} from '{_ESM_CDN.format(version=version)}';"


_WIDGET_ESM = _resolve_widget_esm()

_DEFAULT_MANUAL_ATTRIBUTE_TITLES = {
    "row": "manual_cat",
    "col": "manual_cat",
}
_MANUAL_FILL_VALUE = "N.A."
_DEFAULT_NBHD_COLOR = "#4f80ff"


def _hsv_to_hex(h: float) -> str:
    """Convert HSV color to hex string."""
    r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.9)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _selection_to_payload(selection) -> dict:
    """Normalize a selector result into a JSON-ready payload with ordered ids."""
    if hasattr(selection, "to_json"):
        payload = selection.to_json()
    elif hasattr(selection, "to_dict"):
        payload = selection.to_dict()
    elif isinstance(selection, dict):
        payload = dict(selection)
    else:
        payload = {}

    if "ids" not in payload:
        if hasattr(selection, "names"):
            payload["ids"] = selection.names()
        elif isinstance(selection, Sequence) and not isinstance(selection, str):
            payload["ids"] = list(selection)
        else:
            raise TypeError(
                "`selection` must be a celldega.select.Selection, "
                "a JSON-like selection dict, or a sequence of cell ids."
            )

    ids = payload["ids"]
    if isinstance(ids, str) or not isinstance(ids, Sequence):
        raise TypeError("`selection` ids must be a sequence of cell ids.")

    payload["ids"] = [str(name) for name in ids]
    return payload


def _local_dir_for_url(url: str) -> "Path | None":
    """Filesystem directory backing a ``base_url`` served by
    ``celldega.viz.get_local_server()`` (rooted at the caller's cwd), or
    ``None`` if ``url`` isn't a localhost URL. Used to write a small sidecar
    file (e.g. centroid overrides) that the same local server can then serve
    back over HTTP, rather than syncing large per-cell data through the
    widget's comm channel (which doesn't scale to millions of rows).
    """
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        return None
    local_dir = Path(parsed.path.lstrip("/"))
    return local_dir if local_dir.is_dir() else None


def _coerce_transform_matrix(transform: Any) -> np.ndarray:
    matrix = np.asarray(transform, dtype=float)
    if matrix.shape == (2, 3):
        matrix = np.vstack([matrix, [0.0, 0.0, 1.0]])
    if matrix.shape != (3, 3):
        raise ValueError("transform must be a 3x3 homogeneous matrix or a 2x3 affine matrix")
    return matrix


def _metadata_from_nbhd_like(nbhd_like: Any) -> pd.DataFrame | None:
    obs = getattr(nbhd_like, "obs", None)
    if isinstance(obs, pd.DataFrame):
        meta = obs.copy()
        meta.index = meta.index.astype(str)
        return meta
    return None


def _geometry_from_nbhd_like(nbhd_like: Any) -> gpd.GeoDataFrame | None:
    geometry = getattr(nbhd_like, "geometry", None)
    if isinstance(geometry, gpd.GeoDataFrame):
        return geometry.copy()

    gdf = getattr(nbhd_like, "gdf", None)
    if isinstance(gdf, gpd.GeoDataFrame):
        return gdf.copy()

    return None


def _coerce_nbhd_for_landscape(
    nbhd_like: Any,
    meta_nbhd: pd.DataFrame | None = None,
) -> tuple[gpd.GeoDataFrame | None, pd.DataFrame | None]:
    """Coerce GeoDataFrame, NeighborhoodCollection, or legacy NBHD inputs."""
    if nbhd_like is None:
        return None, meta_nbhd

    collection = getattr(nbhd_like, "collection", None)
    if collection is not None:
        nbhd_like = collection

    if isinstance(nbhd_like, gpd.GeoDataFrame):
        gdf = nbhd_like.copy()
        inferred_meta = None
        prefer_meta_columns = False
    else:
        gdf = _geometry_from_nbhd_like(nbhd_like)
        inferred_meta = _metadata_from_nbhd_like(nbhd_like)
        prefer_meta_columns = True
        if gdf is None:
            raise TypeError(
                "nbhd must be a GeoDataFrame, NeighborhoodCollection, or legacy NBHD object"
            )

    if meta_nbhd is None and inferred_meta is not None:
        meta_nbhd = inferred_meta

    gdf = gdf.copy()
    if gdf.index is not None:
        gdf.index = gdf.index.astype(str)

    if "name" not in gdf.columns:
        if "neighborhood_id" in gdf.columns:
            gdf["name"] = gdf["neighborhood_id"].astype(str)
        elif "nbhd_id" in gdf.columns:
            gdf["name"] = gdf["nbhd_id"].astype(str)
        else:
            gdf["name"] = gdf.index.astype(str)
    else:
        gdf["name"] = gdf["name"].astype(str)

    if isinstance(meta_nbhd, pd.DataFrame):
        meta_nbhd = meta_nbhd.copy()
        meta_nbhd.index = meta_nbhd.index.astype(str)
        meta_by_name = meta_nbhd.reindex(gdf["name"].astype(str))
        for col in meta_by_name.columns:
            if prefer_meta_columns or col not in gdf.columns:
                gdf[col] = meta_by_name[col].to_numpy()

    if "cat" not in gdf.columns:
        gdf["cat"] = gdf["name"]
    gdf["cat"] = gdf["cat"].fillna(gdf["name"]).astype(str)

    if "color" not in gdf.columns:
        gdf["color"] = _DEFAULT_NBHD_COLOR
    gdf["color"] = gdf["color"].fillna(_DEFAULT_NBHD_COLOR).astype(str)

    if "area" not in gdf.columns:
        gdf["area"] = gdf.geometry.area
    gdf["area"] = pd.to_numeric(gdf["area"], errors="coerce").fillna(0)

    return gdf, meta_nbhd


class Landscape(anywidget.AnyWidget):
    """
    A widget for interactive visualization of spatial omics data. This widget
    currently supports segmented spatial transcriptomics data (Xenium, MERSCOPE,
    Visium HD) and H&E image data.

    Args:
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        rotation_orbit (float, optional): Rotating angle around orbit axis for
            point-cloud views.
        rotation_x (float, optional): Rotating angle around X axis for
            point-cloud views.
        token (str): The token traitlet.
        base_url (str or list): The base URL(s) for the widget. Can be a single string
            or a list of dicts with 'url' and 'label' keys for multiple datasets.
            Example: [{'url': 'http://...', 'label': 'Dataset1'}, ...]
            You can also pass a simple list of URL strings.
        dataset_names (list, optional): Short names for the datasets to display in
            the dropdown selector. Should match the length of base_urls.
            Example: ['Brain', 'Kidney'] for two datasets.
        rotate (float, optional): Degrees to rotate the 2D landscape visualization.
        AnnData (AnnData, optional): AnnData object to derive metadata from.
        dataset_name (str, optional): The name of the dataset to visualize. This
            will show up in the user interface bar.
        cell_name_prefix (bool, optional): If True, cell names in adata.obs.index
            are assumed to have a dataset prefix (e.g., "dataset-name_cell-name")
            that should be trimmed when mapping to LandscapeFiles. Default: False.
        use_adata_3d_centroids (bool, optional): For ``technology="point-cloud"``
            views given an ``adata``, render that AnnData's
            ``obsm["spatial"]``/``obs[z_key]`` centroids instead of the geometry
            baked into ``cell_metadata.parquet`` — no DegaFiles rewrite needed to
            preview a candidate alignment. Has no effect on 2D (non point-cloud)
            views, which always use the on-disk x/y. Default: True.
        z_key (str, optional): ``adata.obs`` column holding the Z coordinate used
            for ``use_adata_3d_centroids`` (falls back to 0 if absent). Default:
            "Z".

    ``use_adata_3d_centroids`` writes centroids to a small file next to
    ``base_url`` and fetches it over HTTP when ``base_url`` is a local
    ``celldega.viz.get_local_server()`` address (millions of per-cell
    centroids don't fit through the widget's comm channel); otherwise it
    falls back to syncing them directly through the widget state, which is
    fine for smaller datasets.

    A point-cloud (3D) view requires a real, pre-built DegaFiles ``base_url``
    like any other technology — build one with the ``celldega.pre`` module
    (e.g. after running an alignment with
    :func:`~celldega.align.serial_slices.align_serial_slices`, regenerate
    LandscapeFiles from the aligned ``AnnData`` before visualizing it).
    ``adata`` here is only ever used for cell attributes/metadata, never for
    spatial positions.

    The AnnData input automatically extracts cell attributes (e.g., ``leiden``
    clusters), the corresponding colors (or derives them when missing), and any
    available UMAP coordinates.
    """

    _esm = _WIDGET_ESM
    component = traitlets.Unicode("Landscape").tag(sync=True)

    technology = traitlets.Unicode("Xenium").tag(sync=True)
    base_url = traitlets.Unicode("").tag(sync=True)
    # List of dataset configurations: [{'url': str, 'label': str}, ...]
    base_urls = traitlets.List(trait=traitlets.Dict(), default_value=[]).tag(sync=True)
    cell_name_prefix = traitlets.Bool(False).tag(sync=True)
    token = traitlets.Unicode("").tag(sync=True)
    creds = traitlets.Dict({}).tag(sync=True)
    max_tiles_to_view = traitlets.Int(50).tag(sync=True)

    ini_x = traitlets.Float().tag(sync=True)
    ini_y = traitlets.Float().tag(sync=True)
    ini_z = traitlets.Float().tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    rotation_orbit = traitlets.Float(0).tag(sync=True)
    rotation_x = traitlets.Float(0).tag(sync=True)
    rotate = traitlets.Float(0).tag(sync=True)
    dataset_name = traitlets.Unicode("").tag(sync=True)
    region = traitlets.Dict({}).tag(sync=True)
    scale_bar_microns_per_pixel = traitlets.Float(default_value=None, allow_none=True).tag(
        sync=True
    )

    nbhd = traitlets.Instance(gpd.GeoDataFrame, allow_none=True)
    nbhd_geojson = traitlets.Dict({}).tag(sync=True)

    # Enable editing of neighborhoods when True
    nbhd_edit = traitlets.Bool(False).tag(sync=True)

    meta_nbhd = traitlets.Instance(pd.DataFrame, allow_none=True)

    meta_cluster = traitlets.Dict({}).tag(sync=True)
    selected_cells = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)
    landscape_state = traitlets.Unicode("spatial").tag(sync=True)

    update_trigger = traitlets.Dict().tag(sync=True)
    cell_clusters = traitlets.Dict({}).tag(sync=True)

    # AnnData obs columns (cell attributes)
    cell_attr = traitlets.List(
        trait=traitlets.Unicode(),
        default_value=["leiden"],
    ).tag(sync=True)

    # obs column driving the cluster color legend/meta_cluster_parquet key field
    cluster_attr = traitlets.Unicode("leiden").tag(sync=True)

    segmentation = traitlets.Unicode("default").tag(sync=True)

    # Named alignment variant for point-cloud technology. When set, cell
    # positions are read from cell_metadata_<alignment>.parquet (written by
    # celldega.align.write_alignment_point_cloud) while clusters/genes keep
    # loading from their normal (segmentation-driven) paths.
    alignment = traitlets.Unicode("").tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(600).tag(sync=True)

    use_adata_3d_centroids = traitlets.Bool(True).tag(sync=True)
    centroids_url = traitlets.Unicode("").tag(sync=True)

    def __init__(self, **kwargs):
        adata = kwargs.pop("adata", None) or kwargs.pop("AnnData", None)
        pq_meta_cell = kwargs.pop("meta_cell_parquet", None)
        pq_meta_cluster = kwargs.pop("meta_cluster_parquet", None)
        pq_umap = kwargs.pop("umap_parquet", None)
        pq_meta_nbhd = kwargs.pop("meta_nbhd_parquet", None)
        pq_centroids = kwargs.pop("centroids_parquet", None)
        centroids_url = kwargs.pop("centroids_url", "")

        meta_cell_df = kwargs.pop("meta_cell", None)
        meta_cluster = kwargs.pop("meta_cluster", None)
        umap_df = kwargs.pop("umap", None)
        nbhd_gdf = kwargs.pop("nbhd", None)
        meta_nbhd_df = kwargs.pop("meta_nbhd", None)
        transform = kwargs.pop("transform", None)
        image_scale = kwargs.pop("image_scale", None)
        nbhd_edit = kwargs.pop("nbhd_edit", False)
        use_adata_3d_centroids = kwargs.get("use_adata_3d_centroids", True)
        z_key = kwargs.pop("z_key", "Z")
        meta_cluster_df = None
        # cell_attr = kwargs.pop("cell_attr", ["leiden"])
        cell_attr = list(kwargs.pop("cell_attr", ["leiden"]))
        # Attribute (obs column) that drives the cluster color legend. Defaults to
        # "leiden" for backward compatibility; set e.g. cluster_attr="cell_type" to
        # color by any categorical attribute.
        cluster_attr = kwargs.pop("cluster_attr", "leiden")
        if cluster_attr not in cell_attr:
            cell_attr.append(cluster_attr)

        nbhd_gdf, meta_nbhd_df = _coerce_nbhd_for_landscape(nbhd_gdf, meta_nbhd_df)

        # nbhd_edit can now be True even when nbhd data is provided,
        # allowing users to edit pre-loaded neighborhood polygons

        # Handle base_url which can be a string, list of strings, or list of dicts
        # Also accept base_urls directly for convenience
        raw_base_url = kwargs.pop("base_urls", None) or kwargs.get("base_url", "")
        # Optional dataset_names for short display names in dropdown
        dataset_names = kwargs.pop("dataset_names", None)
        base_urls_list = []

        if isinstance(raw_base_url, list):
            # Convert list to standardized format
            for i, item in enumerate(raw_base_url):
                if isinstance(item, dict):
                    # Already in dict format with 'url' and optionally 'label'
                    url = item.get("url", "")
                    label = item.get("label", f"Dataset {i + 1}")
                    short_label = item.get("short_label", f"DS-{i + 1}")
                    base_urls_list.append({"url": url, "label": label, "short_label": short_label})
                else:
                    # Just a string URL, create a label from the index
                    base_urls_list.append(
                        {
                            "url": str(item),
                            "label": f"Dataset {i + 1}",
                            "short_label": f"DS-{i + 1}",
                        }
                    )

            # Apply dataset_names if provided (overrides short_label)
            if dataset_names and isinstance(dataset_names, list):
                for i, name in enumerate(dataset_names):
                    if i < len(base_urls_list) and name:
                        base_urls_list[i]["short_label"] = str(name)
                        # Also use as label if label is default
                        if base_urls_list[i]["label"] == f"Dataset {i + 1}":
                            base_urls_list[i]["label"] = str(name)

            # Set the first URL as the primary base_url
            if base_urls_list:
                kwargs["base_url"] = base_urls_list[0]["url"]
            kwargs["base_urls"] = base_urls_list
        else:
            # Single string URL
            if raw_base_url:
                base_urls_list = [
                    {"url": raw_base_url, "label": "Dataset 1", "short_label": "DS-1"}
                ]
            kwargs["base_urls"] = base_urls_list

        base_path = (kwargs.get("base_url") or "") + "/"
        path_transformation_matrix = base_path + "micron_to_image_transform.csv"

        if transform is not None:
            transformation_matrix = _coerce_transform_matrix(transform)
        else:
            try:
                transformation_matrix = pd.read_csv(
                    path_transformation_matrix, header=None, sep=r"\s+"
                ).values
                transformation_matrix = _coerce_transform_matrix(transformation_matrix)
            except (FileNotFoundError, urllib.error.HTTPError, urllib.error.URLError):
                transformation_matrix = np.eye(3)  # Fallback for testing
                warnings.warn(
                    f"Transformation matrix not found at {path_transformation_matrix}. "
                    "Using identity.",
                    stacklevel=2,
                )

        if image_scale is not None:
            scale = float(image_scale)
            scale_matrix = np.array([[scale, 0.0, 0.0], [0.0, scale, 0.0], [0.0, 0.0, 1.0]])
            transformation_matrix = scale_matrix @ transformation_matrix

        self._transformation_matrix = transformation_matrix
        try:
            self._inv_transform = np.linalg.inv(transformation_matrix)
        except np.linalg.LinAlgError as e:
            self._inv_transform = np.eye(3)
            warnings.warn(
                f"Matrix inversion failed for transformation_matrix: {e}. "
                "Using identity matrix as fallback.",
                stacklevel=2,
            )

        def _df_to_bytes(df):
            import io

            import pyarrow as pa
            import pyarrow.parquet as pq

            df.columns = df.columns.map(str)
            buf = io.BytesIO()
            pq.write_table(pa.Table.from_pandas(df), buf, compression="zstd")
            return buf.getvalue()

        def _reset_index_for_parquet(df):
            index_name = df.index.name or "index"
            if index_name in df.columns:
                return df.reset_index(drop=True)
            return df.reset_index()

        # Get cell_name_prefix setting
        cell_name_prefix_setting = kwargs.get("cell_name_prefix", False)

        if adata is not None:
            # Never mutate the caller's AnnData. Derive cell metadata from a
            # copy/view of obs, and never call scanpy plotting (sc.pl.umap
            # writes `<attr>_colors` back into adata.uns).
            #
            # Key cell metadata by adata.obs_names (the canonical AnnData cell
            # identifier) — that's what matches the DegaFiles cell_metadata
            # `name` column. A `cell_id` obs *column* is intentionally NOT used
            # as the key: when its values differ from obs_names (e.g. a
            # reordered "cell__slice" form) it silently mismatches every cell,
            # so cluster coloring resolves to "N.A." and point-cloud cells cull.
            obs = adata.obs

            if "color" in obs.columns and "color" not in cell_attr:
                cell_attr.append("color")

            cell_attr = [c for c in cell_attr if c in obs.columns]
            meta_cell_df = obs[cell_attr].copy()

            if meta_cell_df.index.name is None:
                meta_cell_df.index.name = "cell_id"

            # If cell_name_prefix is True, trim the prefix from cell names
            # This allows mapping to LandscapeFiles which have short names
            if cell_name_prefix_setting:
                # Trim prefix before first underscore from index
                new_index = meta_cell_df.index.map(
                    lambda x: x.split("_", 1)[1] if "_" in str(x) else x
                )
                meta_cell_df.index = new_index

            pq_meta_cell = _df_to_bytes(meta_cell_df)

            if cluster_attr in obs.columns:
                cluster_counts = obs[cluster_attr].value_counts().sort_index()
                # Use the caller's stored palette if present, else a
                # deterministic HSV fallback — no scanpy call, so adata is left
                # untouched.
                colors = adata.uns.get(f"{cluster_attr}_colors")
                if colors is None:
                    n = len(cluster_counts)
                    colors = [_hsv_to_hex(i / n) for i in range(n)]

                meta_cluster_df = pd.DataFrame(
                    {
                        "color": list(colors)[: len(cluster_counts)],
                        "count": cluster_counts.values,
                    },
                    index=cluster_counts.index,
                )

                pq_meta_cluster = _df_to_bytes(meta_cluster_df)

            if "X_umap" in adata.obsm:
                umap_df = pd.DataFrame(adata.obsm["X_umap"], index=obs.index)

                # If cell_name_prefix is True, trim the prefix from cell names
                if cell_name_prefix_setting:
                    umap_df.index = umap_df.index.map(
                        lambda x: x.split("_", 1)[1] if "_" in str(x) else x
                    )

                umap_df = umap_df.reset_index().rename(
                    columns={"index": "cell_id", 0: "umap_0", 1: "umap_1"}
                )
                pq_umap = _df_to_bytes(umap_df)

            if use_adata_3d_centroids and "spatial" in adata.obsm:
                spatial_xy = np.asarray(adata.obsm["spatial"])[:, :2]
                z_values = (
                    adata.obs[z_key].to_numpy(dtype=float)
                    if z_key in adata.obs.columns
                    else np.zeros(adata.n_obs)
                )
                centroid_df = pd.DataFrame(
                    {"x": spatial_xy[:, 0], "y": spatial_xy[:, 1], "z": z_values},
                    index=adata.obs.index,
                )

                if cell_name_prefix_setting:
                    centroid_df.index = centroid_df.index.map(
                        lambda x: x.split("_", 1)[1] if "_" in str(x) else x
                    )

                centroid_df = centroid_df.reset_index().rename(columns={"index": "cell_id"})

                # Millions of per-cell centroids don't fit through the widget's
                # comm channel (it silently fails to open above roughly tens of
                # MB) — when base_url is a local dev server, write a small
                # sidecar file next to it instead and let the frontend fetch it
                # over HTTP, exactly like the base cell_metadata.parquet. Falls
                # back to the comm-synced bytes trait otherwise (fine for
                # smaller datasets or non-local base_urls).
                base_url_str = kwargs.get("base_url") or ""
                local_dir = _local_dir_for_url(base_url_str)
                if local_dir is not None:
                    cache_name = f".celldega_centroids_{uuid.uuid4().hex[:10]}.parquet"
                    centroid_df.to_parquet(local_dir / cache_name, index=False)
                    centroids_url = f"{base_url_str.rstrip('/')}/{cache_name}"
                else:
                    pq_centroids = _df_to_bytes(centroid_df)

        if isinstance(meta_cell_df, pd.DataFrame):
            pq_meta_cell = _df_to_bytes(_reset_index_for_parquet(meta_cell_df))

        if isinstance(meta_cluster, pd.DataFrame):
            pq_meta_cluster = _df_to_bytes(_reset_index_for_parquet(meta_cluster))
            meta_cluster_df = meta_cluster

        if isinstance(umap_df, pd.DataFrame):
            pq_umap = _df_to_bytes(umap_df)

        if isinstance(meta_nbhd_df, pd.DataFrame):
            pq_meta_nbhd = _df_to_bytes(_reset_index_for_parquet(meta_nbhd_df))

        parquet_traits = {}
        if pq_meta_cell is not None:
            parquet_traits["meta_cell_parquet"] = traitlets.Bytes(pq_meta_cell).tag(sync=True)
        if pq_meta_cluster is not None:
            parquet_traits["meta_cluster_parquet"] = traitlets.Bytes(pq_meta_cluster).tag(sync=True)
        if pq_umap is not None:
            parquet_traits["umap_parquet"] = traitlets.Bytes(pq_umap).tag(sync=True)
        if pq_meta_nbhd is not None:
            parquet_traits["meta_nbhd_parquet"] = traitlets.Bytes(pq_meta_nbhd).tag(sync=True)
        if pq_centroids is not None:
            parquet_traits["centroids_parquet"] = traitlets.Bytes(pq_centroids).tag(sync=True)

        if parquet_traits:
            self.add_traits(**parquet_traits)

        super().__init__(**kwargs)

        self.cell_attr = cell_attr
        self.cluster_attr = cluster_attr
        self.centroids_url = centroids_url

        # store DataFrames locally without syncing to the frontend
        self.meta_cell = meta_cell_df
        self.meta_nbhd = meta_nbhd_df
        self.nbhd = nbhd_gdf
        self.nbhd_edit = nbhd_edit
        self.umap = umap_df
        if meta_cluster_df is not None:
            self.meta_cluster_df = meta_cluster_df

        # compute geojson for initial nbhd if provided
        if self.nbhd is not None:
            if "geometry_pixel" not in self.nbhd.columns:
                a, b, tx = transformation_matrix[0]
                c, d, ty = transformation_matrix[1]
                coeffs = [a, b, c, d, tx, ty]

                self.nbhd["geometry_pixel"] = self.nbhd.geometry.apply(
                    lambda geom: affine_transform(geom, coeffs)
                )

            gdf_viz = deepcopy(self.nbhd)
            gdf_viz["geometry"] = gdf_viz["geometry_pixel"]
            gdf_viz.drop(columns=["geometry_pixel"], inplace=True)

            self.nbhd_geojson = json.loads(gdf_viz.to_json())
        elif self.nbhd_edit:
            self.nbhd_geojson = {"type": "FeatureCollection", "features": []}

    def trigger_update(self, new_value):
        """Update the update_trigger traitlet with a new value."""
        self.update_trigger = new_value

    def update_cell_clusters(self, new_clusters):
        """Update cell clusters with new data."""
        self.cell_clusters = new_clusters

    def highlight_cells(self, cell_ids):
        """Highlight specific cells by their identifiers."""

        self.selected_cells = list(cell_ids)

    @traitlets.observe("nbhd_geojson")
    def _on_nbhd_geojson_change(self, change):
        """Update ``nbhd`` GeoDataFrame when the GeoJSON changes."""
        if not getattr(self, "nbhd_edit", False):
            return

        new = change["new"]
        if not new:
            self.nbhd = gpd.GeoDataFrame(columns=["name", "geometry"], geometry="geometry")
            return

        gdf = gpd.GeoDataFrame.from_features(new.get("features", []))

        try:
            a, b, tx = self._inv_transform[0]
            c, d, ty = self._inv_transform[1]
            coeffs = [a, b, c, d, tx, ty]
            gdf["geometry"] = gdf.geometry.apply(lambda geom: affine_transform(geom, coeffs))
        except Exception:
            pass

        self.nbhd = gdf

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class ManualAttributeTrait(traitlets.Unicode):
    """Traitlet for configuring manual attribute names via bools or strings."""

    def __init__(self, *, default_name: str, **kwargs):
        self._default_name = default_name
        super().__init__(default_value="", **kwargs)

    def validate(self, obj, value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return self._default_name if value else ""
        if isinstance(value, str):
            return super().validate(obj, value.strip())
        return super().validate(obj, str(value).strip())


class Enrich(anywidget.AnyWidget):
    """
    A widget for interactive enrichment analysis using the Enrichr API.

    Allows users to select a gene list, choose an enrichment library, and specify
    the number of terms to display. Automatically replaces older widgets with the
    same name to prevent notebook bloat.
    """

    _esm = _WIDGET_ESM

    value = traitlets.Int(0).tag(sync=True)
    width = traitlets.Int(650).tag(sync=True)
    height = traitlets.Int(650).tag(sync=True)

    component = traitlets.Unicode("Enrich").tag(sync=True)

    gene_list = traitlets.List(default_value=[]).tag(sync=True)
    background_list = traitlets.List(allow_none=True, default_value=None).tag(sync=True)

    available_libs = traitlets.List(
        [
            "CellMarker_2024",
            "ARCHS4_Tissues",
            "GO_Biological_Process_2025",
            "GO_Cellular_Component_2025",
            "GO_Molecular_Function_2025",
            "GTEx_Tissue_Expression_Up",
            "KEGG_2019_Human",
            "ChEA_2022",
            "MGI_Mammalian_Phenotype_Level_4_2024",
            "Disease_Perturbations_from_GEO_up",
            "Ligand_Perturbations_from_GEO_up",
            "LINCS_L1000_Chem_Pert_down",
            "Ligand_Perturbations_from_GEO_down",
        ]
    ).tag(sync=True)

    inst_lib = traitlets.Unicode("CellMarker_2024").tag(sync=True)
    num_terms = traitlets.Int(50).tag(sync=True)

    term_genes = traitlets.List(default_value=[]).tag(sync=True)
    selected_term = traitlets.Unicode("Select Term").tag(sync=True)
    focused_gene = traitlets.Unicode("").tag(sync=True)

    def __init__(self, **kwargs):
        name = kwargs.pop("name", "default")
        old_widget = _enrich_registry.get(name)
        if old_widget:
            with suppress(Exception):
                old_widget.close()

        kwargs["name"] = name
        super().__init__(**kwargs)
        _enrich_registry[name] = self

    def close(self):  # pragma: no cover - cleanup depends on JS
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


def _colors_from_adata(
    adata: Any,
    category: str | None,
    categories: list[str],
) -> dict[str, str]:
    """Map populations to colors from ``adata.uns[f"{category}_colors"]``.

    Colors are aligned to the categorical's ``categories`` order (scanpy
    convention) so they stay correct even for >9 categories where a string sort
    would not. Returns ``{}`` when no palette is available.
    """
    if adata is None or not category:
        return {}
    uns = getattr(adata, "uns", None)
    obs = getattr(adata, "obs", None)
    if uns is None or obs is None:
        return {}
    palette = uns.get(f"{category}_colors")
    if palette is None or category not in obs:
        return {}
    series = obs[category]
    source = (
        list(series.cat.categories.astype(str))
        if hasattr(series, "cat")
        else list(pd.unique(series.astype(str)))
    )
    mapping = {str(cat): palette[i] for i, cat in enumerate(source) if i < len(palette)}
    return {cat: mapping[cat] for cat in categories if cat in mapping}


def _composition_matrix_inputs(
    data: Any,
    modality: str = "population",
    category: str | None = None,
    color_adata: Any = None,
    group_attrs: list[str] | None = None,
) -> dict[str, Any]:
    """Build Matrix inputs for a composition Clustergram.

    Accepts a Celldega collection / ``MuData`` (reads ``modality``), an
    ``AnnData`` (obs = groups, var = populations), or a ``DataFrame``
    (rows = groups, columns = populations). Returns a dict with:

    * ``df`` - populations x groups DataFrame (Clustergram row/col orientation)
    * ``meta_col`` - optional group (column) attribute table
    * ``colors`` - ``{population: hex}`` palette
    * ``normalized`` - default for ``composition_normalized``
    * ``category`` - resolved population category name
    * ``col_weights`` - optional ``{group: n_cells}`` true per-group magnitude,
      used to scale bar height in non-normalized ("counts") mode even when
      the displayed matrix itself holds proportions
    """
    meta_col: pd.DataFrame | None = None
    collection_obs: pd.DataFrame | None = None
    col_weights: dict[str, float] = {}

    if isinstance(data, pd.DataFrame):
        groups_x_pops = data.copy()
        groups_x_pops.index = groups_x_pops.index.astype(str)
        groups_x_pops.columns = groups_x_pops.columns.astype(str)
        categories = list(groups_x_pops.columns)
        colors = _colors_from_adata(color_adata, category, categories)
        output = "proportion"
        resolved_category = category
    else:
        if hasattr(data, "mod"):  # CelldegaCollection or MuData
            available = list(data.mod)
            if modality not in available:
                raise KeyError(
                    f"modality '{modality}' not found; available modalities: {available}"
                )
            adata = data.mod[modality]
            collection_obs = getattr(data, "obs", None)
        elif hasattr(data, "X") and hasattr(data, "var_names"):  # AnnData
            adata = data
        else:
            raise TypeError("data must be a Celldega collection, MuData, AnnData, or DataFrame")

        matrix = adata.X.toarray() if hasattr(adata.X, "toarray") else np.asarray(adata.X)
        groups_x_pops = pd.DataFrame(
            np.nan_to_num(matrix.astype(float), nan=0.0),
            index=pd.Index(adata.obs_names.astype(str), name=adata.obs.index.name),
            columns=pd.Index(adata.var_names.astype(str), name=adata.var.index.name),
        )
        categories = list(groups_x_pops.columns)
        resolved_category = category or adata.uns.get("category")

        colors: dict[str, str] = {}
        if "color" in adata.var.columns:
            colors = {
                cat: str(col)
                for cat, col in zip(categories, adata.var["color"].astype(str), strict=False)
            }
        else:
            color_key = f"{resolved_category}_colors" if resolved_category else None
            if color_key and color_key in adata.uns:
                colors = {
                    cat: str(col)
                    for cat, col in zip(categories, list(adata.uns[color_key]), strict=False)
                }
        if not colors:
            colors = _colors_from_adata(color_adata, resolved_category, categories)
        output = str(adata.uns.get("output", "proportion"))

        # True per-group cell count, independent of `output`: `calc_population`
        # always stores this on the modality's own obs (collection.py), so
        # "counts" mode can scale bar height correctly even when `df` itself
        # holds proportions (every group's proportions sum to ~1.0 otherwise,
        # making non-normalized mode indistinguishable from normalized mode).
        n_cells_source = None
        if "n_cells" in adata.obs.columns:
            n_cells_source = adata.obs["n_cells"]
        elif collection_obs is not None and "n_cells" in collection_obs.columns:
            n_cells_source = collection_obs.reindex(adata.obs_names)["n_cells"]
        if n_cells_source is not None:
            col_weights = {
                str(name): float(n)
                for name, n in zip(adata.obs_names.astype(str), n_cells_source, strict=False)
                if pd.notna(n)
            }

    # Clustergram composition body: rows = populations, cols = groups.
    df = groups_x_pops.T.copy()
    df.index = df.index.astype(str)
    df.columns = df.columns.astype(str)

    if group_attrs:
        # Prefer the collection's dataset/set obs (richer metadata) over the
        # modality's obs, which is usually just n_cells.
        source_obs = collection_obs if collection_obs is not None else None
        if source_obs is None and not isinstance(data, pd.DataFrame):
            source_obs = getattr(adata, "obs", None)  # type: ignore[name-defined]
        if source_obs is not None:
            missing = [c for c in group_attrs if c not in source_obs.columns]
            if missing:
                raise KeyError(f"group_attrs not found on obs: {missing}")
            meta_col = source_obs.loc[df.columns, list(group_attrs)].copy()
            meta_col.index = meta_col.index.astype(str)

    return {
        "df": df,
        "meta_col": meta_col,
        "col_attr": list(group_attrs) if group_attrs else [],
        "colors": colors,
        "normalized": output != "counts",
        "category": resolved_category,
        "col_weights": col_weights,
    }


class Yearbook(anywidget.AnyWidget):
    """
    A widget for visualizing cell portraits in a yearbook-style grid layout.

    This widget creates a grid of cell "portraits" - zoomed-in views centered on
    selected cells. All portraits share synchronized zoom state but display different
    spatial regions. The control panel works similarly to Landscape, showing gene
    and cell bars based on visible content.

    Args:
        base_url (str): The base URL for the dataset.
        cells (list, optional): List of cell identifiers to display as portraits.
            If not provided and no query is given, random cells will be selected.
        selection (Selection or dict or list, optional): Ordered selection of
            cells to display as portraits. Accepts a ``celldega.select.Selection``
            returned by ``dega.select.Selector.select``, a JSON-ready selection
            dict, or a plain list of cell ids. Yearbook uses its ids as the
            portrait cell order and stores the JSON-ready payload for provenance.
            Pass either ``selection`` or ``cells``, not both.
        front_end_query (dict, optional): Stateless query evaluated in the browser
            against LandscapeFiles (no Python/AnnData required). This is separate
            from the Python-side ``celldega.select`` query module. Supports the
            following formats:

            - Cluster only: ``{"cluster": {"attr": "leiden", "value": "8"}}``
              Returns random cells from the specified cluster.
            - Gene only: ``{"gene": "BRCA1"}``
              Returns cells ranked by gene expression (highest first).
            - Cluster + Gene: ``{"cluster": {"attr": "leiden", "value": "8"}, "gene": "BRCA1"}``
              Returns cells from the cluster ranked by gene expression.
            - Max cells: ``{"max_cells": 100}``
              Limits the number of cells returned (default: num_rows * num_cols * 10).

            (The former ``query`` argument is deprecated; it now maps to
            ``front_end_query``.)
        num_rows (int): Number of rows in the portrait grid. Alias: ``rows``.
        num_cols (int): Number of columns in the portrait grid. Alias: ``cols``.
        portrait_size_um (float): Size of each portrait in micrometers.
        portrait_gap (int): Gap between portraits in pixels. Default is 4.
        pixel_width (float, optional): Pixel width for scale bar calculation.
            If provided, a scale bar will be displayed.
        token (str, optional): Authentication token for data access.
        dataset_name (str, optional): Name to display in the UI.
        width (int): Widget width in pixels. 0 means 100%.
        height (int): Widget height in pixels.
        segmentation (str): Segmentation version to use. Default is "default".
        adata (AnnData, optional): AnnData object for cell metadata.
        cell_attr (list): List of cell attributes to extract from adata.

    Example::

        # Using an explicit list of cell ids
        yb = Yearbook(
            base_url="https://path-to-dataset",
            cells=["cell_1", "cell_2", "cell_3", "cell_4"],
            rows=2,
            cols=2,
            portrait_size_um=100,
        )

        # Using a Python selector result
        selector = dega.select.Selector(adata)
        selection = selector.select(query=selector.attr("leiden") == "5")
        yb = Yearbook(
            base_url="https://path-to-dataset",
            selection=selection,
            rows=2,
            cols=2,
        )

        # Using a stateless front-end query (no AnnData needed)
        yb = Yearbook(
            base_url="https://path-to-dataset",
            front_end_query={"gene": "BRCA1", "max_cells": 50},
            rows=2,
            cols=2,
            portrait_size_um=100,
        )
    """

    _esm = _WIDGET_ESM
    component = traitlets.Unicode("Yearbook").tag(sync=True)

    base_url = traitlets.Unicode("").tag(sync=True)
    token = traitlets.Unicode("").tag(sync=True)
    creds = traitlets.Dict({}).tag(sync=True)

    # Cell list to display as portraits
    cells = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)

    # JSON-ready selector output used to populate cells and preserve provenance.
    selection = traitlets.Dict({}).tag(sync=True)

    # Grid configuration
    num_rows = traitlets.Int(2).tag(sync=True)
    num_cols = traitlets.Int(3).tag(sync=True)

    # Portrait size in micrometers
    portrait_size_um = traitlets.Float(50.0).tag(sync=True)

    # For scale bar calculation
    pixel_width = traitlets.Float(default_value=None, allow_none=True).tag(sync=True)
    scale_bar_microns_per_pixel = traitlets.Float(default_value=None, allow_none=True).tag(
        sync=True
    )

    # Pagination
    current_page = traitlets.Int(0).tag(sync=True)

    # Display options
    dataset_name = traitlets.Unicode("").tag(sync=True)
    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(800).tag(sync=True)

    # Gap between portraits in pixels
    portrait_gap = traitlets.Int(4).tag(sync=True)

    # Segmentation version
    segmentation = traitlets.Unicode("default").tag(sync=True)

    # Zoom state (synced across all portraits)
    zoom_level = traitlets.Float(0).tag(sync=True)

    # Cell name prefix handling (same as Landscape)
    cell_name_prefix = traitlets.Bool(False).tag(sync=True)

    # Cell metadata (similar to Landscape)
    meta_cluster = traitlets.Dict({}).tag(sync=True)
    cell_attr = traitlets.List(
        trait=traitlets.Unicode(),
        default_value=["leiden"],
    ).tag(sync=True)

    # obs column driving the cluster color legend/meta_cluster_parquet key field
    cluster_attr = traitlets.Unicode("leiden").tag(sync=True)

    # Stateless front-end query, evaluated in the browser against LandscapeFiles
    # (no Python/AnnData required). Distinct from the Python-side
    # ``celldega.select`` query module. Supports:
    #   {"cluster": {"attr": "leiden", "value": "8"}} - cells from cluster
    #   {"gene": "BRCA1"} - cells ranked by gene expression
    #   {"cluster": {"attr": "leiden", "value": "8"}, "gene": "BRCA1"} - cluster cells ranked by gene
    #   {"max_cells": 100} - limit number of cells returned (default: num_rows * num_cols * 10)
    front_end_query = traitlets.Dict({}).tag(sync=True)

    def __init__(self, **kwargs):
        # Support 'rows' and 'cols' as aliases for 'num_rows' and 'num_cols'
        if "rows" in kwargs and "num_rows" not in kwargs:
            kwargs["num_rows"] = kwargs.pop("rows")
        elif "rows" in kwargs:
            kwargs.pop("rows")  # Remove duplicate

        if "cols" in kwargs and "num_cols" not in kwargs:
            kwargs["num_cols"] = kwargs.pop("cols")
        elif "cols" in kwargs:
            kwargs.pop("cols")  # Remove duplicate

        # `query` was renamed to `front_end_query` to disambiguate the stateless
        # browser query from the Python-side celldega.select query module.
        if "query" in kwargs:
            if "front_end_query" not in kwargs:
                warnings.warn(
                    "`query` is deprecated and was renamed to `front_end_query`.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                kwargs["front_end_query"] = kwargs.pop("query")
            else:
                kwargs.pop("query")

        selection = kwargs.pop("selection", None)
        if selection is not None:
            if kwargs.get("cells"):
                raise ValueError("Pass either `selection` or `cells`, not both.")

            selection_payload = _selection_to_payload(selection)
            kwargs["cells"] = [str(name) for name in selection_payload["ids"]]
            kwargs["selection"] = selection_payload
            kwargs["current_page"] = 0

        adata = kwargs.pop("adata", None) or kwargs.pop("AnnData", None)
        pq_meta_cell = kwargs.pop("meta_cell_parquet", None)
        pq_meta_cluster = kwargs.pop("meta_cluster_parquet", None)

        meta_cell_df = kwargs.pop("meta_cell", None)
        meta_cluster = kwargs.pop("meta_cluster", None)
        meta_cluster_df = None
        cell_attr = list(kwargs.pop("cell_attr", ["leiden"]))
        # Attribute (obs column) driving the cluster legend; default "leiden".
        cluster_attr = kwargs.pop("cluster_attr", "leiden")
        if cluster_attr not in cell_attr:
            cell_attr.append(cluster_attr)

        # Get cell_name_prefix setting (same as Landscape)
        cell_name_prefix_setting = kwargs.get("cell_name_prefix", False)

        def _df_to_bytes(df):
            import io

            import pyarrow as pa
            import pyarrow.parquet as pq

            df.columns = df.columns.map(str)
            buf = io.BytesIO()
            pq.write_table(pa.Table.from_pandas(df), buf, compression="zstd")
            return buf.getvalue()

        if adata is not None:
            # Never mutate the caller's AnnData, and key cell metadata by
            # obs_names (not a `cell_id` column) so it matches the DegaFiles
            # cell_metadata `name` column — see Landscape for the full rationale.
            obs = adata.obs

            cell_attr = [c for c in cell_attr if c in obs.columns]
            meta_cell_df = obs[cell_attr].copy()

            if meta_cell_df.index.name is None:
                meta_cell_df.index.name = "cell_id"

            # If cell_name_prefix is True, trim the prefix from cell names
            # This allows mapping to DegaFiles which have short names
            if cell_name_prefix_setting:
                # Trim prefix before first underscore from index
                new_index = meta_cell_df.index.map(
                    lambda x: x.split("_", 1)[1] if "_" in str(x) else x
                )
                meta_cell_df.index = new_index

            pq_meta_cell = _df_to_bytes(meta_cell_df)

            if cluster_attr in obs.columns:
                cluster_counts = obs[cluster_attr].value_counts().sort_index()
                colors = adata.uns.get(f"{cluster_attr}_colors")

                # backup color definition (deterministic HSV; no scanpy call)
                if colors is None:
                    n = len(cluster_counts)
                    colors = [_hsv_to_hex(i / n) for i in range(n)]

                meta_cluster_df = pd.DataFrame(
                    {
                        "color": list(colors)[: len(cluster_counts)],
                        "count": cluster_counts.values,
                    },
                    index=cluster_counts.index,
                )

                pq_meta_cluster = _df_to_bytes(meta_cluster_df)

        if isinstance(meta_cell_df, pd.DataFrame):
            pq_meta_cell = _df_to_bytes(meta_cell_df.reset_index())

        if isinstance(meta_cluster, pd.DataFrame):
            pq_meta_cluster = _df_to_bytes(meta_cluster.reset_index())
            kwargs.pop("meta_cluster", None)
            meta_cluster_df = meta_cluster

        parquet_traits = {}
        if pq_meta_cell is not None:
            parquet_traits["meta_cell_parquet"] = traitlets.Bytes(pq_meta_cell).tag(sync=True)
        if pq_meta_cluster is not None:
            parquet_traits["meta_cluster_parquet"] = traitlets.Bytes(pq_meta_cluster).tag(sync=True)

        if parquet_traits:
            self.add_traits(**parquet_traits)

        super().__init__(**kwargs)

        self.cluster_attr = cluster_attr

        # store DataFrames locally without syncing to the frontend
        self.meta_cell = meta_cell_df
        if meta_cluster_df is not None:
            self.meta_cluster_df = meta_cluster_df

    @property
    def total_pages(self):
        """Calculate total number of pages based on cells and grid size."""
        portraits_per_page = self.num_rows * self.num_cols
        return max(1, -(-len(self.cells) // portraits_per_page))  # Ceiling division

    def next_page(self):
        """Navigate to next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1

    def prev_page(self):
        """Navigate to previous page."""
        if self.current_page > 0:
            self.current_page -= 1

    def go_to_page(self, page):
        """Navigate to a specific page."""
        self.current_page = max(0, min(page, self.total_pages - 1))

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class Clustergram(anywidget.AnyWidget):
    """
    Minimal version of the Clustergram widget.

    - Frontend still gets: matrix/parquet data, row/col names, manual_cat,
      manual_cat_config, etc.
    - Manual categories are treated as a simple JSON string.
    - All the old DataFrame-based manual_cat plumbing is removed.

    Matrix slices (browser is source of truth for ``net_mat``)
        On row/column label and matrix-cell clicks, the front-end first updates
        ``click_info`` (interaction only), then emits :attr:`matrix_slice_request` so
        the handler fills :attr:`matrix_slice_result` with axis or cell data
        (``slice_kind``, ``entries``, ``matrix_convention``, etc.). Link another
        widget's trait with ``jslink((cgm, "matrix_slice_result"), ...)`` to consume
        slices without a Python round-trip.

        Use :meth:`request_matrix_slice` from Python when you need an explicit pull
        (requires a **live kernel**).

        **jslink:** Only traits sync between models. For linked custom widgets, mirror
        ``matrix_slice_result``; Python does not run in standalone exported HTML.

    Python access to the same matrix
        If constructed with ``matrix=``, use :meth:`matrix_dataframe` for the underlying
        ``pandas.DataFrame``.
    """

    _esm = _WIDGET_ESM

    # --- core traits used by JS -------------------------------------------------
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Matrix").tag(sync=True)

    network = traitlets.Dict({}).tag(sync=True)
    network_meta = traitlets.Dict({}).tag(sync=True)

    width = traitlets.Int(500).tag(sync=True)
    height = traitlets.Int(500).tag(sync=True)

    click_info = traitlets.Dict({}).tag(sync=True)

    #: Set by Python (or another front-end) to request ``{req_id, op, ...}``:
    #: ``row``/``col`` use ``index``; ``cell`` uses ``row``/``col``; ``row_col``
    #: uses ``row_index``/``col_index`` and optional ``max_entries``. The Matrix
    #: front-end writes the slice into :attr:`matrix_slice_result`.
    matrix_slice_request = traitlets.Dict(default_value={}).tag(sync=True)

    #: Populated by the Matrix front-end in response to :attr:`matrix_slice_request`.
    matrix_slice_result = traitlets.Dict(default_value={}).tag(sync=True)

    # Dendrogram-cut state driven by the front-end slider, keyed by axis, e.g.
    # {"row": {"n_clusters": 5}} or {"col": {"threshold": 0.42}}. Read by
    # `to_cluster` to turn the interactive slider position into flat labels.
    dendro_cut = traitlets.Dict({}).tag(sync=True)

    # Generic row/col selection traitlets
    selected_rows = traitlets.List(default_value=[]).tag(sync=True)
    selected_cols = traitlets.List(default_value=[]).tag(sync=True)

    # Legacy traitlet for gene selection (copied from selected_rows when row entity is 'gene')
    selected_genes = traitlets.List(default_value=[]).tag(sync=True)
    top_n_genes = traitlets.Int(50).tag(sync=True)

    row_names = traitlets.List(default_value=[]).tag(sync=True)
    col_names = traitlets.List(default_value=[]).tag(sync=True)

    # backend-only DataFrames derived from `manual_cat`
    row_manual_df = traitlets.Instance(pd.DataFrame, allow_none=True)
    col_manual_df = traitlets.Instance(pd.DataFrame, allow_none=True)
    row_manual_colors_df = traitlets.Instance(pd.DataFrame, allow_none=True)
    col_manual_colors_df = traitlets.Instance(pd.DataFrame, allow_none=True)

    # Flags that control whether manual categories are shown in the UI.
    manual_row_cat = ManualAttributeTrait(default_name=_DEFAULT_MANUAL_ATTRIBUTE_TITLES["row"]).tag(
        sync=True
    )
    manual_col_cat = ManualAttributeTrait(default_name=_DEFAULT_MANUAL_ATTRIBUTE_TITLES["col"]).tag(
        sync=True
    )

    # Global color registry (JS may write here; Python can also seed it)
    category_colors = traitlets.Dict(default_value={}).tag(sync=True)

    # Colors for value (numeric) attributes: {"positive": "#color", "negative": "#color"}
    # Default: gray for positive, orange for negative
    value_colors = traitlets.Dict(default_value={"positive": "#a9a9a9", "negative": "#ffa500"}).tag(
        sync=True
    )

    # Canonical manual category payload as JSON string.
    manual_cat = traitlets.Unicode("{}").tag(sync=True)

    # Small JSON object describing default attribute names, preferred
    # categories, etc.
    manual_cat_config = traitlets.Unicode("{}").tag(sync=True)

    # How each matrix cell encodes its value / how the body is drawn:
    #   "heatmap"     - color + opacity by value (classic; default)
    #   "dotplot"     - color/opacity by the main matrix (e.g. mean expression),
    #                   square/dot size by the secondary `dot_mat` (e.g. fraction of
    #                   cells expressing). Falls back to "heatmap" if no dot matrix.
    #   "composition" - column-wise stacked bars (rows = populations, cols = groups).
    #                   Only settable on a `Composition` instance; see
    #                   `_validate_viz_mode` below.
    # Changing this trait live re-encodes / rebuilds the body with a transition.
    viz_mode = traitlets.Unicode("heatmap").tag(sync=True)

    # Dotplot-only: whether dot size encodes the secondary `dot_mat` (True,
    # default) or is forced to a full tile, independent of color/opacity.
    dot_size_encoded = traitlets.Bool(True).tag(sync=True)

    # Composition body options (used when viz_mode == "composition").
    # Normalize each column to 100% (True) or keep raw counts (False).
    composition_normalized = traitlets.Bool(True).tag(sync=True)
    # Optional {population_name: hex} palette for stacked segments.
    composition_colors = traitlets.Dict(default_value={}).tag(sync=True)
    # Optional {group_name: n_cells} true per-group magnitude. Scales bar
    # height in non-normalized ("counts") mode even when the displayed matrix
    # holds proportions (e.g. from `DatasetCollection.calc_population`, whose
    # default output already normalizes each group to sum to 1).
    composition_col_weights = traitlets.Dict(default_value={}).tag(sync=True)

    #: Supported `viz_mode` values. "size" (square size ∝ value alone, full
    #: opacity) isn't supported — use "dotplot" instead, which covers the
    #: same "size encodes a value" idea via a proper secondary matrix.
    _VALID_VIZ_MODES = ("heatmap", "dotplot", "composition")

    @traitlets.validate("viz_mode")
    def _validate_viz_mode(self, proposal):
        """Composition mode is only supported through :class:`Composition`.

        The composition-specific traits above still have to live on
        `Clustergram` (the front end has no notion of a Python subclass, it
        only reads whatever traits are synced), but a plain `Clustergram`
        instance isn't a supported way to reach that body — use
        :class:`Composition`, which handles building the right `Matrix` shape
        and reorder semantics for it.
        """
        value = proposal["value"]
        if value not in self._VALID_VIZ_MODES:
            raise traitlets.TraitError(
                f"viz_mode={value!r} is not supported; use one of {self._VALID_VIZ_MODES}."
            )
        if value == "composition" and not isinstance(self, Composition):
            raise traitlets.TraitError(
                "viz_mode='composition' is only supported via celldega.viz.Composition, "
                "not a plain Clustergram."
            )
        return value

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        parquet_data : dict, optional
            Pre-exported parquet payload from your matrix object.
        matrix : object, optional
            If provided and has .export_viz_parquet(), we'll call that.
        network : dict, optional
            Deprecated path, kept only for backwards-compatibility.
        """
        pq_data = kwargs.pop("parquet_data", None)

        if "network" in kwargs:
            warnings.warn(
                "`network` argument is deprecated. Use `matrix` or `parquet_data` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        manual_row_flag = kwargs.pop("manual_row_cat", "")
        manual_col_flag = kwargs.pop("manual_col_cat", "")

        # Store matrix reference for later use (e.g., multi-gene expression calculations)
        self._matrix = None

        if pq_data is None:
            matrix = kwargs.pop("matrix", None)
            if matrix is not None:
                self._matrix = matrix  # Store reference for multi-gene calculations
                pq_data = matrix.export_viz_parquet()
            elif "network" not in kwargs:
                raise ValueError(
                    "You must pass either `network`, `parquet_data`, or `matrix` (for fallback). "
                    "If both `network` and `matrix` are provided, `matrix` will be prioritized."
                )

        # Infer name from pq_data or network
        name = kwargs.get("network", {}).get("name", None)
        if pq_data is not None:
            meta = pq_data.get("meta", {})
            name = meta.get("name", name)
            kwargs.setdefault("network_meta", meta)

            # Entity info can be dict or string - serialize to JSON for frontend
            row_entity = pq_data.get("row_entity", {"entity": "gene", "attr": "name"})
            col_entity = pq_data.get("col_entity", {"entity": "cell", "attr": "leiden"})

            # Convert to JSON strings for syncing with JS
            row_entity_json = json.dumps(row_entity) if isinstance(row_entity, dict) else row_entity
            col_entity_json = json.dumps(col_entity) if isinstance(col_entity, dict) else col_entity

            parquet_traits = {
                "mat_parquet": traitlets.Bytes(pq_data.get("mat", b"")).tag(sync=True),
                # Optional secondary matrix for dot-plot size encoding (may be empty)
                "dot_mat_parquet": traitlets.Bytes(pq_data.get("dot_mat", b"")).tag(sync=True),
                "row_nodes_parquet": traitlets.Bytes(pq_data.get("row_nodes", b"")).tag(sync=True),
                "col_nodes_parquet": traitlets.Bytes(pq_data.get("col_nodes", b"")).tag(sync=True),
                "row_linkage_parquet": traitlets.Bytes(pq_data.get("row_linkage", b"")).tag(
                    sync=True
                ),
                "col_linkage_parquet": traitlets.Bytes(pq_data.get("col_linkage", b"")).tag(
                    sync=True
                ),
                # Entity info as JSON strings
                "row_entity": traitlets.Unicode(row_entity_json).tag(sync=True),
                "col_entity": traitlets.Unicode(col_entity_json).tag(sync=True),
            }
            self.add_traits(**parquet_traits)

        old_widget = _clustergram_registry.get(name)
        if old_widget:
            with suppress(Exception):
                old_widget.close()

        kwargs["name"] = name
        kwargs["manual_row_cat"] = manual_row_flag
        kwargs["manual_col_cat"] = manual_col_flag

        # If a dot-size matrix came through and the caller didn't pick a mode,
        # default to the dot-plot encoding so the extra channel is shown.
        if pq_data is not None and pq_data.get("dot_mat") and "viz_mode" not in kwargs:
            kwargs["viz_mode"] = "dotplot"

        super().__init__(**kwargs)
        _clustergram_registry[name] = self

        # ------------------------------------------------------------------
        # Initialize a simple manual_cat_config from the flags, if the user
        # didn't pass anything explicit.
        # ------------------------------------------------------------------
        config = {"row": None, "col": None}

        if manual_row_flag:
            config["row"] = {
                "attribute": str(manual_row_flag),
                "preferred": [],
                "locked": True,
            }

        if manual_col_flag:
            config["col"] = {
                "attribute": str(manual_col_flag),
                "preferred": [],
                "locked": True,
            }

        # Only overwrite if it's still the default "{}" / empty
        if (config["row"] is not None or config["col"] is not None) and (
            not self.manual_cat_config or self.manual_cat_config == "{}"
        ):
            self.manual_cat_config = json.dumps(config)

        # Seed category_colors from network_meta if available
        base_colors = dict(self.network_meta.get("global_cat_colors", {}))
        if getattr(self, "category_colors", None):
            base_colors.update(self.category_colors)
        self._category_colors = base_colors
        self.category_colors = deepcopy(self._category_colors)

    def to_cluster(
        self,
        axis: str = "row",
        n_clusters: int | None = None,
        threshold: float | None = None,
        criterion: str | None = None,
    ) -> pd.Series:
        """Cut the dendrogram into flat cluster labels via the underlying Matrix.

        Thin wrapper over :meth:`celldega.clust.Matrix.to_cluster`. When neither
        ``n_clusters`` nor ``threshold`` is passed, the cut is read from the
        front-end dendrogram slider state in ``dendro_cut[axis]`` — a dict of
        ``{"n_clusters": int}`` or ``{"threshold": float}`` that the JS widget
        writes as the user drags the slider. Passing an explicit value overrides
        the slider.

        Args:
            axis: ``"row"`` or ``"col"`` — which dendrogram to cut.
            n_clusters: Target number of flat clusters (overrides the slider).
            threshold: Linkage-distance cutoff (overrides the slider).
            criterion: Explicit ``scipy`` ``fcluster`` criterion.

        Returns:
            A ``pd.Series`` of cluster labels indexed by the axis names.

        Raises:
            ValueError: If no Matrix is attached, or no cut is available from
                either the arguments or the front-end slider.
        """
        if self._matrix is None:
            raise ValueError("Clustergram has no Matrix reference; construct with matrix=...")
        if n_clusters is None and threshold is None:
            cut = (self.dendro_cut or {}).get(axis, {})
            n_clusters = cut.get("n_clusters")
            threshold = cut.get("threshold")
            if n_clusters is None and threshold is None:
                raise ValueError(
                    f"no cut for axis '{axis}': move the dendrogram slider or pass "
                    "n_clusters / threshold explicitly"
                )
        return self._matrix.to_cluster(
            axis=axis, n_clusters=n_clusters, threshold=threshold, criterion=criterion
        )

    @property
    def manual_cat_dict(self) -> dict:
        """Convenience accessor: parsed JSON from manual_cat."""
        try:
            return json.loads(self.manual_cat or "{}")
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    # PY-only DataFrames derived from manual_cat JSON
    # ------------------------------------------------------------------
    @traitlets.observe("manual_cat")
    def _on_manual_cat(self, change) -> None:
        """Rebuild backend DataFrames when manual_cat JSON changes."""
        raw = change.get("new") or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}

        self._update_manual_cat_frames(payload)

    def _update_manual_cat_frames(self, payload: dict) -> None:
        """
        Build four DataFrames from the manual_cat payload:

        - row_manual_df: index=row_id, columns=attributes, values=category strings
        - col_manual_df: index=col_id, columns=attributes, values=category strings
        - row_manual_colors_df: index=category, columns=attributes, values=hex colors
        - col_manual_colors_df: index=category, columns=attributes, values=hex colors
        """
        for axis in ("row", "col"):
            axis_payload = payload.get(axis) or {}
            if not axis_payload:
                setattr(self, f"{axis}_manual_df", None)
                setattr(self, f"{axis}_manual_colors_df", None)
                continue

            # union of all indices for this axis
            index_labels = sorted(
                {str(name) for attr in axis_payload.values() for name in (attr.get("values") or {})}
            )

            if index_labels:
                idx = pd.Index(index_labels, name=f"{axis}_id")
                data = {}
                for attr_name, spec in axis_payload.items():
                    values = spec.get("values") or {}
                    series = pd.Series(
                        [values.get(label, _MANUAL_FILL_VALUE) for label in index_labels],
                        index=idx,
                        dtype=object,
                    )
                    data[str(attr_name)] = series
                manual_df = pd.DataFrame(data, index=idx)
            else:
                manual_df = None

            # colors: category -> hex per attribute
            cat_labels = sorted(
                {str(cat) for attr in axis_payload.values() for cat in (attr.get("colors") or {})}
            )

            if cat_labels:
                cat_idx = pd.Index(cat_labels, name="category")
                color_data = {}
                for attr_name, spec in axis_payload.items():
                    cmap = spec.get("colors") or {}
                    series = pd.Series(
                        [cmap.get(cat, None) for cat in cat_labels],
                        index=cat_idx,
                        dtype=object,
                    )
                    color_data[str(attr_name)] = series
                colors_df = pd.DataFrame(color_data, index=cat_idx)
            else:
                colors_df = None

            setattr(self, f"{axis}_manual_df", manual_df)
            setattr(self, f"{axis}_manual_colors_df", colors_df)

    def request_matrix_slice(
        self,
        op: Literal["row", "col", "cell", "row_col"],
        *,
        index: int | None = None,
        row: int | None = None,
        col: int | None = None,
        row_index: int | None = None,
        col_index: int | None = None,
        max_entries: int | None = None,
        timeout: float = 5.0,
        poll_interval: float = 0.02,
    ) -> dict | None:
        """
        Ask the browser Matrix to return a slice from ``net_mat`` (blocking).

        Requires a running Jupyter kernel and an active widget comm. Not available in
        standalone exported HTML without a kernel.

        Parameters
        ----------
        op
            ``row`` or ``col``: pass ``index`` (matrix axis index). ``cell``: pass
            ``row`` and ``col`` matrix indices. ``row_col``: pass ``row_index`` and
            ``col_index`` to get both axis slices in one result; optional
            ``max_entries`` (negative means all, subject to a browser-side cap).
        timeout
            Seconds to wait for :attr:`matrix_slice_result` to match ``req_id``.

        Returns
        -------
        dict | None
            The front-end payload (includes ``req_id``), or ``None`` on timeout.
        """
        if op not in ("row", "col", "cell", "row_col"):
            raise ValueError("op must be 'row', 'col', 'cell', or 'row_col'")

        req_id = str(uuid.uuid4())
        payload: dict[str, Any] = {"req_id": req_id, "op": op}
        if op in ("row", "col"):
            if index is None:
                raise ValueError("index is required when op is 'row' or 'col'")
            payload["index"] = int(index)
        elif op == "cell":
            if row is None or col is None:
                raise ValueError("row and col are required when op is 'cell'")
            payload["row"] = int(row)
            payload["col"] = int(col)
        else:
            if row_index is None or col_index is None:
                raise ValueError("row_index and col_index are required when op is 'row_col'")
            payload["row_index"] = int(row_index)
            payload["col_index"] = int(col_index)
        if max_entries is not None:
            payload["max_entries"] = int(max_entries)

        self.matrix_slice_result = {}
        self.matrix_slice_request = {}
        self.matrix_slice_request = payload

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            res = dict(self.matrix_slice_result or {})
            if res.get("req_id") == req_id:
                return res
            time.sleep(poll_interval)

        return None

    def matrix_dataframe(self) -> pd.DataFrame | None:
        """Return a copy of the Matrix ``data`` when this widget was created with ``matrix=``."""
        m = getattr(self, "_matrix", None)
        if m is None:
            return None
        data = getattr(m, "data", None)
        return data.copy() if data is not None else None

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class Composition(Clustergram):
    """Composition view: count/proportion of categories compared across groups.

    A `Clustergram` subclass with ``viz_mode="composition"``. The body draws
    each group (dataset/sample) as a stacked bar whose segments are
    populations (cell types), reusing the Clustergram's column-attribute
    tracks, reorder buttons (``ini`` / ``sum`` / ``clust``), and the
    control-panel ``PROP``/``COUNTS`` normalization toggle.

    "Composition shows the count or relative proportion of categories within
    each group, and compares those compositions across groups."

    Example::

        dset = dega.DatasetCollection(adata, dataset_col="sample_id",
                                       obs_columns=["condition"])
        dset.calc_population(adata, category="cell_type")
        dega.viz.Composition(
            dset, category="cell_type", group_attrs=["condition"]
        )

    Note: ``calc_population`` already copies ``adata.uns[f"{category}_colors"]``
    onto the population modality it builds, so ``Composition`` picks up the
    same colors from ``dset`` alone — passing ``adata=`` is only needed as a
    fallback (e.g. a plain ``DataFrame`` input, or an ``AnnData``/modality that
    has no color palette of its own).
    """

    def __init__(
        self,
        data: Any,
        modality: str = "population",
        *,
        category: str | None = None,
        colors: dict[str, str] | None = None,
        adata: Any = None,
        group_attrs: list[str] | None = None,
        normalized: bool | None = None,
        col_weights: dict[str, float] | None = None,
        cluster: bool = True,
        name: str = "composition",
        width: int = 700,
        height: int = 450,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            data: A Celldega collection (``DatasetCollection`` / ``SetCollection``),
                a ``MuData``, an ``AnnData`` (obs = groups, var = populations), or a
                ``DataFrame`` (rows = groups, columns = populations) — typically the
                output of ``calc_population``.
            modality: Modality key on a collection/MuData (default ``"population"``).
            category: Population ``obs`` column name used to resolve colors from
                ``adata.uns[f"{category}_colors"]`` when the modality has none.
            colors: Optional ``{population: hex}`` overrides.
            adata: Optional source cell-level ``AnnData`` to fall back to for
                its color palette. Usually unnecessary: ``calc_population``
                already copies the category's colors onto the modality it
                builds, so a ``DatasetCollection``/``SetCollection`` that has
                already run it carries its own colors.
            group_attrs: Dataset/set ``obs`` columns to show as Clustergram column
                attribute tracks (e.g. ``["condition", "timepoint"]``).
            normalized: Column-normalize each bar to 100%. Defaults to ``True`` for
                proportion matrices and ``False`` for count matrices.
            col_weights: Optional ``{group: n_cells}`` true per-group magnitude,
                used to scale bar height in non-normalized ("counts") mode.
                Defaults to `DatasetCollection`/`calc_population`'s own
                ``n_cells`` obs column when available — pass explicitly to
                override, e.g. for a plain ``DataFrame`` input.
            cluster: Run hierarchical clustering before display (default ``True``).
            name: Clustergram registry name.
            width / height: Widget size in pixels.
            **kwargs: Forwarded to :class:`Clustergram`.
        """
        from celldega.clust.matrix import Matrix

        payload = _composition_matrix_inputs(
            data,
            modality=modality,
            category=category,
            color_adata=adata,
            group_attrs=group_attrs,
        )
        merged_colors = dict(payload["colors"])
        if colors:
            merged_colors.update(colors)

        resolved_col_weights = col_weights if col_weights is not None else payload["col_weights"]

        mat = Matrix(
            payload["df"],
            meta_col=payload["meta_col"],
            col_attr=payload["col_attr"] or None,
            row_entity={"entity": "cell_population", "attr": "name"},
            col_entity={"entity": "dataset", "attr": "name"},
            global_colors=merged_colors or None,
            disable_processing=True,
            name=name,
        )
        if cluster:
            mat.clust()
        else:
            # Build viz nodes/ranks without hierarchical clustering so export works.
            mat.make_viz()
            mat._clustered = True

        if normalized is None:
            normalized = payload["normalized"]

        kwargs.setdefault("viz_mode", "composition")
        kwargs.setdefault("composition_normalized", bool(normalized))
        if resolved_col_weights:
            kwargs.setdefault("composition_col_weights", resolved_col_weights)
        if merged_colors:
            kwargs.setdefault("composition_colors", merged_colors)
            kwargs.setdefault("category_colors", merged_colors)
        kwargs.setdefault("width", width)
        kwargs.setdefault("height", height)
        kwargs.setdefault("name", name)
        super().__init__(matrix=mat, **kwargs)
