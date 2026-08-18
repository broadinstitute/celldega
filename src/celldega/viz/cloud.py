"""3D-orbit spatial widgets: ``CellCloud`` and ``NeighborhoodCloud``.

These are the dedicated widgets for the point-cloud family of render
technologies, replacing the older ``Landscape(technology="point-cloud")`` and
``Landscape(technology="neighborhood-cloud")`` entry points. ``Landscape`` is
2D spatial visualization (tile pyramids, image layers); the widgets here are
3D orbit views of a biological entity — cells (``CellCloud``) or precomputed
neighborhood alpha shapes (``NeighborhoodCloud``).

Both inherit a shared :class:`_SpatialWidget` base holding the trait surface and
AnnData→parquet plumbing common to every celldega spatial widget, and reuse the
existing front-end ``render_landscape_ist`` path. The only front-end difference
is the DegaFiles manifest each fetches: ``cell_cloud.json`` /
``neighborhood_cloud.json`` (via the ``manifest_name`` trait) rather than
``landscape_parameters.json`` — with the front-end falling back to
``landscape_parameters.json`` so DegaFiles built before the rename still render.
"""

import uuid

import anywidget
import numpy as np
import pandas as pd
import traitlets

from .widget import (
    _WIDGET_ESM,
    _hsv_to_hex,
    _local_dir_for_url,
)


def _df_to_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to zstd-compressed parquet bytes for the frontend."""
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    df.columns = df.columns.map(str)
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf, compression="zstd")
    return buf.getvalue()


def _reset_index_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Reset a DataFrame's index into a column so it survives parquet round-trip."""
    index_name = df.index.name or "index"
    if index_name in df.columns:
        return df.reset_index(drop=True)
    return df.reset_index()


class _SpatialWidget(anywidget.AnyWidget):
    """Shared base for celldega spatial widgets (trait surface + AnnData plumbing).

    Holds the traits and construction logic common to every spatial widget:
    base URL(s), initial view, cell/cluster attributes, selection sync, and the
    AnnData→parquet extraction that turns an ``adata`` into the ``meta_cell`` /
    ``meta_cluster`` / ``umap`` payloads the frontend consumes. Subclasses set
    ``component`` / ``technology`` / ``manifest_name`` and add their own traits;
    they may override :meth:`_collect_adata_payloads` to derive extra synced
    payloads (e.g. ``CellCloud`` centroids) from the same ``adata``.

    Not instantiated directly — use ``CellCloud`` or ``NeighborhoodCloud``.
    """

    _esm = _WIDGET_ESM

    # Subclasses override these three.
    component = traitlets.Unicode("").tag(sync=True)
    technology = traitlets.Unicode("").tag(sync=True)
    # DegaFiles manifest filename the frontend fetches for this widget. The
    # front-end falls back to "landscape_parameters.json" when this file is
    # absent, so datasets built before the rename keep rendering.
    manifest_name = traitlets.Unicode("landscape_parameters.json").tag(sync=True)

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
    dataset_name = traitlets.Unicode("").tag(sync=True)
    region = traitlets.Dict({}).tag(sync=True)
    scale_bar_microns_per_pixel = traitlets.Float(default_value=None, allow_none=True).tag(
        sync=True
    )

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

    # obs column driving the cluster color legend / meta_cluster_parquet key field
    cluster_attr = traitlets.Unicode("leiden").tag(sync=True)

    segmentation = traitlets.Unicode("default").tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(600).tag(sync=True)

    def __init__(self, **kwargs):
        adata = kwargs.pop("adata", None) or kwargs.pop("AnnData", None)
        pq_meta_cell = kwargs.pop("meta_cell_parquet", None)
        pq_meta_cluster = kwargs.pop("meta_cluster_parquet", None)
        pq_umap = kwargs.pop("umap_parquet", None)

        meta_cell_df = kwargs.pop("meta_cell", None)
        meta_cluster = kwargs.pop("meta_cluster", None)
        umap_df = kwargs.pop("umap", None)
        meta_cluster_df = None

        cell_attr = list(kwargs.pop("cell_attr", ["leiden"]))
        # Attribute (obs column) that drives the cluster color legend. Defaults to
        # "leiden" for backward compatibility; set e.g. cluster_attr="cell_type" to
        # color by any categorical attribute.
        cluster_attr = kwargs.pop("cluster_attr", "leiden")
        if cluster_attr not in cell_attr:
            cell_attr.append(cluster_attr)

        # Normalize base_url / base_urls (string, list of strings, or list of dicts).
        self._normalize_base_urls(kwargs)

        cell_name_prefix_setting = kwargs.get("cell_name_prefix", False)

        parquet_traits = {}

        # Subclass hook: consume non-trait kwargs (e.g. z_key) and register any
        # explicitly-passed binary payloads. Runs whether or not adata is given,
        # so those kwargs never leak into super().__init__ as unknown traits.
        extra_payloads = dict(self._consume_extra_kwargs(kwargs))

        if adata is not None:
            cell_attr, meta_cell_df, meta_cluster_df, umap_df = self._extract_from_adata(
                adata, cell_attr, cluster_attr, cell_name_prefix_setting
            )
            if meta_cell_df is not None:
                pq_meta_cell = _df_to_bytes(meta_cell_df)
            if meta_cluster_df is not None:
                pq_meta_cluster = _df_to_bytes(meta_cluster_df)
            if umap_df is not None:
                pq_umap = _df_to_bytes(umap_df)

            # Adata-derived payloads (e.g. centroids). Explicit payloads from
            # _consume_extra_kwargs take precedence.
            for name, payload in self._collect_adata_payloads(
                adata, kwargs, cell_name_prefix_setting
            ).items():
                extra_payloads.setdefault(name, payload)

        for name, payload in extra_payloads.items():
            parquet_traits[name] = traitlets.Bytes(payload).tag(sync=True)

        if isinstance(meta_cell_df, pd.DataFrame):
            pq_meta_cell = _df_to_bytes(_reset_index_for_parquet(meta_cell_df))

        if isinstance(meta_cluster, pd.DataFrame):
            pq_meta_cluster = _df_to_bytes(_reset_index_for_parquet(meta_cluster))
            meta_cluster_df = meta_cluster

        if isinstance(umap_df, pd.DataFrame):
            pq_umap = _df_to_bytes(umap_df)

        if pq_meta_cell is not None:
            parquet_traits["meta_cell_parquet"] = traitlets.Bytes(pq_meta_cell).tag(sync=True)
        if pq_meta_cluster is not None:
            parquet_traits["meta_cluster_parquet"] = traitlets.Bytes(pq_meta_cluster).tag(sync=True)
        if pq_umap is not None:
            parquet_traits["umap_parquet"] = traitlets.Bytes(pq_umap).tag(sync=True)

        if parquet_traits:
            self.add_traits(**parquet_traits)

        super().__init__(**kwargs)

        self.cell_attr = cell_attr
        self.cluster_attr = cluster_attr

        # store DataFrames locally without syncing to the frontend
        self.meta_cell = meta_cell_df
        self.umap = umap_df
        if meta_cluster_df is not None:
            self.meta_cluster_df = meta_cluster_df

    def _normalize_base_urls(self, kwargs) -> None:
        """Fill ``kwargs['base_url']`` / ``kwargs['base_urls']`` from any accepted form.

        Accepts a single string, a list of URL strings, or a list of
        ``{'url', 'label', 'short_label'}`` dicts (with an optional
        ``dataset_names`` list of short display names), matching ``Landscape``.
        """
        raw_base_url = kwargs.pop("base_urls", None) or kwargs.get("base_url", "")
        dataset_names = kwargs.pop("dataset_names", None)
        base_urls_list = []

        if isinstance(raw_base_url, list):
            for i, item in enumerate(raw_base_url):
                if isinstance(item, dict):
                    url = item.get("url", "")
                    label = item.get("label", f"Dataset {i + 1}")
                    short_label = item.get("short_label", f"DS-{i + 1}")
                    base_urls_list.append({"url": url, "label": label, "short_label": short_label})
                else:
                    base_urls_list.append(
                        {
                            "url": str(item),
                            "label": f"Dataset {i + 1}",
                            "short_label": f"DS-{i + 1}",
                        }
                    )

            if dataset_names and isinstance(dataset_names, list):
                for i, name in enumerate(dataset_names):
                    if i < len(base_urls_list) and name:
                        base_urls_list[i]["short_label"] = str(name)
                        if base_urls_list[i]["label"] == f"Dataset {i + 1}":
                            base_urls_list[i]["label"] = str(name)

            if base_urls_list:
                kwargs["base_url"] = base_urls_list[0]["url"]
            kwargs["base_urls"] = base_urls_list
        else:
            if raw_base_url:
                base_urls_list = [
                    {"url": raw_base_url, "label": "Dataset 1", "short_label": "DS-1"}
                ]
            kwargs["base_urls"] = base_urls_list

    def _extract_from_adata(self, adata, cell_attr, cluster_attr, cell_name_prefix_setting):
        """Derive (cell_attr, meta_cell_df, meta_cluster_df, umap_df) from ``adata``.

        Never mutates the caller's AnnData. Keys cell metadata by ``obs_names``
        (the canonical AnnData cell id that matches the DegaFiles cell_metadata
        ``name`` column) — never a ``cell_id`` obs *column*, which can silently
        mismatch every cell. No scanpy plotting calls (those write
        ``<attr>_colors`` back into ``adata.uns``).
        """
        obs = adata.obs

        if "color" in obs.columns and "color" not in cell_attr:
            cell_attr.append("color")

        cell_attr = [c for c in cell_attr if c in obs.columns]
        meta_cell_df = obs[cell_attr].copy()

        if meta_cell_df.index.name is None:
            meta_cell_df.index.name = "cell_id"

        if cell_name_prefix_setting:
            meta_cell_df.index = meta_cell_df.index.map(
                lambda x: x.split("_", 1)[1] if "_" in str(x) else x
            )

        meta_cluster_df = None
        if cluster_attr in obs.columns:
            cluster_counts = obs[cluster_attr].value_counts().sort_index()
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

        umap_df = None
        if "X_umap" in adata.obsm:
            umap_df = pd.DataFrame(adata.obsm["X_umap"], index=obs.index)
            if cell_name_prefix_setting:
                umap_df.index = umap_df.index.map(
                    lambda x: x.split("_", 1)[1] if "_" in str(x) else x
                )
            umap_df = umap_df.reset_index().rename(
                columns={"index": "cell_id", 0: "umap_0", 1: "umap_1"}
            )

        return cell_attr, meta_cell_df, meta_cluster_df, umap_df

    def _consume_extra_kwargs(self, kwargs) -> dict:
        """Hook: pop subclass-specific non-trait kwargs (stashing on ``self``) and
        return ``{trait_name: parquet_bytes}`` for explicitly-passed binary
        payloads. Runs whether or not an ``adata`` is given. Default: ``{}``.
        """
        return {}

    def _collect_adata_payloads(self, adata, kwargs, cell_name_prefix_setting) -> dict:
        """Hook: subclasses return ``{trait_name: parquet_bytes}`` derived from ``adata``.

        Called with ``adata`` and the resolved ``kwargs`` (so ``base_url`` is
        available) still in scope. May mutate ``kwargs`` to set string traits
        (e.g. ``centroids_url``). Default: no extra payloads.
        """
        return {}

    def trigger_update(self, new_value):
        """Update the update_trigger traitlet with a new value."""
        self.update_trigger = new_value

    def update_cell_clusters(self, new_clusters):
        """Update cell clusters with new data."""
        self.cell_clusters = new_clusters

    def highlight_cells(self, cell_ids):
        """Highlight specific cells by their identifiers."""
        self.selected_cells = list(cell_ids)

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        from contextlib import suppress

        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class CellCloud(_SpatialWidget):
    """3D orbit view of cell centroids (replaces ``Landscape(technology="point-cloud")``).

    Renders a pre-built point-cloud DegaFiles directory — cell positions from
    ``cell_metadata.parquet`` (or ``cell_metadata_<alignment>.parquet`` when
    ``alignment`` is set), colored by cluster/gene. Build one with
    :func:`celldega.align.write_alignment_point_cloud`.

    Args:
        base_url (str or list): DegaFiles URL(s), as in ``Landscape``.
        adata (AnnData, optional): Source of cell attributes/metadata (clusters,
            colors, UMAP). Never used for spatial positions — those come from the
            DegaFiles — except when ``use_adata_3d_centroids`` is set.
        alignment (str, optional): Named alignment variant; cell positions are
            read from ``cell_metadata_<alignment>.parquet``.
        use_adata_3d_centroids (bool): When an ``adata`` with ``obsm["spatial"]``
            is given, render its centroids (``obs[z_key]`` for Z, falling back to
            0) instead of the on-disk geometry — to preview a candidate alignment
            without rewriting DegaFiles. Default: True.
        z_key (str): ``obs`` column holding the Z coordinate for
            ``use_adata_3d_centroids``. Default: "Z".

    ``use_adata_3d_centroids`` writes centroids to a small sidecar file next to
    ``base_url`` and fetches it over HTTP when ``base_url`` is a local
    ``celldega.viz.get_local_server()`` address (millions of per-cell centroids
    don't fit through the widget's comm channel); otherwise it falls back to
    syncing them through widget state, fine for smaller datasets.
    """

    component = traitlets.Unicode("CellCloud").tag(sync=True)
    technology = traitlets.Unicode("point-cloud").tag(sync=True)
    manifest_name = traitlets.Unicode("cell_cloud.json").tag(sync=True)

    # 3D orbit camera
    rotation_orbit = traitlets.Float(0).tag(sync=True)
    rotation_x = traitlets.Float(0).tag(sync=True)

    # Named alignment variant. When set, cell positions are read from
    # cell_metadata_<alignment>.parquet while clusters/genes keep loading from
    # their normal (segmentation-driven) paths.
    alignment = traitlets.Unicode("").tag(sync=True)

    use_adata_3d_centroids = traitlets.Bool(True).tag(sync=True)
    centroids_url = traitlets.Unicode("").tag(sync=True)

    def _consume_extra_kwargs(self, kwargs) -> dict:
        # z_key only affects adata centroid extraction, but pop it always so it
        # never reaches super().__init__ as an unknown trait.
        self._z_key = kwargs.pop("z_key", "Z")
        explicit = kwargs.pop("centroids_parquet", None)
        # Explicitly-passed centroids (bytes, or a pre-set centroids_url) win
        # over — and suppress — the adata-derived extraction.
        self._has_explicit_centroids = explicit is not None or bool(kwargs.get("centroids_url"))
        return {"centroids_parquet": explicit} if explicit is not None else {}

    def _collect_adata_payloads(self, adata, kwargs, cell_name_prefix_setting) -> dict:
        """Derive per-cell centroids from ``adata.obsm['spatial']`` + ``obs[z_key]``.

        Writes a sidecar parquet next to a local ``base_url`` and sets
        ``centroids_url`` (preferred for large datasets), else returns the bytes
        as a ``centroids_parquet`` payload synced through widget state.
        """
        if self._has_explicit_centroids:
            return {}
        if not kwargs.get("use_adata_3d_centroids", True) or "spatial" not in adata.obsm:
            return {}

        z_key = self._z_key
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

        # Millions of per-cell centroids don't fit through the widget comm
        # channel (it silently fails above roughly tens of MB) — when base_url is
        # a local dev server, write a small sidecar file next to it and let the
        # frontend fetch it over HTTP (exactly like cell_metadata.parquet). Fall
        # back to the comm-synced bytes trait otherwise.
        base_url_str = kwargs.get("base_url") or ""
        local_dir = _local_dir_for_url(base_url_str)
        if local_dir is not None:
            cache_name = f".celldega_centroids_{uuid.uuid4().hex[:10]}.parquet"
            centroid_df.to_parquet(local_dir / cache_name, index=False)
            kwargs["centroids_url"] = f"{base_url_str.rstrip('/')}/{cache_name}"
            return {}
        return {"centroids_parquet": _df_to_bytes(centroid_df)}


class NeighborhoodCloud(_SpatialWidget):
    """3D orbit view of neighborhood alpha shapes (replaces
    ``Landscape(technology="neighborhood-cloud")``).

    Renders a pre-built neighborhood-cloud DegaFiles directory: one precomputed
    alpha-shape polygon per (cluster, slice), cheap to display regardless of
    dataset size, with real cell centroids loaded on demand when a cluster is
    selected. Build one with :func:`celldega.align.write_nbhd_cloud` (or
    :func:`celldega.pre.write_nbhd_cloud_dataset`).

    The neighborhood geometry lives entirely on disk under the DegaFiles
    ``nbhd_cloud/`` tree and is fetched by the front-end; this widget carries
    only the shared spatial trait surface plus the 3D orbit camera. (The 2D
    neighborhood *drawing* editor is a ``Landscape`` feature and intentionally
    not part of ``NeighborhoodCloud``.)

    Args:
        base_url (str or list): DegaFiles URL(s), as in ``Landscape``.
        adata (AnnData, optional): Source of cell attributes/metadata.
    """

    component = traitlets.Unicode("NeighborhoodCloud").tag(sync=True)
    technology = traitlets.Unicode("neighborhood-cloud").tag(sync=True)
    manifest_name = traitlets.Unicode("neighborhood_cloud.json").tag(sync=True)

    # 3D orbit camera
    rotation_orbit = traitlets.Float(0).tag(sync=True)
    rotation_x = traitlets.Float(0).tag(sync=True)
