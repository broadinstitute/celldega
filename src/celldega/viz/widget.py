import pathlib
import anywidget
import traitlets

class Landscape(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    component = traitlets.Unicode("Landscape").tag(sync=True)

    ini_x = traitlets.Float(4500).tag(sync=True)
    ini_y = traitlets.Float(3200).tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    max_image_zoom = traitlets.Int(16).tag(sync=True)
    bounce_time = traitlets.Int(200).tag(sync=True)
    token_traitlet = traitlets.Unicode('token').tag(sync=True)
    base_url = traitlets.Unicode('').tag(sync=True)    


class Toy(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Toy").tag(sync=True)