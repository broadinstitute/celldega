"""
Widget module for interactive visualization components.
"""

from contextlib import suppress
from pathlib import Path

import anywidget
import traitlets


_clustergram_registry = {}  # maps names to widget instances


class Landscape(anywidget.AnyWidget):
    """
    A widget for interactive visualization of spatial omics data. This widget
    currently supports iST (Xenium and MERSCOPE) and sST (Visium HD data)

    Args:
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
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

    _esm = Path(__file__).parent / "../static" / "widget.js"
    _css = Path(__file__).parent / "../static" / "widget.css"
    component = traitlets.Unicode("Landscape").tag(sync=True)

    technology = traitlets.Unicode("sst").tag(sync=True)
    base_url = traitlets.Unicode("").tag(sync=True)
    token = traitlets.Unicode("").tag(sync=True)
    creds = traitlets.Dict({}).tag(sync=True)
    ini_x = traitlets.Float().tag(sync=True)
    ini_y = traitlets.Float().tag(sync=True)
    ini_z = traitlets.Float().tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    square_tile_size = traitlets.Float(1.4).tag(sync=True)
    dataset_name = traitlets.Unicode("").tag(sync=True)
    region = traitlets.Dict({}).tag(sync=True)
    nbhd = traitlets.Dict({}).tag(sync=True)

    meta_cell = traitlets.Dict({}).tag(sync=True)
    meta_cluster = traitlets.Dict({}).tag(sync=True)
    umap = traitlets.Dict({}).tag(sync=True)
    landscape_state = traitlets.Unicode("spatial").tag(sync=True)

    update_trigger = traitlets.Dict().tag(sync=True)
    cell_clusters = traitlets.Dict({}).tag(sync=True)

    segmentation = traitlets.Unicode("default").tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(800).tag(sync=True)

    def trigger_update(self, new_value):
        """
        Update the update_trigger traitlet with a new value.

        Parameters:
        - new_value: New value to trigger update with
        """
        # This method updates the update_trigger traitlet with a new value
        # You can pass any information necessary for the update, or just a timestamp
        self.update_trigger = new_value

    def update_cell_clusters(self, new_clusters):
        """
        Update cell clusters with new data.

        Parameters:
        - new_clusters: New cluster data to update with
        """
        # Convert the new_clusters to a JSON serializable format if necessary
        self.cell_clusters = new_clusters


class Clustergram(anywidget.AnyWidget):
    """
    A widget for interactive visualization of a hierarchically clustered matrix.

    Automatically replaces older widgets with the same name to prevent notebook bloat.

    Args:
        value (int): The value traitlet.
        component (str): The component traitlet.
        network (dict): The network traitlet.
        click_info (dict): The click_info traitlet.

    Returns:
        Clustergram: A widget for visualizing a hierarchically clustered matrix.
    """

    _esm = Path(__file__).parent / "../static" / "widget.js"
    _css = Path(__file__).parent / "../static" / "widget.css"

    value = traitlets.Int(0).tag(sync=True)
    component = traitlets.Unicode("Matrix").tag(sync=True)
    network = traitlets.Dict({}).tag(sync=True)
    network_meta = traitlets.Dict({}).tag(sync=True)
    width = traitlets.Int(600).tag(sync=True)
    height = traitlets.Int(600).tag(sync=True)
    click_info = traitlets.Dict({}).tag(sync=True)

    def __init__(self, **kwargs):
        pq_data = kwargs.pop("parquet_data", None)

        # Allow fallback via a 'matrix' kwarg
        if pq_data is None:
            matrix = kwargs.pop("matrix", None)
            if matrix is not None:
                pq_data = matrix.export_viz_parquet()
            elif "network" not in kwargs:
                raise ValueError(
                    "You must pass either `network`, `parquet_data`, or `matrix` (for fallback). If both `network` and `matrix` are provided, `matrix` will be prioritized."
                )

        # Infer name from pq_data or network
        name = kwargs.get("network", {}).get("name", None)
        if pq_data is not None:
            meta = pq_data.get("meta", {})
            name = meta.get("name", name)
            kwargs.setdefault("network_meta", meta)

            parquet_traits = {
                "mat_parquet": traitlets.Bytes(pq_data.get("mat", b"")).tag(sync=True),
                "row_nodes_parquet": traitlets.Bytes(pq_data.get("row_nodes", b"")).tag(sync=True),
                "col_nodes_parquet": traitlets.Bytes(pq_data.get("col_nodes", b"")).tag(sync=True),
                "row_linkage_parquet": traitlets.Bytes(pq_data.get("row_linkage", b"")).tag(
                    sync=True
                ),
                "col_linkage_parquet": traitlets.Bytes(pq_data.get("col_linkage", b"")).tag(
                    sync=True
                ),
            }
            self.add_traits(**parquet_traits)

        old_widget = _clustergram_registry.get(name)
        if old_widget:
            with suppress(Exception):
                old_widget.close()

        kwargs["name"] = name
        super().__init__(**kwargs)
        _clustergram_registry[name] = self
