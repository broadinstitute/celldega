import pathlib
import anywidget
import traitlets
import json

class Landscape(anywidget.AnyWidget):
    """
    A widget for visualizing a 'landscape' view of spatial omics data.

    Args:
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        bounce_time (int): The time taken for the view to bounce back after panning.
        token (str): The token traitlet.
        base_url (str): The base URL for the widget.
        dataset_name (str, optional): The name of the dataset to visualize. This will show up in the user interface bar.

    Attributes:
        component (str): The name of the component.
        technology (str): The technology used.
        base_url (str): The base URL for the widget.
        token (str): The token traitlet.
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_z (float): The initial z-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        dataset_name (str): The name of the dataset to visualize.
        update_trigger (dict): The dictionary to trigger updates.
        cell_clusters (dict): The dictionary containing cell cluster information.

    Returns:
        Landscape: A widget for visualizing a 'landscape' view of spatial omics data.
    """
    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    component = traitlets.Unicode("Landscape").tag(sync=True)

    technology = traitlets.Unicode("sst").tag(sync=True)
    base_url = traitlets.Unicode("").tag(sync=True)
    token = traitlets.Unicode("").tag(sync=True)
    ini_x = traitlets.Float(1000).tag(sync=True)
    ini_y = traitlets.Float(1000).tag(sync=True)
    ini_z = traitlets.Float(0).tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    square_tile_size = traitlets.Float(1.4).tag(sync=True)
    dataset_name = traitlets.Unicode("").tag(sync=True)

    update_trigger = traitlets.Dict().tag(sync=True)
    cell_clusters = traitlets.Dict().tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(800).tag(sync=True)

    def trigger_update(self, new_value):
        # This method updates the update_trigger traitlet with a new value
        # You can pass any information necessary for the update, or just a timestamp
        self.update_trigger = new_value

    def update_cell_clusters(self, new_clusters):
        # Convert the new_clusters to a JSON serializable format if necessary
        self.cell_clusters = new_clusters


class Matrix(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Matrix").tag(sync=True)

    network = traitlets.Dict({}).tag(sync=True)
    click_info = traitlets.Dict({}).tag(sync=True)


class MatrixNew(anywidget.AnyWidget):
    _esm = pathlib.Path(__file__).parent / "../static" / "widget.js"
    _css = pathlib.Path(__file__).parent / "../static" / "widget.css"
    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("MatrixNew").tag(sync=True)

    network = traitlets.Dict({}).tag(sync=True)
    width = traitlets.Int(600).tag(sync=True)
    height = traitlets.Int(600).tag(sync=True)

    click_info = traitlets.Dict({}).tag(sync=True)
