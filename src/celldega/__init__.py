import importlib.metadata
import pathlib

import anywidget
import traitlets
from traitlets import Unicode, Int, Float

try:
    __version__ = importlib.metadata.version("celldega")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


class Landscape(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "static" / "widget.css"
    component = traitlets.Unicode("Landscape").tag(sync=True)

    ini_x = Float(4500).tag(sync=True)
    ini_y = Float(3200).tag(sync=True)
    ini_zoom = Float(0).tag(sync=True)
    max_image_zoom = Int(16).tag(sync=True)
    bounce_time = Int(200).tag(sync=True)
    token_traitlet = Unicode('token').tag(sync=True)
    base_url = Unicode('').tag(sync=True)    


class Toy(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "static" / "widget.css"
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Toy").tag(sync=True)