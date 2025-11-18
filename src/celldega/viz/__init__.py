"""
Module for visualization
"""

from ipywidgets import HBox, Layout, jslink

from .local_server import get_local_server
from .widget import Clustergram, Enrich, Landscape


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
    """
    Display a `Landscape` widget and a `Clustergram` widget side by side.

    Args:
        landscape (Landscape): A `Landscape` widget.
        mat (Clustergram): A `Clustergram` widget.
        width (str): The width of the widgets.
        height (str): The height of the widgets.
        enrich (bool | Enrich): If True, create an `Enrich` widget; if an
            `Enrich` instance is provided, use it directly. If False, no
            enrichment widget is shown.
        row_enrich (bool): If True (default), run enrichment analysis when
            row dendrogram clusters are selected.
        col_enrich (bool): If True, run enrichment analysis when column
            dendrogram clusters are selected.
        enrich_kwargs (dict | None): Optional kwargs passed to `Enrich` when
            `enrich=True`.

    Returns:
        HBox: Visualization display containing the widgets.
    """
    # Link clustergram click_info to landscape update_trigger
    jslink((mat, "click_info"), (landscape, "update_trigger"))

    # Layouts
    mat.layout = Layout(width=width)
    landscape.layout = Layout(width=width, height=height)

    enrich_widget: Enrich | None = None
    if isinstance(enrich, Enrich):
        enrich_widget = enrich
    elif enrich:
        config = dict(enrich_kwargs or {})
        config.setdefault("gene_list", [])
        config.setdefault("width", 250)
        enrich_widget = Enrich(**config)

    if enrich_widget is not None:

        def _forward_gene_to_landscape(gene: str) -> None:
            if gene:
                landscape.trigger_update({"type": "row_label", "value": {"name": gene}})

        _link_clustergram_to_enrich(
            mat,
            enrich_widget,
            row_enrich=row_enrich,
            col_enrich=col_enrich,
            gene_focus_callback=_forward_gene_to_landscape,
        )

    children = [landscape, mat]
    if enrich_widget is not None:
        children.append(enrich_widget)

    return HBox(children)


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

    def _set_gene_list(genes) -> None:
        enrich.gene_list = list(genes) if genes else []

    def _on_selected_genes(change) -> None:
        genes = change["new"] or []

        click_info = getattr(cgm, "click_info", {}) or {}
        click_type = (click_info.get("type") or "").lower()
        selected_names = (click_info.get("value") or {}).get("selected_names") or []

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
            elif click_type.startswith("col"):
                if not col_enrich:
                    _set_gene_list([])
                    return

        _set_gene_list(genes)

    def _on_click_info(change) -> None:
        info = change["new"] or {}
        click_type = (info.get("type") or "").lower()
        selected_names = (info.get("value") or {}).get("selected_names") or []

        if click_type.startswith("col"):
            if not col_enrich:
                return
            if selected_names:
                cgm.selected_genes = list(selected_names)
        elif click_type.startswith("row"):
            if not row_enrich:
                _set_gene_list([])

    def _on_focused_gene(change) -> None:
        if gene_focus_callback is None:
            return
        gene = change["new"] or ""
        gene_focus_callback(gene)

    cgm.observe(_on_selected_genes, names="selected_genes")
    cgm.observe(_on_click_info, names="click_info")
    enrich.observe(_on_focused_gene, names="focused_gene")


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

    enrich = Enrich(gene_list=[], width=250)

    _link_clustergram_to_enrich(
        cgm,
        enrich,
        row_enrich=row_enrich,
        col_enrich=col_enrich,
    )

    return HBox([cgm, enrich], layout=Layout(width="1000px"))


__all__ = [
    "Clustergram",
    "Enrich",
    "Landscape",
    "clustergram_enrich",
    "get_local_server",
    "landscape_clustergram",
]
