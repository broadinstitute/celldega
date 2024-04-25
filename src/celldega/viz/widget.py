import pathlib
import anywidget
import traitlets

class Landscape(anywidget.AnyWidget):

    """
    A widget for visualizing a 'landscape' view of spatial omics data. 

    Parameters
    ----------
    ini_x : float
        The initial x-coordinate of the view.
    ini_y : float
        The initial y-coordinate of the view.
    ini_zoom : float
        The initial zoom level of the view.
    bounce_time : int
        The time taken for the view to bounce back after panning.
    token_traitlet : str
        The token traitlet.
    base_url : str
        The base URL for the widget.

    Returns
    -------
    Landscape
        A widget for visualizing a 'landscape' view of spatial omics data.

    Examples
    --------
    >>> from celldega.viz import Landscape
    >>> Landscape(ini_x=4500, ini_y=3200, ini_zoom=0, max_image_zoom=16, bounce_time=200, token_traitlet='token', base_url='')

    
    """

    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    component = traitlets.Unicode("Landscape").tag(sync=True)

    ini_x = traitlets.Float(4500).tag(sync=True)
    ini_y = traitlets.Float(3200).tag(sync=True)
    ini_z = traitlets.Float(0).tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    token_traitlet = traitlets.Unicode('token').tag(sync=True)
    base_url = traitlets.Unicode('').tag(sync=True)    


class Toy(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Toy").tag(sync=True)