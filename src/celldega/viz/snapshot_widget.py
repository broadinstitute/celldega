"""Small, self-contained notebook postcards, optionally linked to a live viewer."""

from __future__ import annotations

import base64
from copy import deepcopy
import io
from pathlib import Path
import threading

import anywidget
from PIL import Image
import traitlets

from .screenshots import Screenshot, read_png_record
from .snapshots import restore_spec, validate_snapshot


class Snapshot(anywidget.AnyWidget):
    """Display a static PNG, name and memo, with expandable reproducibility metadata.

    Pass a PNG path (plain PNGs work too), a captured snapshot dictionary, or a
    name in a linked viewer's ``snap`` collection. Linking a viewer adds a blue
    **Show this view** control when the image contains compatible replay metadata.
    The viewer must already be displayed in this kernel. Each card embeds its PNG
    in notebook widget state; it does not load the visualization renderer or data.

    Examples::

        Snapshot(landscape=landscape, snapshot="Glomerulus")
        Snapshot("figures/glomerulus.png", landscape=landscape)
        Snapshot(clustergram=cgm, snapshot="Markers")
        Snapshot("figures/overview.png", name="Overview", description="My memo")

    ``panel`` selects the replay panel in a composite PNG. ``allow_resize=True``
    permits navigation into a differently sized viewer; data identity is always
    checked. Images alone cannot restore a view. Multiple cards coexist, including
    cards with the same name. Linking requires a live kernel; static previews and
    metadata remain available in saved widget state.
    """

    _esm = Path(__file__).with_name("_snapshot.js")
    image = traitlets.Unicode("").tag(sync=True)
    name = traitlets.Unicode("").tag(sync=True)
    description = traitlets.Unicode("").tag(sync=True)
    metadata = traitlets.Dict(default_value={}).tag(sync=True)
    can_restore = traitlets.Bool(False).tag(sync=True)
    target_label = traitlets.Unicode("").tag(sync=True)
    status = traitlets.Unicode("").tag(sync=True)
    busy = traitlets.Bool(False).tag(sync=True)
    # With a Landscape or Clustergram, the card asks the viewer to open its view in
    # the browser (view_request -> the viewer's view_request; its view_result back),
    # so it works in saved notebooks and static pages too.
    js_link = traitlets.Bool(False).tag(sync=True)
    view = traitlets.Dict(default_value={}).tag(sync=True)
    view_request = traitlets.Dict(default_value={}).tag(sync=True)
    view_result = traitlets.Dict(default_value={}).tag(sync=True)

    def __init__(
        self,
        snapshot=None,
        *,
        landscape=None,
        clustergram=None,
        yearbook=None,
        linked=None,
        name=None,
        description=None,
        panel=None,
        allow_resize=True,
        **kwargs,
    ):
        viewers = [w for w in (landscape, clustergram, yearbook, linked) if w is not None]
        if len(viewers) > 1:
            raise ValueError("Link only one viewer to a Snapshot")
        if not isinstance(allow_resize, bool):
            raise ValueError("allow_resize must be a boolean")
        self._linked = viewers[0] if viewers else None
        self._allow_resize = allow_resize
        self._pending = None
        self._timer = None
        self._observer = None
        self._closed = False
        key = None
        if (
            isinstance(snapshot, str)
            and self._linked is not None
            and snapshot in getattr(self._linked, "snap", {})
        ):
            key = snapshot
            snapshot = self._linked.snap[key]
        if isinstance(snapshot, Screenshot):
            if not snapshot.done or snapshot.error:
                raise ValueError(
                    snapshot.error or "Capture is pending; create the card in a later cell"
                )
            snapshot = snapshot.path

        record = {}
        path = None
        if isinstance(snapshot, dict):
            record = deepcopy(snapshot)
            if record.get("_path"):
                path = Path(record["_path"])
        elif isinstance(snapshot, str | Path):
            path = Path(snapshot).expanduser()
        else:
            raise ValueError("snapshot must be a PNG path, a capture dictionary, or a saved name")

        if path is not None:
            data = path.read_bytes()
            record = record or read_png_record(path) or {}
        else:
            image = record.get("image") or {}
            png = image.get("png") if isinstance(image, dict) else None
            if not png:
                raise ValueError("Snapshot has no PNG image or file path")
            data = base64.b64decode(png, validate=True)
        # Accept PNGs only and do not pass arbitrary URLs/HTML through to the browser.
        with Image.open(io.BytesIO(data)) as png:
            if png.format != "PNG":
                raise ValueError("Snapshot requires a PNG image")
            png.verify()

        self._restore = None
        if record.get("schema") == "celldega.view":
            self._restore = restore_spec(record)
        elif record.get("widgets"):
            panels = record["widgets"]
            panel = record.get("_panel", 0) if panel is None else panel
            if (
                isinstance(panel, bool)
                or not isinstance(panel, int)
                or not 0 <= panel < len(panels)
            ):
                raise ValueError(f"panel must be an integer from 0 to {len(panels) - 1}")
            self._restore = panels[panel].get("snapshot")
        if self._restore:
            validate_snapshot(self._restore)
            self._restore = restore_spec(self._restore)
        if self._linked is not None and not all(
            callable(getattr(self._linked, method, None))
            for method in ("restore_snapshot", "get_apply_result", "observe", "unobserve")
        ):
            raise ValueError("The linked viewer must support Snapshot restoration")

        details = {k: v for k, v in record.items() if k not in ("image", "_path", "_panel")}
        super().__init__(
            image=base64.b64encode(data).decode("ascii"),
            name=str(
                name
                if name is not None
                else key or record.get("title") or (path.stem if path else "Snapshot")
            ),
            description=str(
                description if description is not None else record.get("description") or ""
            ),
            metadata=details,
            can_restore=bool(self._linked is not None and self._restore),
            target_label=type(self._linked).__name__ if self._linked is not None else "",
            **kwargs,
        )
        self.on_msg(self._on_snapshot_action)
        if self.can_restore and getattr(type(self._linked), "_JS_VIEW_LINK", False):
            from ipywidgets import jsdlink

            self.view = deepcopy(self._restore)
            self._links = [
                jsdlink((self, "view_request"), (self._linked, "view_request")),
                jsdlink((self._linked, "view_result"), (self, "view_result")),
            ]
            self.js_link = True

    def _clear_pending(self):
        if getattr(self, "_timer", None):
            self._timer.cancel()
            self._timer = None
        if getattr(self, "_observer", None) is not None:
            self._linked.unobserve(self._observer, names="apply_capture_id")
            self._observer = None
        self._pending = None

    def _on_snapshot_action(self, _widget, content, _buffers):
        if not isinstance(content, dict) or content.get("event") != "restore":
            return
        self.show_view()

    def show_view(self):
        """Request navigation in the linked viewer; report its exact acknowledgement."""
        if not self.can_restore or self.busy or self._closed:
            return None
        self.busy = True
        self.status = "Opening this view…"

        def check(_change=None):
            if self._pending is None:
                return
            result = self._linked.get_apply_result(self._pending)
            if result is None:
                return
            self._clear_pending()
            self.busy = False
            self.status = (
                f"Could not open view: {result.get('error') or 'restore failed'}"
                if result.get("event") == "apply_error"
                else f"View opened in {self.target_label}."
            )

        def timeout():
            if self._closed or self._pending is None:
                return
            self._clear_pending()
            self.busy = False
            self.status = "No reply from the viewer. Display it in this notebook and try again."

        self._observer = check
        self._linked.observe(check, names="apply_capture_id")
        try:
            request_id = self._linked.restore_snapshot(
                self._restore, allow_resize=self._allow_resize
            )
            self._pending = request_id
            self._timer = threading.Timer(35, timeout)
            self._timer.daemon = True
            self._timer.start()
            check()  # Also handle a synchronous reply, e.g. an in-process transport.
            return request_id
        except Exception as exc:
            self._clear_pending()
            self.busy = False
            self.status = f"Could not open view: {exc}"
            return None

    def close(self):
        self._closed = True
        self._clear_pending()
        for link in getattr(self, "_links", []):
            link.unlink()
        super().close()


def _snapshot_record(item) -> dict:
    """A Snapshot's record (the PNG's embedded record, or an in-memory capture).

    Accepts a PNG path, a :class:`Screenshot`, a record dictionary (e.g. an entry of
    ``widget.snap``) or an in-memory capture (``widget.latest_snapshot``).
    """
    if isinstance(item, Screenshot):
        if not item.done or item.error:
            raise ValueError(item.error or "Capture is pending; add it in a later cell")
        item = item.path
    if isinstance(item, str | Path):
        path = Path(item).expanduser()
        record = read_png_record(path)
        if not record:
            raise ValueError(f"{path} has no Celldega Snapshot record")
        return {**record, "_path": str(path)}
    if isinstance(item, dict):
        return deepcopy(item)
    raise ValueError("A Snapshot is a PNG path, a Screenshot, or a capture dictionary")


def _saved_view(record: dict, kind: str) -> dict | None:
    """The saved view for ``kind`` (e.g. ``"landscape"``) in a Snapshot record."""
    if record.get("schema") == "celldega.view":
        return record if record.get("kind") == kind else None
    widgets = record.get("widgets") or []
    panel = record.get("_panel")
    candidates = (
        [widgets[panel]] if isinstance(panel, int) and 0 <= panel < len(widgets) else widgets
    )
    for widget in candidates:
        snapshot = widget.get("snapshot") or {}
        if snapshot.get("kind") == kind:
            return snapshot
    return None


class Snapshots:
    """A named collection of Snapshots, e.g. points of interest to pin on a Landscape.

    Give it PNG paths, a folder of Snapshot PNGs, a viewer's ``snap`` collection, or
    add Snapshots one at a time. Passed to a Landscape (``Landscape(..., pins=...)``
    or ``landscape.pins = ...``), each Landscape Snapshot becomes a pin at the center
    of its view; the **PINS** button shows them, and clicking one opens its view.

    Examples::

        poi = dega.viz.Snapshots(["figures/glomerulus.png", "figures/medulla.png"])
        poi = dega.viz.Snapshots("celldega_files/snapshots")   # every Snapshot PNG
        poi = dega.viz.Snapshots(landscape.snap)
        poi.card("Glomerulus", landscape=landscape)             # one postcard, by name
        dega.viz.Landscape(base_url=..., snapshots=poi)         # pinned on the tissue
        landscape.pins = poi                                    # or pin them later
    """

    def __init__(self, items=None):
        self._items: dict[str, dict] = {}
        if items is None:
            return
        if isinstance(items, Snapshots):
            items = dict(items._items)
        if isinstance(items, dict) and not _looks_like_record(items):
            for name, item in items.items():
                self.add(item, name=str(name))
        elif isinstance(items, str | Path) and Path(items).expanduser().is_dir():
            for path in sorted(Path(items).expanduser().glob("*.png")):
                if read_png_record(path):
                    self.add(path)
        elif isinstance(items, str | Path | dict | Screenshot):
            self.add(items)
        else:
            for item in items:
                self.add(item)

    def add(self, snapshot, *, name: str | None = None) -> str:
        """Add a Snapshot; returns its name (repeated names get `` (2)``, etc.)."""
        record = _snapshot_record(snapshot)
        base = str(
            name
            or record.get("title")
            or (Path(record["_path"]).stem if record.get("_path") else "Snapshot")
        )
        key, suffix = base, 2
        while key in self._items:
            key = f"{base} ({suffix})"
            suffix += 1
        self._items[key] = record
        return key

    def __getitem__(self, name: str) -> dict:
        return self._items[name]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, name) -> bool:
        return name in self._items

    def names(self) -> list[str]:
        return list(self._items)

    def card(self, name: str, **kwargs) -> Snapshot:
        """A postcard for one of these Snapshots, chosen by name.

        ``poi.card("Glomerulus", landscape=landscape)`` links it to a viewer, like
        :class:`Snapshot`; other keyword arguments go to :class:`Snapshot` too.
        """
        if name not in self._items:
            raise KeyError(f"No Snapshot named {name!r}; have {self.names()}")
        kwargs.setdefault("name", name)
        return Snapshot(self._items[name], **kwargs)

    def __repr__(self) -> str:
        return f"Snapshots({self.names()!r})"

    def pins(self) -> list[dict]:
        """One pin per spatial Landscape Snapshot: name, memo, position and view.

        A pin sits at the center of the Snapshot's view; Snapshots of other widgets,
        or of the UMAP or XY spaces, have no place on the tissue and are skipped.
        """
        out = []
        for name, record in self._items.items():
            view = _saved_view(record, "landscape")
            state = (view or {}).get("state") or {}
            target = (state.get("view") or {}).get("target")
            if (
                not view
                or state.get("space", "spatial") != "spatial"
                or not isinstance(target, list | tuple)
                or len(target) < 2
            ):
                continue
            try:
                x, y = float(target[0]), float(target[1])
            except (TypeError, ValueError):
                continue
            out.append(
                {
                    "name": name,
                    "description": str(record.get("description") or view.get("description") or ""),
                    "target": [x, y],
                    "snapshot": restore_spec(view),
                }
            )
        return out


def _looks_like_record(value: dict) -> bool:
    """A single Snapshot record, rather than a ``{name: snapshot}`` collection."""
    return any(key in value for key in ("celldega_screenshot", "schema", "widgets"))
