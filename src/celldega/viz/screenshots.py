"""Screenshots with provenance: an image, a description, and what it takes to redo it.

``landscape.screenshot(description="...")`` (or ``dega.viz.screenshot(linked, ...)``
for several linked widgets, or the PIC button in a widget's control panel) writes two
files next to each other:

- ``<name>.png``: the image, with its record embedded: description, author, time, and
  per widget
  its saved view (``snapshot``: replay settings and data identity, for
  ``restore_snapshot``), the observed state, and the data it came from (dataset name,
  URLs, AnnData shape, Matrix source);
- ``<name>.md``: the description, the image, and code to replay supported settings.

A saved view is the versioned image, replay state, observations and provenance.
A screenshot is its user-facing image export. It becomes an evidence artifact when
used to support or contradict a claim; reports collect artifacts and reasoning
outside the Viz API. ``dega.viz.from_png`` reopens the referenced source data and
restores supported settings; in-memory inputs must be supplied again. See the
Viz API documentation for supported controls and remaining limitations.

Capture is asynchronous: the browser sends the image after the cell has finished, so
``screenshot()`` returns a :class:`Screenshot` whose output updates when the files are
written.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable
from copy import deepcopy
import io
import json
from pathlib import Path
import pprint
import re
import threading
import time
from typing import Any
import zlib

from .snapshots import restore_spec


# 3: a widget's replay settings are kept once, in its saved view (``snapshot.state``).
SCHEMA_VERSION = 3
# Manual exports have an application-neutral default.
DEFAULT_DIR = "celldega_files/screenshots"
# PNG text chunk holding the record.
PNG_KEY = "celldega"
# Bound decoded metadata without imposing Pillow's 1 MiB compressed-text limit.
MAX_PNG_METADATA_BYTES = 64 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Seconds to wait for the browser before saving what arrived.
CAPTURE_TIMEOUT = 8.0
# Gap between widgets in a composite image, in pixels.
GAP = 16


# ---- provenance ------------------------------------------------------------------
def _adata_summary(adata) -> dict:
    out: dict[str, Any] = {"n_obs": int(adata.n_obs), "n_vars": int(adata.n_vars)}
    filename = getattr(adata, "filename", None)
    if filename:
        out["filename"] = str(filename)
    return out


def widget_source(widget) -> dict:
    """What a widget shows data from, as far as Python knows it."""
    kind = type(widget).__name__
    out: dict[str, Any] = {"widget": kind}
    name = getattr(widget, "_registry_key", None)
    if name and name != "default":
        out["name"] = name
    for key in ("technology", "dataset_name", "base_url", "zarr_url", "cluster_attr"):
        value = getattr(widget, key, None)
        if value:
            out[key] = value
    base_urls = getattr(widget, "base_urls", None)
    if base_urls:
        out["base_urls"] = list(base_urls)
    cell_attr = getattr(widget, "cell_attr", None)
    if cell_attr:
        out["cell_attr"] = list(cell_attr)
    adata = getattr(widget, "_adata", None)
    if adata is not None:
        out["adata"] = _adata_summary(adata)
    matrix = getattr(widget, "_matrix", None)
    if matrix is not None:
        info: dict[str, Any] = {}
        for key, attr in (("name", "name"), ("source", "_source")):
            value = getattr(matrix, attr, None)
            if value:
                info[key] = str(value)
        data = getattr(matrix, "data", None)
        if data is not None and hasattr(data, "shape"):
            info["shape"] = [int(n) for n in data.shape]
        if info:
            out["matrix"] = info
    extra = getattr(widget, "screenshot_metadata", None)
    if extra:
        out.update(extra)
    # Constructor inputs are explicit and JSON-compatible. In particular, do not
    # serialize credentials, callbacks, AnnData, parquet bytes or matrix values.
    keys = (
        "width",
        "height",
        "data_revision",
        "row_label_scale",
        "col_label_scale",
        "viz_mode",
        "rank_dim",
        "technology",
        "dataset_name",
        "base_url",
        "zarr_url",
        "zarr_layer",
        "cluster_attr",
        "cell_attr",
        "cell_name_prefix",
        "segmentation",
        "alignment",
        "manifest_name",
        "centroids_url",
        "use_adata_3d_centroids",
        "cell_size",
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
    )
    options = {
        key: deepcopy(value)
        for key in keys
        if (value := getattr(widget, key, None)) is not None and value != ""
    }
    if base_urls:
        options["base_urls"] = [
            {k: deepcopy(v) for k, v in item.items() if k in {"url", "label", "short_label"}}
            for item in base_urls
            if isinstance(item, dict)
        ]
    if matrix is not None:
        source = getattr(matrix, "_source", None)
        if source:
            options["url"] = str(source)
    is_matrix = hasattr(widget, "set_categories")
    inline_spatial = any(
        bool(getattr(widget, key, None))
        for key in (
            "meta_cell_parquet",
            "meta_cluster_parquet",
            "umap_parquet",
            "centroids_parquet",
        )
    )
    out["options"] = options
    out["requires_data"] = (
        not bool(options.get("url")) if is_matrix else adata is not None or inline_spatial
    )
    return out


def replay_settings(widget: dict) -> dict:
    """A record widget's replay settings: its saved view's, else (older records) ``state``."""
    snapshot = widget.get("snapshot") or {}
    settings = snapshot.get("state")
    return settings if isinstance(settings, dict) else widget.get("state") or {}


def _brief(value: Any, items: int = 8) -> Any:
    """``value`` with long lists and mappings shortened, for summaries and prompts."""
    if isinstance(value, dict):
        entries = list(value.items())
        out = {k: _brief(v, items) for k, v in entries[: items * 3]}
        if len(entries) > items * 3:
            out["..."] = f"{len(entries) - items * 3} more"
        return out
    if isinstance(value, list | tuple):
        out = [_brief(v, items) for v in value[:items]]
        if len(value) > items:
            out.append(f"... {len(value) - items} more")
        return out
    return value


def _in_view(state: dict | None, top: int = 10) -> dict:
    viewport = (state or {}).get("viewport") or {}
    out = {}
    for key in ("clusters", "genes"):
        items = viewport.get(key) or []
        if items:
            out[key] = items[:top]
    return out


# ---- images ----------------------------------------------------------------------
def _decode(png_b64: str):
    from PIL import Image

    return Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("RGBA")


def compose(images_b64: list[str]):
    """Place images side by side at a common height (the smallest, so none is upscaled)."""
    from PIL import Image

    images = [_decode(b) for b in images_b64 if b]
    if not images:
        raise ValueError("no image to save")
    if len(images) == 1:
        return images[0]
    height = min(img.height for img in images)
    scaled = [
        img
        if img.height == height
        else img.resize((round(img.width * height / img.height), height))
        for img in images
    ]
    width = sum(img.width for img in scaled) + GAP * (len(scaled) - 1)
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    x = 0
    for img in scaled:
        canvas.paste(img, (x, 0))
        x += img.width + GAP
    return canvas


def _checked_record(record: Any) -> dict:
    if (
        not isinstance(record, dict)
        or type(record.get("celldega_screenshot")) is not int
        or record["celldega_screenshot"] not in (1, 2, SCHEMA_VERSION)
        or not isinstance(record.get("widgets"), list)
        or any(not isinstance(widget, dict) for widget in record["widgets"])
    ):
        raise ValueError("Invalid or unsupported Celldega screenshot metadata")
    return record


def _inflate_metadata(data: bytes) -> bytes:
    """Decompress with a hard output bound, including highly compressible lists."""
    decoder = zlib.decompressobj()
    try:
        text = decoder.decompress(data, MAX_PNG_METADATA_BYTES + 1)
    except zlib.error as exc:
        raise ValueError("Invalid compressed Celldega PNG metadata") from exc
    if len(text) > MAX_PNG_METADATA_BYTES or decoder.unconsumed_tail:
        raise ValueError("Celldega PNG metadata exceeds the 64 MiB limit")
    if not decoder.eof or decoder.unused_data:
        raise ValueError("Invalid compressed Celldega PNG metadata")
    return text


def _decode_metadata(chunk_type: bytes, data: bytes) -> dict:
    _keyword, _, payload = data.partition(b"\0")
    encoding = "latin-1"
    if chunk_type == b"iTXt":
        if len(payload) < 4 or payload[0] not in (0, 1) or payload[1] != 0:
            raise ValueError("Invalid Celldega PNG text chunk")
        compressed = payload[0] == 1
        fields = payload[2:].split(b"\0", 2)  # language, translated keyword, text
        if len(fields) != 3:
            raise ValueError("Invalid Celldega PNG text chunk")
        text = _inflate_metadata(fields[2]) if compressed else fields[2]
        encoding = "utf-8"
    elif chunk_type == b"zTXt":
        if not payload or payload[0] != 0:
            raise ValueError("Invalid Celldega PNG text chunk")
        text = _inflate_metadata(payload[1:])
    else:
        text = payload
    if len(text) > MAX_PNG_METADATA_BYTES:
        raise ValueError("Celldega PNG metadata exceeds the 64 MiB limit")
    try:
        return _checked_record(json.loads(text.decode(encoding)))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Celldega PNG metadata JSON") from exc


def read_png_record(path: str | Path) -> dict | None:
    """Read bounded Celldega PNG text metadata, or ``None`` for a plain PNG.

    Parses the text chunks directly so large selections can exceed Pillow's
    default 1 MiB compressed-text limit without changing global image settings.
    Image data is skipped, and metadata checksums and chunk boundaries are checked.
    """
    with Path(path).open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(0)
        if stream.read(8) != _PNG_SIGNATURE:
            raise ValueError("Not a PNG file")
        record = None
        first = True
        while stream.tell() < size:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError("Truncated PNG chunk")
            length, chunk_type = int.from_bytes(header[:4], "big"), header[4:]
            if length > 0x7FFFFFFF or stream.tell() + length + 4 > size:
                raise ValueError("Invalid PNG chunk length")
            if first and (chunk_type != b"IHDR" or length != 13):
                raise ValueError("Missing PNG image header")
            first = False
            if chunk_type in (b"iTXt", b"tEXt", b"zTXt"):
                prefix = stream.read(min(length, 80))
                keyword, separator, _text = prefix.partition(b"\0")
                if separator and keyword == PNG_KEY.encode("ascii"):
                    if record is not None:
                        raise ValueError("Duplicate Celldega PNG metadata")
                    # Encoded text has a small header in addition to its JSON.
                    if length > MAX_PNG_METADATA_BYTES + 1024:
                        raise ValueError("Celldega PNG metadata exceeds the 64 MiB limit")
                    data = prefix + stream.read(length - len(prefix))
                    crc = int.from_bytes(stream.read(4), "big")
                    if zlib.crc32(data, zlib.crc32(chunk_type)) != crc:
                        raise ValueError("Invalid Celldega PNG metadata checksum")
                    record = _decode_metadata(chunk_type, data)
                    continue
                stream.seek(length - len(prefix) + 4, 1)
            else:
                stream.seek(length + 4, 1)
            if chunk_type == b"IEND":
                if length:
                    raise ValueError("Invalid PNG end chunk")
                return record
    raise ValueError("Missing PNG end chunk")


# ---- files -----------------------------------------------------------------------
def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:60] or "screenshot"


def resolve_path(path: str | Path | None, hint: str) -> Path:
    """Where to write: a ``.png`` path as given, else an auto-named file in a folder."""
    if path and str(path).lower().endswith(".png"):
        target = Path(path)
    else:
        folder = Path(path) if path else Path(DEFAULT_DIR)
        target = folder / f"{_slug(hint)}_{time.strftime('%Y%m%d-%H%M%S')}.png"
        n = 2
        while target.exists():
            target = target.with_name(f"{target.stem.rsplit('_v', 1)[0]}_v{n}.png")
            n += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _variable(kind: str) -> str:
    return {"Landscape": "landscape", "Clustergram": "cgm"}.get(kind, _slug(kind).replace("-", "_"))


def _markdown(record: dict, image_name: str) -> str:
    lines = [
        f"# {record.get('title') or Path(image_name).stem}",
        "",
        record.get("description") or "_No description._",
        "",
        f"![{record.get('title') or 'screenshot'}]({image_name})",
        "",
        f"_{record.get('author', 'you')}, {record.get('created', '')}, Celldega "
        f"{record.get('celldega') or 'unknown version'}_",
        "",
    ]
    code = []
    widgets = record.get("widgets") or []
    for index, widget in enumerate(widgets):
        source = widget.get("source") or {}
        variable = _variable(source.get("widget", "view"))
        if widget.get("snapshot"):
            variable = "view" if len(widgets) == 1 else f"view_{index + 1}"
            panel = f", panel={index}" if len(widgets) > 1 else ""
            code.append(f"{variable} = dega.viz.from_png({image_name!r}{panel})")
            code.append(f"display({variable})")
        elif widget.get("state"):
            settings = pprint.pformat(widget["state"], width=80, sort_dicts=False)
            code.append(f"{variable}.apply_state({settings})")
        elif widget.get("view_state"):
            code.append(f"# {widget['source']['widget']} camera: {widget['view_state']}")
    if code:
        lines += [
            "## Replay supported settings",
            "",
            "Reopen the PNG as an interactive visualization using its saved data references:",
            "",
            "```python",
            *code,
            "```",
            "",
            "The original datasets must remain available. For inputs kept only in memory, "
            "pass the original data again, for example `matrix=matrix` or `adata=adata`. "
            "Use a source URL override when the data has moved. Older exports containing "
            "only replay settings require an existing widget with the same data loaded.",
            "",
            "Restoring first checks that the widget shows the same data (cell, gene and "
            "cluster names, or a Clustergram's row and column names) and canvas size, and "
            "changes nothing if not. It is a partial restore: gates, edited neighborhood "
            "geometry, custom non-manual palettes and cross-widget links are not restored. "
            "The image records what was shown.",
            "",
        ]
    lines += ["## Data", ""]
    for widget in record.get("widgets") or []:
        source = widget.get("source") or {}
        details = ", ".join(f"{k}: {v}" for k, v in source.items() if k != "widget")
        lines.append(f"- **{source.get('widget', 'widget')}**: {details or 'no details'}")
    if record.get("metadata"):
        lines += ["", "## Notes", "", *(f"- {k}: {v}" for k, v in record["metadata"].items())]
    return "\n".join(lines) + "\n"


def write_screenshot(
    path: str | Path | None,
    shots: list[dict],
    *,
    description: str = "",
    title: str = "",
    author: str = "you",
    metadata: dict | None = None,
) -> Path:
    """Write a screenshot's self-contained PNG record and readable ``.md`` companion.

    Args:
        path: A ``.png`` file, a folder for an auto-named file, or ``None`` for
            :data:`DEFAULT_DIR`.
        shots: One per widget: ``{"image": base64 PNG, "source": widget_source(...),
            "snapshot": saved view (restore_spec), "observed_state": ...,
            "view_state": camera, "in_view": {...}}``. ``"state"`` (apply_state
            settings) is kept only when there is no saved view.

    Returns:
        Path: The PNG written.
    """
    from importlib.metadata import PackageNotFoundError, version

    from PIL.PngImagePlugin import PngInfo

    images = [s.get("image") for s in shots if s.get("image")]
    image = compose(images)
    hint = title or next(
        (s["source"].get("dataset_name") for s in shots if s.get("source", {}).get("dataset_name")),
        "-".join(s["source"]["widget"] for s in shots),
    )
    target = resolve_path(path, hint)
    try:
        celldega_version = version("celldega")
    except PackageNotFoundError:
        celldega_version = ""
    record = {
        "celldega_screenshot": SCHEMA_VERSION,
        "title": title,
        "description": description,
        "author": author,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "celldega": celldega_version,
        "restoration": "partial",
        "image": target.name,
        "size": [image.width, image.height],
        "widgets": [
            {k: v for k, v in s.items() if k != "image" and v not in (None, {}, [])} for s in shots
        ],
        "metadata": dict(metadata or {}),
    }
    for widget in record["widgets"]:
        if widget.get("snapshot"):
            widget["snapshot"] = {
                **widget["snapshot"],
                "description": description,
                "author": author,
            }
            # The replay settings live in the saved view; keep one copy.
            if isinstance(widget["snapshot"].get("state"), dict):
                widget.pop("state", None)
    text = json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text.encode("utf-8")) > MAX_PNG_METADATA_BYTES:
        raise ValueError("Celldega PNG metadata exceeds the 64 MiB limit")
    info = PngInfo()
    info.add_itxt(PNG_KEY, text, zip=True)
    image.save(target, pnginfo=info)
    target.with_suffix(".md").write_text(_markdown(record, target.name))
    return target


def load_screenshot(path: str | Path) -> dict:
    """Read a screenshot's embedded PNG record; explicit legacy JSON paths also work.

    A neighboring JSON file never overrides PNG metadata. For a legacy JSON-only
    record, pass its ``.json`` path explicitly.
    """
    path = Path(path)
    if path.suffix.lower() == ".json":
        if path.stat().st_size > MAX_PNG_METADATA_BYTES:
            raise ValueError("Celldega screenshot metadata exceeds the 64 MiB limit")
        return _checked_record(json.loads(path.read_text(encoding="utf-8")))
    png = path if path.suffix.lower() == ".png" else path.with_suffix(".png")
    record = read_png_record(png)
    if record is None:
        raise ValueError(f"{path} is not a Celldega screenshot")
    return record


def load_screenshots(folder: str | Path) -> list[dict]:
    """PNG records and legacy JSON-only records in a folder, oldest first.

    Ignore unrelated or malformed files. A PNG is authoritative even when a stale
    JSON sidecar exists; the companion must not substitute for a damaged PNG.
    """
    records = []
    if not Path(folder).is_dir():
        return records
    files = sorted(Path(folder).iterdir())
    pngs = [path for path in files if path.is_file() and path.suffix.lower() == ".png"]
    png_stems = {path.stem for path in pngs}
    legacy = [
        path
        for path in files
        if path.is_file() and path.suffix.lower() == ".json" and path.stem not in png_stems
    ]
    for path in [*pngs, *legacy]:
        try:
            record = load_screenshot(path)
        except (OSError, ValueError, UnicodeError):
            continue
        record["_path"] = str(path if path.suffix.lower() == ".png" else path.with_suffix(".png"))
        records.append(record)
    return sorted(records, key=lambda r: r.get("created", ""))


def summarize(records: Iterable[dict]) -> str:
    """Markdown summary of saved screenshot records for reports or briefings.

    Long settings (an explicit order, a cell selection) are shortened, so a briefing
    stays small; the records themselves keep everything.
    """
    lines = ["### Screenshots shared by the scientist", ""]
    for record in records:
        name = Path(record.get("_path") or record.get("image") or "screenshot").name
        lines.append(
            f"**{record.get('title') or name}** ({record.get('author', 'you')}, "
            f"{record.get('created', '')}): {record.get('description') or 'no description'}"
        )
        for widget in record.get("widgets") or []:
            source = widget.get("source") or {}
            parts = []
            settings = replay_settings(widget)
            if settings:
                parts.append(f"view {json.dumps(_brief(settings))}")
            for key, items in (widget.get("in_view") or {}).items():
                names = ", ".join(str(i.get("name")) for i in items[:8])
                parts.append(f"{key} in view: {names}")
            label = source.get("dataset_name") or source.get("widget", "widget")
            lines.append(f"- {source.get('widget', 'widget')} ({label}): " + "; ".join(parts))
        lines.append("")
    return "\n".join(lines).strip()


# ---- capture from live widgets ----------------------------------------------------
def find_widgets(items) -> list:
    """Celldega widgets that can take screenshots, from widgets or containers (HBox)."""
    found: list = []
    for item in items:
        if hasattr(item, "request_raster"):
            if item not in found:
                found.append(item)
        elif hasattr(item, "children"):
            found += [w for w in find_widgets(item.children) if w not in found]
    return found


class Screenshot:
    """A screenshot being captured or saved; displays its status and preview.

    Attributes:
        path: The PNG (written once ``done``).
        done: Whether the files are written (or capture failed: see ``error``).
        error: Why nothing was saved, if so.
    """

    def __init__(self, description: str = "") -> None:
        self.description = description
        self.path: Path | None = None
        self.done = False
        self.error = ""
        self._finished = threading.Event()
        self._status = None

    def wait(self, timeout: float | None = None) -> bool:
        """Block until saved (only from another thread: in a notebook cell the browser
        can't reply until the cell finishes)."""
        return self._finished.wait(timeout)

    @property
    def record(self) -> dict | None:
        return load_screenshot(self.path) if self.path and self.done and not self.error else None

    def _set(self, path: Path | None = None, error: str = "") -> None:
        self.path, self.error, self.done = path, error, True
        self._finished.set()
        self._render()

    def _html(self) -> str:
        if not self.done:
            return "<span style='color:#8a929b'>Capturing the screenshot…</span>"
        if self.error:
            return f"<span style='color:#c0392b'>Screenshot not saved: {self.error}</span>"
        thumb = ""
        try:
            data = base64.b64encode(self.path.read_bytes()).decode()
            thumb = (
                f"<img src='data:image/png;base64,{data}' "
                "style='max-width:240px;max-height:160px;border:1px solid #d3d3d3;display:block'>"
            )
        except OSError:
            pass
        return f"{thumb}<span style='color:#47515b;font-size:12px'>Saved {self.path} (+ .md)</span>"

    def _render(self) -> None:
        if self._status is not None:
            self._status.value = self._html()

    def _ipython_display_(self) -> None:
        from IPython.display import display
        import ipywidgets as widgets

        if self._status is None:
            self._status = widgets.HTML(self._html())
        display(self._status)

    def __repr__(self) -> str:
        state = "saving" if not self.done else (f"failed: {self.error}" if self.error else "saved")
        return f"Screenshot({str(self.path) if self.path else '…'}, {state})"


class _Capture:
    """Collect each widget's image and state from the browser, then write the files.

    Replies arrive on the kernel's main thread after the calling cell finishes; a
    timer saves whatever arrived if a widget never answers (e.g. not displayed).
    """

    def __init__(self, widgets, result: Screenshot, path, title, author, metadata, max_size):
        self.widgets = widgets
        self.result = result
        self.args = (path, title, author, metadata)
        self.lock = threading.Lock()
        self.pending: list[tuple[Any, str, int]] = []
        self.handlers: list[tuple[Any, str, Any]] = []
        self.finished = False
        # Replies can arrive while requests are still being sent (a fast browser);
        # only decide we're done once every request is out.
        self.ready = False
        self.timer = threading.Timer(CAPTURE_TIMEOUT, self.finish)
        self.timer.daemon = True
        for widget in widgets:
            kwargs = {}
            if type(widget).__name__ == "Clustergram" or hasattr(widget, "set_categories"):
                kwargs = {"max_rows": 1, "max_cols": 1, "include_values": False}
            self._request(
                widget,
                "snapshot_capture_id",
                lambda w=widget, k=kwargs: w.request_snapshot(
                    max_size=max_size, description=result.description, author=author, **k
                ),
            )
        self.ready = True
        self.timer.start()
        self._check()

    def _request(self, widget, trait: str, send) -> None:
        def on_reply(_change, self=self):
            self._check()

        widget.observe(on_reply, names=trait)
        self.handlers.append((widget, trait, on_reply))
        self.pending.append((widget, trait, send()))

    def _check(self) -> None:
        if self.ready and all(rid in w._snapshot_replies for w, _trait, rid in self.pending):
            self.finish()

    def finish(self) -> None:
        with self.lock:
            if self.finished:
                return
            self.finished = True
        self.timer.cancel()
        for widget, trait, handler in self.handlers:
            widget.unobserve(handler, names=trait)
        shots = []
        for widget, _trait, rid in self.pending:
            reply = widget._snapshot_replies.get(rid, {})
            snapshot = reply.get("snapshot") or {}
            image = snapshot.get("image") or {}
            state = snapshot.get("observed_state")
            shots.append(
                {
                    "image": image.get("png", ""),
                    "source": widget_source(widget),
                    "observed_state": deepcopy(state),
                    "snapshot": restore_spec(snapshot),
                    "capture_error": reply.get("error")
                    or ("snapshot timed out" if not snapshot else ""),
                    "view_state": image.get("view_state") or {},
                    "in_view": _in_view(state),
                }
            )
        if not any(s["image"] for s in shots):
            # A browser error says why; silence usually means nothing is displayed.
            errors = [s["capture_error"] for s in shots if s["capture_error"]]
            reasons = [e for e in errors if e != "snapshot timed out"]
            self.result._set(
                error="; ".join(reasons)
                if reasons
                else "no widget sent an image (are they displayed?)"
            )
            return
        path, title, author, metadata = self.args
        try:
            target = write_screenshot(
                path,
                shots,
                description=self.result.description,
                title=title,
                author=author,
                metadata=metadata,
            )
        except Exception as exc:  # surface in the cell's output, not the log
            self.result._set(error=str(exc))
            return
        self.result._set(path=target)


def screenshot(
    *widgets,
    description: str = "",
    path: str | Path | None = None,
    title: str = "",
    metadata: dict | None = None,
    author: str = "you",
    max_size: int = 2048,
) -> Screenshot:
    """Save a screenshot of one or more widgets with a description and provenance.

    Pass widgets or containers of them (e.g. the ``linked`` row from
    ``dega.viz.spatial_clustergram``): several widgets are placed side by side in one
    image, and each one's state is recorded.

    Args:
        description: What you're looking at and why it's interesting.
        path: A ``.png`` file, or a folder for an auto-named file (default
            ``celldega_files/screenshots``).
        title: Optional short title (also used in the file name).
        metadata: Anything else to record, e.g. ``{"adata": "data/kidney.h5ad"}``.
            Set ``widget.screenshot_metadata`` to record it with every screenshot
            of that widget, including ones taken with its PIC button.
        max_size: Longest side of each widget's image, in pixels.

    Returns:
        Screenshot: Displays its progress and a preview; ``.path`` once saved.
    """
    found = find_widgets(widgets)
    result = Screenshot(description)
    if not found:
        result._set(error="no Celldega widget that can take screenshots was given")
        return result
    _Capture(found, result, path, title, author, metadata, max_size)
    return result


def save_from_browser(widget, content: dict) -> Path:
    """Save a screenshot the widget's PIC button captured in the browser.

    The PIC message carries one saved view (``snapshot``): image, observed state,
    replay settings and identity, recorded the same way as :func:`screenshot`.
    """
    snapshot = content.get("snapshot") or {}
    image = snapshot.get("image") or {}
    observed = snapshot.get("observed_state")
    shot = {
        "image": image.get("png") or "",
        "source": widget_source(widget),
        "observed_state": deepcopy(observed),
        "snapshot": restore_spec(snapshot),
        "view_state": dict(image.get("view_state") or {}),
        "in_view": _in_view(observed),
    }
    return write_screenshot(
        getattr(widget, "screenshot_dir", None) or None,
        [shot],
        description=str(content.get("description") or ""),
        title=str(content.get("title") or ""),
        author="you",
    )


class Screenshots:
    """Mixin for widgets that can take screenshots (needs ``request_raster``).

    Adds :meth:`screenshot` and handles the PIC button in the widget's control panel,
    which captures in the browser and asks Python to save. Subclasses call
    :meth:`_listen_for_pics` from ``__init__``.
    """

    #: Folder for screenshots (PIC button and ``screenshot()`` without a path).
    screenshot_dir: str | Path | None = None
    #: Extra provenance recorded with every screenshot of this widget, e.g.
    #: ``{"adata": "data/kidney.h5ad", "notebook": "kidney_review.ipynb"}``.
    screenshot_metadata: dict | None = None

    def screenshot(
        self,
        description: str = "",
        path: str | Path | None = None,
        *,
        title: str = "",
        metadata: dict | None = None,
        max_size: int = 2048,
    ) -> Screenshot:
        """Save what this widget shows as a PNG with a description and provenance.

        Writes ``<name>.png`` (with the record embedded) and
        ``<name>.md`` (description, image, and ``from_png`` code to reopen
        the view). The browser sends the image after the cell finishes, so the
        returned object's output updates when the files are written.

        Args:
            description: What you're looking at and why it's interesting.
            path: A ``.png`` file, or a folder for an auto-named file (default
                :attr:`screenshot_dir`, else ``celldega_files/screenshots``).
            title: Optional short title (also used in the file name).
            metadata: Anything else to record, e.g. the AnnData's path.
            max_size: Longest side of the image, in pixels.

        Returns:
            Screenshot: Displays its progress and a preview; ``.path`` once saved.
        """
        return screenshot(
            self,
            description=description,
            path=path or self.screenshot_dir,
            title=title,
            metadata=metadata,
            max_size=max_size,
        )

    def _listen_for_pics(self) -> None:
        self.on_msg(self._on_pic_msg)

    def _on_pic_msg(self, _widget, content, _buffers) -> None:
        if not isinstance(content, dict) or content.get("event") != "pic":
            return
        try:
            target = save_from_browser(self, content)
        except Exception as exc:
            self.send({"event": "pic_error", "id": content.get("id"), "error": str(exc)})
            return
        self.send({"event": "pic_saved", "id": content.get("id"), "path": str(target)})
