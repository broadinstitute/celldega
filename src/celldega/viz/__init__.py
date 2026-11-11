"""
Module for visualization
"""

import contextlib
import json

from ipywidgets import HBox, Layout, VBox, jsdlink, jslink

from .cloud import CellCloud, NeighborhoodCloud
from .landmark_widget import Landmark
from .local_server import get_local_server, get_proxy_server
from .reopen import from_png
from .screenshots import (
    Screenshot,
    load_screenshot,
    load_screenshots,
    load_snapshot,
    load_snapshots,
    screenshot,
    snapshot,
)
from .snapshot_widget import Snapshot
from .snapshots import fingerprint_dataset
from .widget import Clerk, Clustergram, Composition, Enrich, Landscape, Yearbook


def _clustergram_col_attr(cgm: "Clustergram", default: str = "leiden") -> str:
    """The cell attribute a Clustergram's columns represent (e.g. ``leiden``, ``cell_type``).

    Read from the Clustergram's ``col_entity`` (``{"entity": ..., "attr": ...}``) so
    linked Landscape/Yearbook queries color cells by whatever attribute the columns
    actually encode, rather than assuming ``leiden``.
    """
    raw = getattr(cgm, "col_entity", None)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = None
    if isinstance(raw, dict):
        return raw.get("attr") or default
    return default


def _pixel_height(value: str | int, fallback: int = 700) -> int:
    """Return a widget-compatible pixel height from a CSS pixel value."""
    try:
        pixels = int(str(value).strip().removesuffix("px"))
    except ValueError:
        return fallback
    return pixels if pixels > 0 else fallback


# Narrowest panel that fits the Clustergram control panel: the order/dendrogram
# grid (~170px), then the ROW/COL category bars and the search column, which
# narrow from ~210px and ~150px to ~120px and ~100px. Narrower scrolls the
# controls (the canvas itself sets the panel width above this).
_CLUSTERGRAM_MIN_PANEL_WIDTH = 400


# The front end draws the deck canvas at ``width + 100`` (room for labels; see
# js/deck-gl/matrix/deck_mat.js), plus a 1px border on each side.
_CLUSTERGRAM_CANVAS_PADDING = 102


def _columns_are_clusters(mat: Clustergram) -> bool:
    """Whether a Clustergram's columns are clusters of cells (not genes, single cells
    or neighborhoods), so the Landscape's highlighted clusters name its columns."""
    entity = getattr(mat, "col_entity", None) or {"entity": "cell", "attr": "leiden"}
    if isinstance(entity, str):
        try:
            entity = json.loads(entity)
        except ValueError:
            entity = {"entity": entity}
    if not isinstance(entity, dict):
        return False
    return entity.get("entity", "cell") == "cell" and entity.get("attr") != "name"


def _clustergram_panel_width(mat: Clustergram) -> str:
    """Panel width for a Clustergram: its full canvas, but never narrower than its controls."""
    canvas = int(mat.width or 0) + _CLUSTERGRAM_CANVAS_PADDING
    return f"{max(canvas, _CLUSTERGRAM_MIN_PANEL_WIDTH)}px"


def spatial_clustergram(
    spatial: "Landscape | CellCloud | NeighborhoodCloud | Yearbook",
    mat: Clustergram,
    width: str = "600px",
    height: str = "700px",
    *,
    enrich: bool | Enrich = False,
    row_enrich: bool = True,
    col_enrich: bool = False,
    enrich_kwargs: dict | None = None,
    cluster_attr: str | None = None,
    clerk: "bool | Clerk" = False,
    clerk_layout: str = "sidecar",
    clerk_kwargs: dict | None = None,
) -> "HBox | VBox":
    """
    Display a spatial widget and a `Clustergram` widget side by side, linked
    so that clicking a Clustergram row/column updates the spatial widget.

    Works with any of celldega's spatial widgets: `Landscape`, `CellCloud`,
    `NeighborhoodCloud`, or `Yearbook`. `Landscape`/`CellCloud`/
    `NeighborhoodCloud` share an ``update_trigger`` trait and are linked via
    a front-end ``jslink`` (no round-trip through Python); `Yearbook` has no
    such trait and is instead linked by observing the Clustergram's
    ``click_info`` in Python and translating it into a
    ``front_end_query`` (same mechanism as `landscape_yearbook_clustergram`).

    Args:
        spatial (Landscape | CellCloud | NeighborhoodCloud | Yearbook): The
            spatial widget to link.
        mat (Clustergram): A `Clustergram` widget.
        width (str): The width of the spatial widget. The Clustergram panel is
            sized to the Clustergram's canvas (its ``width`` plus ~100px for
            labels), widened if needed so its control panel fits.
        height (str): The total height of the spatial widget, including its
            control bar, and the default height of the `Enrich` widget. The
            Clustergram's ``height`` sets only its canvas; its controls and
            dendrogram add about 200px, so ``Clustergram(height=<height - 200>)``
            lines the two up (e.g. the 700px default with ``height=500``). The
            row stretches every widget to the tallest one.
        enrich (bool | Enrich): If True, create an `Enrich` widget; if an
            `Enrich` instance is provided, use it directly. If False, no
            enrichment widget is shown. Ignored for a `Yearbook` `spatial`.
        row_enrich (bool): If True (default), run enrichment analysis when
            row dendrogram clusters are selected.
        col_enrich (bool): If True, run enrichment analysis when column
            dendrogram clusters are selected.
        enrich_kwargs (dict | None): Optional kwargs passed to `Enrich` when
            `enrich=True`.
        cluster_attr (str | None): The cell attribute (``adata.obs`` column)
            a clicked cluster refers to. Only used when `spatial` is a
            `Yearbook`; defaults to the Clustergram's own ``col_entity``
            attribute (see `_clustergram_col_attr`).
        clerk (bool | Clerk): If True, create a `Clerk`; if a `Clerk` is given,
            use it. Either way it is linked (:func:`link_clerk`) to the spatial
            widget, the Clustergram and any `Enrich` here. If False, no Clerk.
        clerk_layout (str): ``"sidecar"`` (default) adds Clerk to the end of the
            row as a narrow column the row's height, like `Enrich`: it takes the
            room the row leaves (240-300 px), and the views keep their widths. A row
            wider than the notebook scrolls sideways. ``"wide"`` puts Clerk full
            width under the row.
        clerk_kwargs (dict | None): Optional kwargs passed to `Clerk` when
            `clerk=True`, e.g. ``{"context_info": "..."}``.

    Returns:
        HBox: The widgets side by side; with ``clerk_layout="wide"``, a VBox with
        that row above the Clerk.
    """
    if clerk_layout not in ("sidecar", "wide"):
        raise ValueError("clerk_layout must be 'sidecar' or 'wide'")
    clerk_widget = _clerk_for_layout(clerk, clerk_layout, height, clerk_kwargs)

    if isinstance(spatial, Yearbook):
        attr = cluster_attr or _clustergram_col_attr(mat)
        _link_clustergram_to_yearbook(mat, spatial, attr)

        mat.layout = Layout(width=width)
        spatial.layout = Layout(width="100%", height=height)

        if clerk_widget is not None:
            # A Yearbook has no raster for Clerk; it still reads the Clustergram.
            _link_clerk_once(clerk_widget, clustergram=mat)
        return _with_clerk([spatial, mat], clerk_widget, clerk_layout)

    # Link clustergram click_info to the spatial widget's update_trigger
    jslink((mat, "click_info"), (spatial, "update_trigger"))
    # Clusters highlighted in the Landscape (by its bars, a Clustergram click or a
    # Clerk link) show as blue column labels when the columns are those clusters.
    if spatial.has_trait("selected_clusters") and _columns_are_clusters(mat):
        jsdlink((spatial, "selected_clusters"), (mat, "highlighted_cols"))

    # Layouts
    mat.layout = Layout(width=_clustergram_panel_width(mat))
    spatial.layout = Layout(width=width, height=height)

    enrich_widget: Enrich | None = None
    if isinstance(enrich, Enrich):
        enrich_widget = enrich
    elif enrich:
        config = dict(enrich_kwargs or {})
        config.setdefault("gene_list", [])
        config.setdefault("width", 250)
        config.setdefault("height", _pixel_height(height))
        enrich_widget = Enrich(**config)

    if enrich_widget is not None:
        _link_clustergram_to_enrich(
            mat,
            enrich_widget,
            row_enrich=row_enrich,
            col_enrich=col_enrich,
        )
        # Browser-native and persisted with saved widget state: Enrich gene
        # clicks follow the same route in Jupyter and static documentation.
        jslink((enrich_widget, "focused_gene"), (spatial, "focused_gene"))

    children = [spatial, mat]
    if enrich_widget is not None:
        children.append(enrich_widget)

    if clerk_widget is not None:
        _link_clerk_once(clerk_widget, landscape=spatial, clustergram=mat, enrich=enrich_widget)
        if clerk_layout == "sidecar":
            _fit_row_beside_clerk([spatial, mat, enrich_widget])
    return _with_clerk(children, clerk_widget, clerk_layout)


#: A sidecar Clerk fills the room the row leaves, between these widths (px).
CLERK_SIDECAR_MIN_WIDTH = 240
CLERK_SIDECAR_MAX_WIDTH = 300
#: Room under a sidecar row for its horizontal scrollbar, when it's wider than the notebook.
ROW_SCROLLBAR_PADDING = "0 0 14px 0"


def _clerk_for_layout(
    clerk: "bool | Clerk", layout: str, height: str, kwargs: dict | None
) -> "Clerk | None":
    """The Clerk to show (created if asked for), sized for its layout."""
    if isinstance(clerk, Clerk):
        widget = clerk
    elif clerk:
        widget = Clerk(**dict(kwargs or {}))
    else:
        return None
    if layout == "sidecar":
        widget.height = _pixel_height(height)  # the row's height
        if widget.width:
            # A width the caller set is kept as is.
            widget.layout = Layout(flex="0 0 auto")
        else:
            # Fill the room the row leaves, within a narrow column's bounds.
            widget.layout = Layout(
                flex=f"1 1 {CLERK_SIDECAR_MAX_WIDTH}px",
                min_width=f"{CLERK_SIDECAR_MIN_WIDTH}px",
                max_width=f"{CLERK_SIDECAR_MAX_WIDTH}px",
            )
    else:
        widget.width = 0  # the full width of the notebook
    return widget


def _fit_row_beside_clerk(widgets: list) -> None:
    """Beside a sidecar Clerk, the views keep their full widths; only Clerk flexes.

    A row wider than the notebook scrolls sideways (see :func:`_with_clerk`) rather
    than squeezing the views.
    """
    for widget in widgets:
        if widget is not None:
            layout = widget.layout
            widget.layout = Layout(width=layout.width, height=layout.height, flex="0 0 auto")


def _link_clerk_once(clerk: "Clerk", **widgets) -> None:
    """Link only what this Clerk isn't linked to yet (it may come pre-linked)."""
    linked = getattr(clerk, "_linked_widgets", None) or {}
    fresh = {k: w for k, w in widgets.items() if w is not None and linked.get(k) is not w}
    if fresh:
        link_clerk(clerk, **fresh)


def _with_clerk(children: list, clerk: "Clerk | None", layout: str) -> "HBox | VBox":
    if clerk is None:
        return HBox(children)
    if layout == "sidecar":
        # Wider than the notebook, the row scrolls sideways, with room for the
        # scrollbar under it, rather than squeezing the views.
        return HBox(
            [*children, clerk],
            # Exactly the output's width, so this row (not the output) scrolls.
            layout=Layout(width="100%", overflow="auto hidden", padding=ROW_SCROLLBAR_PADDING),
        )
    return VBox([HBox(children), clerk])


def landscape_clustergram(
    landscape: Landscape,
    mat: Clustergram,
    width: str = "600px",
    height: str = "700px",
    *,
    enrich: bool | Enrich = False,
    row_enrich: bool = True,
    col_enrich: bool = False,
    enrich_kwargs: dict | None = None,
) -> HBox:
    """Deprecated alias for :func:`spatial_clustergram`, kept for backward
    compatibility. Prefer `spatial_clustergram`, which also works with
    `CellCloud`, `NeighborhoodCloud`, and `Yearbook`.
    """
    return spatial_clustergram(
        landscape,
        mat,
        width,
        height,
        enrich=enrich,
        row_enrich=row_enrich,
        col_enrich=col_enrich,
        enrich_kwargs=enrich_kwargs,
    )


def _link_clustergram_to_enrich(
    cgm: Clustergram,
    enrich: Enrich,
    *,
    row_enrich: bool = True,
    col_enrich: bool = False,
) -> None:
    cgm.row_enrich_enabled = row_enrich
    cgm.col_enrich_enabled = col_enrich
    if hasattr(cgm, "_record_category_colors"):
        cgm._record_category_colors({"In term": "#2f74ff", "Out of term": "#ffffff"})

    # The whole Clustergram <-> Enrich interaction runs in the browser, so it
    # behaves identically with a live kernel and in a static notebook export.
    # The Clustergram front end decides which selections become enrichment
    # gene sets (honoring row/col_enrich_enabled) and writes them to
    # ``enrichment_genes``; Enrich CLEAR/manual lists flow back through the
    # same bidirectional link and update the bold enrichment-gene labels.
    jslink((cgm, "enrichment_genes"), (enrich, "gene_list"))
    jsdlink((cgm, "enrichment_source_label"), (enrich, "source_label"))
    jslink((enrich, "focused_gene"), (cgm, "focused_gene"))
    jsdlink((enrich, "term_genes"), (cgm, "highlighted_genes"))


def clustergram_enrich(
    cgm: Clustergram,
    *,
    row_enrich: bool = True,
    col_enrich: bool = False,
) -> HBox:
    """
    Display a `Clustergram` widget and an `Enrich` widget side by side.

    Args:
        cgm (Clustergram): A `Clustergram` widget.
        row_enrich (bool): If True (default), run enrichment analysis when
            row dendrogram clusters are selected.
        col_enrich (bool): If True, run enrichment analysis when column
            dendrogram clusters are selected.

    Returns:
        HBox: Visualization display containing both widgets.
    """
    cgm.layout = Layout(width="600px")

    enrich = Enrich(gene_list=[], width=250, height=700)

    _link_clustergram_to_enrich(
        cgm,
        enrich,
        row_enrich=row_enrich,
        col_enrich=col_enrich,
    )

    return HBox([cgm, enrich], layout=Layout(width="1000px"))


def landscape_yearbook(
    landscape: Landscape,
    yearbook: Yearbook,
    width: str = "100%",
    height: str = "400px",
    cluster_attr: str = "leiden",
) -> "VBox":
    """
    Display a `Landscape` widget above a `Yearbook` widget with linked queries.

    When the user clicks on a cluster in the Landscape, the Yearbook automatically
    updates to show cells from that cluster. When a gene is selected, cells are
    ranked by gene expression.

    Args:
        landscape (Landscape): A `Landscape` widget.
        yearbook (Yearbook): A `Yearbook` widget.
        width (str): The width of the widgets.
        height (str): The height of each widget.
        cluster_attr (str): The cell attribute (``adata.obs`` column) a clicked
            cluster value refers to (default ``"leiden"``). If the click payload
            carries its own ``attr`` it takes precedence, so linked Clustergrams
            over non-leiden sets (cell types, domains) color the right cells.

    Returns:
        VBox: Visualization display containing both widgets stacked vertically.

    Example::

        landscape = dega.viz.Landscape(base_url="...", adata=adata)
        yearbook = dega.viz.Yearbook(base_url="...", rows=2, cols=4)
        display = dega.viz.landscape_yearbook(landscape, yearbook)
    """

    # Link Landscape update_trigger to Yearbook query
    def _on_update_trigger(change):
        info = change["new"] or {}
        click_type = (info.get("type") or "").lower()
        value = info.get("value") or {}
        attr = value.get("attr") or cluster_attr

        current_query = dict(yearbook.front_end_query or {})

        if click_type == "col_label":
            # Cluster selected
            cluster_name = value.get("name", "")
            if cluster_name:
                current_query["cluster"] = {"attr": attr, "value": str(cluster_name)}
                yearbook.front_end_query = current_query
        elif click_type == "row_label":
            # Gene selected
            gene_name = value.get("name", "")
            if gene_name:
                current_query["gene"] = gene_name
                yearbook.front_end_query = current_query
        elif click_type == "col_dendro":
            # Multiple clusters selected via dendrogram
            selected_names = value.get("selected_names", [])
            if selected_names and len(selected_names) == 1:
                current_query["cluster"] = {"attr": attr, "value": str(selected_names[0])}
                yearbook.front_end_query = current_query

    landscape.observe(_on_update_trigger, names="update_trigger")

    # Layouts
    landscape.layout = Layout(width=width, height=height)
    yearbook.layout = Layout(width=width, height=height)

    return VBox([landscape, yearbook])


def _link_clustergram_to_yearbook(cgm: Clustergram, yearbook: Yearbook, attr: str) -> None:
    """Observe a Clustergram's ``click_info`` and translate it into a Yearbook
    ``front_end_query`` (cluster selection or gene ranking). Shared by
    `spatial_clustergram` (Yearbook branch) and `landscape_yearbook_clustergram`.
    """

    def _on_click_info(change):
        info = change["new"] or {}
        click_type = (info.get("type") or "").lower()
        value = info.get("value") or {}

        current_query = dict(yearbook.front_end_query or {})

        if click_type == "col_label":
            # Cluster selected
            cluster_name = value.get("name", "")
            if cluster_name:
                current_query["cluster"] = {"attr": attr, "value": str(cluster_name)}
                yearbook.front_end_query = current_query
        elif click_type == "row_label":
            # Gene selected
            gene_name = value.get("name", "")
            if gene_name:
                current_query["gene"] = gene_name
                yearbook.front_end_query = current_query
        elif click_type.startswith("col_dendro"):
            # Multiple clusters selected via dendrogram
            selected_names = value.get("selected_names", [])
            if selected_names and len(selected_names) == 1:
                current_query["cluster"] = {"attr": attr, "value": str(selected_names[0])}
                yearbook.front_end_query = current_query
        elif click_type.startswith("row_dendro"):
            # Multiple genes selected - use first one
            selected_names = value.get("selected_names", [])
            if selected_names:
                current_query["gene"] = selected_names[0]
                yearbook.front_end_query = current_query

    cgm.observe(_on_click_info, names="click_info")


def landscape_yearbook_clustergram(
    landscape: Landscape,
    yearbook: Yearbook,
    cgm: Clustergram,
    width: str = "600px",
    height: str = "400px",
    cluster_attr: str | None = None,
) -> "VBox":
    """
    Display a `Landscape` and `Clustergram` side by side, with a `Yearbook` below.

    All three widgets are linked:
    - Clustergram clicks update both Landscape and Yearbook
    - Gene selections rank cells in Yearbook by expression
    - Cluster selections filter cells in Yearbook

    Args:
        landscape (Landscape): A `Landscape` widget.
        yearbook (Yearbook): A `Yearbook` widget.
        cgm (Clustergram): A `Clustergram` widget.
        width (str): The width of each widget in the top row.
        height (str): The height of each widget.

    Returns:
        VBox: Visualization display with Landscape+Clustergram on top, Yearbook below.

    Example::

        landscape = dega.viz.Landscape(base_url="...", adata=adata)
        yearbook = dega.viz.Yearbook(base_url="...", rows=2, cols=4)
        cgm = dega.viz.Clustergram(matrix=mat)
        display = dega.viz.landscape_yearbook_clustergram(landscape, yearbook, cgm)
    """
    # Link clustergram click_info to landscape update_trigger
    jslink((cgm, "click_info"), (landscape, "update_trigger"))

    # Attribute the Clustergram's columns encode (e.g. leiden, cell_type, domain)
    attr = cluster_attr or _clustergram_col_attr(cgm)

    # Link Clustergram to Yearbook
    _link_clustergram_to_yearbook(cgm, yearbook, attr)

    # Layouts
    landscape.layout = Layout(width=width, height=height)
    cgm.layout = Layout(width=width, height=height)
    yearbook.layout = Layout(width="100%", height=height)

    top_row = HBox([landscape, cgm])
    return VBox([top_row, yearbook])


def _feed_landscape_raster_to_clerk(
    landscape: Landscape, clerk: Clerk, *, capture_on_select: bool = True
) -> None:
    """Wire a Landscape's raster capture into a Clerk's image evidence.

    Copies the captured PNG and its exact view state (zoom/pan) into the Clerk, and
    (optionally) requests a fresh capture whenever the Landscape selection changes so the
    attached raster reflects what the user is inspecting.
    """

    def _copy_raster(change):
        png = change["new"] or ""
        if png:
            # Preview first: the panel redraws when ``has_image`` flips.
            clerk.image_thumb_b64 = landscape.raster_thumb or ""
            clerk.image_b64 = png

    def _copy_view_state(change):
        vs = change["new"] or {}
        if vs:
            clerk.image_view_state = dict(vs)

    landscape.observe(_copy_raster, names="raster_png")
    landscape.observe(_copy_view_state, names="raster_view_state")

    if capture_on_select:

        def _capture(_change):
            with contextlib.suppress(Exception):
                landscape.request_raster()

        landscape.observe(_capture, names="update_trigger")

    # Request an initial capture so the first question can include an image.
    with contextlib.suppress(Exception):
        landscape.request_raster()


def _feed_clustergram_genes_to_clerk(cgm: Clustergram, clerk: Clerk) -> None:
    """Wire a Clustergram's selected genes into a Clerk's ``gene_list`` evidence."""

    def _on_selected_genes(change):
        clerk.gene_list = list(change["new"] or [])

    cgm.observe(_on_selected_genes, names="selected_genes")


def link_clerk(
    clerk: Clerk,
    *,
    landscape: Landscape | None = None,
    clustergram: Clustergram | None = None,
    enrich: Enrich | None = None,
    capture_on_select: bool = True,
) -> Clerk:
    """Link a standalone `Clerk` to whichever widgets you pass -- the integration point.

    Clerk stands alone and only sees the widgets you pass it. Widgets are modular and
    swappable: pass any subset. The usual case is ``Landscape`` + ``Clustergram`` +
    ``Enrich``. Each question from the chat box captures the linked views as they are
    at that moment:

    - ``landscape`` -> a screenshot of the current view (+ zoom/pan view state) in
      ``clerk.image_b64`` / ``clerk.image_view_state``.
    - ``clustergram`` -> a snapshot of what's on screen (``Clustergram.request_state``),
      plus any genes named in the question; its selected genes also flow into
      ``clerk.gene_list``.
    - ``enrich`` -> the enrichment results on screen (``Enrich.request_state``). Clerk
      then stops fetching its own Enrichr terms.

    Yearbook is intentionally *not* linked into Clerk -- it's a sidecar you lay out
    separately. This only wires state; lay the widgets out however you like. Returns
    ``clerk`` for chaining.

    Args:
        clerk (Clerk): The Clerk widget to link.
        landscape (Landscape | None): Source of raster / view-state evidence.
        clustergram (Clustergram | None): Source of matrix and gene-list evidence.
        enrich (Enrich | None): Source of enrichment-result evidence.
        capture_on_select (bool): Re-capture the Landscape raster on each selection.
    """
    # Remember linked widgets so later features (set-state, evidence sharing) can find
    # them without re-plumbing.
    linked = dict(getattr(clerk, "_linked_widgets", {}) or {})
    if clustergram is not None:
        _feed_clustergram_genes_to_clerk(clustergram, clerk)
        linked["clustergram"] = clustergram
    if landscape is not None:
        _feed_landscape_raster_to_clerk(landscape, clerk, capture_on_select=capture_on_select)
        linked["landscape"] = landscape
    if enrich is not None:
        linked["enrich"] = enrich
        clerk.fetch_enrichr = False  # read the Enrich panel's results instead
    clerk._linked_widgets = linked
    return clerk


def landscape_clerk(
    landscape: Landscape,
    clerk: Clerk,
    width: str = "600px",
    height: str = "650px",
    *,
    capture_on_select: bool = True,
) -> HBox:
    """Convenience layout: a `Landscape` beside a portrait `Clerk`, wired via
    :func:`link_clerk`.

    For anything else, call :func:`link_clerk` and arrange the widgets yourself.

    Args:
        landscape (Landscape): A `Landscape` widget.
        clerk (Clerk): A `Clerk` widget.
        width (str): Width of the Landscape widget.
        height (str): Height of both widgets.
        capture_on_select (bool): Re-capture the raster on each Landscape selection.

    Returns:
        HBox: Both widgets side by side.
    """
    link_clerk(clerk, landscape=landscape, capture_on_select=capture_on_select)
    landscape.layout = Layout(width=width, height=height)
    clerk.layout = Layout(height=height)
    return HBox([landscape, clerk])


__all__ = [
    "CellCloud",
    "Clerk",
    "Clustergram",
    "Composition",
    "Enrich",
    "Landmark",
    "Landscape",
    "NeighborhoodCloud",
    "Screenshot",
    "Snapshot",
    "Yearbook",
    "clustergram_enrich",
    "from_png",
    "get_local_server",
    "get_proxy_server",
    "landscape_clerk",
    "landscape_clustergram",
    "landscape_yearbook",
    "landscape_yearbook_clustergram",
    "link_clerk",
    "load_screenshot",
    "load_screenshots",
    "load_snapshot",
    "load_snapshots",
    "screenshot",
    "snapshot",
    "spatial_clustergram",
]
