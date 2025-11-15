"""
Module for visualization
"""

import pandas as pd
from ipywidgets import HBox, Layout, jslink

from .local_server import get_local_server
from .widget import Clustergram, Enrich, Landscape


def landscape_clustergram(landscape, mat, width="600px", height="700px"):
    """
    Display a `Landscape` widget and a `Clustergram` widget side by side.

    Args:
        landscape (Landscape): A `Landscape` widget.
        cgm (Clustergram): A `Clustergram` widget.
        width (str): The width of the widgets.
        height (str): The height of the widgets.

    Returns:
        HBox: Visualization display containing both widgets

    Example:
    See example [Landscape-Matrix_Xenium](../../../examples/brief_notebooks/Landscape-Matrix_Xenium) notebook
    """
    # Use `jslink` to directly link `click_info` from `mat` to `trigger_value` in `landscape_ist`
    jslink((mat, "click_info"), (landscape, "update_trigger"))

    # Set layouts for the widgets
    mat.layout = Layout(width=width)  # Adjust as needed
    landscape.layout = Layout(width=width, height=height)  # Adjust as needed

    return HBox([landscape, mat])


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
        row_enrich (bool): If ``True`` (default), run enrichment analysis when
            row dendrogram clusters are selected.
        col_enrich (bool): If ``True``, run enrichment analysis when column
            dendrogram clusters are selected.

    Returns:
        HBox: Visualization display containing both widgets
    """

    cgm.layout = Layout(width="600px")

    enrich = Enrich(gene_list=[], width=250)

    def _ensure_attribute_index(axis: str) -> pd.Index:
        names = getattr(cgm, f"{axis}_names", []) or []
        return pd.Index([str(name) for name in names], name=f"{axis}_id")

    ENRICH_COLUMN_NAME = "Enrichment Membership"
    ENRICH_COLORS = {"In term": "#2f74ff", "Out of term": "#ffffff"}

    def _set_gene_list(genes):
        enrich.gene_list = list(genes) if genes else []

    def _update_enrichment_membership(term_genes):
        index = _ensure_attribute_index("row")
        if index.empty:
            return

        existing = cgm.row_attributes_df
        if existing is None or existing.empty:
            df = pd.DataFrame(index=index)
        else:
            df = existing.reindex(index)

        if not term_genes:
            if ENRICH_COLUMN_NAME in df.columns:
                df = df.drop(columns=[ENRICH_COLUMN_NAME])
            cgm.row_attributes_df = df if not df.empty else None
            colors = dict(cgm.row_attribute_colors or {})
            colors.pop(ENRICH_COLUMN_NAME, None)
            cgm.row_attribute_colors = colors
            return

        normalized = {str(g).lower() for g in term_genes}
        membership = pd.Series("Out of term", index=index, dtype=object)
        membership[index.str.lower().isin(normalized)] = "In term"
        df[ENRICH_COLUMN_NAME] = membership

        cgm.row_attributes_df = df
        colors = dict(cgm.row_attribute_colors or {})
        colors[ENRICH_COLUMN_NAME] = ENRICH_COLORS
        cgm.row_attribute_colors = colors

    def _on_selected_genes(change):
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
            if click_type.startswith("row") and not row_enrich:
                _set_gene_list([])
                return
            if click_type.startswith("col") and not col_enrich:
                _set_gene_list([])
                return

        _set_gene_list(genes)

    def _on_click_info(change):
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

    cgm.observe(_on_selected_genes, names="selected_genes")
    cgm.observe(_on_click_info, names="click_info")

    def _on_term_genes(change):
        _update_enrichment_membership(change["new"] or [])

    enrich.observe(_on_term_genes, names="term_genes")

    return HBox([cgm, enrich], layout=Layout(width="1000px"))


__all__ = ["Clustergram", "Enrich", "Landscape", "get_local_server", "landscape_clustergram"]
