"""
Module for visualization
"""

from .widget import Landscape, Matrix
from ipywidgets import jslink, HBox, Layout

def landscape_matrix(landscape, mat, width='600px', height='700px'):
    """
    Display a `Landscape` widget and a `Matrix` widget side by side.

    Args:
        landscape (Landscape): A `Landscape` widget.
        mat (Matrix): A `Matrix` widget.
        width (str): The width of the widgets.
        height (str): The height of the widgets.

    Returns:
        Visualization display

    Example:
    See example [Landscape-Matrix_Xenium](../../../examples/brief_notebooks/Landscape-Matrix_Xenium) notebook
    """

    # Use `jslink` to directly link `click_info` from `mat` to `trigger_value` in `landscape_ist`
    jslink((mat, 'click_info'), (landscape, 'update_trigger'))

    # Set layouts for the widgets
    mat.layout = Layout(width=width)  # Adjust as needed
    landscape.layout = Layout(width=width, height=height)  # Adjust as needed

    # Display widgets side by side
    widgets_side_by_side = HBox([landscape, mat])

    display(widgets_side_by_side)

__all__ = ["Landscape", "Matrix", 'landscape_matrix']
