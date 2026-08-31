"""
Module for visualization
"""

import json

from ipywidgets import HBox, Layout, VBox, jslink

from .cloud import CellCloud, NeighborhoodCloud
from .landmark_widget import Landmark
from .local_server import get_local_server, get_proxy_server
from .widget import Clustergram, Composition, Enrich, Landscape, Yearbook


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
) -> HBox:
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
        width (str): The width of the widgets.
        height (str): The height of the widgets.
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

    Returns:
        HBox: Visualization display containing the widgets.
    """
    if isinstance(spatial, Yearbook):
        attr = cluster_attr or _clustergram_col_attr(mat)
        _link_clustergram_to_yearbook(mat, spatial, attr)

        mat.layout = Layout(width=width)
        spatial.layout = Layout(width="100%", height=height)

        return HBox([spatial, mat])

    # Link clustergram click_info to the spatial widget's update_trigger
    jslink((mat, "click_info"), (spatial, "update_trigger"))

    # Layouts
    mat.layout = Layout(width=width)
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

        def _forward_gene_to_spatial(gene: str) -> None:
            if gene:
                if mat.focused_gene == gene:
                    # Re-focusing the same gene must still notify JS (traitlets
                    # suppresses no-change sets), so blank first to force a
                    # change event and re-center the row.
                    mat.focused_gene = ""
                mat.focused_gene = gene
                spatial.trigger_update({"type": "row_label", "value": {"name": gene}})

        _link_clustergram_to_enrich(
            mat,
            enrich_widget,
            row_enrich=row_enrich,
            col_enrich=col_enrich,
            gene_focus_callback=_forward_gene_to_spatial,
        )

    children = [spatial, mat]
    if enrich_widget is not None:
        children.append(enrich_widget)

    return HBox(children)


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
    gene_focus_callback=None,
) -> None:
    enrich_colors = {"In term": "#2f74ff", "Out of term": "#ffffff"}

    def _record_colors() -> None:
        if hasattr(cgm, "_record_category_colors"):
            cgm._record_category_colors(enrich_colors)

    _record_colors()

    def _set_gene_list(genes, source_label: str = "") -> None:
        enrich.source_label = source_label if genes else ""
        enrich.gene_list = list(genes) if genes else []

    def _selection_source_label(click_type: str) -> str:
        labels = {
            "row_crop": "Clustergram row crop",
            "col_crop": "Clustergram column crop",
            "row_dendro": "Clustergram row dendrogram",
            "col_dendro": "Clustergram column dendrogram",
        }
        return labels.get(click_type, "Clustergram selection")

    def _on_selected_genes(change) -> None:
        genes = change["new"] or []

        click_info = getattr(cgm, "click_info", {}) or {}
        click_type = (click_info.get("type") or "").lower()
        click_value = click_info.get("value") or {}
        selected_names = click_value.get("selected_names") or []

        # A row label selects one gene for linked views, but it is not an
        # enrichment gene set. Preserve the current enrichment result instead
        # of replacing or clearing it.
        if click_type == "row_label":
            return

        is_dendro = click_type.startswith(("row", "col"))
        matches_click = (
            bool(selected_names)
            and len(selected_names) == len(genes)
            and set(selected_names) == set(genes)
        )

        if is_dendro and matches_click:
            if click_type.startswith("row"):
                if not row_enrich:
                    _set_gene_list([])
                    return
            elif click_type.startswith("col") and not col_enrich:
                _set_gene_list([])
                return

        _set_gene_list(genes, _selection_source_label(click_type))

    def _on_click_info(change) -> None:
        info = change["new"] or {}
        click_type = (info.get("type") or "").lower()
        selected_names = (info.get("value") or {}).get("selected_names") or []

        if click_type.startswith("col"):
            if not col_enrich:
                return
            if selected_names:
                cgm.selected_genes = list(selected_names)
        elif click_type.startswith("row") and click_type != "row_label":
            if not row_enrich:
                _set_gene_list([])

    def _on_focused_gene(change) -> None:
        if gene_focus_callback is None:
            return
        gene = change["new"] or ""
        gene_focus_callback(gene)

    def _on_term_genes(change) -> None:
        # Mirror the selected enriched term's genes onto the Clustergram so its
        # row labels can highlight them (blue, matching Enrich's "In term"
        # paragraph color). Enrich clears term_genes on CLEAR/term-deselect,
        # which resets the highlight through this same path.
        cgm.highlighted_genes = list(change["new"] or [])

    cgm.observe(_on_selected_genes, names="selected_genes")
    cgm.observe(_on_click_info, names="click_info")
    enrich.observe(_on_focused_gene, names="focused_gene")
    enrich.observe(_on_term_genes, names="term_genes")
    if enrich.term_genes:
        cgm.highlighted_genes = list(enrich.term_genes)


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

    def _focus_gene_in_clustergram(gene: str) -> None:
        if gene:
            if cgm.focused_gene == gene:
                # Force a change event so re-clicking the same gene re-centers
                # its row (traitlets suppresses no-change sets).
                cgm.focused_gene = ""
            cgm.focused_gene = gene

    _link_clustergram_to_enrich(
        cgm,
        enrich,
        row_enrich=row_enrich,
        col_enrich=col_enrich,
        gene_focus_callback=_focus_gene_in_clustergram,
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


__all__ = [
    "CellCloud",
    "Clustergram",
    "Composition",
    "Enrich",
    "Landmark",
    "Landscape",
    "NeighborhoodCloud",
    "Yearbook",
    "clustergram_enrich",
    "get_local_server",
    "get_proxy_server",
    "landscape_clustergram",
    "landscape_yearbook",
    "landscape_yearbook_clustergram",
    "spatial_clustergram",
]
