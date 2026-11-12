"""Widget module for interactive visualization components."""

import asyncio
from collections.abc import Sequence
import colorsys
import concurrent.futures
import contextlib
from copy import deepcopy
import importlib.metadata
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Literal
import urllib.error
from urllib.parse import quote, urlparse
import uuid
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.affinity import affine_transform
import traitlets

from celldega.nbhd.utils import _nbhd_geometry

from ._widget_lifecycle import CelldegaWidget
from .screenshots import Screenshots


_LOCAL_ESM = (Path(__file__).parent / "../static" / "celldega.js").resolve()
_ESM_CDN = "https://cdn.jsdelivr.net/npm/celldega@{version}/src/celldega/static/celldega.js"


def _serve_local_esm() -> str:
    """Serve the local bundle over HTTP once and return a shim that imports it.

    Uses Celldega's CORS-enabled local server on ``src/celldega/static``. The URL carries
    the bundle's modification time, so a rebuilt bundle is not served from the browser
    cache after a kernel restart.
    """
    from .local_server import get_local_server

    port = get_local_server(_LOCAL_ESM.parent)
    stamp = int(_LOCAL_ESM.stat().st_mtime)
    url = f"http://localhost:{port}/{_LOCAL_ESM.name}?v={stamp}"
    return f"export {{ default }} from '{url}';"


def _resolve_widget_esm() -> "Path | str":
    """Front-end module for the celldega anywidgets.

    Returns the local ``celldega.js`` for development (anywidget inlines it into
    the widget state on save), or a tiny ESM shim that imports the published
    bundle from jsdelivr otherwise. The shim is what lets saved widget state stay
    small: instead of embedding the ~10 MB bundle once per widget, each widget
    stores ~80 bytes and the browser fetches/caches the CDN bundle a single time,
    reused across every widget and notebook.

    Resolution order:
      1. ``CELLDEGA_LOCAL_ESM=serve``                    -> local file served once over
         HTTP, imported by a tiny shim (dev; small widget state, see below).
      2. ``CELLDEGA_LOCAL_ESM`` (any other value) or ``ANYWIDGET_HMR`` set -> local file
         inlined into each widget (dev / HMR).
      3. ``CELLDEGA_ESM_VERSION`` env var               -> CDN at that version.
      4. installed version, if a clean ``X.Y.Z`` release -> CDN at that version.
      5. otherwise (dev / unpublished, e.g. ``0.16.0a1``) -> local file (safe,
         self-contained, since that version may not be on the CDN).

    Inlining puts the whole ~12 MB bundle into every widget's state. A row of linked
    widgets then sends tens of MB at once, and some front ends (notably VS Code) try to
    draw the row before every child widget has arrived ("Error displaying widget: model
    not found"). ``serve`` avoids that while developing against a local build; it needs
    the browser to reach ``localhost`` on the kernel's machine, so it suits a local
    kernel, not a remote JupyterHub.
    """
    local = os.environ.get("CELLDEGA_LOCAL_ESM", "")
    if local.strip().lower() == "serve":
        return _serve_local_esm()
    if local or os.environ.get("ANYWIDGET_HMR"):
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
                "`selection` must be an object with to_json()/to_dict() returning "
                "'ids', a selection dict with 'ids', or a sequence of cell ids."
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


_SHARED_LOCAL_SERVER_PORT: int | None = None


def _zarr_store_url(zarr_url: Any) -> str:
    """URL for an AnnData Zarr store: an http(s) URL as is, or a local path
    served by one shared ``celldega.viz.get_local_server()`` (rooted at cwd)."""
    global _SHARED_LOCAL_SERVER_PORT

    text = os.fspath(zarr_url)
    if urlparse(text).scheme in ("http", "https"):
        return text.rstrip("/")
    path = Path(text).expanduser().resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"No Zarr store at {path}")
    cwd = Path.cwd().resolve()
    try:
        relative = path.relative_to(cwd)
    except ValueError:
        raise ValueError(
            f"zarr_url {path} is outside the working directory {cwd}, which the local "
            "server serves; move the store under it or pass an http(s) URL."
        ) from None
    if _SHARED_LOCAL_SERVER_PORT is None:
        from .local_server import get_local_server

        _SHARED_LOCAL_SERVER_PORT = get_local_server()
    return f"http://localhost:{_SHARED_LOCAL_SERVER_PORT}/{quote(relative.as_posix())}"


# Widget messages much larger than this can fail to reach the browser.
_SIGNATURE_WARN_BYTES = 30_000_000


def _signature_parquet(adata_sig: Any, groupby: str) -> bytes:
    """``adata_sig`` cell-type means as parquet for UMAP/XY viewport estimates.

    Genes are rows and cell types are columns (DegaFiles' df_sig layout), with
    ``groupby`` and ``units`` in the schema's ``viewport_signature`` metadata.
    Genes with no expression in any cell type are dropped.
    """
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq
    from scipy import sparse

    meta = adata_sig.uns.get("viewport_signature") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    # The estimate reads meta["layer"], else the mean counts in layers["counts"]
    # (a "log1p" layer is for z-scored views), else X, else sc.get.aggregate's
    # "mean" layer.
    layer = meta.get("layer") or ("counts" if "counts" in adata_sig.layers else None)
    if layer is not None and layer not in adata_sig.layers:
        raise ValueError(f"adata_sig has no layer {layer!r}.")
    values = adata_sig.layers[layer] if layer is not None else adata_sig.X
    if values is None and "mean" in adata_sig.layers:
        layer, values = "mean", adata_sig.layers["mean"]
    if values is None:
        raise ValueError(
            "adata_sig needs cell-type means in layers['counts'] or X, "
            "or the 'mean' layer of sc.get.aggregate."
        )
    values = np.asarray(values.toarray() if sparse.issparse(values) else values, dtype=np.float32)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("adata_sig must hold finite, nonnegative means (before z-scoring).")
    groups = pd.Index(adata_sig.obs_names.astype(str))
    genes = pd.Index(adata_sig.var_names.astype(str))
    if not (groups.is_unique and genes.is_unique):
        raise ValueError("adata_sig needs unique cell types (obs_names) and genes (var_names).")

    meta = {
        "groupby": meta.get("groupby", groupby),
        "units": (meta.get("layers") or {}).get(layer)
        or meta.get("units", "mean expression per cell"),
    }
    expressed = (values > 0).any(axis=0)
    frame = pd.DataFrame(values[:, expressed].T, index=genes[expressed], columns=groups)
    table = pa.Table.from_pandas(frame.rename_axis("gene").reset_index(), preserve_index=False)
    table = table.replace_schema_metadata(
        {**(table.schema.metadata or {}), b"viewport_signature": json.dumps(meta).encode()}
    )
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    data = buffer.getvalue()
    if len(data) > _SIGNATURE_WARN_BYTES:
        warnings.warn(
            f"adata_sig is {len(data) / 1e6:.0f} MB, which may be too large to send to "
            "the browser; save it as an AnnData Zarr store and pass gene_signature_url.",
            stacklevel=3,
        )
    return data


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


def _coerce_nbhd_for_landscape(
    nbhd_like: Any,
    meta_nbhd: pd.DataFrame | None = None,
) -> tuple[gpd.GeoDataFrame | None, pd.DataFrame | None]:
    """Coerce a GeoDataFrame or neighborhood-like object (e.g. a
    ``celldega.nbhd.NeighborhoodCollection``) into Landscape geometry."""
    if nbhd_like is None:
        return None, meta_nbhd

    if isinstance(nbhd_like, gpd.GeoDataFrame):
        gdf = nbhd_like.copy()
        inferred_meta = None
        prefer_meta_columns = False
    else:
        gdf = _nbhd_geometry(nbhd_like)
        inferred_meta = _metadata_from_nbhd_like(nbhd_like)
        prefer_meta_columns = True
        if gdf is None:
            raise TypeError("nbhd must be a GeoDataFrame or an object exposing to_geodataframe()")

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


class _RasterCapture(traitlets.HasTraits):
    """Mixin: ask the browser for a screenshot of what a widget shows.

    ``request_raster()`` sends the browser a one-off message; its reply fills these
    Python-side traits. They are deliberately *not* synced, so captured images never
    end up in the notebook's saved widget state. Subclasses call
    :meth:`_listen_for_raster` from ``__init__``.
    """

    raster_png = traitlets.Unicode("")
    raster_thumb = traitlets.Unicode("")
    # The exact deck.gl view state (zoom/pan/rotation) at capture time, for
    # reproducibility -- pairs with ``raster_png`` (Landscape; empty for a Clustergram,
    # whose view is reproduced with apply_state).
    raster_view_state = traitlets.Dict(default_value={})
    raster_error = traitlets.Unicode("")
    # Id of the latest request the browser answered (successfully or not). Set last,
    # so observers of this trait see the finished capture.
    raster_capture_id = traitlets.Int(0)
    latest_snapshot = traitlets.Dict(default_value={})
    snapshot_error = traitlets.Unicode("")
    snapshot_capture_id = traitlets.Int(0)
    # Optional, producer-declared immutable revision of the data (a release tag, a
    # commit hash, or dega.viz.fingerprint_dataset(...)). Saved views record it, and
    # restoring compares it when both the view and the widget declare one.
    data_revision = traitlets.Unicode("").tag(sync=True)

    def request_snapshot(
        self,
        *,
        max_size=1024,
        thumb_size=192,
        description=None,
        author=None,
        background: str | None = "white",
        **state_options,
    ) -> int:
        """Capture image, observed state, replay settings and identity in one browser task.

        ``background`` is a CSS color behind the image where the visualization draws
        nothing (white by default); ``None`` keeps the canvas's transparency.

        The asynchronous reply sets ``latest_snapshot`` and ``snapshot_capture_id``.
        These traits are never synced or embedded in notebook widget state.
        """
        metadata = {
            key: value
            for key, value in {"description": description, "author": author}.items()
            if value is not None
        }
        if any(not isinstance(value, str) for value in metadata.values()):
            raise ValueError("description and author must be strings")
        if background is not None and not isinstance(background, str):
            raise ValueError("background must be a CSS color string or None")
        self._snapshot_request_id += 1
        self.send(
            {
                "event": "capture_snapshot",
                "id": self._snapshot_request_id,
                "options": {
                    "max_size": int(max_size),
                    "thumb_size": int(thumb_size),
                    "background": background,
                    "state": state_options,
                    **metadata,
                },
            }
        )
        return self._snapshot_request_id

    def _on_snapshot_msg(self, _widget, content, _buffers) -> None:
        if not isinstance(content, dict) or content.get("event") not in (
            "snapshot",
            "snapshot_error",
        ):
            return
        rid = content.get("id")
        if not isinstance(rid, int) or not 0 < rid <= self._snapshot_request_id:
            return
        self._snapshot_replies[rid] = deepcopy(content)
        while len(self._snapshot_replies) > 64:
            del self._snapshot_replies[next(iter(self._snapshot_replies))]
        if rid >= self._latest_snapshot_id:
            self._latest_snapshot_id = rid
            self.snapshot_error = str(content.get("error") or "")
            if content["event"] == "snapshot":
                snapshot = deepcopy(content.get("snapshot") or {})
                self.latest_snapshot = snapshot
                image = snapshot.get("image") or {}
                self.raster_view_state = dict(image.get("view_state") or {})
                self.raster_thumb = image.get("thumb") or ""
                self.raster_png = image.get("png") or ""
                if hasattr(self, "latest_state"):
                    self.latest_state = dict(snapshot.get("observed_state") or {})
        # Every reply wakes waiters; callers match the exact request id in the cache.
        self.snapshot_capture_id = rid

    def request_raster(self, max_size: int = 1024, thumb_size: int = 192) -> int:
        """Ask the browser to capture the current view.

        Capture is asynchronous. The reply sets ``raster_png`` (base64 PNG with no
        ``data:`` prefix, longest side at most ``max_size`` px), ``raster_thumb`` (a
        preview at most ``thumb_size`` px) and ``raster_view_state`` (the exact zoom/pan
        at capture time). ``observe`` those traits, or read them once the browser has
        replied; a failed capture sets ``raster_error`` instead. Nothing is written to
        disk.

        Args:
            max_size (int): Longest side of the captured image, in pixels.
            thumb_size (int): Longest side of the preview, in pixels.

        Returns:
            int: The id of this request.
        """
        self._raster_request_id += 1
        self.send(
            {
                "event": "capture_raster",
                "id": self._raster_request_id,
                "max_size": int(max_size),
                "thumb_size": int(thumb_size),
            }
        )
        return self._raster_request_id

    def _listen_for_raster(self) -> None:
        self._raster_request_id = 0
        self._snapshot_request_id = 0
        self._latest_snapshot_id = 0
        self._snapshot_replies = {}
        self.on_msg(self._on_custom_msg)
        self.on_msg(self._on_snapshot_msg)

    def _on_custom_msg(self, _widget, content, _buffers) -> None:
        """Handle a screenshot reply from the browser."""
        if not isinstance(content, dict):
            return
        event = content.get("event")
        if event not in ("raster", "raster_error"):
            return
        reply_id = content.get("id")
        reply_id = reply_id if isinstance(reply_id, int) else self.raster_capture_id
        # Ignore stale replies (e.g. a second view answering an older request).
        if reply_id < self.raster_capture_id:
            return
        if event == "raster_error":
            self.raster_error = str(content.get("error") or "Raster capture failed")
        else:
            self.raster_error = ""
            # View state and preview first, so observers of ``raster_png`` see a
            # consistent capture.
            self.raster_view_state = dict(content.get("view_state") or {})
            self.raster_thumb = content.get("thumb") or ""
            self.raster_png = content.get("png") or ""
        self.raster_capture_id = reply_id


class _StateGetter(traitlets.HasTraits):
    """Mixin: request bounded observations of what a widget shows (the getter).

    The widget's front end answers a ``{"event": "get_state", "id", "options"}``
    message with ``{"event": "state", "id", "state"}`` (or ``"state_error"``). The
    snapshot is kept Python-side only -- these traits are never synced, so snapshots
    are not saved into the notebook's widget state. Subclasses call
    :meth:`_listen_for_state` from ``__init__`` and expose a ``request_state`` method
    that builds the options.
    """

    latest_state = traitlets.Dict(default_value={})
    state_error = traitlets.Unicode("")
    # Id of the latest request the browser answered (successfully or not). Set last,
    # so observers of this trait see the finished snapshot.
    state_capture_id = traitlets.Int(0)

    def _listen_for_state(self) -> None:
        self._state_request_id = 0
        self.on_msg(self._on_state_msg)

    def _send_state_request(self, options: dict) -> int:
        self._state_request_id += 1
        self.send({"event": "get_state", "id": self._state_request_id, "options": options})
        return self._state_request_id

    def _on_state_msg(self, _widget, content, _buffers) -> None:
        if not isinstance(content, dict) or content.get("event") not in ("state", "state_error"):
            return
        reply_id = content.get("id")
        reply_id = reply_id if isinstance(reply_id, int) else self.state_capture_id
        if reply_id < self.state_capture_id:
            return  # stale reply (e.g. a second view answering an older request)
        if content["event"] == "state_error":
            self.state_error = str(content.get("error") or "State snapshot failed")
        else:
            self.state_error = ""
            self.latest_state = dict(content.get("state") or {})
        self.state_capture_id = reply_id


class _StateSnapshots(_StateGetter):
    """Mixin: the getter plus setters and saved-view restores, with acknowledgements.

    For widgets whose front end applies ``apply_state`` and ``restore_snapshot``
    (Landscape, Clustergram and the spatial clouds); subclasses define
    ``apply_state``.

    Python can't wait for the browser inside the cell that sent a request: the
    kernel handles the browser's reply only after the cell finishes. Check
    :meth:`get_apply_result` (or observe ``apply_capture_id``) from a later cell;
    :meth:`wait_for_apply` and :meth:`apply_state_async` are for code running
    outside a cell, such as a background task or an application.
    """

    apply_error = traitlets.Unicode("")
    apply_capture_id = traitlets.Int(0)
    # from_png constructs a widget before it has a browser view. A synced
    # one-shot request survives that gap; the renderer consumes and clears it.
    _initial_snapshot = traitlets.Dict(default_value={}).tag(sync=True)

    @property
    def apply_request_id(self) -> int:
        """ID of the last submitted setter; submission alone is not success."""
        return self._apply_request_id

    def get_apply_result(self, request_id: int) -> dict | None:
        """This request's acknowledgement (``None`` while pending), never a newer one's.

        In a notebook, call it from a cell after the one that made the request.
        """
        return deepcopy(self._apply_replies.get(request_id))

    async def wait_for_apply(self, request_id: int, *, timeout: float = 10) -> list[str]:
        """Await an exact browser acknowledgement; timeout does not cancel browser work.

        Not from the notebook cell that made the request: the reply can't arrive
        until that cell finishes, so the wait would time out. Use it from a
        background task (``asyncio.ensure_future``) or an application; in a
        notebook, check :meth:`get_apply_result` in a later cell instead.

        Browser failures may leave partial changes. A timed-out call raises rather
        than claiming success; recapture the view before using it as evidence.
        """
        if not isinstance(request_id, int) or request_id < 1:
            raise ValueError("request_id must be a positive integer")
        if not isinstance(timeout, int | float) or not np.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            reply = self.get_apply_result(request_id)
            if reply is not None:
                if reply["event"] == "apply_error":
                    raise ValueError(reply.get("error") or "apply_state failed")
                return list(reply.get("done") or [])
            if loop.time() >= deadline:
                raise TimeoutError(
                    f"No browser acknowledgement for request {request_id} within "
                    f"{timeout:g} s. Awaited in the notebook cell that sent it? The "
                    "reply arrives only after the cell finishes: check "
                    f"get_apply_result({request_id}) in a later cell."
                )
            await asyncio.sleep(min(0.01, max(0, deadline - loop.time())))

    async def apply_state_async(self, changes: dict, *, timeout: float = 10) -> list[str]:
        """Submit settings and return after the browser confirms completion.

        Like :meth:`wait_for_apply`, not from the notebook cell that sends them.
        """
        if not isinstance(timeout, int | float) or not np.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        self.apply_state(changes)
        return await self.wait_for_apply(self.apply_request_id, timeout=timeout)

    def restore_snapshot(
        self,
        snapshot: dict,
        *,
        allow_resize: bool = False,
        allow_unverified: bool | None = None,  # accepted for earlier callers; not needed
    ) -> int:
        """Restore a saved view's supported settings, after the browser checks it fits.

        The browser compares the saved view's data identity (cell, gene and
        cluster-label names, or a Clustergram's row and column names, plus a declared
        ``data_revision``) and canvas size with what it shows, and changes nothing if
        either differs. ``allow_resize=True`` accepts a different canvas size.
        ``allow_unverified`` is accepted for earlier callers and ignored: saved views
        no longer need it.

        Returns a request id: check :meth:`get_apply_result` in a later cell, or
        observe ``apply_capture_id`` / ``apply_error``.
        """
        from .snapshots import validate_snapshot

        if not isinstance(allow_resize, bool):
            raise ValueError("allow_resize must be a boolean")
        validate_snapshot(snapshot)
        self._apply_request_id += 1
        self.send(
            {
                "event": "restore_snapshot",
                "id": self._apply_request_id,
                "snapshot": deepcopy(snapshot),
                "options": {"allow_resize": allow_resize},
            }
        )
        return self._apply_request_id

    def restore_png(self, path: str | Path, *, panel: int = 0, allow_resize: bool = False) -> int:
        """Restore a PNG's saved panel into this already displayed visualization.

        Use ``dega.viz.from_png`` to construct a fresh widget instead. Returns an
        acknowledgement request id, as :meth:`restore_snapshot` does.
        """
        from .reopen import _png_panel

        _saved, snapshot = _png_panel(path, panel)
        return self.restore_snapshot(snapshot, allow_resize=allow_resize)

    def _queue_initial_snapshot(self, snapshot: dict, *, allow_resize: bool = False) -> int:
        """Queue from_png's one-shot restore for the first browser render."""
        from .snapshots import validate_snapshot

        validate_snapshot(snapshot)
        if not isinstance(allow_resize, bool):
            raise ValueError("allow_resize must be a boolean")
        self._apply_request_id += 1
        self._initial_snapshot = {
            "event": "restore_snapshot",
            "id": self._apply_request_id,
            "snapshot": deepcopy(snapshot),
            "options": {"allow_resize": allow_resize},
        }
        return self._apply_request_id

    def _listen_for_state(self) -> None:
        super()._listen_for_state()
        self._apply_request_id = 0
        self._apply_replies = {}
        self._latest_apply_id = 0
        self.on_msg(self._on_apply_msg)

    def _send_apply_request(self, changes: dict) -> int:
        self._apply_request_id += 1
        self.send({"event": "apply_state", "id": self._apply_request_id, "changes": changes})
        return self._apply_request_id

    def _on_apply_msg(self, _widget, content, _buffers) -> None:
        if not isinstance(content, dict) or content.get("event") not in ("applied", "apply_error"):
            return
        reply_id = content.get("id")
        if not isinstance(reply_id, int):
            return
        self._apply_replies[reply_id] = dict(content)
        while len(self._apply_replies) > 64:
            del self._apply_replies[next(iter(self._apply_replies))]
        if reply_id >= self._latest_apply_id:
            self._latest_apply_id = reply_id
            self.apply_error = (
                str(content.get("error") or "apply_state failed")
                if content["event"] == "apply_error"
                else ""
            )
        self.apply_capture_id = reply_id


class Landscape(Screenshots, _RasterCapture, _StateSnapshots, CelldegaWidget):
    """
    Interactive spatial tissue and low dimensional embedding landscapes.

    Spatial datasets read image, cell-boundary, transcript, and expression
    DegaFiles through ``base_url``. Single-cell UMAP/XY views can instead read
    AnnData Zarr through ``zarr_url``. The browser loads the source files
    directly; optional ``adata`` supplies metadata, colors, and UMAP positions.
    See the Landscape guide and File Formats documentation for storage layouts.

    Args:
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        min_zoom (float, optional): Furthest zoom out. Default: one zoom level
            past the tissue-wide view.
        max_zoom (float, optional): Closest zoom in. Default: about 10 µm
            across the map's shorter side.
        max_tiles_to_view (int, optional): Tiles in view below which
            transcripts and cell boundaries load automatically (close-up).
            Default: 50.
        intermediate_zoom_limit (float, optional): How far out the TRX button
            can still load transcripts and cell boundaries on demand, as a
            multiple of ``max_tiles_to_view``. This counts tiles, so 9 allows a
            view 3 times wider than close-up. 1 turns this off. Default: 9.
        rotation_orbit (float, optional): Rotating angle around orbit axis for
            point-cloud views.
        rotation_x (float, optional): Rotating angle around X axis for
            point-cloud views.
        token (str): The token traitlet.
        base_url (str or list): DegaFiles URL(s), mutually exclusive with
            zarr_url. Can be a single string
            or a list of dicts with 'url' and 'label' keys for multiple datasets.
            Example: [{'url': 'http://...', 'label': 'Dataset1'}, ...]
            You can also pass a simple list of URL strings.
        zarr_url (str or Path, optional): A single-cell AnnData Zarr store to read
            instead of DegaFiles (``technology="Chromium"``, the default with
            ``zarr_url``): an http(s) URL, e.g. on Hugging Face, or a local path
            under the working directory, served by a local server. Gene
            expression comes from a CSC matrix in the store, ``X`` or a layer
            such as ``adata.layers["counts_csc"] = adata.layers["counts"].tocsc()``.
            Optional ``var["mean"]`` and ``var["max"]`` hold the gene statistics
            DegaFiles keep in ``meta_gene.parquet``; cell attributes, cluster
            colors (``uns[f"{cluster_attr}_colors"]``), and ``obsm["X_umap"]`` come
            from the store unless ``adata`` is passed too. Consolidate the store's
            metadata (``zarr.consolidate_metadata``) so it opens in one request.
        zarr_layer (str, optional): The ``zarr_url`` layer to read expression
            from, or ``"X"``. By default, ``X`` if it is CSC, else the store's
            only CSC layer.
        gene_signature_url (str or Path, optional): Dense AnnData Zarr of cell-type
            mean expression for UMAP/XY viewport estimates. ``obs_names`` match
            the cell category labels and ``var_names`` are genes. The estimate
            reads nonnegative means from ``layers['counts']`` (mean counts per
            cell) when present, else ``X``; a ``layers['log1p']`` of mean log1p
            expression can sit alongside for z-scored views. ``uns['viewport_signature']``
            is a JSON string with ``groupby`` (the cell attribute) and
            ``units``, and optionally ``layer`` (the layer to read) and
            ``layers`` (units per layer).
        adata_sig (AnnData, optional): The same cell-type means as an in-memory
            AnnData, read the same way, e.g. ``sc.get.aggregate(adata,
            by="leiden", func="mean", layer="counts")`` (whose ``"mean"`` layer
            is used when there is neither ``layers['counts']`` nor ``X``). Sent
            with the widget, so keep it to tens of MB; save larger signatures to
            Zarr for ``gene_signature_url``. ``groupby`` defaults to
            ``cluster_attr`` and ``units`` to "mean expression per cell" unless
            ``uns['viewport_signature']`` sets them. Spatial DegaFiles fall back
            to their own ``df_sig.parquet`` for their clusters.
        dataset_names (list, optional): Short names for the datasets to display in
            the dropdown selector. Should match the length of base_urls.
            Example: ['Brain', 'Kidney'] for two datasets.
        rotate (float, optional): Degrees to rotate the 2D landscape visualization.
        adata (AnnData, optional): Cell metadata from ``obs``, cluster colors
            from ``uns``, and UMAP coordinates from ``obsm["X_umap"]``.
            Overrides source metadata; ``obs_names`` must match source cell IDs.
            Expression is read from DegaFiles or Zarr, not from this object.
        AnnData (AnnData, optional): Alias of adata.
        cluster_attr (str, optional): Cell attribute used for cluster colors and
            composition bars. Default: "leiden".
        cell_attr (list of str, optional): Cell attributes to expose. The
            cluster_attr is always included. Default: ["leiden"].
        landscape_state (str, optional): "spatial", "umap", or "xy", depending
            on the available data. Single-cell data defaults to UMAP when
            supplied, otherwise XY.
        xy_genes (list of str, optional): Genes for the X and Y expression axes.
            When empty at initialization, uses the two genes with the highest
            whole-dataset mean expression; ties/missing statistics use dataset
            gene order. Explicit axes and later saved-view restores take precedence.
        xy_scale (str, optional): "linear" or "log1p". Default: "log1p".
        nbhd (GeoDataFrame, optional): Neighborhood polygons, or an object
            exposing to_geodataframe(). Polygons retain their spatial/UMAP/XY
            coordinate-space metadata.
        nbhd_edit (bool, optional): Enable neighborhood editing. Default: False.
        dataset_name (str, optional): The name of the dataset to visualize. This
            will show up in the user interface bar.
        cell_name_prefix (bool, optional): If True, cell names in adata.obs.index
            are assumed to have a dataset prefix (e.g., "dataset-name_cell-name")
            that should be trimmed when mapping to DegaFiles. Default: False.
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
    (e.g. :func:`celldega.pre.write_point_cloud_dataset` for a 3D ``AnnData``).
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
    # Single-cell data from an AnnData Zarr store instead of DegaFiles.
    zarr_url = traitlets.Unicode("").tag(sync=True)
    zarr_layer = traitlets.Unicode("").tag(sync=True)
    # List of dataset configurations: [{'url': str, 'label': str}, ...]
    base_urls = traitlets.List(trait=traitlets.Dict(), default_value=[]).tag(sync=True)
    cell_name_prefix = traitlets.Bool(False).tag(sync=True)
    token = traitlets.Unicode("").tag(sync=True)
    creds = traitlets.Dict({}).tag(sync=True)
    max_tiles_to_view = traitlets.Int(50).tag(sync=True)
    intermediate_zoom_limit = traitlets.Float(9.0).tag(sync=True)

    ini_x = traitlets.Float().tag(sync=True)
    ini_y = traitlets.Float().tag(sync=True)
    ini_z = traitlets.Float().tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    min_zoom = traitlets.Float(default_value=None, allow_none=True).tag(sync=True)
    max_zoom = traitlets.Float(default_value=None, allow_none=True).tag(sync=True)
    rotation_orbit = traitlets.Float(0).tag(sync=True)
    rotation_x = traitlets.Float(0).tag(sync=True)
    rotate = traitlets.Float(0).tag(sync=True)
    dataset_name = traitlets.Unicode("").tag(sync=True)
    region = traitlets.Dict({}).tag(sync=True)
    scale_bar_microns_per_pixel = traitlets.Float(default_value=None, allow_none=True).tag(
        sync=True
    )

    # All neighborhoods, with a `space` column and full coordinate_space metadata.
    nbhd = traitlets.Instance(gpd.GeoDataFrame, allow_none=True)
    nbhd_geojson = traitlets.Dict({}).tag(sync=True)

    # Enable editing of neighborhoods when True
    nbhd_edit = traitlets.Bool(False).tag(sync=True)

    meta_nbhd = traitlets.Instance(pd.DataFrame, allow_none=True)

    meta_cluster = traitlets.Dict({}).tag(sync=True)
    #: Pins shown with the PINS button (see :attr:`pins`): name, memo, position and
    #: saved view of each Snapshot.
    pin_data = traitlets.List(default_value=[]).tag(sync=True)
    #: Whether the pins are shown (the PINS button toggles it).
    show_pins = traitlets.Bool(False).tag(sync=True)
    #: A Snapshot card asks to open its view (``{"id", "snapshot"}``) and the browser
    #: answers in ``view_result``; linked in the browser, so cards work without a
    #: kernel too (see :class:`Snapshot`).
    view_request = traitlets.Dict({}).tag(sync=True)
    view_result = traitlets.Dict({}).tag(sync=True)
    _JS_VIEW_LINK = True
    selected_cells = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)
    #: Clusters highlighted in the browser while cells are colored by cluster (set by
    #: the front end; a linked Clustergram shows them as blue column labels).
    selected_clusters = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)
    landscape_state = traitlets.Unicode("spatial").tag(sync=True)
    xy_genes = traitlets.List(trait=traitlets.Unicode(), default_value=[], maxlen=2).tag(sync=True)
    xy_scale = traitlets.Enum(["linear", "log1p"], default_value="log1p").tag(sync=True)
    gene_signature_url = traitlets.Unicode("").tag(sync=True)
    # All drawn NBHDs keep their coordinate space. Only physical polygons
    # receive a tissue affine when exposed as a Python GeoDataFrame.
    gates = traitlets.Dict({"type": "FeatureCollection", "features": []}).tag(sync=True)
    view_space = traitlets.Dict({}).tag(sync=True)

    update_trigger = traitlets.Dict().tag(sync=True)
    # Browser-linked gene focus (e.g. a click in Enrich). The front end turns
    # this into the same gene-selection action as a Clustergram row click.
    focused_gene = traitlets.Unicode("").tag(sync=True)
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
    # celldega.pre.write_point_cloud_dataset(name=...)) while clusters/genes keep
    # loading from their normal (segmentation-driven) paths.
    alignment = traitlets.Unicode("").tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(600).tag(sync=True)

    use_adata_3d_centroids = traitlets.Bool(True).tag(sync=True)
    centroids_url = traitlets.Unicode("").tag(sync=True)

    #: Keys :meth:`apply_state` understands.
    APPLY_STATE_KEYS = (
        "clusters",
        "genes",
        "view",
        "zoom_to",
        "reset_view",
        "space",
        "layers",
        "channels",
        "sliders",
        "image_source",
        "selected_cells",
        "xy",
    )

    def request_state(self, max_bars: int = 25) -> int:
        """Ask the browser for a snapshot of what this Landscape shows.

        The snapshot holds the space (spatial / UMAP), the camera (target, zoom), how
        cells are colored (``"cluster"`` or genes), the selected clusters and genes,
        and the cluster and gene counts in the current field of view (as in the bar
        charts). Asynchronous: the reply sets :attr:`latest_state`. Drawn
        neighborhoods are already in Python: see :meth:`neighborhood_summary`.

        Args:
            max_bars: Cap on the clusters and genes listed for the field of view.

        Returns:
            int: The id of this request.
        """
        return self._send_state_request({"max_bars": int(max_bars)})

    def apply_state(self, changes: dict) -> list[str]:
        """Change what the Landscape shows, as its controls would.

        Input structure is validated here, so mistakes raise in the calling cell.
        Availability (names, layers, views) is checked in the browser, which then
        applies the changes; check :meth:`get_apply_result` with
        :attr:`apply_request_id` in a later cell, or observe ``apply_capture_id`` and
        ``apply_error``. Runtime failures may leave partial changes.

        Args:
            changes: Any of:

                - ``clusters``: cluster names to select / highlight (exactly; ``[]``
                  clears the selection), like clicking cluster bars.
                - ``genes``: genes to color cells by (up to 20; ``[]`` returns to
                  cluster colors), like the comma-separated gene search.
                - ``view``: ``{"target": [x, y], "zoom": z}`` camera position (orbit
                  views also take ``rotationOrbit`` and ``rotationX``).
                - ``zoom_to``: ``{"clusters": [...]}`` or ``{"cells": [...]}`` to frame
                  those cells (spatial view).
                - ``reset_view``: ``True`` to return to the starting view.
                - ``space``: ``"spatial"``, ``"umap"`` or ``"xy"``.
                - ``selected_cells``: cell names to select (``[]`` clears them).
                - ``xy``: ``{"genes": [x_gene, y_gene], "scale": "linear" | "log1p"}``
                  for the XY expression view (up to two genes).
                - ``layers``: booleans for image, cells, transcripts, neighborhoods.
                - ``channels``: ``{name: {"visible": bool, "intensity": 0..100}}``.
                - ``sliders``: cell/nbhd values and ``trx: {"size": ..., "opacity": ...}``.
                - ``image_source``: ``"primary"`` or ``"he"`` (when available).

        Returns:
            list[str]: What was submitted; not confirmation that the browser applied it.

        Raises:
            ValueError: For an unknown key or an invalid value (nothing changes).
        """
        if not isinstance(changes, dict):
            raise ValueError("changes must be a dict")
        unknown = sorted(set(changes) - set(self.APPLY_STATE_KEYS))
        if unknown:
            raise ValueError(
                f"Unknown Landscape setting(s): {unknown}; supported: {list(self.APPLY_STATE_KEYS)}"
            )

        def _names(key):
            value = changes[key]
            if isinstance(value, str) or not isinstance(value, list | tuple):
                raise ValueError(f"{key} must be a list of names")
            return [str(v) for v in value]

        browser: dict[str, Any] = {}
        described: list[str] = []
        for key in ("layers", "channels", "sliders"):
            if key in changes:
                _validate_landscape_controls(key, changes[key])
                browser[key] = deepcopy(changes[key])
                described.append(f"updated {key}")
        if "image_source" in changes:
            if changes["image_source"] not in ("primary", "he"):
                raise ValueError("image_source must be 'primary' or 'he'")
            browser["image_source"] = changes["image_source"]
            described.append("updated image_source")
        if "clusters" in changes:
            browser["clusters"] = _names("clusters")
            described.append(
                f"highlighted clusters {', '.join(browser['clusters'])}"
                if browser["clusters"]
                else "cleared the cluster selection"
            )
        if "genes" in changes:
            browser["genes"] = _names("genes")
            if len(browser["genes"]) > 20:
                raise ValueError("genes supports at most 20 names")
            described.append(
                f"colored cells by {', '.join(browser['genes'])}"
                if browser["genes"]
                else "returned to cluster colors"
            )
        if "selected_cells" in changes:
            browser["selected_cells"] = _names("selected_cells")
            described.append("updated selected cells")
        if "xy" in changes:
            xy = changes["xy"]
            if (
                not isinstance(xy, dict)
                or set(xy) != {"genes", "scale"}
                or not isinstance(xy["genes"], list | tuple)
                or len(xy["genes"]) > 2
                or any(not isinstance(g, str) or not g for g in xy["genes"])
                or xy["scale"] not in ("linear", "log1p")
            ):
                raise ValueError("xy requires up to two genes and a linear or log1p scale")
            browser["xy"] = deepcopy(xy)
            described.append("updated XY axes")
        if "reset_view" in changes and not isinstance(changes["reset_view"], bool):
            raise ValueError("reset_view must be a boolean")
        camera_keys = [
            key
            for key in ("view", "zoom_to", "reset_view")
            if key in changes and (key != "reset_view" or changes[key])
        ]
        if len(camera_keys) > 1:
            raise ValueError("pass only one of view, zoom_to or reset_view")
        if changes.get("reset_view"):
            browser["reset_view"] = True
            described.append("reset the view")
        elif "zoom_to" in changes:
            target = changes["zoom_to"]
            if (
                not isinstance(target, dict)
                or len(target) != 1
                or not (target.get("clusters") or target.get("cells"))
            ):
                raise ValueError("zoom_to must be {'clusters': [...]} or {'cells': [...]}")
            key = "clusters" if target.get("clusters") else "cells"
            names = target[key]
            if isinstance(names, str) or not isinstance(names, list | tuple):
                raise ValueError(f"zoom_to.{key} must be a list of names")
            browser["zoom_to"] = {key: [str(n) for n in names]}
            described.append(f"zoomed to {key} {', '.join(map(str, names[:10]))}")
        elif "view" in changes:
            view = changes["view"]
            if (
                not isinstance(view, dict)
                or not view
                or set(view) - {"target", "zoom", "rotationOrbit", "rotationX"}
            ):
                raise ValueError("view must be {'target': [x, y], 'zoom': z}")
            if "target" in view and (
                not isinstance(view["target"], list | tuple) or len(view["target"]) not in (2, 3)
            ):
                raise ValueError("view.target must contain two or three finite numbers")
            try:
                browser["view"] = {
                    k: ([float(v) for v in view[k]] if k == "target" else float(view[k]))
                    for k in ("target", "zoom", "rotationOrbit", "rotationX")
                    if k in view
                }
                if not all(np.all(np.isfinite(v)) for v in browser["view"].values()):
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError("view coordinates and zoom must be finite numbers") from None
            described.append("moved the view")
        space = changes.get("space")
        if space is not None and space not in ("spatial", "umap", "xy"):
            raise ValueError("space must be 'spatial', 'umap' or 'xy'")
        if "zoom_to" in browser and (space or self.landscape_state) != "spatial":
            raise ValueError("zoom_to works in the spatial view; switch space first")

        if space is not None:
            browser["space"] = space
            described.append(f"switched to the {space} view")
        self._send_apply_request(browser)
        return described

    def neighborhood_summary(self, max_clusters: int = 8) -> list[dict]:
        """Drawn neighborhoods, with each one's cell count and cluster mix.

        Reads :attr:`nbhd_polygons` (regions drawn in the Landscape, in any space) and
        this Landscape's per-cell clusters (``meta_cell[cluster_attr]``).

        Returns:
            list[dict]: ``{"name", "space", "n_cells", "clusters": [{"name", "count",
            "fraction"}, ...]}`` per neighborhood, largest clusters first.
        """
        frame = self.nbhd_polygons
        if frame.empty:
            return []
        clusters = None
        meta = self.meta_cell
        if isinstance(meta, pd.DataFrame) and self.cluster_attr in meta:
            clusters = meta[self.cluster_attr].astype(str)
            clusters.index = clusters.index.astype(str)
        summary = []
        for _, row in frame.iterrows():
            ids = row.get("cell_ids")
            ids = [str(i) for i in ids] if isinstance(ids, list | tuple | np.ndarray) else []
            entry: dict[str, Any] = {
                "name": str(row.get("name") or ""),
                "space": row.get("space"),
                "n_cells": len(ids),
                "clusters": [],
            }
            if clusters is not None and ids:
                counts = clusters.reindex(ids).dropna().value_counts()
                total = int(counts.sum())
                entry["clusters"] = [
                    {"name": str(name), "count": int(count), "fraction": round(count / total, 3)}
                    for name, count in counts.head(max_clusters).items()
                ]
            summary.append(entry)
        return summary

    def __init__(self, **kwargs):
        # Snapshots to pin on the tissue (``snapshots=``; ``pins=`` is an alias).
        pins = kwargs.pop("snapshots", None)
        pins = kwargs.pop("pins", None) if pins is None else pins
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

        if kwargs.get("zarr_url"):
            if kwargs.get("base_url") or kwargs.get("base_urls"):
                raise ValueError(
                    "Pass either base_url (DegaFiles) or zarr_url (AnnData Zarr), not both."
                )
            technology = kwargs.setdefault("technology", "Chromium")
            if technology != "Chromium":
                raise ValueError("zarr_url supports technology='Chromium' only.")
            kwargs["zarr_url"] = _zarr_store_url(kwargs["zarr_url"])
            if transform is None:
                transform = np.eye(3)

        if kwargs.get("gene_signature_url"):
            kwargs["gene_signature_url"] = _zarr_store_url(kwargs["gene_signature_url"])

        adata_sig = kwargs.pop("adata_sig", None)
        pq_signatures = None
        if adata_sig is not None:
            if kwargs.get("gene_signature_url"):
                raise ValueError("Pass either adata_sig or gene_signature_url, not both.")
            pq_signatures = _signature_parquet(adata_sig, cluster_attr)

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
        if pq_signatures is not None:
            parquet_traits["gene_signature_parquet"] = traitlets.Bytes(pq_signatures).tag(sync=True)

        if parquet_traits:
            self.add_traits(**parquet_traits)

        super().__init__(**kwargs)

        self._listen_for_raster()
        self._listen_for_pics()
        self._listen_for_state()
        if pins is not None:
            self.pins = pins

        self.cell_attr = cell_attr
        self.cluster_attr = cluster_attr
        self.centroids_url = centroids_url

        # store DataFrames locally without syncing to the frontend
        self.meta_cell = meta_cell_df
        self.meta_nbhd = meta_nbhd_df
        self.nbhd = nbhd_gdf
        self.nbhd_edit = nbhd_edit
        self.umap = umap_df
        self._adata = adata
        if meta_cluster_df is not None:
            self.meta_cluster_df = meta_cluster_df

        # A frame returned by another Landscape can contain multiple spaces.
        # Convert only native tissue geometry to image pixels; embedding
        # polygons already carry their displayed coordinates and axis metadata.
        if nbhd_gdf is not None:
            gdf_viz = nbhd_gdf.copy()
            spaces = [
                value if isinstance(value, dict) else {"kind": "spatial"}
                for value in gdf_viz.get("coordinate_space", [None] * len(gdf_viz))
            ]
            if "coordinate_space" in gdf_viz:
                gdf_viz["coordinate_space"] = spaces
            physical = np.array([space.get("kind") == "spatial" for space in spaces], dtype=bool)
            a, b, tx = transformation_matrix[0]
            c, d, ty = transformation_matrix[1]
            gdf_viz.loc[physical, "geometry"] = gdf_viz.loc[physical, "geometry"].map(
                lambda geom: affine_transform(geom, [a, b, c, d, tx, ty])
            )
            if "geometry_pixel" in gdf_viz:
                has_pixels = physical & gdf_viz["geometry_pixel"].notna()
                gdf_viz.loc[has_pixels, "geometry"] = gdf_viz.loc[has_pixels, "geometry_pixel"]
                gdf_viz = gdf_viz.drop(columns="geometry_pixel")

            self.nbhd_geojson = json.loads(gdf_viz.loc[physical].to_json())
            embedded = json.loads(gdf_viz.loc[~physical].to_json())["features"]
            if embedded:
                self.gates = {
                    "type": "FeatureCollection",
                    "features": [*embedded, *self.gates.get("features", [])],
                }
        elif self.nbhd_edit:
            self.nbhd_geojson = {"type": "FeatureCollection", "features": []}

        # Restore gates supplied at construction after initializing the legacy
        # physical-neighborhood input. Every Landscape exposes the same frame.
        if self.gates.get("features"):
            self._on_gates_change({"old": {}, "new": self.gates})
        else:
            self.nbhd = self.nbhd_polygons

    def trigger_update(self, new_value):
        """Update the update_trigger traitlet with a new value."""
        self.update_trigger = new_value

    def update_cell_clusters(self, new_clusters):
        """Update cell clusters with new data."""
        self.cell_clusters = new_clusters

    def highlight_cells(self, cell_ids):
        """Highlight specific cells by their identifiers."""

        self.selected_cells = list(cell_ids)

    def set_xy(self, x_gene=None, y_gene=None, *, scale="log1p"):
        """Show source expression on X/Y, using linear or log1p scaling.

        Both genes may be omitted to start with all cells overlapping. A gene
        for Y requires a gene for X. No UMAP is required. Return with
        ``landscape_state = 'spatial'`` (or ``'umap'`` when available).
        """
        if y_gene and not x_gene:
            raise ValueError("Specify an X gene before a Y gene.")
        if scale not in ("linear", "log1p"):
            raise ValueError("scale must be 'linear' or 'log1p'.")
        genes = [gene for gene in (x_gene, y_gene) if gene]
        if self._adata is not None:
            missing = set(genes) - set(self._adata.var_names)
            if missing:
                raise ValueError(f"Unknown genes: {sorted(missing)}")
        with self.hold_trait_notifications():
            self.xy_scale = scale
            self.xy_genes = genes
            self.landscape_state = "xy"

    def get_selected_cells(self, adata=None):
        """Return selected IDs, or a copied AnnData subset when ``adata`` is supplied."""
        ids = list(self.selected_cells)
        if adata is None:
            return ids
        return adata[adata.obs_names.isin(ids)].copy()

    def save_gates(self, path):
        """Save named polygons, coordinate spaces and selected cell IDs as GeoJSON."""
        path = Path(path)
        path.write_text(json.dumps(self.gates, indent=2), encoding="utf-8")
        return path

    def load_gates(self, path):
        """Restore NBHDs; only polygons matching the current coordinate space are drawn."""
        gates = json.loads(Path(path).read_text(encoding="utf-8"))
        if gates.get("type") != "FeatureCollection" or not isinstance(gates.get("features"), list):
            raise ValueError("Expected a GeoJSON FeatureCollection.")
        for feature in gates["features"]:
            space = feature.get("properties", {}).get("coordinate_space", {})
            if space.get("kind") not in ("spatial", "umap", "xy") or feature.get(
                "geometry", {}
            ).get("type") not in ("Polygon", "MultiPolygon"):
                raise ValueError("Each NBHD needs polygon geometry and a physical/UMAP/XY space.")
        self.gates = gates

    def select_gate(self, name):
        """Restore a gate's view and select its saved cells (names must be unambiguous)."""
        matches = [
            feature
            for feature in self.gates.get("features", [])
            if feature.get("properties", {}).get("name") == name
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected one gate named {name!r}; found {len(matches)}.")
        props = matches[0]["properties"]
        space = props["coordinate_space"]
        if space["kind"] == "xy":
            self.set_xy(*space.get("genes", []), scale=space["scale"])
        else:
            self.landscape_state = space["kind"]
        self.selected_cells = list(props.get("cell_ids", []))

    # NBHD is the umbrella for manually drawn gates in all three views.
    save_nbhds = save_gates
    load_nbhds = load_gates
    select_nbhd = select_gate

    @staticmethod
    def _polygon_vertices(geometry):
        polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
        rings = [ring for polygon in polygons for ring in [polygon.exterior, *polygon.interiors]]
        return (
            [list(ring.coords.xy[0]) for ring in rings],
            [list(ring.coords.xy[1]) for ring in rings],
        )

    @property
    def pins(self) -> list[dict]:
        """Points of interest on the tissue or the UMAP, one per Snapshot (**PINS**).

        Set it to Snapshots to annotate the Landscape: a :class:`Snapshots`
        collection, PNG paths, a folder of Snapshot PNGs, or a viewer's ``snap``.
        Each Landscape Snapshot of the tissue or the UMAP becomes a pin at the center
        of its view, shown while the Landscape shows that space; hovering shows its
        name and memo, and clicking opens its view::

            landscape.pins = dega.viz.Snapshots(landscape.snap)
            landscape.show_pins = True  # or press PINS

        Returns the pins (name, description, position and saved view).
        """
        return deepcopy(self.pin_data)

    @pins.setter
    def pins(self, snapshots) -> None:
        from .snapshot_widget import Snapshots

        if snapshots is None:
            self.pin_data = []
            return
        kept, other = [], []
        for pin in Snapshots(snapshots).pins():
            source = (pin.get("snapshot") or {}).get("source") or {}
            (kept if self._same_data(source) else other).append(pin)
        if other:
            warnings.warn(
                "Not pinned, Snapshots of other data than this Landscape: "
                + ", ".join(p["name"] for p in other),
                stacklevel=2,
            )
        self.pin_data = kept

    # Constructor options that say which data a Landscape shows (besides its URLs).
    _DATA_KEYS = (
        "zarr_layer",
        "technology",
        "segmentation",
        "alignment",
        "dataset_name",
        "cell_name_prefix",
        "data_revision",
    )

    def _same_data(self, source: dict) -> bool:
        """Whether a Snapshot's ``source`` is this Landscape's data, as far as both say.

        Opening a pin checks the data itself (its cell, gene and cluster names) too.
        """

        def urls(values) -> set[str]:
            out = {str(values(key) or "") for key in ("base_url", "zarr_url")}
            for entry in values("base_urls") or []:
                out.add(str(entry.get("url", "") if isinstance(entry, dict) else entry))
            return {url.rstrip("/") for url in out if url}

        # Where the data lives: DegaFiles (base_url) and an AnnData Zarr are different
        # data, even though neither side names the other's location.
        mine = urls(lambda k: getattr(self, k, None) if self.has_trait(k) else None)
        theirs = urls(source.get)
        if mine and theirs and not mine & theirs:
            return False
        for key in self._DATA_KEYS:
            theirs = source.get(key)
            mine = getattr(self, key, None) if self.has_trait(key) else None
            if theirs in (None, "", []) or mine in (None, "", []):
                continue
            if isinstance(mine, list | tuple) or isinstance(theirs, list | tuple):
                if list(mine) != list(theirs):
                    return False
            elif str(mine) != str(theirs):
                return False
        return True

    @property
    def nbhd_polygons(self):
        """All NBHDs with geometry, space, cell IDs and x/y vertex rings.

        Physical polygons use native tissue coordinates; UMAP and XY retain
        their displayed coordinates and their saved embedding/axis metadata.
        Display Y increases downward; UMAP's ``axes.y.reversed`` marks that
        increasing the raw embedding's second coordinate is drawn upward.
        Each element of x/y is a polygon ring, including any interior holes.
        ``nbhd`` exposes the same frame, updated when browser edits arrive.
        """
        features = deepcopy(self.nbhd_geojson.get("features", []))
        for feature in features:
            feature.setdefault("properties", {}).setdefault("coordinate_space", {"kind": "spatial"})
        features.extend(
            deepcopy(feature)
            for feature in self.gates.get("features", [])
            if feature.get("properties", {}).get("coordinate_space", {}).get("kind") != "spatial"
        )
        if not features:
            return gpd.GeoDataFrame(
                columns=["name", "space", "coordinate_space", "cell_ids", "x", "y", "geometry"],
                geometry="geometry",
            )
        frame = gpd.GeoDataFrame.from_features(features)
        frame["space"] = frame["coordinate_space"].map(lambda space: space["kind"])
        a, b, tx = self._inv_transform[0]
        c, d, ty = self._inv_transform[1]
        physical = frame["space"].eq("spatial")
        frame.loc[physical, "geometry"] = frame.loc[physical, "geometry"].map(
            lambda geom: affine_transform(geom, [a, b, c, d, tx, ty])
        )
        vertices = frame.geometry.map(self._polygon_vertices)
        frame["x"] = vertices.map(lambda xy: xy[0])
        frame["y"] = vertices.map(lambda xy: xy[1])
        return frame

    @traitlets.observe("gates")
    def _on_gates_change(self, change):
        """Keep the physical renderer and the multi-space Python frame in sync."""

        def physical(collection):
            return [
                feature
                for feature in (collection or {}).get("features", [])
                if feature.get("properties", {}).get("coordinate_space", {}).get("kind")
                == "spatial"
            ]

        current = physical(change["new"])
        if current or physical(change["old"]):
            self.nbhd_geojson = {"type": "FeatureCollection", "features": deepcopy(current)}
        self.nbhd = self.nbhd_polygons

    @traitlets.observe("nbhd_geojson")
    def _on_nbhd_geojson_change(self, change):
        """Physical edits must preserve neighborhoods drawn in other spaces."""
        self.nbhd = self.nbhd_polygons


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


class Enrich(_StateGetter, CelldegaWidget):
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
    # Short provenance string shown above the Enrichr link (for example,
    # ``"Clustergram row crop"``). Empty means the gene list was supplied directly.
    source_label = traitlets.Unicode("").tag(sync=True)
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
        name = kwargs.pop("name", None)
        registry_key = kwargs.pop("registry_key", None)
        if name is None and registry_key is None:
            registry_key = "default"
        super().__init__(name=name, registry_key=registry_key, **kwargs)
        self._listen_for_state()

    def request_state(self, max_terms: int = 15) -> int:
        """Ask the browser for a snapshot of the enrichment results on screen.

        The snapshot holds the library, the input gene list and its source, the top
        terms with their statistics (combined score, p-value, adjusted p-value, odds
        ratio) and overlapping genes, the selected term and its genes, and a link to
        the full results on Enrichr. Asynchronous, like
        :meth:`Clustergram.request_state`: the reply sets :attr:`latest_state`.

        Args:
            max_terms: Cap on reported terms.

        Returns:
            int: The id of this request.
        """
        return self._send_state_request({"max_terms": int(max_terms)})


class Clerk(CelldegaWidget):
    """Clerk -- Celldega's AI tool for exploring and interpreting its visualizations.

    Works like :class:`Enrich`, but instead of the Enrichr API it talks to Claude via
    the local ``claude`` CLI (kernel-side, no API key). The scientist asks free-form
    questions in a chat box; Celldega bundles the available evidence -- the gene list,
    pre-fetched Enrichr terms, a captured Landscape raster, and any free-text context --
    into a single-shot prompt so Claude reasons only from what it is shown.

    Reads as both a *law clerk* (gathers evidence, drafts reasoning, the human decides)
    and a *bodega clerk* (fetches what you ask for).

    Clerk is standalone and wide by default. Link it to other widgets (which can live in
    other notebook cells) either from the constructor or via ``dega.viz.link_clerk``::

        clerk = dega.viz.Clerk(landscape=ls, clustergram=cgm, enrich=en)

    Or lay it out with them, linked: as a narrow sidecar column at the end of the row,
    like Enrich, or full width underneath::

        dega.viz.spatial_clustergram(ls, cgm, clerk=True)                     # sidecar
        dega.viz.spatial_clustergram(ls, cgm, clerk=True, clerk_layout="wide")

    Enrichr results Clerk gets are drawn in the conversation, like the Enrich panel: a
    bar graph of the top terms and a paragraph of the genes tested.

    Args:
        landscape (Landscape): Optional. Link a Landscape; its raster + zoom/pan flow in
            as image evidence.
        clustergram (Clustergram): Optional. Link a Clustergram; selected genes flow into
            ``gene_list``.
        enrich (Enrich): Optional. Remembered for enrichment-term evidence sharing
            (roadmap).
        gene_list (list): Marker / DE genes for the selection.
        context_info (str): Free-text context (dataset, cluster id, notes).
        model (str): Optional Claude model alias or id (e.g. ``"opus"``, ``"sonnet"``,
            ``"haiku"``). Empty inherits the CLI default. A smaller model is
            cheaper/faster for routine annotation.
        effort (str): Reasoning effort, ``"low"`` to ``"max"`` (``"xhigh"`` in between);
            empty inherits the CLI default. Higher effort is slower and uses more tokens.
        width (int): Widget width in px; 0 (default) means full container width.
        name (str): Registry key; creating a new Clerk with the same name closes the old.
    """

    _esm = _WIDGET_ESM

    component = traitlets.Unicode("Clerk").tag(sync=True)

    # Wide by default (0 -> 100% of the container, like Landscape). Clerk is meant to be
    # a standalone wide panel, linked to widgets that live elsewhere in the notebook.
    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(450).tag(sync=True)

    # Evidence
    gene_list = traitlets.List(default_value=[]).tag(sync=True)
    context_info = traitlets.Unicode("").tag(sync=True)
    # The full image sent to the model stays Python-side (not synced), so it is never
    # saved into the notebook's widget state; the panel only gets a small preview.
    image_b64 = traitlets.Unicode("")
    image_thumb_b64 = traitlets.Unicode("").tag(sync=True)
    has_image = traitlets.Bool(False).tag(sync=True)
    # View state (zoom/pan) paired with image_b64, captured from the linked Landscape.
    image_view_state = traitlets.Dict(default_value={}).tag(sync=True)

    # Model config
    model = traitlets.Unicode("").tag(sync=True)
    # Reasoning effort ("low", "medium", "high", "xhigh", "max"); "" = CLI default.
    effort = traitlets.Unicode("").tag(sync=True)
    timeout = traitlets.Int(180).tag(sync=True)

    # Chat state (kept in memory only)
    messages = traitlets.List(default_value=[]).tag(sync=True)
    pending = traitlets.Bool(False).tag(sync=True)
    error = traitlets.Unicode("").tag(sync=True)

    # JS sets this dict (with a unique ``id``) to trigger a single-shot call.
    request = traitlets.Dict(default_value={}).tag(sync=True)

    # Whether the panel fetches its own Enrichr terms for the gene list. Turned off
    # when an Enrich widget is linked: Clerk then reads that panel's results instead.
    fetch_enrichr = traitlets.Bool(True).tag(sync=True)

    # Earlier work shared with Clerk (Markdown), sent with every question as clearly
    # labeled prior conclusions; see load_briefing. Python-side only; the panel shows
    # briefing_label so it's visible what Clerk was told.
    briefing = traitlets.Unicode("")
    briefing_label = traitlets.Unicode("").tag(sync=True)

    # Cluster names the panel links ("cluster 4" -> highlight it), and their labels
    # (Clerk's tentative cell types, or yours) for hover text.
    cluster_names = traitlets.List(default_value=[]).tag(sync=True)
    cluster_labels = traitlets.Dict(default_value={}).tag(sync=True)
    # True while the scientist's view is saved (evidence links were followed); the
    # panel then offers RETURN.
    can_restore = traitlets.Bool(False).tag(sync=True)

    def __init__(self, **kwargs):
        name = kwargs.pop("name", None)
        registry_key = kwargs.pop("registry_key", None)
        if name is None and registry_key is None:
            registry_key = "default"
        # Widgets can be linked straight from the constructor:
        # ``Clerk(landscape=ls, clustergram=cgm, enrich=en)``. Pop them before
        # super().__init__ since they are not traits.
        link_targets = {
            key: kwargs.pop(key, None) for key in ("landscape", "clustergram", "enrich")
        }
        capture_on_select = kwargs.pop("capture_on_select", True)

        super().__init__(name=name, registry_key=registry_key, **kwargs)
        self._last_request_id = None
        self._linked_widgets = {}
        self._worker: threading.Thread | None = None
        # Cell types Clerk has proposed (see findings_df / write_cell_types).
        self.findings: list[dict] = []
        # One entry per question: steps, screenshots and the state behind them.
        self.record: list[dict] = []
        self._paused: dict | None = None
        # Labels Clerk put on the Clustergram, per axis, so it never overwrites yours.
        self._clerk_marks: dict[str, dict] = {}
        self._saved_view: dict | None = None
        # Screenshots Clerk saved (paths), newest last.
        self.screenshots: list[str] = []
        # Analysis notebooks Clerk drafted (see run_analysis), newest last.
        self.analyses: list[dict] = []
        # Where the data for analysis notebooks lives, e.g. {"adata": "data/x.h5ad"}.
        self.analysis_data: dict = {}
        # Messages change from Clerk's worker and from analysis runs, in other threads.
        self._messages_lock = threading.RLock()
        self._evidence_executor = None
        self._last_evidence: concurrent.futures.Future | None = None
        # Which Clustergram rows/columns to describe with each question: on screen by
        # default ("viewport"), or "ranked" / a list of names; see
        # Clustergram.request_state for the options.
        self.clustergram_options = {
            "rows": "viewport",
            "cols": "viewport",
            "max_rows": 40,
            "max_cols": 30,
        }
        self.has_image = bool(self.image_b64)
        self.observe(self._on_request, names="request")
        self.observe(self._on_image, names="image_b64")
        self.briefing_sources: list[str] = []
        self._briefing_from: list[str] = []
        self.observe(self._on_briefing, names="briefing")
        # The panel's OPEN button sends a saved conversation as a one-off message.
        self.on_msg(self._on_panel_msg)

        if any(w is not None for w in link_targets.values()):
            from . import link_clerk

            link_clerk(self, capture_on_select=capture_on_select, **link_targets)

    def _on_image(self, change):
        self.has_image = bool(change["new"])
        if not change["new"]:
            self.image_thumb_b64 = ""

    def _on_briefing(self, change):
        text = change["new"] or ""
        # Sources come from load_briefing; text set directly has none.
        self.briefing_sources, self._briefing_from = self._briefing_from, []
        if not text.strip():
            self.briefing_sources = []
            self.briefing_label = ""
            return
        sources = f" from {', '.join(self.briefing_sources)}" if self.briefing_sources else ""
        self.briefing_label = f"Briefing: {len(text):,} characters of earlier work{sources}"

    def load_briefing(self, *sources, append: bool = False) -> str:
        """Give Clerk earlier work to start from, as a visible, labeled briefing.

        Each source is an exported report folder or its ``record.json`` (see
        :meth:`export`), a Markdown / text file, or another :class:`Clerk`. Records are
        summarized (questions, final answers, recorded cell types). The briefing goes
        with every question under "Earlier work", as conclusions to check rather than
        evidence, and the panel shows that one is loaded. Set :attr:`briefing` directly
        for free text, or to ``""`` to clear it.

        Args:
            append: Add to the current briefing instead of replacing it.

        Returns:
            str: The briefing text.
        """
        from ..clerk import report
        from . import screenshots as screenshot_module

        parts, names = [], []
        for source in sources:
            if isinstance(source, Clerk):
                parts.append(report.summarize(source.record, source.findings, "Earlier session"))
                names.append("another Clerk panel")
                continue
            path = Path(source)
            shots = None
            if path.is_dir() and not (path / "record.json").is_file():
                shots = screenshot_module.load_screenshots(path)
                if not shots:
                    raise FileNotFoundError(f"no Clerk record or screenshots in {source}")
            elif path.is_dir():
                path = path / "record.json"
            elif path.suffix == ".png" or (path.suffix == ".json" and _is_screenshot_record(path)):
                shots = [{**screenshot_module.load_screenshot(path), "_path": str(path)}]
            if shots is not None:
                parts.append(screenshot_module.summarize(shots))
                names.append(path.name)
                continue
            if not path.is_file():
                raise FileNotFoundError(f"no briefing source at {source}")
            if path.suffix == ".json":
                data = json.loads(path.read_text())
                parts.append(
                    report.summarize(
                        data.get("questions") or [],
                        data.get("findings") or [],
                        f"Earlier session ({path.parent.name}, exported "
                        f"{(data.get('meta') or {}).get('exported', 'unknown date')})",
                    )
                )
            else:
                parts.append(path.read_text())
            names.append(path.parent.name if path.name == "record.json" else path.name)
        text = "\n\n".join(parts)
        if append and self.briefing:
            text = f"{self.briefing}\n\n{text}"
            names = [*self.briefing_sources, *names]
        self.briefing = ""  # re-label even if the text is unchanged
        self._briefing_from = names
        self.briefing = text
        return text

    def _on_request(self, change):
        """Handle a question from the chat UI.

        The model call runs in a background thread so the kernel stays free while
        Claude thinks: other cells can run, and linked widgets keep updating.
        """
        req = change["new"] or {}
        req_id = req.get("id")
        if not req_id or req_id == self._last_request_id:
            return
        self._last_request_id = req_id

        if req.get("export"):
            self._export_from_panel(title=str(req.get("report_title") or ""))
            return
        if req.get("save_conversation"):
            self._save_from_panel()
            return

        # Evidence clicked in the conversation (works while Clerk is still answering):
        # genes, clusters and cited views, shown right away in the linked widgets.
        # The scientist's own view is saved first, so "Back" can restore it.
        if req.get("show_genes") is not None:
            self._follow_evidence(self._show_genes, req["show_genes"], focus=req.get("focus"))
            return
        if req.get("show_clusters") is not None:
            self._follow_evidence(self._show_clusters, req["show_clusters"])
            return
        if req.get("apply_view") is not None:
            self._follow_evidence(self._apply_view, req["apply_view"])
            return
        if req.get("show_snapshot") is not None:
            self._follow_evidence(self._show_snapshot, req["show_snapshot"])
            return
        if req.get("restore_view"):
            self._queue_evidence(self._restore_view)
            return

        if self._worker is not None and self._worker.is_alive():
            self.error = "Clerk is still answering the previous question."
            return

        if req.get("continue"):
            paused, self._paused = self._paused, None
            if not paused:
                return
            self.error = ""
            self.pending = True
            self._worker = threading.Thread(
                target=self._resume, args=(paused,), name="celldega-clerk", daemon=True
            )
            self._worker.start()
            return
        if self._paused is not None:  # a new question drops a paused one
            session = self._paused["call"].pop("session", None)
            if session is not None:
                session.close()
        self._paused = None

        question = req.get("question", "")
        call = {
            # Earlier turns, so follow-up questions keep their context.
            "history": [dict(m) for m in self.messages],
            "gene_list": req.get("gene_list") or list(self.gene_list),
            "enrichr_terms": req.get("enrichr_terms") or [],
            "enrichr_library": str(req.get("enrichr_library") or ""),
            "enrichr_short_id": str(req.get("enrichr_short_id") or ""),
            "info": self.context_info,
            "image_b64": self.image_b64 or None,
            "model": self.model,
            "effort": self.effort,
            "timeout": self.timeout,
            "briefing": self.briefing,
            "history_questions": self.history_questions,
            "history_chars": self.history_chars,
        }

        # Append the user's message so it renders immediately.
        self.messages = [*self.messages, {"role": "user", "content": question}]
        self.error = ""
        self.pending = True
        self._worker = threading.Thread(
            target=self._answer, args=(question, call), name="celldega-clerk", daemon=True
        )
        self._worker.start()

    # Seconds to wait for a fresh Landscape snapshot before asking anyway.
    snapshot_timeout = 5.0
    # Screenshot the linked Clustergram with each capture, for the record and report
    # (Clerk itself reads the Clustergram's text snapshot, which is more precise).
    capture_clustergram = True

    def _request_and_wait(self, requests) -> list[bool]:
        """Send requests to the browser and wait for their replies (worker thread).

        ``requests`` is a list of ``(widget, id_trait, send)``: ``send()`` issues the
        request and returns its id, and the widget sets ``id_trait`` to that id once
        the browser has answered. All replies share one ``snapshot_timeout``. The
        kernel's main thread is free while this waits, so it can receive the replies.

        Returns:
            list[bool]: Whether each request was answered in time.
        """

        def received(widget, trait, rid):
            if trait in ("snapshot_capture_id", "apply_capture_id"):
                cache = (
                    widget._snapshot_replies
                    if trait == "snapshot_capture_id"
                    else widget._apply_replies
                )
                return rid in cache
            return getattr(widget, trait) >= rid

        pending = []
        for widget, id_trait, send in requests:
            done = threading.Event()
            target = {"id": None}

            def _on_reply(change, done=done, target=target, widget=widget, id_trait=id_trait):
                if target["id"] is not None and received(widget, id_trait, target["id"]):
                    done.set()

            widget.observe(_on_reply, names=id_trait)
            pending.append((widget, id_trait, send, _on_reply, done, target))
        try:
            for widget, id_trait, send, _cb, done, target in pending:
                target["id"] = send()
                if received(widget, id_trait, target["id"]):
                    done.set()
            deadline = time.monotonic() + self.snapshot_timeout
            for *_, done, _target in pending:
                done.wait(max(0.0, deadline - time.monotonic()))
            return [done.is_set() for *_, done, _target in pending]
        finally:
            for widget, id_trait, _send, callback, _done, _target in pending:
                widget.unobserve(callback, names=id_trait)

    _GENE_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9._-]+")

    def _mentioned_rows(self, texts, limit: int = 40) -> list[str]:
        """Clustergram row names (e.g. genes) mentioned in ``texts``, in order.

        Matches exactly, or case-insensitively when the word is written in capitals
        or contains a digit (``muc2`` won't match, ``MUC2`` / ``Muc2`` will), so plain
        English words that happen to be gene symbols aren't picked up.
        """
        cgm = self._linked_widgets.get("clustergram")
        names = [str(n) for n in (getattr(cgm, "row_names", None) or [])]
        return self._find_names(texts, names, limit)

    def _known_genes(self) -> list[str]:
        """Gene names Clerk can link: the Clustergram's rows, else the Landscape's genes."""
        cgm = self._linked_widgets.get("clustergram")
        names = [str(n) for n in (getattr(cgm, "row_names", None) or [])]
        if not names:
            landscape = self._linked_widgets.get("landscape")
            adata = getattr(landscape, "_adata", None)
            if adata is not None:
                names = [str(n) for n in adata.var_names]
        return names

    def _known_clusters(self) -> list[str]:
        """Cluster names Clerk can link: the Clustergram's columns, else the Landscape's."""
        cgm = self._linked_widgets.get("clustergram")
        names = [str(n) for n in (getattr(cgm, "col_names", None) or [])]
        if not names:
            landscape = self._linked_widgets.get("landscape")
            meta = getattr(landscape, "meta_cell", None)
            attr = getattr(landscape, "cluster_attr", "leiden")
            if isinstance(meta, pd.DataFrame) and attr in meta:
                names = [str(n) for n in pd.unique(meta[attr].astype(str))]
        return names

    def _cluster_labels(self) -> dict[str, str]:
        """``{cluster: label}`` for hover text: Clerk's latest proposals, then yours."""
        labels = {f["cluster"]: f"{f['label']} (Clerk, tentative)" for f in self.findings}
        cgm = self._linked_widgets.get("clustergram")
        if cgm is not None and hasattr(cgm, "_category_target"):
            try:
                _axis, attribute = cgm._category_target("col", None)
            except ValueError:
                attribute = None
            if attribute:
                values = ((cgm.manual_cat_dict or {}).get("col") or {}).get(attribute, {})
                for cluster, label in (values.get("values") or {}).items():
                    if label and label != self._clerk_marks.get("col", {}).get(cluster):
                        labels[str(cluster)] = str(label)
        return labels

    def _links_for(self, text: str, genes: Sequence[str] = ()) -> dict:
        """Genes in ``text`` the panel can make clickable (``{"genes": [...]}`` or ``{}``).

        Also refreshes :attr:`cluster_names` / :attr:`cluster_labels`, which the panel
        uses to link "cluster N" in any message.
        """
        found = self._find_names([text], self._known_genes(), limit=500)
        found += [str(g) for g in genes if str(g) not in found]
        known = self._known_clusters()
        if known != list(self.cluster_names):
            self.cluster_names = known
        labels = self._cluster_labels()
        labels = {c: labels[c] for c in known if c in labels}
        if labels != dict(self.cluster_labels):
            self.cluster_labels = labels
        return {"genes": found} if found else {}

    # "[MYH11]" (brackets without a link target): Markdown leaves the brackets.
    _BRACKETED = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9._/-]*)\](?!\()")

    def _unbracket_names(self, text: str, genes: Sequence[str] = ()) -> str:
        """Drop brackets Clerk put around gene or cluster names ("[MYH11]").

        The panel links those names by itself; in brackets they would show as
        "[MYH11]". Figure links ("[Fig 1A](view:1A)") and other brackets are kept.
        """
        known = {str(g).upper() for g in genes} | {str(c).upper() for c in self.cluster_names}
        if not known or "[" not in (text or ""):
            return text

        def plain(match):
            name = match.group(1)
            return name if name.upper() in known else match.group(0)

        return self._BRACKETED.sub(plain, text)

    def _find_names(self, texts, names: list[str], limit: int) -> list[str]:
        """Names from ``names`` mentioned in ``texts`` (see :meth:`_mentioned_rows`)."""
        if not names:
            return []
        exact = set(names)
        by_upper = {}
        for name in names:
            by_upper.setdefault(name.upper(), name)
        found: list[str] = []
        for text in texts:
            for raw in self._GENE_TOKEN.findall(text or ""):
                # Dots and dashes occur inside symbols (HLA-DRA) but not at the end of
                # one: "...and PTPRC." -> PTPRC.
                token = raw.rstrip("._-")
                name = token if token in exact else None
                if name is None and (token.isupper() or any(c.isdigit() for c in token)):
                    name = by_upper.get(token.upper())
                if name and name not in found:
                    found.append(name)
        return found[:limit]

    def _refresh_views(
        self,
        question: str = "",
        extra_rows: Sequence[str] = (),
        markers: dict | None = None,
    ) -> dict:
        """Capture the linked views as they are now, before a question is sent.

        The Landscape screenshot lands in ``image_b64`` (via the ``link_clerk``
        observers). The Clustergram snapshot covers what's on screen plus any of its
        rows named in the question or in Clerk's previous answer. Views that aren't
        linked or displayed time out; the question still goes ahead, with a note.

        Returns:
            dict: ``clustergram_state`` (or ``None``), ``image_fresh`` (bool),
            ``notes`` for the prompt, and ``summary`` lines for the panel.
        """
        result = {
            "clustergram_image": "",
            "clustergram_thumb": "",
            "snapshots": {},
            "clustergram_state": None,
            "enrich_state": None,
            "landscape_state": None,
            "neighborhoods": None,
            "image_fresh": False,
            "notes": [],
            "summary": [],
        }
        requests = []
        labels = []
        snapshot_ids = {}

        def capture(name, widget, **options):
            def send():
                rid = widget.request_snapshot(**options)
                snapshot_ids[name] = rid
                return rid

            requests.append((widget, "snapshot_capture_id", send))
            labels.append(name)

        landscape = self._linked_widgets.get("landscape")
        has_landscape = landscape is not None and hasattr(landscape, "request_snapshot")
        if has_landscape:
            capture("landscape", landscape)
        cgm = self._linked_widgets.get("clustergram")
        has_cgm = cgm is not None and hasattr(cgm, "request_state")
        if has_cgm:
            last_answer = next(
                (
                    m.get("content", "")
                    for m in reversed(self.messages)
                    if m.get("role") == "assistant"
                ),
                "",
            )
            options = dict(self.clustergram_options)
            mentioned = self._mentioned_rows([question, last_answer])
            options.setdefault(
                "extra_rows",
                list(dict.fromkeys([*(str(g) for g in extra_rows), *mentioned])),
            )
            if markers:
                options["markers"] = markers
            if self.capture_clustergram and hasattr(cgm, "request_snapshot"):
                capture("clustergram", cgm, **options)
            else:
                requests.append((cgm, "state_capture_id", lambda: cgm.request_state(**options)))
                labels.append("clustergram")
        enrich = self._linked_widgets.get("enrich")
        has_enrich = enrich is not None and hasattr(enrich, "request_state")
        if has_enrich:
            requests.append((enrich, "state_capture_id", enrich.request_state))
            labels.append("enrich")
        if not requests:
            result["notes"].append(
                "No Landscape, Clustergram or Enrich panel is linked to Clerk; only the "
                "text evidence below is available."
            )
            return result

        answered = dict(zip(labels, self._request_and_wait(requests), strict=True))
        captured = {}
        for name, rid in snapshot_ids.items():
            reply = self._linked_widgets[name]._snapshot_replies.get(rid, {})
            snapshot = reply.get("snapshot")
            answered[name] = bool(snapshot) and not reply.get("error")
            if answered[name]:
                captured[name] = snapshot
                result["snapshots"][name] = snapshot
        if has_landscape:
            if answered.get("landscape"):
                image = captured["landscape"]["image"]
                self.image_b64 = image.get("png") or ""
                self.image_thumb_b64 = image.get("thumb") or ""
                self.image_view_state = dict(image.get("view_state") or {})
                result["image_fresh"] = True
                result["summary"].append("Landscape view")
            else:
                result["notes"].append(
                    "The linked Landscape did not return a screenshot this time (it may "
                    "not be displayed); any image attached is from an earlier view."
                )
                result["summary"].append("Landscape: no new screenshot")
            if answered.get("landscape"):
                result["landscape_state"] = deepcopy(captured["landscape"]["observed_state"])
            if hasattr(landscape, "neighborhood_summary"):
                try:
                    neighborhoods = landscape.neighborhood_summary()
                except Exception:  # drawn regions are optional evidence
                    neighborhoods = []
                if neighborhoods:
                    result["neighborhoods"] = neighborhoods
                    result["summary"].append(f"{len(neighborhoods)} drawn neighborhoods")
        if has_cgm:
            if "clustergram" in captured:
                result["clustergram_image"] = captured["clustergram"]["image"].get("png", "")
                result["clustergram_thumb"] = captured["clustergram"]["image"].get("thumb", "")
            state = (
                captured["clustergram"]["observed_state"]
                if "clustergram" in captured
                else cgm.latest_state
                if "clustergram" not in snapshot_ids and not cgm.state_error
                else None
            )
            if answered.get("clustergram") and state:
                state = deepcopy(state)
                result["clustergram_state"] = state
                rows = state.get("rows") or {}
                cols = state.get("cols") or {}
                line = (
                    f"Clustergram: {len(rows.get('names') or [])} rows x "
                    f"{len(cols.get('names') or [])} columns"
                )
                if rows.get("added"):
                    line += f" (incl. {len(rows['added'])} asked about)"
                result["summary"].append(line)
            else:
                result["notes"].append(
                    "A Clustergram is linked but did not return a snapshot this time (it "
                    "may not be displayed, or the page needs reloading after an update)."
                )
                result["summary"].append("Clustergram: no snapshot")
        if has_enrich:
            if answered.get("enrich") and not enrich.state_error and enrich.latest_state:
                state = dict(enrich.latest_state)
                result["enrich_state"] = state
                if state.get("terms"):
                    result["summary"].append(
                        f"Enrich: {len(state['terms'])} {state.get('library') or ''} terms".replace(
                            "  ", " "
                        )
                    )
            else:
                result["notes"].append(
                    "An Enrich panel is linked but did not return its results this time "
                    "(it may not be displayed)."
                )
                result["summary"].append("Enrich: no snapshot")
        return result

    def _record_evidence(
        self,
        summary: list[str],
        image_fresh: bool,
        snapshots: dict | None = None,
        clustergram_thumb: str = "",
    ) -> None:
        """Attach what was sent to the latest question: previews of the Landscape and
        Clustergram screenshots, the views to return to, and a summary line."""
        from .snapshots import restore_spec

        landscape_thumb = self.image_thumb_b64 if image_fresh else ""
        if not summary and not landscape_thumb and not clustergram_thumb:
            return
        messages = [dict(m) for m in self.messages]
        for message in reversed(messages):
            if message.get("role") == "user":
                if landscape_thumb:
                    message["image"] = landscape_thumb
                if clustergram_thumb:
                    message["clustergram_image"] = clustergram_thumb
                if landscape_thumb or clustergram_thumb:
                    message["snapshots"] = {
                        name: restore_spec(snapshot) for name, snapshot in (snapshots or {}).items()
                    }
                message["evidence"] = list(summary)
                break
        self.messages = messages

    # Rounds of lookups / view changes Clerk may make for one question; each is another
    # model call. Checking carefully can take a few (markers -> Enrichr -> PubMed).
    max_action_rounds = 6

    # How much of this panel's conversation goes with each question: the last N
    # questions (with Clerk's replies and actions), within a character budget.
    history_questions = 10
    history_chars = 40_000

    @staticmethod
    def _markers_needed(reads: dict) -> dict | None:
        """One Clustergram markers request covering ``lookup.markers`` and any
        ``enrichr`` specs that name a cluster."""
        spec = reads.get("markers")
        clusters: list[str] = []
        n = 0
        every = False
        if spec:
            n = spec["n"]
            if spec["clusters"] is None:
                every = True
            else:
                clusters.extend(spec["clusters"])
        for entry in reads.get("enrichr") or []:
            if entry["cluster"]:
                clusters.append(entry["cluster"])
                n = max(n, entry["n"])
        if not every and not clusters:
            return None
        return {"clusters": None if every else list(dict.fromkeys(clusters)), "n": n or 25}

    def _record_findings(self, findings: dict, question: str) -> None:
        """Keep proposed cell types (``celldega-findings``) and note them in the chat."""
        recorded = []
        for item in findings.get("cell_types") or []:
            if not isinstance(item, dict) or item.get("cluster") is None or not item.get("label"):
                continue
            entry = {
                "cluster": str(item["cluster"]),
                "label": str(item["label"]),
                "confidence": str(item.get("confidence") or ""),
                "markers": [str(g) for g in item.get("markers") or []],
                "notes": str(item.get("notes") or ""),
                "question": question,
                "recorded": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.findings.append(entry)
            confidence = f" ({entry['confidence']})" if entry["confidence"] else ""
            recorded.append(f"{entry['cluster']} → {entry['label']}{confidence}")
        if not recorded:
            return
        latest = self.findings[-len(recorded) :]
        n = len(recorded)
        # One short line in the chat; the per-cluster list is in its Evidence.
        message = {
            "role": "action",
            "content": f"Recorded tentative cell types for {n} cluster{'s' if n != 1 else ''}",
            "detail": "Recorded cell types: " + ", ".join(recorded),
        }
        cgm = self._linked_widgets.get("clustergram")
        can_label = hasattr(cgm, "set_categories") and self.label_clustergram is not False
        # Label right away when set to, or when the scientist asked Clerk to label
        # (Clerk then marks the block "label": true); otherwise offer to.
        label_now = can_label and (self.label_clustergram is True or findings.get("label") is True)
        if can_label and not label_now:
            try:
                _axis, attribute = cgm._category_target("col", None)
            except (AttributeError, ValueError):
                attribute = self.clustergram_label_attribute
            message["label_offer"] = {
                "id": uuid.uuid4().hex[:12],
                "status": "offered",
                # The manual column category the labels would go in.
                "attribute": attribute,
                "cell_types": [
                    {"cluster": e["cluster"], "label": e["label"], "markers": e["markers"]}
                    for e in latest
                ],
            }
        self._append(message)
        self._log_step("findings", ", ".join(recorded), cell_types=[dict(e) for e in latest])
        if label_now:
            labeled = self._label_clustergram(
                {e["cluster"]: e["label"] for e in latest},
                {e["cluster"]: e["markers"] for e in latest},
            )
            if labeled:
                self._append({"role": "action", "content": labeled[0], "detail": labeled[1]})

    # Recorded cell types can label the linked Clustergram's columns (a manual
    # category) and mark the marker genes Clerk relied on (rows) with the same label.
    # "ask" offers this as a button under the recorded types; True labels right away;
    # False never labels.
    label_clustergram: "bool | Literal['ask']" = "ask"
    # Attributes used when the Clustergram has no manual category set up on an axis.
    clustergram_label_attribute = "clerk_cell_type"
    clustergram_marker_attribute = "clerk_marker"

    def _label_from_offer(self, offer_id: str) -> None:
        """Apply the cell types a LABEL button offered (see :attr:`label_clustergram`)."""
        if self.pending:
            return
        messages = [dict(m) for m in self.messages]
        for message in messages:
            offer = message.get("label_offer")
            if isinstance(offer, dict) and offer.get("id") == offer_id:
                break
        else:
            return
        if offer.get("status") != "offered":
            return
        if not hasattr(self._linked_widgets.get("clustergram"), "set_categories"):
            self._append({"role": "error", "content": "Link a Clustergram to label it."})
            return
        cell_types = [c for c in offer.get("cell_types") or [] if isinstance(c, dict)]
        labeled = self._label_clustergram(
            {str(c.get("cluster")): str(c.get("label")) for c in cell_types},
            {str(c.get("cluster")): [str(g) for g in c.get("markers") or []] for c in cell_types},
        )
        offer = {**offer, "status": "done"}
        if labeled:
            offer["result"], offer["result_detail"] = labeled
        else:
            offer["result"] = "Nothing to label: the Clustergram already shows these labels"
        message["label_offer"] = offer
        self.messages = messages

    def _label_axis(self, cgm, axis: str, labels: dict, default_attribute: str):
        """Set Clerk's labels on one Clustergram axis, keeping the scientist's own.

        A name already labeled with something Clerk didn't put there is left alone;
        ``None`` clears a label Clerk set earlier. Returns ``(applied, kept, attribute)``.
        """
        try:
            _axis, attribute = cgm._category_target(axis, None)
        except ValueError:
            attribute = default_attribute
        current = ((cgm.manual_cat_dict or {}).get(axis) or {}).get(attribute, {}).get(
            "values"
        ) or {}
        mine = self._clerk_marks.setdefault(axis, {})
        apply, kept = {}, []
        for name, label in labels.items():
            existing = current.get(name)
            if existing and existing != mine.get(name):
                if label is not None:
                    kept.append(f"{name} ({existing})")
                continue
            if label is None and not existing:
                continue
            if existing != label:
                apply[name] = label
        if apply:
            cgm.set_categories(apply, axis=axis, attribute=attribute)
            for name, label in apply.items():
                if label is None:
                    mine.pop(name, None)
                else:
                    mine[name] = label
        return apply, kept, attribute

    def _label_clustergram(
        self, labels: dict[str, str], markers: dict | None = None
    ) -> tuple[str, str] | None:
        """Label Clustergram columns with Clerk's proposals and mark their marker genes.

        ``labels`` maps clusters to cell types; ``markers`` maps clusters to the genes
        Clerk cited, which are labeled (rows) with their cluster's cell type, in the
        same color. Labels the scientist set are never overwritten.

        Returns:
            ``(summary, detail)`` describing what changed (a short line and the
            per-cluster list), or ``None`` when nothing changed.
        """
        cgm = self._linked_widgets.get("clustergram")
        if cgm is None or not hasattr(cgm, "set_categories"):
            return None
        summary, detail = [], []
        previous = dict(self._clerk_marks.get("col") or {})
        try:
            applied, kept, attribute = self._label_axis(
                cgm, "col", labels, self.clustergram_label_attribute
            )
        except ValueError as exc:
            self._append({"role": "error", "content": f"Couldn't label the Clustergram: {exc}"})
            return None
        if applied:
            n = len(applied)
            summary.append(f"Labeled {n} Clustergram column{'s' if n != 1 else ''}")
            pairs = ", ".join(f"{k} → {v}" for k, v in applied.items())
            detail.append(f"Clustergram columns ({attribute}): {pairs}")
        if kept:
            summary.append(f"kept your labels for {len(kept)}")
            detail.append("Kept your labels for " + ", ".join(kept))

        rows = self._marker_rows(cgm, labels, markers or {}, previous)
        if rows:
            try:
                marked, _kept_rows, row_attribute = self._label_axis(
                    cgm, "row", rows, self.clustergram_marker_attribute
                )
            except ValueError as exc:
                marked, row_attribute = {}, ""
                summary.append("couldn't mark marker genes")
                detail.append(f"Couldn't mark marker genes: {exc}")
            shown = [g for g, label in marked.items() if label is not None]
            if shown:
                summary.append(f"marked {len(shown)} marker gene{'s' if len(shown) != 1 else ''}")
                detail.append(f"Marker genes ({row_attribute}): " + ", ".join(shown))
        if not summary:
            return None
        return "; ".join(summary), "\n".join(detail)

    def _marker_rows(self, cgm, labels: dict, markers: dict, previous: dict) -> dict:
        """``{gene: cell type}`` for cited marker genes that are Clustergram rows.

        A relabeled cluster's earlier marks are cleared (``None``) unless re-cited.
        """
        names = [str(n) for n in (getattr(cgm, "row_names", None) or [])]
        by_upper = {}
        for name in names:
            by_upper.setdefault(name.upper(), name)
        rows: dict[str, str | None] = {}
        mine = self._clerk_marks.get("row") or {}
        for cluster, label in labels.items():
            old = previous.get(cluster)
            if old and old != label:
                for gene, mark in mine.items():
                    if mark == old:
                        rows.setdefault(gene, None)
            for gene in markers.get(cluster) or []:
                name = by_upper.get(str(gene).strip().upper())
                if name:
                    rows[name] = label
        return rows

    # -- Analysis notebooks: drafted by Clerk, run by the scientist or Claude Code --

    def _analysis_sources(self) -> list[str]:
        """Where the data for an analysis notebook lives, as lines for the notebook
        and the prompt: the linked widgets' sources and :attr:`analysis_data`."""
        from .screenshots import widget_source

        lines = [f"{key}: {value}" for key, value in (self.analysis_data or {}).items()]
        for name, widget in self._linked_widgets.items():
            if name == "enrich":
                continue
            source = widget_source(widget)
            parts = [
                f"{key} {source[key]}"
                for key in ("dataset_name", "base_url", "zarr_url", "technology", "cluster_attr")
                if source.get(key)
            ]
            matrix = source.get("matrix")
            if isinstance(matrix, dict) and matrix.get("source"):
                parts.append(f"matrix source {matrix['source']}")
            adata = source.get("adata")
            if isinstance(adata, dict) and adata.get("filename"):
                parts.append(f"AnnData file {adata['filename']}")
            elif isinstance(adata, dict) and adata.get("n_obs") is not None:
                parts.append(
                    f"an in-memory AnnData ({adata['n_obs']} x {adata.get('n_vars')}, no "
                    "file path: ask the scientist for clerk.analysis_data)"
                )
            elif isinstance(adata, str) and adata:
                parts.append(f"AnnData {adata}")
            for key, value in (getattr(widget, "screenshot_metadata", None) or {}).items():
                parts.append(f"{key} {value}")
            if parts:
                lines.append(f"{source['widget']}: " + ", ".join(parts))
        return lines

    # Analysis notebooks are written only when the scientist asks for the analysis
    # (Clerk marks those "requested: yes"); a notebook Clerk suggests on its own waits
    # for a click on Draft notebook. True drafts every one; False none.
    draft_notebooks: "bool | Literal['ask']" = "ask"

    def _draft_notebook(self, notebook: dict, question: str) -> None:
        """Write a notebook Clerk drafted, or offer it first (never run here)."""
        from ..clerk.analysis import purpose

        title = str(notebook.get("title") or "Analysis")
        if self.draft_notebooks is False:
            self._append(
                {
                    "role": "note",
                    "content": f"Clerk suggested an analysis notebook ({title}); "
                    "drafting notebooks is turned off.",
                }
            )
            return
        if self.draft_notebooks is True or notebook.get("requested"):
            self._write_notebook(notebook, question)
            return
        self._append(
            {
                "role": "action",
                "content": f"Suggested an analysis notebook: {title}",
                "detail": purpose(notebook),
                "notebook_offer": {
                    "id": uuid.uuid4().hex[:12],
                    "status": "offered",
                    "title": title,
                    "purpose": purpose(notebook),
                    "question": question,
                    "notebook": deepcopy(notebook),
                },
            }
        )

    def draft_notebook(self, offer_id: str | None = None) -> Path | None:
        """Write a notebook Clerk suggested (as the panel's Draft notebook button does).

        ``offer_id`` picks the suggestion; by default the latest one not yet drafted.
        Returns the notebook's path, or ``None`` if there was nothing to draft.
        """
        with self._messages_lock:
            messages = [dict(m) for m in self.messages]
            offers = [
                m
                for m in messages
                if (m.get("notebook_offer") or {}).get("status") == "offered"
                and offer_id in (None, m["notebook_offer"]["id"])
            ]
            if not offers:
                return None
            message = offers[-1]
            offer = message["notebook_offer"]
            entry = self._write_notebook(offer["notebook"], offer["question"], append=False)
            if entry is None:
                return None
            # The suggestion's line becomes the drafted notebook's (path, Run button).
            message.pop("notebook_offer")
            message.update(
                content=f"Drafted an analysis notebook: {entry['title']}",
                detail=f"Analysis notebook: {entry['path']}",
                analysis=dict(entry),
            )
            self.messages = messages
        return Path(entry["path"])

    def _write_notebook(self, notebook: dict, question: str, *, append: bool = True):
        """Write a drafted notebook to disk and add it to :attr:`analyses`."""
        from ..clerk.analysis import write_notebook

        try:
            path = write_notebook(
                notebook,
                Path(self.output_dir) / "analyses",
                question=question,
                sources=self._analysis_sources(),
            )
        except Exception as exc:
            self._append({"role": "error", "content": f"Couldn't write the notebook: {exc}"})
            return None
        entry = {
            "id": uuid.uuid4().hex[:12],
            "title": str(notebook.get("title") or "Analysis"),
            "path": str(path),
            "status": "drafted",
            "summary": "",
            "question": question,
        }
        self.analyses.append(entry)
        if append:
            self._append(
                {
                    "role": "action",
                    "content": f"Drafted an analysis notebook: {entry['title']}",
                    "detail": f"Analysis notebook: {path}",
                    "analysis": dict(entry),
                }
            )
        self._log_step("notebook", str(path), title=entry["title"])
        return entry

    def _update_analysis(self, entry: dict) -> None:
        """Show an analysis notebook's new status on its line in the panel."""
        with self._messages_lock:
            messages = [dict(m) for m in self.messages]
            for message in messages:
                if (message.get("analysis") or {}).get("id") == entry["id"]:
                    message["analysis"] = dict(entry)
            self.messages = messages

    def run_analysis(self, which: str | int = -1, *, wait: bool = False):
        """Have Claude Code run an analysis notebook Clerk drafted, in a separate process.

        Claude Code may run the notebook (``jupyter nbconvert``) and fix small errors
        in it, and nothing else. Its summary appears in the conversation, so Clerk can
        interpret the results with the next question. Inspect the notebook first: its
        path is in :attr:`analyses` and on its line in the panel. You can also run it
        yourself instead.

        Args:
            which: An entry of :attr:`analyses` by id, path or index (default: the
                latest).
            wait: Block until the run finishes and return its result; otherwise the
                run continues in the background and its thread is returned.
        """
        from ..clerk.analysis import run_with_claude_code

        entry = None
        if isinstance(which, int) and self.analyses:
            entry = self.analyses[which]
        else:
            entry = next(
                (a for a in self.analyses if which in (a["id"], a["path"], Path(a["path"]).name)),
                None,
            )
        if entry is None:
            raise ValueError(f"No analysis notebook {which!r}; see clerk.analyses")
        if entry["status"] == "running":
            return None

        def task():
            entry.update(status="running", summary="")
            self._update_analysis(entry)
            result = run_with_claude_code(entry["path"])
            entry.update(
                status="done" if result["ok"] else "failed",
                summary=result["summary"],
                log=result["log"],
            )
            self._update_analysis(entry)
            verb = "ran" if result["ok"] else "couldn't run"
            # In the conversation, so Clerk reads the results with the next question.
            self._append(
                {
                    "role": "action",
                    "content": f"Claude Code {verb} the analysis notebook {entry['title']}",
                    "detail": f"{entry['path']}\n\n{result['summary']}",
                }
            )
            return result

        if wait:
            return task()
        thread = threading.Thread(target=task, name="celldega-clerk-analysis", daemon=True)
        thread.start()
        return thread

    @property
    def snapshots(self):
        """The views Clerk was shown in this conversation, as :class:`Snapshots`.

        One per widget per capture, named by question: ``"Q1 Landscape"``,
        ``"Q1 Clustergram"`` (a later capture for the same question is ``"Q1.2
        Landscape"``), with the question as the memo; plus the Snapshots Clerk saved
        with its screenshot action. They're kept in memory (and written as Snapshot
        PNGs when you export a report); ``clerk.snapshots.save(folder)`` writes them::

            clerk.snapshots.card("Q1 Landscape", landscape=landscape)
            landscape.pins = clerk.snapshots
        """
        from .snapshot_widget import Snapshots

        out = Snapshots()
        for number, entry in enumerate(self.record, start=1):
            captures = 0
            question = str(entry.get("question") or "")
            for step in entry.get("steps") or []:
                if step.get("kind") == "screenshot":
                    path = Path(str(step.get("text") or ""))
                    if path.suffix.lower() == ".png" and path.is_file():
                        # A PNG without a Snapshot record is skipped.
                        with contextlib.suppress(ValueError):
                            out.add(path)
                    continue
                if step.get("kind") != "capture" or not (
                    step.get("image") or step.get("clustergram_image")
                ):
                    continue
                captures += 1
                label = f"Q{number}" if captures == 1 else f"Q{number}.{captures}"
                for key, widget in (("image", "landscape"), ("clustergram_image", "clustergram")):
                    view = (step.get("snapshots") or {}).get(widget)
                    if not step.get(key) or not view:
                        continue
                    name = f"{label} {widget.title()}"
                    out.add(
                        {
                            **deepcopy(view),
                            "image": {"png": step[key]},
                            "title": name,
                            "description": question,
                        },
                        name=name,
                    )
        return out

    def findings_df(self) -> pd.DataFrame:
        """Cell types Clerk has proposed, one row per proposal (latest last).

        Columns: ``cluster``, ``label``, ``confidence``, ``markers`` (supporting genes),
        ``notes``, ``question`` (what was asked) and ``recorded`` (time).
        """
        columns = ["cluster", "label", "confidence", "markers", "notes", "question", "recorded"]
        return pd.DataFrame(
            [{**f, "markers": ", ".join(f["markers"])} for f in self.findings], columns=columns
        )

    def write_cell_types(
        self,
        adata,
        groupby: str,
        key: str = "clerk_cell_type",
        *,
        overwrite: bool = False,
        unassigned: str = "Unassigned",
    ) -> pd.Series:
        """Write Clerk's latest proposed cell type per cluster into ``adata.obs[key]``.

        Works for a cell-level AnnData (``obs[groupby]`` holds each cell's cluster) and
        for a cluster-level one such as the signature AnnData behind a Clustergram.
        Clusters without a proposal get ``unassigned``. Adds a column only: an existing
        ``key`` is left alone unless ``overwrite=True``. The labels used, and where they
        came from, are recorded in ``adata.uns["clerk_cell_types"][key]``.

        Returns:
            pd.Series: The new column.
        """
        if groupby not in adata.obs:
            raise KeyError(f"{groupby!r} is not a column of adata.obs")
        if key in adata.obs and not overwrite:
            raise ValueError(f"adata.obs already has {key!r}; pass overwrite=True to replace it")
        labels: dict[str, str] = {}
        for finding in self.findings:  # later proposals win
            labels[finding["cluster"]] = finding["label"]
        values = adata.obs[groupby].astype(str).map(labels).fillna(unassigned)
        adata.obs[key] = pd.Categorical(values)
        adata.uns.setdefault("clerk_cell_types", {})[key] = {
            "groupby": groupby,
            "labels": labels,
            "written": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return adata.obs[key]

    def _append(self, message: dict) -> None:
        with self._messages_lock:
            self.messages = [*self.messages, message]
        if self.pending and message.get("role") in ("error", "pause"):
            self._log_step(message["role"], str(message.get("content", "")))

    #: Terms per library in an inline Enrichr result; its chart scrolls, as in the
    #: Enrich panel. Clerk itself reads the top ``ENRICHMENT_PROMPT_TERMS``.
    ENRICHMENT_TERMS = 20
    ENRICHMENT_PROMPT_TERMS = 8

    def _append_enrichment(
        self,
        label: str,
        genes: list,
        results: dict,
        *,
        once: bool = False,
        url: str = "",
        title: str = "",
    ) -> None:
        """Show Enrichr results in the conversation, like the Enrich panel.

        The panel draws an ``enrichment`` message as a bar graph of the top terms per
        library and a paragraph of the genes tested, linked to the views, plus a link
        to the same results on the Enrichr website (``url``) when known. The
        results already reach the model as text, so these messages are left out of
        its history. ``once`` skips results identical to the last ones shown.
        """

        def number(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        libraries = {}
        for library, terms in (results or {}).items():
            rows = []
            for term in list(terms or [])[: self.ENRICHMENT_TERMS]:
                row = {
                    "name": str(term.get("name", "")),
                    "score": number(term.get("score")) or 0.0,
                    "genes": [str(g) for g in term.get("genes") or []],
                }
                for key in ("adjusted_p", "odds_ratio"):
                    if number(term.get(key)) is not None:
                        row[key] = number(term.get(key))
                rows.append(row)
            if rows:
                libraries[str(library)] = rows
        if not libraries:
            return
        genes = [str(g) for g in dict.fromkeys(genes or []) if str(g)]
        if once:
            key = (tuple(genes), json.dumps(libraries, sort_keys=True))
            if key == getattr(self, "_last_enrichment", None):
                return
            self._last_enrichment = key
        message = {
            "role": "enrichment",
            "content": f"Enrichr results for {label}",
            # The panel folds the results under this title, e.g. "Cluster 4 upregulated".
            "title": title or label,
            "label": label,
            "genes": genes,
            "libraries": libraries,
        }
        if url:
            message["url"] = url
        self._append(message)

    # -- The case record: what was asked, what Clerk did, and how to reproduce it --

    def _start_record(self, question: str, call: dict, question_index: int, summary) -> None:
        """Open the record for a new question (see :meth:`export`)."""
        self.record.append(
            {
                "question": question,
                "asked": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": call.get("model") or "",
                "effort": call.get("effort") or "",
                "message_index": question_index,
                "sent_with": list(summary),
                "context": call.get("info") or "",
                "gene_list": list(call.get("gene_list") or []),
                "briefing": bool(call.get("briefing")),
                "steps": [],
            }
        )

    def _log_step(self, kind: str, text: str, **extra) -> None:
        if self.record:
            self.record[-1]["steps"].append({"kind": kind, "text": text, **extra})

    def _log_capture(self, views: dict, label: str) -> None:
        """Keep observed evidence separately from the subset of settings we can replay."""
        from .screenshots import widget_source
        from .snapshots import restore_spec

        if not self.record:
            return
        observations = deepcopy(
            {
                key: views[key]
                for key in ("landscape_state", "clustergram_state", "enrich_state", "neighborhoods")
                if views.get(key) is not None
            }
        )
        sources = {name: widget_source(widget) for name, widget in self._linked_widgets.items()}
        landscape = _landscape_reproduction(views.get("landscape_state"))
        clustergram = _clustergram_reproduction(views.get("clustergram_state"))
        image = self.image_b64 if views.get("image_fresh") else ""
        clustergram_image = views.get("clustergram_image") or ""
        if not (image or clustergram_image or landscape or clustergram or observations):
            return
        last = next(
            (st for st in reversed(self.record[-1]["steps"]) if st["kind"] == "capture"), None
        )
        snapshots = {
            name: restore_spec(value) for name, value in views.get("snapshots", {}).items()
        }

        def replay_contracts(saved):
            # A new capture time alone is redundant; changed data or replay settings
            # must survive even when the capped observations and pixels are identical.
            return {
                name: {key: value for key, value in snapshot.items() if key != "captured_at"}
                for name, snapshot in saved.items()
            }

        if (
            last
            and last.get("observations") == observations
            and last.get("sources") == sources
            and last.get("image") == image
            and last.get("clustergram_image") == clustergram_image
            and replay_contracts(last.get("snapshots", {})) == replay_contracts(snapshots)
        ):
            return
        self._log_step(
            "capture",
            label,
            image=image,
            clustergram_image=clustergram_image,
            landscape=landscape,
            clustergram=clustergram,
            observations=observations,
            sources=sources,
            snapshots=snapshots,
            view_state=dict(self.image_view_state or {}) if image else {},
        )

    # Caps on what one lookup request can ask for.
    _MAX_LOOKUP_GENES = 200
    _MAX_ENRICHR_REQUESTS = 4
    _MAX_PUBMED_QUERIES = 3

    def _apply_actions(self, actions: dict) -> tuple[list[str], dict]:
        """Validate a ``celldega-actions`` request and apply its view changes.

        ``lookup`` is read-only and nothing in it changes what the scientist sees:
        ``genes`` (rows added to the next Clustergram snapshot), ``markers`` (ranked
        markers per cluster, ``{"clusters": [...], "n": 25}``), ``enrichr`` (a spec or
        list of specs, each ``{"genes": [...]}`` or ``{"cluster": "4", "n": 25}``,
        plus optional ``libraries``) and ``pubmed`` (a query or list of queries).
        ``clustergram`` settings go to ``Clustergram.apply_state`` (its legacy
        ``lookup_genes`` key is read as ``lookup.genes``).

        Returns:
            tuple: ``(changes, reads)``; ``changes`` describes view changes made,
            ``reads`` holds the validated lookups (run after the views are re-read).

        Raises:
            ValueError: For something Clerk can't do, or an invalid request.
        """
        unknown = sorted(set(actions) - {"clustergram", "landscape", "lookup", "snapshot"})
        if unknown:
            raise ValueError(
                f"unknown action(s) {unknown}; use 'lookup', 'clustergram', 'landscape' "
                "and/or 'snapshot'"
            )
        snapshot = actions.get("snapshot")
        if snapshot is not None and not isinstance(snapshot, dict):
            raise ValueError("'snapshot' must be like {'title': ..., 'description': ...}")
        landscape_settings = actions.get("landscape")
        landscape = self._linked_widgets.get("landscape")
        if landscape_settings is not None and (
            landscape is None or not hasattr(landscape, "apply_state")
        ):
            raise ValueError("no Landscape is linked")
        lookup = actions.get("lookup") or {}
        settings = dict(actions.get("clustergram") or {})
        if not isinstance(lookup, dict):
            raise ValueError("'lookup' must be an object")

        def _names(value, what):
            if value is None:
                return []
            if isinstance(value, str) or not isinstance(value, list | tuple):
                raise ValueError(f"{what} must be a list of names")
            return [str(v) for v in value][: self._MAX_LOOKUP_GENES]

        reads: dict[str, Any] = {
            "genes": _names(settings.pop("lookup_genes", None), "lookup_genes")
            + _names(lookup.get("genes"), "lookup.genes"),
            "markers": None,
            "enrichr": [],
            "pubmed": [],
            "snapshot": dict(snapshot) if snapshot is not None else None,
        }
        markers = lookup.get("markers")
        if markers is not None:
            if not isinstance(markers, dict):
                raise ValueError("lookup.markers must be like {'clusters': ['4'], 'n': 25}")
            reads["markers"] = {
                "clusters": None
                if markers.get("clusters") is None
                else _names(markers["clusters"], "markers.clusters"),
                "n": int(markers.get("n", 25)),
            }
        enrichr = lookup.get("enrichr")
        for spec in ([enrichr] if isinstance(enrichr, dict) else enrichr or [])[
            : self._MAX_ENRICHR_REQUESTS
        ]:
            if not isinstance(spec, dict) or not (spec.get("genes") or spec.get("cluster")):
                raise ValueError("each lookup.enrichr needs 'genes' or 'cluster'")
            reads["enrichr"].append(
                {
                    "genes": _names(spec.get("genes"), "enrichr.genes"),
                    "cluster": None if spec.get("cluster") is None else str(spec["cluster"]),
                    "n": int(spec.get("n", 25)),
                    "libraries": _names(spec.get("libraries"), "enrichr.libraries") or None,
                }
            )
        pubmed = lookup.get("pubmed")
        queries = [pubmed] if isinstance(pubmed, str) else list(pubmed or [])
        reads["pubmed"] = [str(q) for q in queries if str(q).strip()][: self._MAX_PUBMED_QUERIES]

        cgm = self._linked_widgets.get("clustergram")
        needs_cgm = (
            settings
            or reads["genes"]
            or reads["markers"]
            or any(spec["cluster"] for spec in reads["enrichr"])
        )
        if needs_cgm and (cgm is None or not hasattr(cgm, "apply_state")):
            raise ValueError("no Clustergram is linked")
        # Validate both widgets' changes before applying either.
        if landscape_settings:
            unknown_keys = sorted(set(landscape_settings) - set(landscape.APPLY_STATE_KEYS))
            if unknown_keys:
                raise ValueError(f"unknown Landscape setting(s): {unknown_keys}")
        before_cgm = getattr(cgm, "_apply_request_id", 0)
        changes = [f"the Clustergram: {c}" for c in (cgm.apply_state(settings) if settings else [])]
        self._pending_clustergram_apply = (
            cgm._apply_request_id if getattr(cgm, "_apply_request_id", 0) != before_cgm else None
        )
        self._pending_landscape_apply = None
        if landscape_settings:
            before = getattr(landscape, "_apply_request_id", 0)
            changes += [f"the Landscape: {c}" for c in landscape.apply_state(landscape_settings)]
            if getattr(landscape, "_apply_request_id", 0) != before:
                self._pending_landscape_apply = landscape._apply_request_id
        return changes, reads

    #: Folder for everything Clerk writes: exported reports (``report_<time>``) and
    #: its screenshots (``screenshots``), so one ignore rule covers them.
    output_dir = "clerk_files"
    #: Folder for screenshots Clerk takes (default: ``<output_dir>/screenshots``).
    screenshot_dir = None

    def _save_snapshot(self, views: dict, spec: dict, question: str) -> None:
        """Save the views just captured as a screenshot Clerk took (``snapshot`` action)."""
        from .screenshots import _in_view, widget_source, write_screenshot
        from .snapshots import restore_spec

        shots = []
        landscape = self._linked_widgets.get("landscape")
        if landscape is not None and views.get("image_fresh") and self.image_b64:
            shots.append(
                {
                    "image": self.image_b64,
                    "source": widget_source(landscape),
                    "state": _landscape_reproduction(views.get("landscape_state")),
                    "observed_state": deepcopy(views.get("landscape_state")),
                    "snapshot": restore_spec(views.get("snapshots", {}).get("landscape", {})),
                    "view_state": dict(self.image_view_state or {}),
                    "in_view": _in_view(views.get("landscape_state")),
                }
            )
        cgm = self._linked_widgets.get("clustergram")
        if cgm is not None and views.get("clustergram_image"):
            shots.append(
                {
                    "image": views["clustergram_image"],
                    "source": widget_source(cgm),
                    "state": _clustergram_reproduction(views.get("clustergram_state")),
                    "observed_state": deepcopy(views.get("clustergram_state")),
                    "snapshot": restore_spec(views.get("snapshots", {}).get("clustergram", {})),
                }
            )
        if not shots:
            self._append(
                {"role": "error", "content": "Couldn't take a screenshot: no view sent an image."}
            )
            return
        try:
            target = write_screenshot(
                self.screenshot_dir or Path(self.output_dir) / "screenshots",
                shots,
                description=str(spec.get("description") or ""),
                title=str(spec.get("title") or ""),
                author="Clerk",
                metadata={"question": question},
            )
        except Exception as exc:
            self._append({"role": "error", "content": f"Couldn't save the screenshot: {exc}"})
            return
        self.screenshots.append(str(target))
        self._append({"role": "action", "content": f"Saved a screenshot: {target}"})
        self._log_step("screenshot", str(target), description=str(spec.get("description") or ""))

    def _wait_for_landscape_apply(self) -> None:
        """Wait for view changes to finish before claiming success or capturing evidence."""
        for name in ("clustergram", "landscape"):
            pending = getattr(self, f"_pending_{name}_apply", None)
            widget = self._linked_widgets.get(name)
            if pending is None or widget is None:
                continue
            answered = self._request_and_wait(
                [(widget, "apply_capture_id", lambda rid=pending: rid)]
            )[0]
            setattr(self, f"_pending_{name}_apply", None)
            if not answered:
                raise ValueError(
                    f"{name.title()} did not confirm the view change before the timeout"
                )
            reply = widget._apply_replies[pending]
            if reply["event"] == "apply_error":
                raise ValueError(
                    f"{name.title()} view change failed: {reply.get('error') or 'apply_state failed'}"
                )

    @staticmethod
    def _describe_reads(reads: dict) -> list[str]:
        """Short descriptions of the lookups, for the conversation."""
        out = []
        genes = reads.get("genes") or []
        if genes:
            shown = ", ".join(genes) if len(genes) <= 8 else f"{len(genes)} genes"
            out.append(f"Looked up {shown} in the Clustergram (view unchanged)")
        markers = reads.get("markers")
        if markers:
            which = (
                "clusters " + ", ".join(markers["clusters"])
                if markers.get("clusters")
                else "all clusters"
            )
            out.append(f"Read the top {markers['n']} ranked markers of {which}")
        for spec in reads.get("enrichr") or []:
            source = (
                f"cluster {spec['cluster']}'s top {spec['n']} markers"
                if spec["cluster"]
                else f"{len(spec['genes'])} genes"
            )
            libraries = ", ".join(spec["libraries"] or ["default libraries"])
            out.append(f"Ran Enrichr ({libraries}) on {source}")
        out.extend(f"Searched PubMed: {query!r}" for query in reads.get("pubmed") or [])
        if reads.get("snapshot") is not None:
            out.append("Took a screenshot")
        return out

    def _run_lookups(self, reads: dict, clustergram_state: dict | None) -> list[str]:
        """Run the Enrichr / PubMed lookups (worker thread); returns text for the prompt."""
        from ..clerk import lookups

        results = []
        by_cluster = {
            str(entry.get("cluster")): [g["name"] for g in entry.get("genes") or []]
            for entry in (clustergram_state or {}).get("cluster_markers") or []
        }
        for spec in reads.get("enrichr") or []:
            if spec["cluster"]:
                genes = by_cluster.get(spec["cluster"], [])[: spec["n"]]
                label = f"cluster {spec['cluster']}'s top {len(genes)} markers"
                # Ranked markers (rank_genes_groups) are the cluster's upregulated genes.
                title = f"Cluster {spec['cluster']} upregulated"
            else:
                genes, label = spec["genes"], f"{len(spec['genes'])} genes"
                title = label[:1].upper() + label[1:]
            if not genes:
                results.append(f"Enrichr for {label}: no genes to test.")
                continue
            try:
                found = lookups.enrichr(
                    genes,
                    spec["libraries"] or lookups.DEFAULT_LIBRARIES,
                    top=self.ENRICHMENT_TERMS,
                )
                url = lookups.enrichr_link(genes)
                # Clerk reads the top few terms; the panel's chart scrolls through more.
                brief = {lib: terms[: self.ENRICHMENT_PROMPT_TERMS] for lib, terms in found.items()}
                results.append(lookups.format_enrichr(label, brief, url=url))
            except Exception as exc:  # network or service problems become a note
                results.append(f"Enrichr for {label} failed: {exc}")
                continue
            self._append_enrichment(label, genes, found, url=url, title=title)
        for query in reads.get("pubmed") or []:
            try:
                results.append(lookups.format_pubmed(query, lookups.pubmed(query)))
            except Exception as exc:
                results.append(f"PubMed search {query!r} failed: {exc}")
        return results

    def _use_views(self, call: dict, views: dict) -> None:
        call["clustergram_state"] = views["clustergram_state"]
        call["enrich_state"] = views["enrich_state"]
        call["landscape_state"] = views.get("landscape_state")
        call["neighborhoods"] = views.get("neighborhoods")
        call["notes"] = list(views["notes"])
        call["image_b64"] = self.image_b64 or None

    def _answer(self, question, call):
        """Answer one question (worker thread), following any actions Clerk asks for."""
        from .. import clerk

        try:
            views = self._refresh_views(question)
            self._use_views(call, views)
            # Where a notebook Clerk drafts should load its data from.
            sources = self._analysis_sources()
            if sources:
                call["notes"].append("Data for analysis notebooks: " + "; ".join(sources))
            summary = list(views["summary"])
            if call.get("gene_list"):
                summary.append(f"{len(call['gene_list'])} selected genes")
            if call.get("enrichr_terms"):
                summary.append(f"{len(call['enrichr_terms'])} Enrichr terms")
            if call.get("info"):
                summary.append("context")
            self._record_evidence(
                summary,
                views["image_fresh"],
                views.get("snapshots"),
                views.get("clustergram_thumb", ""),
            )
            if call.get("enrichr_terms"):
                # The panel's own Enrichr results for the selected genes, shown once
                # per gene list rather than with every question about it.
                url = _enrichr_page(call.get("enrichr_short_id"))
                if url:
                    call["notes"].append(f"Enrichr page for the selected genes' results: {url}")
                n = len(call.get("gene_list") or [])
                self._append_enrichment(
                    f"{n} selected genes",
                    call.get("gene_list") or [],
                    {call.get("enrichr_library") or "CellMarker_2024": call["enrichr_terms"]},
                    once=True,
                    url=url,
                    title=f"{n} selected gene{'s' if n != 1 else ''}",
                )
                # The chart scrolls through them all; Clerk reads the top few.
                call["enrichr_terms"] = call["enrichr_terms"][: self.ENRICHMENT_PROMPT_TERMS]
            cgm = self._linked_widgets.get("clustergram")
            # Lookups (Enrichr, PubMed) work without widgets; Clustergram / Landscape
            # lookups and changes only when those are linked.
            landscape = self._linked_widgets.get("landscape")
            call["actions_help"] = clerk.actions_help(
                clustergram=cgm is not None and hasattr(cgm, "apply_state"),
                landscape=landscape is not None and hasattr(landscape, "apply_state"),
            )
            question_index = len(self.messages) - 1
            self._start_record(question, call, question_index, summary)
            self._log_capture(views, "When asked")
            # One CLI session per question: follow-up rounds resume it and send only
            # what is new, so the evidence already sent is read from the API's cache.
            call["session"] = clerk.Session()
            self._work(question, call, question_index, answer=_ask(question, call))
        except Exception as exc:  # surface every failure in the panel, not the log
            self._report_failure(exc)
        finally:
            self._finish_question(call)
            self.pending = False

    def _resume(self, paused: dict) -> None:
        """Continue a paused question (worker thread) with a fresh round budget."""
        try:
            self._work(
                paused["question"],
                paused["call"],
                paused["question_index"],
                pending_actions=paused["actions"],
            )
        except Exception as exc:
            self._report_failure(exc)
        finally:
            self._finish_question(paused["call"])
            self.pending = False

    def _finish_question(self, call: dict) -> None:
        """Record the question's token use and close its CLI session, unless paused."""
        if self._paused is not None and self._paused["call"] is call:
            return  # Continue will resume the same session
        session = call.pop("session", None)
        if session is None:
            return
        if self.record and session.usage:
            self.record[-1]["usage"] = session.totals()
        session.close()

    def _report_failure(self, exc: Exception) -> None:
        from .. import clerk

        message = (
            str(exc) if isinstance(exc, clerk.ClerkBackendError) else f"Unexpected error: {exc}"
        )
        self.error = message
        self.messages = [*self.messages, {"role": "error", "content": message}]

    def _continue(self, question, call, changed: dict, found: list[str], notes: list[str]):
        """The next round: resume the question's session with only what's new.

        Falls back to a fresh call with all the evidence if the session can't be resumed.
        """
        from .. import clerk

        session = call.get("session")
        if session is not None and session.started:
            try:
                return clerk.follow_up(
                    session,
                    notes=notes,
                    lookups=found,
                    model=call.get("model") or "",
                    effort=call.get("effort") or "",
                    timeout=call.get("timeout") or clerk.DEFAULT_TIMEOUT,
                    **changed,
                )
            except clerk.ClerkBackendError as exc:
                if str(exc) == clerk.LOGIN_HELP:
                    raise
                session.close()
                call["session"] = clerk.Session()
                self._log_step(
                    "note", f"Session could not be resumed ({exc}); resent all evidence."
                )
        return _ask(question, call)

    def _work(self, question, call, question_index, answer=None, pending_actions=None):
        """Notebook adapter for the transport-independent Clerk workflow."""
        from ..clerk.engine import run_turn

        workflow = run_turn(
            answer, max_rounds=self.max_action_rounds, pending_actions=pending_actions
        )
        response = None
        while True:
            try:
                event = workflow.send(response)
            except StopIteration:
                return
            response = None
            kind = event["kind"]
            if kind == "answer":
                from ..clerk.llm import resolve_dendrogram_groups

                text = event["text"]
                views, problems = resolve_dendrogram_groups(
                    event["views"], call.get("clustergram_state")
                )
                if problems:
                    self._append(
                        {
                            "role": "error",
                            "content": "Some cited views were changed: " + "; ".join(problems),
                        }
                    )
                links = self._links_for(text)
                text = self._unbracket_names(text, links.get("genes", ()))
                message = {"role": "assistant", "content": text, **links}
                if views:
                    message["views"] = views
                self._append(message)
                self._log_step("answer", text, views=views)
            elif kind == "findings":
                self._record_findings(event["findings"], question)
            elif kind == "notebook":
                self._draft_notebook(event["notebook"], question)
            elif kind == "error":
                self._append({"role": "error", "content": event["text"]})
                if not self.pending:
                    self._log_step("error", event["text"])
            elif kind == "pause":
                self._paused = {
                    "question": question,
                    "call": call,
                    "question_index": question_index,
                    "actions": event["actions"],
                }
                self._append(
                    {
                        "role": "pause",
                        "content": f"Clerk has made {event['rounds']} "
                        "lookups or view changes for this question and paused. Continue?",
                    }
                )
            elif kind == "apply":
                try:
                    changes, reads = self._apply_actions(event["actions"])
                    self._wait_for_landscape_apply()
                    response = {"changes": changes, "reads": reads}
                except ValueError as exc:
                    response = {"error": str(exc)}
            elif kind == "observe":
                changes, reads = event["changes"], event["reads"]
                did = (["Changed " + "; ".join(changes)] if changes else []) + self._describe_reads(
                    reads
                )
                involved = list(reads.get("genes") or [])
                for spec in reads.get("enrichr") or []:
                    involved += [g for g in spec["genes"] if g not in involved]
                label = ". ".join(did)
                self._append(
                    {"role": "action", "content": label, **self._links_for(label, involved)}
                )
                self._log_step("action", label, actions=event["actions"])
                options = (
                    {"extra_rows": reads["genes"], "markers": self._markers_needed(reads)}
                    if event["continue"]
                    else {}
                )
                views = self._refresh_views(question, **options)
                self._log_capture(views, label)
                if reads.get("snapshot") is not None:
                    self._save_snapshot(views, reads["snapshot"], question)
                if event["continue"]:
                    found = self._run_lookups(reads, views["clustergram_state"])
                    if found:
                        self._log_step("lookups", "\n\n".join(found))
                    response = {"views": views, "found": found, "did": did}
            elif kind == "follow_up":
                views, found, did = (event["evidence"][key] for key in ("views", "found", "did"))
                changed = _changed_views(call, views, self.image_b64)
                self._use_views(call, views)
                call["lookups"] = _keep_recent([*(call.get("lookups") or []), *found])
                call.setdefault("done", []).extend(d[0].lower() + d[1:] for d in did)
                note = (
                    "For this question you have so far: " + "; ".join(call["done"]) + ". The "
                    "evidence and lookup results reflect this. Continue answering the "
                    "scientist's question without repeating what you already said or "
                    "requesting any of these again."
                )
                call["notes"].append(note)
                call["history"] = [
                    dict(m) for i, m in enumerate(self.messages) if i != question_index
                ]
                response = self._continue(question, call, changed, found, [*views["notes"], note])

    def export(
        self,
        folder: str | Path | None = None,
        *,
        title: str = "",
        adata=None,
        groupby: str | None = None,
        key: str = "clerk_cell_type",
        write_h5ad: bool = False,
        names: dict | None = None,
        html: bool = True,
    ) -> dict[str, Path]:
        """Save a record of this conversation that you can take with you.

        Writes into ``folder`` (default ``<output_dir>/report_<date>-<time>``, i.e.
        ``clerk_files/report_...``):

        - ``report.html``: the whole conversation as one page. Each screenshot sits
          under the code that recreates that view (``landscape.apply_state(...)``,
          ``cgm.apply_state(...)``); Clerk's work and evidence are collapsed.
        - ``report.ipynb``: the same as a notebook, to re-run the code.
        - ``record.json``: everything, machine-readable.
        - ``screenshots/``: each capture as a Celldega screenshot (a PNG carrying the
          record to reopen its view with ``dega.viz.from_png``).
        - ``findings.csv``: the cell types Clerk proposed.

        With ``adata`` and ``groupby``, the latest cell types are also written into
        ``adata.obs[key]`` (see :meth:`write_cell_types`; a column Clerk wrote before
        is replaced) and saved as ``cell_types.csv``, plus ``adata.h5ad`` with
        ``write_h5ad=True``.

        Args:
            title: Optional report name, shown as its heading and used in the
                default folder name (followed by a timestamp).
            names: Variable names for the reproduction code, default
                ``{"landscape": "landscape", "clustergram": "cgm"}``.
            html: Also render ``report.html`` (needs ``nbconvert``).

        Returns:
            dict: Paths written, by kind.
        """
        from ..clerk import report

        title = " ".join(title.split())
        stem = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:50] or "report"
        folder = Path(folder or Path(self.output_dir) / f"{stem}_{time.strftime('%Y%m%d-%H%M%S')}")
        try:
            celldega_version = importlib.metadata.version("celldega")
        except importlib.metadata.PackageNotFoundError:
            celldega_version = ""
        meta = {
            "title": title,
            "context": self.context_info,
            "widgets": sorted(self._linked_widgets),
            "celldega": celldega_version,
            "models": sorted({e["model"] or "default" for e in self.record}),
            "briefing": self.briefing,
            "briefing_sources": list(self.briefing_sources),
        }
        written = report.write_report(
            folder,
            self.record,
            self.findings,
            meta,
            names=names,
            html_report=html,
            messages=[dict(m) for m in self.messages],
        )
        if adata is not None:
            if not groupby:
                raise ValueError("pass groupby= (the cluster column) to annotate adata")
            mine = key in (adata.uns.get("clerk_cell_types") or {})
            column = self.write_cell_types(adata, groupby, key, overwrite=mine)
            written["cell_types"] = folder / "cell_types.csv"
            pd.DataFrame({groupby: adata.obs[groupby].astype(str), key: column}).to_csv(
                written["cell_types"]
            )
            if write_h5ad:
                written["adata"] = folder / "adata.h5ad"
                adata.write_h5ad(written["adata"])
        return written

    # Most genes one click can show (the Landscape's gene search allows 20).
    _MAX_SHOWN_GENES = 20

    def _queue_evidence(self, task, *args, **kwargs) -> concurrent.futures.Future:
        """Run evidence clicks in order on one background thread (saving the view
        waits for the browser, which the kernel's main thread must stay free for)."""
        if self._evidence_executor is None:
            self._evidence_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="celldega-clerk-evidence"
            )
        self._last_evidence = self._evidence_executor.submit(task, *args, **kwargs)
        return self._last_evidence

    def _follow_evidence(self, show, *args, **kwargs) -> concurrent.futures.Future:
        def task():
            if self._saved_view is None:
                self._save_view()
                if self._saved_view is None:
                    if self.error:
                        self._append({"role": "error", "content": self.error})
                    return
            show(*args, **kwargs)

        return self._queue_evidence(task)

    def _save_view(self) -> None:
        """Remember coordinated, identified views before following an evidence link."""
        from .snapshots import restore_spec

        requests, ids = [], {}
        for name in ("clustergram", "landscape"):
            widget = self._linked_widgets.get(name)
            if not hasattr(widget, "request_snapshot"):
                continue

            def send(widget=widget, name=name):
                options = (
                    {"max_rows": 1, "max_cols": 1, "include_values": False}
                    if name == "clustergram"
                    else {}
                )
                ids[name] = widget.request_snapshot(**options)
                return ids[name]

            requests.append((widget, "snapshot_capture_id", send))
        self._request_and_wait(requests)
        saved = {"snapshots": {}}
        for name, rid in ids.items():
            widget = self._linked_widgets[name]
            reply = widget._snapshot_replies.get(rid, {})
            snapshot = reply.get("snapshot")
            if not snapshot or reply.get("error"):
                self.error = f"Couldn't save your {name} view before following the evidence link"
                return
            saved[name] = deepcopy(snapshot["state"])
            saved["snapshots"][name] = restore_spec(snapshot)
        cgm = self._linked_widgets.get("clustergram")
        if cgm is not None:
            saved["highlighted_genes"] = list(cgm.highlighted_genes)
        self._saved_view = saved
        self.can_restore = bool(saved["snapshots"])

    def _restore_captured_widget(self, name: str, snapshot: dict) -> None:
        """Restore one identified capture and wait for its exact browser reply."""
        widget = self._linked_widgets.get(name)
        if not hasattr(widget, "restore_snapshot"):
            raise ValueError(f"no {name.title()} is linked")
        rid = widget.restore_snapshot(snapshot)
        answered = self._request_and_wait([(widget, "apply_capture_id", lambda: rid)])[0]
        reply = widget._apply_replies.get(rid, {})
        if not answered or reply.get("event") == "apply_error":
            raise ValueError(reply.get("error") or "browser did not confirm restoration")

    def _show_snapshot(self, snapshots) -> None:
        """Revisit the views a question was sent with (one or both widgets), keeping
        the pre-click view for Back."""
        if not isinstance(snapshots, dict) or not (
            snapshots.get("landscape") or snapshots.get("clustergram")
        ):
            self.error = "This image has no saved view."
            self._append({"role": "error", "content": self.error})
            return
        # Clustergram focus can change the Landscape; restore the image's view last.
        for name in ("clustergram", "landscape"):
            if name not in snapshots:
                continue
            try:
                self._restore_captured_widget(name, snapshots[name])
            except ValueError as exc:
                self.error = f"Couldn't show the captured view: {name}: {exc}"
                self._append({"role": "error", "content": self.error})
                return
        self.error = ""

    def _restore_view(self) -> None:
        """Back: verify saved data and acknowledge restoration before clearing history."""
        saved = self._saved_view
        if not saved:
            return
        # Linked Clustergram focus can change Landscape; restore Landscape last.
        for name in ("clustergram", "landscape"):
            widget = self._linked_widgets.get(name)
            snapshot = saved.get("snapshots", {}).get(name)
            if not snapshot:
                continue
            try:
                # Same-session undo: the restore still checks the saved view matches
                # the loaded data (e.g. after a dataset switch).
                self._restore_captured_widget(name, snapshot)
                if name == "clustergram":
                    widget.highlighted_genes = saved.get("highlighted_genes") or []
            except ValueError as exc:
                self.error = f"Couldn't fully restore your view: {name}: {exc}"
                self._append({"role": "error", "content": self.error})
                return  # keep the saved view available to retry
        self._saved_view = None
        self.can_restore = False
        self.error = ""

    def _show_genes(self, genes, focus: str | None = None) -> None:
        """Show genes clicked in the conversation on the linked views.

        The Landscape colors cells by them (like its gene search); the Clustergram
        marks them as blue row labels and zooms to ``focus`` (the gene just clicked).
        An empty list returns the Landscape to cluster colors.
        """
        if not isinstance(genes, list | tuple):
            return
        genes = [str(g) for g in genes][: self._MAX_SHOWN_GENES]
        landscape = self._linked_widgets.get("landscape")
        cgm = self._linked_widgets.get("clustergram")
        if not hasattr(landscape, "apply_state") and not hasattr(cgm, "apply_state"):
            self.error = "Link a Landscape or Clustergram to show genes."
            return
        problems = []
        if hasattr(landscape, "apply_state"):
            try:
                landscape.apply_state({"genes": genes})
            except ValueError as exc:
                problems.append(f"Landscape: {exc}")
        if hasattr(cgm, "apply_state"):
            rows = set(map(str, cgm.row_names or []))
            cgm.highlighted_genes = [g for g in genes if g in rows]
            # Zoom the Clustergram to a single gene shown. Its focus also reaches a
            # Landscape linked through Enrich, as that one gene, so for several genes
            # leave the focus alone (it would replace them with one).
            if len(genes) == 1 and str(focus or "") in rows and focus in genes:
                focus_gene = str(focus)
            elif not genes:
                focus_gene = ""
            else:
                focus_gene = None
            if focus_gene is not None:
                try:
                    cgm.apply_state({"focus_gene": focus_gene})
                except ValueError as exc:
                    problems.append(f"Clustergram: {exc}")
        if problems:
            self.error = f"Couldn't show {', '.join(genes) or 'the genes'}: " + "; ".join(problems)

    def _show_clusters(self, clusters) -> None:
        """Highlight clusters clicked in the conversation in the linked Landscape."""
        landscape = self._linked_widgets.get("landscape")
        if not hasattr(landscape, "apply_state"):
            self.error = "Link a Landscape to show clusters."
            return
        if not isinstance(clusters, list | tuple):
            return
        try:
            landscape.apply_state({"clusters": [str(c) for c in clusters]})
        except ValueError as exc:
            self.error = f"Couldn't show clusters: {exc}"

    def _apply_view(self, view) -> None:
        """Show a view Clerk cited (``[Fig 1A](view:1A)``) in the linked widgets."""
        from ..clerk.llm import RESOLVED_VIEW_KEYS, VIEW_KEYS

        if not isinstance(view, dict):
            return
        problems = []
        for widget_name, keys in VIEW_KEYS.items():
            settings = view.get(widget_name)
            if not settings:
                continue
            widget = self._linked_widgets.get(widget_name)
            if not hasattr(widget, "apply_state"):
                problems.append(f"no {widget_name.title()} is linked")
                continue
            allowed = (*keys, *RESOLVED_VIEW_KEYS.get(widget_name, ()))
            settings = {k: v for k, v in settings.items() if k in allowed}
            # A group the view names is resolved when the answer arrives (by then
            # the cut and members are known); an unresolved one can't be shown.
            settings.pop("dendrogram_group", None)
            try:
                widget.apply_state(settings)
            except ValueError as exc:
                problems.append(f"{widget_name.title()}: {exc}")
        if problems:
            self.error = "Couldn't show that view: " + "; ".join(problems)

    def _export_from_panel(self, *, title: str = "") -> None:
        """The panel's Write report button: write a report and say where it went."""
        try:
            written = self.export(title=title)
        except Exception as exc:
            self._append({"role": "error", "content": f"Couldn't write the report: {exc}"})
            return
        main = written.get("html") or written.get("notebook") or written["record"]
        self._append(
            {
                "role": "note",
                "content": f"Saved this conversation to {main} "
                f"(with {', '.join(p.name for k, p in written.items() if p != main)}).",
            }
        )

    # -- Saved conversations: SAVE / OPEN, save_conversation / load_conversation --

    #: Format version of a saved conversation file.
    CONVERSATION_VERSION = 1

    def save_conversation(self, path: str | Path | None = None, *, title: str = "") -> Path:
        """Save the conversation to reopen later with :meth:`load_conversation`.

        Writes one JSON file: the panel's messages (with their gene, cluster and view
        links and Enrichr results), the record of each question with the replay settings
        of its captures, Clerk's proposed cell types, the context, and links to the data
        the linked widgets show. Each question's screenshot preview is kept; full-size
        captures are left out to keep the file light (:meth:`export` keeps those).

        Reading a saved conversation needs no Claude. Its links change the linked
        widgets, so they need the same data loaded.

        Args:
            path: A ``.json`` file, or a folder for an auto-named one (default
                ``<output_dir>/conversations``, i.e. ``clerk_files/conversations``).
            title: Optional name, also used in the file name.

        Returns:
            Path: The file written.
        """
        from .screenshots import widget_source

        location = Path(path) if path else Path(self.output_dir) / "conversations"
        if location.suffix.lower() == ".json":
            target = location
        else:
            stem = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:50] or "conversation"
            target = location / f"{stem}_{time.strftime('%Y%m%d-%H%M%S')}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            celldega_version = importlib.metadata.version("celldega")
        except importlib.metadata.PackageNotFoundError:
            celldega_version = ""
        record = [
            {
                **entry,
                "steps": [
                    {k: v for k, v in step.items() if k not in ("image", "clustergram_image")}
                    for step in entry.get("steps") or []
                ],
            }
            for entry in deepcopy(self.record)
        ]
        payload = {
            "celldega_clerk_conversation": self.CONVERSATION_VERSION,
            "title": title,
            "saved": time.strftime("%Y-%m-%d %H:%M:%S"),
            "celldega": celldega_version,
            "context_info": self.context_info,
            "model": self.model,
            "effort": self.effort,
            "cluster_names": list(self.cluster_names),
            "cluster_labels": dict(self.cluster_labels),
            "sources": {name: widget_source(w) for name, w in self._linked_widgets.items()},
            "messages": [dict(m) for m in self.messages],
            "record": record,
            "findings": [dict(f) for f in self.findings],
        }
        target.write_text(json.dumps(payload, default=str), encoding="utf-8")
        return target

    def load_conversation(self, path: str | Path) -> dict:
        """Reopen a saved conversation in the panel, without Claude.

        Opens a file from :meth:`save_conversation` (or the panel's SAVE button), or a
        report folder from :meth:`export` (or its ``record.json``). The panel shows the
        conversation as it was: its genes, clusters and cited views stay clickable and
        change the linked widgets, which need the same data loaded. A new question
        continues the conversation, with the loaded one as its history.

        Replaces the current conversation, record and proposed cell types.

        Args:
            path: The conversation ``.json``, or an export folder or its ``record.json``.

        Returns:
            dict: What was saved: ``title``, ``saved``, ``celldega``, ``context_info``
            and ``sources`` (the data the original widgets showed).
        """
        path = Path(path)
        if path.is_dir():
            path = path / "record.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._load_conversation_data(data, path.parent)

    def _load_conversation_data(self, data, folder: Path | None) -> dict:
        from ..clerk import report
        from .snapshots import restore_spec

        if not isinstance(data, dict):
            raise ValueError("Not a saved Clerk conversation or exported report")
        if "celldega_clerk_conversation" in data:
            if data["celldega_clerk_conversation"] != self.CONVERSATION_VERSION:
                raise ValueError(
                    "Unsupported saved conversation version "
                    f"{data['celldega_clerk_conversation']!r}"
                )
            saved = data
        elif isinstance(data.get("questions"), list):  # an export's record.json
            meta = data.get("meta") or {}
            record = report.record_with_images(data["questions"], folder)
            saved = {
                "title": meta.get("title", ""),
                "saved": meta.get("exported", ""),
                "celldega": meta.get("celldega", ""),
                "context_info": meta.get("context", ""),
                "messages": data.get("messages") or self._messages_from_record(record),
                "record": record,
                "findings": data.get("findings") or [],
            }
        else:
            raise ValueError("Not a saved Clerk conversation or exported report")
        if self.pending:
            raise RuntimeError("Clerk is answering; open the conversation once it's done")
        if not isinstance(saved.get("messages"), list):
            raise ValueError("The saved conversation has no messages")

        if self._paused is not None:  # a loaded conversation replaces a paused question
            session = self._paused["call"].pop("session", None)
            if session is not None:
                session.close()
            self._paused = None
        self.record = list(saved.get("record") or [])
        self.findings = list(saved.get("findings") or [])
        # Keep what this session already knows; fill in what it doesn't.
        if saved.get("context_info") and not self.context_info:
            self.context_info = saved["context_info"]
        if saved.get("cluster_names") and not self.cluster_names:
            self.cluster_names = list(saved["cluster_names"])
        if saved.get("cluster_labels") and not self.cluster_labels:
            self.cluster_labels = dict(saved["cluster_labels"])
        self._last_enrichment = None
        self.error = ""
        messages = [dict(m) for m in saved["messages"] if isinstance(m, dict)]
        # Earlier conversations kept replay state only in the record. Recover it
        # from the initial capture, never from a view Clerk changed to later.
        questions = (m for m in messages if m.get("role") == "user")
        for message, entry in zip(questions, self.record, strict=False):
            if (
                not message.get("image")
                or message.get("snapshots")
                or message.get("content") != entry.get("question")
            ):
                continue
            capture = next(
                (
                    step
                    for step in entry.get("steps") or []
                    if step.get("kind") == "capture" and step.get("text") == "When asked"
                ),
                {},
            )
            if (capture.get("snapshots") or {}).get("landscape"):
                message["snapshots"] = {
                    name: restore_spec(snapshot) for name, snapshot in capture["snapshots"].items()
                }
        self.messages = messages
        return {
            key: saved.get(key) for key in ("title", "saved", "celldega", "context_info", "sources")
        }

    def _messages_from_record(self, record: list[dict]) -> list[dict]:
        """The panel's messages, rebuilt from a record (reports exported before 0.29)."""
        messages = []
        for entry in record:
            messages.append(
                {
                    "role": "user",
                    "content": entry.get("question", ""),
                    "evidence": list(entry.get("sent_with") or []),
                }
            )
            for step in entry.get("steps") or []:
                kind, text = step.get("kind"), str(step.get("text") or "")
                if kind == "answer":
                    message = {"role": "assistant", "content": text, **self._links_for(text)}
                    if step.get("views"):
                        message["views"] = step["views"]
                    messages.append(message)
                elif kind in ("action", "findings", "screenshot") and text:
                    messages.append({"role": "action", "content": text})
                elif kind == "error" and text:
                    messages.append({"role": "error", "content": text})
        return messages

    def _save_from_panel(self) -> None:
        """The panel's SAVE button: save the conversation and say where it went."""
        try:
            target = self.save_conversation()
        except Exception as exc:
            self._append({"role": "error", "content": f"Couldn't save the conversation: {exc}"})
            return
        self._append(
            {
                "role": "note",
                "content": f"Saved this conversation to {target}. Reopen it with OPEN or "
                f"clerk.load_conversation({str(target)!r}).",
            }
        )

    def _on_panel_msg(self, _widget, content, _buffers) -> None:
        """One-off panel messages: a LABEL offer accepted, or OPEN's saved conversation."""
        if not isinstance(content, dict):
            return
        if content.get("event") == "label_clustergram":
            self._label_from_offer(str(content.get("id") or ""))
            return
        if content.get("event") == "run_analysis":
            self.run_analysis(str(content.get("id") or ""))
            return
        if content.get("event") == "draft_notebook":
            self.draft_notebook(str(content.get("id") or "") or None)
            return
        if content.get("event") != "load_conversation":
            return
        name = str(content.get("name") or "the file")
        try:
            self._load_conversation_data(json.loads(content.get("text") or ""), None)
        except Exception as exc:
            self._append({"role": "error", "content": f"Couldn't open {name}: {exc}"})
            return
        self._append({"role": "note", "content": f"Opened the conversation saved in {name}."})

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the question in flight (if any) has been answered.

        Args:
            timeout (float | None): Seconds to wait; ``None`` waits indefinitely.

        Returns:
            bool: ``True`` if Clerk is idle afterwards.
        """
        worker = self._worker
        if worker is not None:
            worker.join(timeout)
        return worker is None or not worker.is_alive()

    def ask(self, question, **kwargs):
        """Ask a question from Python (bypasses the chat UI). Returns the answer text.

        Unlike the chat box, this blocks until the answer arrives. A cell can't wait
        for the browser, so this uses the views' latest snapshots (e.g. the last
        Landscape capture and ``Clustergram.latest_state``) rather than fresh ones.
        """
        from .. import clerk

        self.wait()
        genes = kwargs.pop("gene_list", None) or list(self.gene_list)
        history = [dict(m) for m in self.messages]
        cgm = self._linked_widgets.get("clustergram")
        latest = dict(getattr(cgm, "latest_state", None) or {}) or None
        self.messages = [*self.messages, {"role": "user", "content": question}]
        self.pending = True
        self.error = ""
        try:
            answer = clerk.ask(
                question,
                history=history,
                clustergram_state=kwargs.pop("clustergram_state", None) or latest,
                gene_list=genes,
                enrichr_terms=kwargs.pop("enrichr_terms", None) or [],
                info=kwargs.pop("info", None) or self.context_info,
                image_b64=kwargs.pop("image_b64", None) or self.image_b64 or None,
                model=kwargs.pop("model", None) or self.model,
                effort=kwargs.pop("effort", None) or self.effort,
                timeout=kwargs.pop("timeout", None) or self.timeout,
            )
            self.messages = [*self.messages, {"role": "assistant", "content": answer}]
            return answer
        except clerk.ClerkBackendError as exc:
            self.error = str(exc)
            raise
        finally:
            self.pending = False


def _is_screenshot_record(path: Path) -> bool:
    try:
        return bool(json.loads(path.read_text()).get("celldega_screenshot"))
    except (OSError, ValueError, AttributeError):
        return False


#: A question's call fields that are Clerk's own bookkeeping, not ``clerk.ask`` options.
_CLERK_CALL_ONLY = frozenset({"done", "enrichr_library", "enrichr_short_id"})

_ENRICHR_SHORT_ID = re.compile(r"^[A-Za-z0-9]{1,64}$")


def _enrichr_page(short_id) -> str:
    """The Enrichr web page for a gene list the panel uploaded, or ``""``."""
    from ..clerk import lookups

    short_id = str(short_id or "")
    return lookups.enrichr_app_url(short_id) if _ENRICHR_SHORT_ID.match(short_id) else ""


def _ask(question: str, call: dict) -> str:
    """``clerk.ask`` with a question's call settings (minus Clerk's own bookkeeping)."""
    from .. import clerk

    return clerk.ask(question, **{k: v for k, v in call.items() if k not in _CLERK_CALL_ONLY})


def _changed_views(call: dict, views: dict, image_b64: str) -> dict:
    """The views (and screenshot) that differ from what was last sent to Clerk."""
    changed = {
        key: views.get(key)
        for key in ("clustergram_state", "landscape_state", "neighborhoods", "enrich_state")
        if views.get(key) and views.get(key) != call.get(key)
    }
    if views.get("image_fresh") and image_b64 and image_b64 != call.get("image_b64"):
        changed["image_b64"] = image_b64
    return changed


# Cap on lookup results carried into one prompt (characters, newest kept).
MAX_LOOKUP_CHARS = 24_000


def _keep_recent(results: list[str], limit: int = MAX_LOOKUP_CHARS) -> list[str]:
    """The newest lookup results that fit in ``limit`` characters, in order."""
    kept: list[str] = []
    total = 0
    for text in reversed(results):
        if kept and total + len(text) > limit:
            break
        kept.append(text)
        total += len(text)
    return kept[::-1]


def _validate_replay_controls(widget, changes):
    axes = {"row", "col"}
    if "categories" in changes and "annotations" in changes:
        raise ValueError("Use categories or annotations, not both")
    for key in ("dendrogram", "annotations"):
        if key in changes and (not isinstance(changes[key], dict) or set(changes[key]) - axes):
            raise ValueError(f"{key} must contain row and/or col")
    for value in changes.get("dendrogram", {}).values():
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not np.isfinite(value)
            or not 0 <= value <= 100
        ):
            raise ValueError("dendrogram cuts must be percentages from 0 to 100")
    for axis, spec in changes.get("annotations", {}).items():
        if spec is None:
            continue
        if (
            not isinstance(spec, dict)
            or set(spec) != {"attribute", "values", "colors"}
            or not isinstance(spec["attribute"], str)
            or not spec["attribute"]
            or not isinstance(spec["values"], dict)
            or not isinstance(spec["colors"], dict)
        ):
            raise ValueError("annotations require attribute, values and colors")
        widget._check_category_names(axis, spec["values"])
        if any(not isinstance(v, str) or not v for v in spec["values"].values()):
            raise ValueError("Annotation values must be nonempty strings")
        if any(
            not isinstance(v, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", v)
            for v in spec["colors"].values()
        ):
            raise ValueError("Annotation colors must be six-digit hex colors")
    if "selection" in changes:
        selection = changes["selection"]
        if not isinstance(selection, dict) or set(selection) - {
            "rows",
            "cols",
            "genes",
            "highlighted_genes",
            "dendrogram",
        }:
            raise ValueError("Invalid Clustergram selection")
        for key in ("rows", "cols", "genes", "highlighted_genes"):
            if key not in selection:
                continue
            value = selection[key]
            if (
                not isinstance(value, list)
                or any(not isinstance(v, str) for v in value)
                or len(set(value)) != len(value)
            ):
                raise ValueError(f"selection.{key} must be a list of unique names")
            if key in ("rows", "cols"):
                widget._check_category_names(key[:-1], dict.fromkeys(value))
        group = selection.get("dendrogram")
        if group is not None:
            # A group at the current cut: by its members, or by the name the
            # Clustergram snapshot lists it under.
            by_name = (
                isinstance(group, dict)
                and set(group) == {"axis", "name"}
                and group["axis"] in axes
                and isinstance(group["name"], str)
                and bool(group["name"])
            )
            if not by_name:
                if (
                    not isinstance(group, dict)
                    or set(group) != {"axis", "members"}
                    or group["axis"] not in axes
                    or not isinstance(group["members"], list)
                    or not group["members"]
                    or any(not isinstance(v, str) for v in group["members"])
                    or len(set(group["members"])) != len(group["members"])
                ):
                    raise ValueError(
                        "selection.dendrogram requires axis and unique members (or name)"
                    )
                widget._check_category_names(group["axis"], dict.fromkeys(group["members"]))


def _validate_clustergram_controls(widget, changes: dict) -> dict:
    _validate_replay_controls(widget, changes)
    out = {
        key: deepcopy(changes[key])
        for key in ("order", "crop", "view", "dendrogram", "annotations", "selection")
        if key in changes
    }
    for key in ("order", "crop"):
        if key not in out:
            continue
        value = out[key]
        if not isinstance(value, dict) or set(value) - {"row", "col"}:
            raise ValueError(f"{key} must contain row and/or col")
        for axis, spec in value.items():
            if key == "crop" and spec is None:
                continue
            if key == "order" and isinstance(spec, str):
                if spec not in ("clust", "rank", "rankvar", "ini", "alpha"):
                    raise ValueError(f"unknown order: {spec}")
                continue
            if not isinstance(spec, list) or not spec or len(set(map(str, spec))) != len(spec):
                raise ValueError(f"{key}.{axis} must be a nonempty list of unique names")
            known = list(map(str, widget.row_names if axis == "row" else widget.col_names))
            if known and (
                set(map(str, spec)) - set(known) or (key == "order" and len(spec) != len(known))
            ):
                raise ValueError(f"{key}.{axis} must use this Clustergram's {axis} names")
            value[axis] = list(map(str, spec))
    if "view" in out:
        view = out["view"]
        if not isinstance(view, dict) or not view or set(view) - {"target", "zoom"}:
            raise ValueError("view must contain target and/or zoom")
        for key, values in view.items():
            if (
                not isinstance(values, list | tuple)
                or len(values) != 2
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, int | float)
                    or not np.isfinite(v)
                    or (key == "zoom" and v < 0)
                    for v in values
                )
            ):
                raise ValueError(f"view.{key} must contain two finite numbers (zoom >= 0)")
            view[key] = list(values)
    return out


def _validate_landscape_controls(key: str, value: dict) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a dict")

    def bounded(v, maximum):
        return (
            not isinstance(v, bool)
            and isinstance(v, int | float)
            and np.isfinite(v)
            and 0 <= v <= maximum
        )

    if key == "layers":
        if set(value) - {"image", "cells", "transcripts", "neighborhoods"} or any(
            not isinstance(v, bool) for v in value.values()
        ):
            raise ValueError("layers accepts image/cells/transcripts/neighborhoods booleans")
    elif key == "channels":
        for settings in value.values():
            if (
                not isinstance(settings, dict)
                or set(settings) - {"visible", "intensity"}
                or ("visible" in settings and not isinstance(settings["visible"], bool))
                or ("intensity" in settings and not bounded(settings["intensity"], 100))
            ):
                raise ValueError("channels accepts visible (bool) and intensity (0..100)")
    elif key == "sliders":
        if set(value) - {"cell", "trx", "nbhd"}:
            raise ValueError("sliders accepts cell, trx and nbhd")
        for name, setting in value.items():
            if name == "trx":
                if (
                    not isinstance(setting, dict)
                    or set(setting) - {"size", "opacity", "value"}
                    or any(
                        # The size limit depends on the dataset's transcript scale,
                        # which only the browser knows; it checks that bound.
                        not bounded(
                            v, 150 if k == "opacity" else float("inf") if k == "size" else 100
                        )
                        for k, v in setting.items()
                    )
                ):
                    raise ValueError("trx accepts size, opacity (0..150) or value (0..100)")
            elif not bounded(setting, 100):
                raise ValueError(f"{name} must be between 0 and 100")


def _landscape_reproduction(state: dict | None) -> dict:
    """The supported subset of a captured Landscape's settings (not a full restore)."""
    if not state:
        return {}
    out: dict[str, Any] = {}
    if state.get("space"):
        out["space"] = state["space"]
    view = state.get("view_state") or {}
    if view.get("target") is not None and view.get("zoom") is not None:
        out["view"] = {"target": list(view["target"]), "zoom": view["zoom"]}
    if state.get("selected_genes"):
        out["genes"] = list(state["selected_genes"])
    elif state.get("color_by") == "cluster":
        out["clusters"] = list(state.get("selected_clusters") or [])
    for key in ("layers", "channels", "sliders", "image_source"):
        if key in state:
            out[key] = deepcopy(state[key])
    return out


def _clustergram_reproduction(state: dict | None) -> dict:
    """The supported subset of a captured Clustergram's settings (not a full restore)."""
    if not state:
        return {}
    out: dict[str, Any] = {}
    level = state.get("marker_level") or {}
    if level:
        out["marker_level"] = "all" if level.get("current") is None else level["current"]
    display = state.get("display") or {}
    if display.get("mode"):
        out["mode"] = display["mode"]
    if display.get("size"):
        out["size"] = display["size"]
    if "focused_row" in display:
        out["focus_gene"] = display["focused_row"] or ""
    # Observations list named orders and small crops only (see request_state); the
    # complete settings are in a saved view's ``state``.
    for key in ("view", "order", "crop"):
        if state.get(key):
            out[key] = deepcopy(state[key])
    return out


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


def _composition_from_cells(
    data: Any,
    groupby: str,
    category: str | None,
    group_attrs: list[str] | None,
    color_adata: Any = None,
) -> dict[str, Any]:
    """Composition inputs from a cell-level AnnData/MuData: crosstab ``groupby`` x ``category``."""
    if category is None:
        raise ValueError("`category` is required with `groupby`")
    obs = getattr(data, "obs", None)
    if not isinstance(obs, pd.DataFrame):
        raise TypeError("`groupby` requires a cell-level AnnData or MuData")
    missing = [col for col in (groupby, category, *(group_attrs or [])) if col not in obs]
    if missing:
        raise KeyError(f"columns not found on obs: {missing}")

    counts = obs.groupby([groupby, category], observed=True).size().unstack(fill_value=0)
    counts.index = counts.index.astype(str)
    counts.columns = counts.columns.astype(str)
    group_sizes = counts.sum(axis=1)
    groups_x_pops = counts.div(group_sizes.where(group_sizes > 0, 1), axis=0)

    df = groups_x_pops.T.copy()
    meta_col = None
    if group_attrs:
        meta_col = obs.groupby(groupby, observed=True)[list(group_attrs)].first()
        meta_col.index = meta_col.index.astype(str)
        meta_col = meta_col.reindex(df.columns)
        categorical = [
            c for c in meta_col.columns if isinstance(meta_col[c].dtype, pd.CategoricalDtype)
        ]
        meta_col = meta_col.astype(dict.fromkeys(categorical, str))

    categories = list(counts.columns)
    return {
        "df": df,
        "meta_col": meta_col,
        "col_attr": list(group_attrs) if group_attrs else [],
        "colors": _colors_from_adata(data, category, categories)
        or _colors_from_adata(color_adata, category, categories),
        "normalized": True,
        "category": category,
        "col_weights": {str(name): float(n) for name, n in group_sizes.items()},
    }


def _composition_matrix_inputs(
    data: Any,
    modality: str = "population",
    category: str | None = None,
    color_adata: Any = None,
    group_attrs: list[str] | None = None,
    groupby: str | None = None,
) -> dict[str, Any]:
    """Build Matrix inputs for a composition Clustergram.

    Accepts a cell-level ``AnnData``/``MuData`` with ``groupby`` (cells are
    cross-tabulated into groups x ``category``), a ``MuData`` or any object
    exposing ``mod`` (reads ``modality``), an ``AnnData`` (obs = groups, var =
    populations), or a ``DataFrame`` (rows = groups, columns = populations).
    Returns a dict with:

    * ``df`` - populations x groups DataFrame (Clustergram row/col orientation)
    * ``meta_col`` - optional group (column) attribute table
    * ``colors`` - ``{population: hex}`` palette
    * ``normalized`` - default for ``composition_normalized``
    * ``category`` - resolved population category name
    * ``col_weights`` - optional ``{group: n_cells}`` true per-group magnitude,
      used to scale bar height in non-normalized ("counts") mode even when
      the displayed matrix itself holds proportions
    """
    if groupby is not None:
        return _composition_from_cells(data, groupby, category, group_attrs, color_adata)

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
        if hasattr(data, "mod"):  # MuData, or any object exposing modalities
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
            raise TypeError("data must be a MuData, AnnData, or DataFrame")

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

        # True per-group cell count, independent of `output`: population
        # matrices (e.g. `calc_nbhd_by_pop`) store it in obs["n_cells"], so
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
        # Prefer the MuData's group-level obs (richer metadata) over the
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


class Yearbook(Screenshots, _RasterCapture, _StateSnapshots, CelldegaWidget):
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
        selected_cells (list[str], optional): IDs checked in the portrait grid.
            Independent of the portrait candidates in ``cells`` and the input
            ``selection``. Checked IDs persist across page and query changes.
            Assign a new list to update the checked portraits from Python.
        selection (Selection or dict or list, optional): Ordered selection of
            cells to display as portraits. Accepts a selection object exposing
            ``to_json()``/``to_dict()`` (e.g. a ``celldega.select``
            selection), a JSON-ready selection dict with ``ids``, or a plain
            list of cell ids. Yearbook uses its ids as the
            portrait cell order and stores the JSON-ready payload for provenance.
            Pass either ``selection`` or ``cells``, not both.
        front_end_query (dict, optional): Stateless query evaluated in the browser
            against DegaFiles (no Python/AnnData required). Supports the
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

        # Using an ordered selection of cell ids from an AnnData
        selection = adata.obs_names[adata.obs["leiden"] == "5"][:4].tolist()
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

    # Checked portrait IDs, kept independently of the current candidates/page.
    selected_cells = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)

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

    # Stateless front-end query, evaluated in the browser against DegaFiles
    # (no Python/AnnData required). Supports:
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
        # browser query from Python-side cell selections.
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

        self._listen_for_raster()
        self._listen_for_state()
        self._listen_for_pics()

    def get_selected_cells(self, adata=None):
        """Return checked IDs, or a copied AnnData subset in its original row order."""
        ids = list(self.selected_cells)
        if adata is None:
            return ids
        return adata[adata.obs_names.isin(ids)].copy()

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


class Clustergram(Screenshots, _RasterCapture, _StateSnapshots, CelldegaWidget):
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

        Use :meth:`request_matrix_slice` to dispatch a non-blocking request, or
        ``await`` :meth:`request_matrix_slice_async` when you need the response in
        Python (both require a **live kernel**).

        **jslink:** Only traits sync between models. For linked custom widgets, mirror
        ``matrix_slice_result``; Python does not run in standalone exported HTML.

    Python access to the same matrix
        If constructed with ``matrix=``, use :meth:`matrix_dataframe` for the underlying
        ``pandas.DataFrame``.
    """

    _esm = _WIDGET_ESM
    _registry_namespace = "matrix"

    # --- core traits used by JS -------------------------------------------------
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Matrix").tag(sync=True)

    network = traitlets.Dict({}).tag(sync=True)
    network_meta = traitlets.Dict({}).tag(sync=True)

    width = traitlets.Int(500).tag(sync=True)
    height = traitlets.Int(500).tag(sync=True)

    # Multipliers for the row/column label text. Column labels default a
    # little smaller so longer category names remain readable when zoomed in.
    row_label_scale = traitlets.Float(1.0).tag(sync=True)
    col_label_scale = traitlets.Float(0.8).tag(sync=True)

    click_info = traitlets.Dict({}).tag(sync=True)

    #: Set by Python (or another front-end) to request ``{req_id, op, ...}``:
    #: ``row``/``col`` use ``index``; ``cell`` uses ``row``/``col``; ``row_col``
    #: uses ``row_index``/``col_index`` and optional ``max_entries``. The Matrix
    #: front-end writes the slice into :attr:`matrix_slice_result`.
    matrix_slice_request = traitlets.Dict(default_value={}).tag(sync=True)

    #: Populated by the Matrix front-end in response to :attr:`matrix_slice_request`.
    matrix_slice_result = traitlets.Dict(default_value={}).tag(sync=True)

    def request_state(
        self,
        rows: str | Sequence[str] = "viewport",
        cols: str | Sequence[str] = "viewport",
        *,
        max_rows: int = 50,
        max_cols: int = 50,
        extra_rows: Sequence[str] = (),
        extra_cols: Sequence[str] = (),
        include_values: bool = True,
        markers: dict | None = None,
    ) -> int:
        """Ask the browser for bounded scientific observations of this Clustergram.

        The snapshot reports, by name and in display order: the chosen rows and
        columns, each axis's order, the marker level (DIM slider), the dendrogram
        groups at the current cut, row/column attributes for the chosen items, the
        selection (clicked label, selected genes, dendrogram group, Enrich term
        genes, crop), and the values (and dot sizes) for the chosen rows x columns.
        Everything is bounded: an explicit (custom or attribute) order is labeled
        rather than listed, and a crop of more than 100 names is counted. Complete
        replay settings come with a saved view (:meth:`request_snapshot`).

        Capture is asynchronous: the reply sets :attr:`latest_state`, or
        :attr:`state_error` on failure. ``observe`` :attr:`latest_state` or read it
        in a later cell; a cell that requests a snapshot can't wait for it.

        Args:
            rows: ``"viewport"`` (rows on screen), ``"ranked"`` (the top of the
                current order, after any crop or marker-level filter), or a list of
                row names.
            cols: Same for columns.
            max_rows: Cap on reported rows.
            max_cols: Cap on reported columns.
            extra_rows: Row names to add after the main selection (e.g. genes asked
                about that aren't on screen); listed in ``rows["added"]``.
            extra_cols: Same for columns.
            include_values: Include the value and dot-size block.
            markers: Also report ranked markers (``rank_genes_groups``) per cluster,
                read from the front end without changing the view:
                ``{"clusters": ["4", "5"], "n": 25}`` (``clusters`` defaults to all).
                Lands in ``latest_state["cluster_markers"]``.

        Returns:
            int: The id of this request.
        """

        def _axis(spec):
            if isinstance(spec, str):
                if spec not in ("viewport", "ranked"):
                    raise ValueError("rows/cols must be 'viewport', 'ranked', or a list of names")
                return spec
            return [str(name) for name in spec]

        def _markers(spec):
            if not spec:
                return None
            if not isinstance(spec, dict):
                raise ValueError("markers must be a dict like {'clusters': ['<cluster>'], 'n': 25}")
            clusters = spec.get("clusters")
            return {
                "clusters": None if clusters is None else [str(c) for c in clusters],
                "n": int(spec.get("n", 10)),
            }

        return self._send_state_request(
            {
                "rows": _axis(rows),
                "cols": _axis(cols),
                "max_rows": int(max_rows),
                "max_cols": int(max_cols),
                "extra_rows": [str(name) for name in extra_rows],
                "extra_cols": [str(name) for name in extra_cols],
                "include_values": bool(include_values),
                "markers": _markers(markers),
            }
        )

    #: Keys :meth:`apply_state` understands (the setter half of the Clustergram's API).
    APPLY_STATE_KEYS = (
        "marker_level",
        "mode",
        "size",
        "focus_gene",
        "categories",
        "annotations",
        "dendrogram",
        "selection",
        "view",
        "order",
        "crop",
    )

    def apply_state(self, changes: dict) -> list[str]:
        """Change what the Clustergram shows, as its controls would.

        Input structure is validated here, so mistakes raise in the calling cell.
        Availability (names, orders, controls) is checked in the browser, which then
        applies the changes; check :meth:`get_apply_result` with
        :attr:`apply_request_id` in a later cell, or observe ``apply_capture_id`` and
        ``apply_error``. Runtime failures may leave partial changes.

        Args:
            changes: Any of:

                - ``marker_level``: marker genes per cluster (the DIM slider), snapped
                  to the nearest precomputed level, or ``"all"`` for every row.
                - ``mode``: ``"heatmap"`` or ``"dotplot"``.
                - ``size``: ``"prop"`` (dot size by e.g. fraction expressing) or
                  ``"unit"`` (full-size marks), like the PROP / UNIT buttons.
                - ``focus_gene``: a row name to zoom to and bold, like the search
                  box; ``""`` clears it.
                - ``categories``: manual categories, as for :meth:`set_categories`:
                  ``{"values": {"<name>": "<category>"}, "axis": "col", "attribute":
                  "cell_type", "colors": {...}, "replace": False}``. Only the names
                  given change.
                - ``annotations``: ``{"row": spec, "col": spec}`` replacing each
                  given axis's manual annotations, where spec is ``{"attribute",
                  "values", "colors"}`` or ``None`` (clears the axis). Not with
                  ``categories``.
                - ``dendrogram``: ``{"row": 35, "col": 65}`` cut percentages (0-100).
                - ``selection``: any of ``rows``, ``cols``, ``genes``,
                  ``highlighted_genes`` (lists of names) and ``dendrogram``
                  (``{"axis", "members"}``, a group that exists at the current cut,
                  or ``{"axis", "name"}`` with the name ``get_state`` lists it under).
                - ``view``: ``{"target": [x, y], "zoom": [x_zoom, y_zoom]}``.
                - ``crop``: ``{"row": [...names], "col": None}``; None clears an axis.
                - ``order``: per axis, a named order (``"clust"``, ``"rank"``,
                  ``"rankvar"``, ``"ini"``, ``"alpha"``) or every name in display order.

        Returns:
            list[str]: What was submitted, e.g. ``"DIM -> 10 markers per cluster"``;
            not confirmation that the browser applied it.

        Raises:
            ValueError: For an unknown key or an invalid value (nothing changes).
        """
        if not isinstance(changes, dict):
            raise ValueError("changes must be a dict")
        unknown = sorted(set(changes) - set(self.APPLY_STATE_KEYS))
        if unknown:
            raise ValueError(
                f"Unknown Clustergram setting(s): {unknown}; supported: {list(self.APPLY_STATE_KEYS)}"
            )

        navigation = _validate_clustergram_controls(self, changes)
        updates: list[tuple[str, Any, str]] = []
        if "marker_level" in changes:
            level = changes["marker_level"]
            if level is None or str(level).lower() == "all":
                updates.append(("rank_dim", 0, "DIM -> all rows"))
            else:
                try:
                    n = int(level)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"marker_level must be a number or 'all', not {level!r}"
                    ) from None
                if n <= 0:
                    raise ValueError("marker_level must be positive (or 'all')")
                updates.append(("rank_dim", n, f"DIM -> {n} markers per cluster"))
        if "mode" in changes:
            mode = changes["mode"]
            if mode not in ("heatmap", "dotplot"):
                raise ValueError("mode must be 'heatmap' or 'dotplot'")
            updates.append(("viz_mode", mode, f"mode -> {mode}"))
        if "size" in changes:
            size = str(changes["size"]).lower()
            if size not in ("prop", "unit"):
                raise ValueError("size must be 'prop' or 'unit'")
            updates.append(("dot_size_encoded", size == "prop", f"dot size -> {size.upper()}"))
        if "focus_gene" in changes:
            gene = str(changes["focus_gene"] or "")
            if gene and self.row_names and gene not in self.row_names:
                raise ValueError(f"{gene!r} is not a row of this Clustergram")
            updates.append(("focused_gene", gene, f"zoomed to {gene}" if gene else "cleared focus"))

        categories = changes.get("categories")
        if categories is not None:
            if not isinstance(categories, dict) or not isinstance(categories.get("values"), dict):
                raise ValueError(
                    "categories must be like {'values': {'<name>': '<category>'}, 'axis': 'col'}"
                )
            category_kwargs = {
                key: categories[key]
                for key in ("axis", "attribute", "colors", "replace")
                if key in categories
            }
            category_axis, category_attribute = self._category_target(
                category_kwargs.get("axis", "col"), category_kwargs.get("attribute")
            )
            self._check_category_names(category_axis, categories["values"])

        described = [description for *_, description in updates]
        browser = deepcopy(changes)
        if categories is not None:
            browser["categories"] = {**categories, "attribute": category_attribute}
            described.append(f"submitted {category_axis} categories ({category_attribute})")
        described.extend(f"updated {key}" for key in navigation)
        self._send_apply_request(browser)
        return described

    # Manual-category setter replies (see set_categories), Python-side only.
    categories_error = traitlets.Unicode("")

    def _category_target(self, axis: str, attribute: str | None) -> tuple[str, str]:
        """The axis and manual attribute a category assignment goes to."""
        if axis not in ("row", "col"):
            raise ValueError("axis must be 'row' or 'col'")
        if attribute:
            return axis, str(attribute)
        try:
            config = json.loads(self.manual_cat_config or "{}")
        except json.JSONDecodeError:
            config = {}
        configured = (config.get(axis) or {}).get("attribute")
        if configured and configured not in ("True", "False"):
            return axis, str(configured)
        flag = self.manual_col_cat if axis == "col" else self.manual_row_cat
        if flag and flag not in ("True", "False"):
            return axis, str(flag)
        raise ValueError(
            f"no manual {axis} category is set up; pass attribute=... (e.g. 'cell_type')"
        )

    def _check_category_names(self, axis: str, values: dict) -> None:
        known = self.col_names if axis == "col" else self.row_names
        unknown = [str(name) for name in values if known and str(name) not in known]
        if unknown:
            raise ValueError(f"not {axis} names of this Clustergram: {unknown[:10]}")

    def set_categories(
        self,
        values: dict,
        *,
        axis: str = "col",
        attribute: str | None = None,
        colors: dict | None = None,
        replace: bool = False,
    ) -> int:
        """Assign manual categories, as the category editor would.

        For example ``cgm.set_categories({"4": "Goblet cells", "5": "Plasma cells"})``
        labels clusters 4 and 5 in the Clustergram's manual column category. The
        browser updates the category strips, bars and labels, and syncs the result back
        to :attr:`manual_cat` (and so to ``col_manual_df`` / ``row_manual_df``).

        Args:
            values: ``{row or column name: category}``; an empty category removes the
                assignment.
            axis: ``"col"`` (default) or ``"row"``.
            attribute: The manual attribute, e.g. ``"cell_type"``. Defaults to the one
                set up with ``manual_col_cat`` / ``manual_row_cat``; passing one turns
                manual categories on for that axis.
            colors: Optional ``{category: hex}``. New categories otherwise get the
                editor's next distinct color.
            replace: Clear the axis's other assignments first.

        Returns:
            int: The id of this request.
        """
        axis, attribute = self._category_target(axis, attribute)
        self._check_category_names(axis, values)
        self._category_request_id = getattr(self, "_category_request_id", 0) + 1
        self.send(
            {
                "event": "set_categories",
                "id": self._category_request_id,
                "axis": axis,
                "attribute": attribute,
                "values": {str(k): (None if v is None else str(v)) for k, v in values.items()},
                "colors": {str(k): str(v) for k, v in (colors or {}).items()},
                "replace": bool(replace),
            }
        )
        return self._category_request_id

    def _on_categories_msg(self, _widget, content, _buffers) -> None:
        if not isinstance(content, dict):
            return
        if content.get("event") == "categories_error":
            self.categories_error = str(content.get("error") or "set_categories failed")
        elif content.get("event") == "categories_set":
            self.categories_error = ""

    # Dendrogram-cut state driven by the front-end slider, keyed by axis, e.g.
    # {"row": {"n_clusters": 5}} or {"col": {"threshold": 0.42}}. Read by
    # `to_cluster` to turn the interactive slider position into flat labels.
    dendro_cut = traitlets.Dict({}).tag(sync=True)

    # Generic row/col selection traitlets
    selected_rows = traitlets.List(default_value=[]).tag(sync=True)
    selected_cols = traitlets.List(default_value=[]).tag(sync=True)

    # Legacy traitlet for gene selection (copied from selected_rows when row entity is 'gene')
    selected_genes = traitlets.List(default_value=[]).tag(sync=True)
    # Gene set intended for enrichment. Unlike selected_genes, a single row
    # label click does not overwrite this value. Keeping the two concerns
    # separate makes browser-only widget links match live Python behavior.
    enrichment_genes = traitlets.List(default_value=[]).tag(sync=True)
    enrichment_source_label = traitlets.Unicode("").tag(sync=True)
    row_enrich_enabled = traitlets.Bool(True).tag(sync=True)
    col_enrich_enabled = traitlets.Bool(False).tag(sync=True)
    # A gene selected in Enrich. The Clustergram front-end centers its matching
    # row without replacing the current enrichment gene set.
    focused_gene = traitlets.Unicode("").tag(sync=True)
    # Genes to visually highlight (blue row labels), e.g. the members of an
    # enriched term selected in a linked Enrich widget. Matched
    # case-insensitively against row names. Deliberately separate from
    # ``selected_genes``, which *feeds* enrichment input — reusing it would
    # loop the linkage.
    highlighted_genes = traitlets.List(default_value=[]).tag(sync=True)
    #: Columns drawn with blue labels: e.g. the clusters highlighted in a linked
    #: Landscape (see `spatial_clustergram`), or columns shift-clicked here.
    highlighted_cols = traitlets.List(default_value=[]).tag(sync=True)
    #: Snapshot cards open their view through these, in the browser (see Landscape).
    view_request = traitlets.Dict({}).tag(sync=True)
    view_result = traitlets.Dict({}).tag(sync=True)
    _JS_VIEW_LINK = True
    #: Upper bound on the gene set a column click sends to enrichment.
    top_n_genes = traitlets.Int(50).tag(sync=True)

    #: Share of the *visible* rows a column click sends to enrichment, as a
    #: percentage, capped by :attr:`top_n_genes`. Percentage rather than a flat
    #: count because under a reduced :attr:`rank_dim` view a fixed "top 50"
    #: can be the entire view, which enriches a gene set against itself. A
    #: floor of 5 genes applies so very narrow views still say something.
    top_gene_percent = traitlets.Float(10.0).tag(sync=True)

    #: Column-click marker candidates must be strictly above this matrix value.
    #: ``0`` is a natural default after row z-scoring: only genes enriched in
    #: the clicked column are sent to Enrich. Set to ``None`` to disable.
    top_gene_min_value = traitlets.Float(0.0, allow_none=True).tag(sync=True)

    #: Active precomputed level: markers per group, or total rows for metric views.
    #: ``0`` (default) means the full matrix. Set to one of the levels
    #: precomputed by ``Matrix.cluster(view=...)`` to open already reduced; the
    #: front end snaps to the nearest available level and writes the applied
    #: value back. Has no effect when the matrix carries no views.
    rank_dim = traitlets.Int(0).tag(sync=True)

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
    # holds proportions (e.g. `Composition(adata, groupby=...)`, which
    # normalizes each group to sum to 1).
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
        explicit_name = kwargs.pop("name", None)
        explicit_registry_key = kwargs.pop("registry_key", None)

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

        if explicit_registry_key is not None:
            name = explicit_registry_key
        elif explicit_name is not None:
            name = explicit_name
        kwargs["manual_row_cat"] = manual_row_flag
        kwargs["manual_col_cat"] = manual_col_flag

        # If a dot-size matrix came through and the caller didn't pick a mode,
        # default to the dot-plot encoding so the extra channel is shown.
        if pq_data is not None and pq_data.get("dot_mat") and "viz_mode" not in kwargs:
            kwargs["viz_mode"] = "dotplot"

        super().__init__(name=name, **kwargs)

        self._listen_for_state()
        self._listen_for_raster()
        self._listen_for_pics()
        self.on_msg(self._on_categories_msg)

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

        Thin wrapper over :meth:`celldega.clust.Matrix.cut_tree`. When neither
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
        return self._matrix.cut_tree(
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
    ) -> str:
        """
        Request a slice from the browser Matrix and return its request ID.

        This method deliberately does not wait for ``matrix_slice_result``: blocking
        the executing kernel thread prevents inbound widget comm messages from being
        processed. Observe ``matrix_slice_result`` using the returned ID, or use
        ``await request_matrix_slice_async(...)`` in an async notebook cell.

        Parameters
        ----------
        op
            ``row`` or ``col``: pass ``index`` (matrix axis index). ``cell``: pass
            ``row`` and ``col`` matrix indices. ``row_col``: pass ``row_index`` and
            ``col_index`` to get both axis slices in one result; optional
            ``max_entries`` (negative means all, subject to a browser-side cap).

        Returns
        -------
        str
            Request ID that will be included in :attr:`matrix_slice_result`.
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

        # Deliberately do not blank matrix_slice_result here: it is a shared
        # mailbox that click-driven front-end slices also write, and clearing
        # it would destroy a concurrent caller's not-yet-read response. The
        # per-request UUID makes stale reads impossible for req_id-checking
        # consumers.
        self.matrix_slice_request = {}
        self.matrix_slice_request = payload
        return req_id

    async def request_matrix_slice_async(
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
    ) -> dict | None:
        """Request a browser matrix slice and asynchronously wait for its result.

        ``await`` this method from an async notebook cell (awaiting yields to the
        kernel event loop so it can process the front-end comm message). Resolution
        is observer-driven: a temporary ``matrix_slice_result`` observer fulfills
        the wait the moment the response with this request's ID arrives, so the
        response cannot be missed even if a click-driven slice overwrites the
        shared ``matrix_slice_result`` mailbox immediately afterwards.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        expected: dict[str, str] = {}

        def _on_result(change: dict) -> None:
            res = dict(change["new"] or {})
            if res.get("req_id") == expected.get("req_id") and not future.done():
                future.set_result(res)

        self.observe(_on_result, names="matrix_slice_result")
        try:
            expected["req_id"] = self.request_matrix_slice(
                op,
                index=index,
                row=row,
                col=col,
                row_index=row_index,
                col_index=col_index,
                max_entries=max_entries,
            )
            # A synchronous in-process responder can fill the result during
            # request_matrix_slice, before `expected` was populated — check once.
            res = dict(self.matrix_slice_result or {})
            if res.get("req_id") == expected["req_id"]:
                return res
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return None
        finally:
            self.unobserve(_on_result, names="matrix_slice_result")

    def matrix_dataframe(self) -> pd.DataFrame | None:
        """Return a copy of the Matrix ``data`` when this widget was created with ``matrix=``."""
        m = getattr(self, "_matrix", None)
        if m is None:
            return None
        data = getattr(m, "data", None)
        return data.copy() if data is not None else None


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

        # Cell-level AnnData: cells are cross-tabulated into samples x cell types
        dega.viz.Composition(
            adata, groupby="sample_id", category="cell_type", group_attrs=["condition"]
        )

    Colors come from ``adata.uns[f"{category}_colors"]``. A precomputed
    population matrix (``AnnData`` with groups as obs and populations as var,
    a ``MuData`` modality, or a ``DataFrame``) works too.
    """

    def __init__(
        self,
        data: Any,
        modality: str = "population",
        *,
        groupby: str | None = None,
        category: str | None = None,
        colors: dict[str, str] | None = None,
        adata: Any = None,
        group_attrs: list[str] | None = None,
        normalized: bool | None = None,
        col_weights: dict[str, float] | None = None,
        cluster: bool = True,
        row_entity: str | dict[str, str] | None = None,
        col_entity: str | dict[str, str] | None = None,
        name: str = "composition",
        width: int = 700,
        height: int = 450,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            data: A cell-level ``AnnData``/``MuData`` with ``groupby``, or a
                precomputed population matrix: a ``MuData`` (or any object
                exposing ``mod``), an ``AnnData`` (obs = groups, var =
                populations), or a ``DataFrame`` (rows = groups, columns =
                populations).
            modality: Modality key on a MuData (default ``"population"``).
            groupby: With cell-level ``data``, the ``obs`` column defining the
                groups (e.g. a sample column); cells are cross-tabulated against
                ``category``.
            category: Population ``obs`` column name (required with
                ``groupby``); also used to resolve colors from
                ``uns[f"{category}_colors"]`` when the matrix has none.
            colors: Optional ``{population: hex}`` overrides.
            adata: Optional source cell-level ``AnnData`` to fall back to for
                its color palette, e.g. for a plain ``DataFrame`` input.
            group_attrs: Group-level ``obs`` columns to show as Clustergram column
                attribute tracks (e.g. ``["condition", "timepoint"]``). With
                ``groupby`` the first value per group is used.
            normalized: Column-normalize each bar to 100%. Defaults to ``True`` for
                proportion matrices and ``False`` for count matrices.
            col_weights: Optional ``{group: n_cells}`` true per-group magnitude,
                used to scale bar height in non-normalized ("counts") mode.
                Defaults to the group sizes (``groupby``) or the matrix's own
                ``n_cells`` obs column when available — pass explicitly to
                override, e.g. for a plain ``DataFrame`` input.
            cluster: Run hierarchical clustering before display (default ``True``).
            row_entity: Population selection identity. Defaults to
                ``{"entity": "cell_population", "attr": "name"}``. To link
                cell types to a Landscape, use ``{"entity": "cell",
                "attr": "cell_type"}`` with the Landscape's cluster attribute.
            col_entity: Group selection identity. Defaults to
                ``{"entity": "dataset", "attr": "name"}``. Use ``"nbhd"``
                to link band names to a Landscape's neighborhood geometries.
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
            groupby=groupby,
        )
        merged_colors = dict(payload["colors"])
        if colors:
            merged_colors.update(colors)

        resolved_col_weights = col_weights if col_weights is not None else payload["col_weights"]

        mat = Matrix(
            payload["df"],
            meta_col=payload["meta_col"],
            col_attr=payload["col_attr"] or None,
            row_entity=row_entity
            if row_entity is not None
            else {"entity": "cell_population", "attr": "name"},
            col_entity=col_entity
            if col_entity is not None
            else {"entity": "dataset", "attr": "name"},
            global_colors=merged_colors or None,
            name=name,
        )
        if cluster:
            mat.cluster()
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
