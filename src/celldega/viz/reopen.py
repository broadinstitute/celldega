"""Reopen the supported interactive state stored in a Celldega PNG."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlparse

from .screenshots import load_screenshot
from .snapshots import validate_snapshot


# Only data/configuration values may come from an image. In particular, never
# deserialize arbitrary widget classes, _esm code, credentials or callbacks.
_SOURCE_OPTIONS = frozenset(
    [
        "width",
        "height",
        "data_revision",
        "base_url",
        "base_urls",
        "zarr_url",
        "zarr_layer",
        "url",
        "name",
        "technology",
        "dataset_name",
        "cluster_attr",
        "cell_attr",
        "cell_name_prefix",
        "segmentation",
        "alignment",
        "manifest_name",
        "centroids_url",
        "use_adata_3d_centroids",
        "spatial_key",
        "ini_x",
        "ini_y",
        "ini_z",
        "ini_zoom",
        "min_zoom",
        "max_zoom",
        "rotation_orbit",
        "rotation_x",
        "rotate",
        "scale_bar_microns_per_pixel",
        "cell_size",
        "max_tiles_to_view",
        "intermediate_zoom_limit",
        "viz_mode",
        "rank_dim",
        "row_label_scale",
        "col_label_scale",
    ]
)


def _png_panel(path: str | Path, panel: int) -> tuple[dict, dict]:
    record = load_screenshot(path)
    widgets = record.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        raise ValueError("PNG has no saved visualization panels")
    if isinstance(panel, bool) or not isinstance(panel, int) or not 0 <= panel < len(widgets):
        raise ValueError(f"panel must be an integer from 0 to {len(widgets) - 1}")
    saved = widgets[panel]
    if not isinstance(saved, dict):
        raise ValueError("PNG has an invalid visualization panel")
    snapshot = saved.get("snapshot")
    validate_snapshot(snapshot)
    return deepcopy(saved), deepcopy(snapshot)


def _source_bytes(location: str) -> bytes:
    if urlparse(location).scheme in ("http", "https"):
        import requests

        response = requests.get(location, timeout=30)
        response.raise_for_status()
        return response.content
    return Path(location).read_bytes()


def _degafiles_matrix(base_url: str, name: str) -> dict:
    """The same clustered Parquet payload the standalone JS constructor reads."""
    root = f"{base_url.rstrip('/')}/cgm/{name}"
    meta = json.loads(_source_bytes(f"{root}/meta.json"))
    payload = {
        "meta": meta,
        "row_entity": meta.get("row_entity", {"entity": "gene", "attr": "name"}),
        "col_entity": meta.get("col_entity", {"entity": "cell", "attr": "leiden"}),
    }
    for key in ("mat", "row_nodes", "col_nodes", "row_linkage", "col_linkage"):
        payload[key] = _source_bytes(f"{root}/{key}.parquet")
    try:
        payload["dot_mat"] = _source_bytes(f"{root}/dot_mat.parquet")
    except FileNotFoundError:
        pass
    except Exception as error:
        # Only the optional file being absent is harmless. Authentication,
        # connection and other failures must not silently change dotplot data.
        if getattr(getattr(error, "response", None), "status_code", None) != 404:
            raise
    return payload


def from_png(
    path: str | Path,
    *,
    panel: int = 0,
    allow_resize: bool = False,
    **overrides,
):
    """Construct an interactive visualization from a Celldega screenshot PNG.

    The PNG supplies source references, construction options and supported replay
    settings. Data is loaded from its recorded location; it is not embedded in the
    image. Pass constructor overrides to relocate data or provide original
    in-memory inputs, e.g. ``matrix=mat`` or ``adata=adata``. A composite screenshot
    has one widget per panel; select it with the zero-based ``panel`` argument.

    Display the returned widget. It restores once its browser renderer is ready,
    checking the schema, data identity and canvas dimensions before replay. In a
    later notebook cell, inspect ``viz.get_apply_result(viz.apply_request_id)``;
    ``None`` means pending, and an ``apply_error`` reply explains a failed restore.
    ``allow_resize=True`` accepts a different canvas extent. This is a partial
    semantic restore, not a guarantee of identical pixels.
    """
    from .cloud import CellCloud, NeighborhoodCloud
    from .widget import Clustergram, Landscape

    if not isinstance(allow_resize, bool):
        raise ValueError("allow_resize must be a boolean")
    saved, snapshot = _png_panel(path, panel)
    browser_source = snapshot.get("source") or {}
    python_source = saved.get("source") or {}
    if not isinstance(browser_source, dict) or not isinstance(python_source, dict):
        raise ValueError("PNG has invalid data source metadata")
    source = {**browser_source, **python_source}
    default_kind = "Clustergram" if snapshot["kind"] == "clustergram" else "Landscape"
    kind = source.get("widget") or default_kind
    classes = {
        "Landscape": Landscape,
        "CellCloud": CellCloud,
        "NeighborhoodCloud": NeighborhoodCloud,
        "Clustergram": Clustergram,
        "Composition": Clustergram,
    }
    constructor = classes.get(kind)
    if constructor is None:
        raise ValueError(f"Cannot reopen PNG visualization type {kind!r}")
    if (constructor is Clustergram) != (snapshot["kind"] == "clustergram"):
        raise ValueError("PNG source type does not match its saved view")

    options = {}
    for origin in (browser_source, python_source):
        stored = origin.get("options") or {}
        if not isinstance(stored, dict):
            raise ValueError("PNG has invalid constructor options")
        options.update({key: value for key, value in stored.items() if key in _SOURCE_OPTIONS})
    # Older PNGs recorded source URLs without a construction options object.
    for key in _SOURCE_OPTIONS:
        if key in source:
            options.setdefault(key, source[key])
    if constructor is Clustergram:
        matrix_source = source.get("matrix")
        if isinstance(matrix_source, dict) and matrix_source.get("source"):
            options.setdefault("url", matrix_source["source"])

    # New captures record construction dimensions. Legacy captures and responsive
    # widgets need their actual CSS canvas size (not the downscaled PNG size).
    viewport = snapshot.get("viewport") or {}
    padding = 100 if constructor is Clustergram else 0
    for axis in ("width", "height"):
        if not options.get(axis) and isinstance(viewport.get(axis), int | float):
            options[axis] = max(1, round(viewport[axis]) - padding)

    selectors = ("matrix", "network", "parquet_data", "url", "base_url", "base_urls", "zarr_url")
    if any(overrides.get(key) is not None for key in selectors):
        for key in selectors:
            options.pop(key, None)
        # A different supplied source has no known producer-declared revision
        # unless the caller supplies it too. Never manufacture a matching one.
        options.pop("data_revision", None)
    options.update(overrides)
    supplied_data = any(overrides.get(key) is not None for key in (*selectors, "adata", "AnnData"))
    if source.get("requires_data") and not supplied_data:
        argument = (
            "matrix=original_matrix" if constructor is Clustergram else "adata=original_adata"
        )
        raise ValueError(f"PNG was captured with in-memory data; pass {argument} to from_png")

    if constructor is Clustergram:
        url = options.pop("url", None)
        base_url = options.pop("base_url", None)
        options.pop("base_urls", None)
        if not any(options.get(key) is not None for key in ("matrix", "network", "parquet_data")):
            if url:
                from celldega.clust import Matrix

                options["matrix"] = Matrix.read_zarr(url)
            elif base_url:
                options["parquet_data"] = _degafiles_matrix(
                    base_url, options.get("name", "default")
                )
            else:
                raise ValueError("PNG has no reusable Matrix source; pass matrix=original_matrix")
    elif not any(options.get(key) for key in ("base_url", "base_urls", "zarr_url")):
        raise ValueError(
            "PNG has no reusable spatial data source; pass base_url=... or zarr_url=..."
        )

    # A source can cross runtimes (e.g. a browser Cloud PNG reopened in Python).
    # Keep only constructor traits for recorded options; caller overrides remain
    # explicit and can include inputs such as adata or parquet_data.
    traits = constructor.class_traits()
    options = {
        key: value
        for key, value in options.items()
        if key in traits or key in overrides or key in ("matrix", "parquet_data", "name")
    }
    viz = constructor(**options)
    viz._queue_initial_snapshot(snapshot, allow_resize=allow_resize)
    return viz
