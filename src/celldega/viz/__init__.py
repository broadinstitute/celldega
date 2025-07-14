"""
Module for visualization
"""

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
) -> HBox:
    """
    Display a `Clustergram` widget and an `Enrich` widget side by side.

    Args:
        cgm (Clustergram): A `Clustergram` widget.

    Returns:
        HBox: Visualization display containing both widgets
    """

    cgm.layout = Layout(width="600px")

    enrich = Enrich(gene_list=[], width=250)
    jslink((cgm, "selected_genes"), (enrich, "gene_list"))
    return HBox([cgm, enrich], layout=Layout(width="1000px"))


__all__ = ["Clustergram", "Enrich", "Landscape", "get_local_server", "landscape_clustergram"]
