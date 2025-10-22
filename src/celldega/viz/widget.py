"""
Widget module for interactive visualization components.
"""

import colorsys
from contextlib import suppress
from copy import deepcopy
import json
from pathlib import Path
import urllib.error
import warnings

import anywidget
import geopandas as gpd
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc
from shapely.affinity import affine_transform
import traitlets


_clustergram_registry = {}  # maps names to widget instances
_enrich_registry = {}  # maps names to widget instances


def _hsv_to_hex(h: float) -> str:
    """Convert HSV color to hex string."""
    r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.9)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class Landscape(anywidget.AnyWidget):
    """
    A widget for interactive visualization of spatial omics data. This widget
    currently supports iST (Xenium and MERSCOPE) and sST (Visium HD data, with and without cell segmentation)

    Args:
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        rotation_orbit (float, optional): Rotating angle around orbit axis for point-cloud views.
        rotation_x (float, optional): Rotating angle around X axis for point-cloud views.
        token (str): The token traitlet.
        base_url (str): The base URL for the widget.
        AnnData (AnnData, optional): AnnData object to derive metadata from.
        dataset_name (str, optional): The name of the dataset to visualize. This will show up in the user interface bar.

    The AnnData input automatically extracts cell attributes (e.g., ``leiden``
    clusters), the corresponding colors (or derives them when missing), and any
    available UMAP coordinates.

    Attributes:
        component (str): The name of the component.
        technology (str): The technology used.
        base_url (str): The base URL for the widget.
        token (str): The token traitlet.
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_z (float): The initial z-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        rotation_orbit (float): Rotating angle around orbit axis for point-cloud views.
        rotation_x (float): Rotating angle around X axis for point-cloud views.
        dataset_name (str): The name of the dataset to visualize.
        update_trigger (dict): The dictionary to trigger updates.
        cell_clusters (dict): The dictionary containing cell cluster information.

    Returns:
        Landscape: A widget for visualizing a 'landscape' view of spatial omics data.
    """

    _esm = Path(__file__).parent / "../static" / "widget.js"
    _css = Path(__file__).parent / "../static" / "widget.css"
    component = traitlets.Unicode("Landscape").tag(sync=True)

    technology = traitlets.Unicode("Xenium").tag(sync=True)
    base_url = traitlets.Unicode("").tag(sync=True)
    token = traitlets.Unicode("").tag(sync=True)
    creds = traitlets.Dict({}).tag(sync=True)
    max_tiles_to_view = traitlets.Int(50).tag(sync=True)
    ini_x = traitlets.Float().tag(sync=True)
    ini_y = traitlets.Float().tag(sync=True)
    ini_z = traitlets.Float().tag(sync=True)
    ini_zoom = traitlets.Float(0).tag(sync=True)
    rotation_orbit = traitlets.Float(0).tag(sync=True)
    rotation_x = traitlets.Float(0).tag(sync=True)
    square_tile_size = traitlets.Float(1.4).tag(sync=True)
    dataset_name = traitlets.Unicode("").tag(sync=True)
    region = traitlets.Dict({}).tag(sync=True)

    nbhd = traitlets.Instance(gpd.GeoDataFrame, allow_none=True)
    nbhd_geojson = traitlets.Dict({}).tag(sync=True)

    # Enable editing of neighborhoods when True
    nbhd_edit = traitlets.Bool(False).tag(sync=True)

    meta_nbhd = traitlets.Instance(pd.DataFrame, allow_none=True)

    meta_cluster = traitlets.Dict({}).tag(sync=True)
    landscape_state = traitlets.Unicode("spatial").tag(sync=True)

    update_trigger = traitlets.Dict().tag(sync=True)
    cell_clusters = traitlets.Dict({}).tag(sync=True)

    # make a traitlet for cell_attr a list that will have the AnnData obs columns
    cell_attr = traitlets.List(trait=traitlets.Unicode(), default_value=["leiden"]).tag(sync=True)

    segmentation = traitlets.Unicode("default").tag(sync=True)

    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(800).tag(sync=True)

    def __init__(self, **kwargs):
        adata = kwargs.pop("adata", None) or kwargs.pop("AnnData", None)
        pq_meta_cell = kwargs.pop("meta_cell_parquet", None)
        pq_meta_cluster = kwargs.pop("meta_cluster_parquet", None)
        pq_umap = kwargs.pop("umap_parquet", None)
        pq_meta_nbhd = kwargs.pop("meta_nbhd_parquet", None)

        meta_cell_df = kwargs.pop("meta_cell", None)
        meta_cluster = kwargs.pop("meta_cluster", None)
        umap_df = kwargs.pop("umap", None)
        nbhd_gdf = kwargs.pop("nbhd", None)
        meta_nbhd_df = kwargs.pop("meta_nbhd", None)
        nbhd_edit = kwargs.pop("nbhd_edit", False)
        meta_cluster_df = None
        cell_attr = kwargs.pop("cell_attr", ["leiden"])

        if nbhd_gdf is not None and nbhd_edit:
            raise ValueError("nbhd_edit cannot be True when nbhd data is provided")

        base_path = (kwargs.get("base_url") or "") + "/"

        path_transformation_matrix = base_path + "micron_to_image_transform.csv"

        try:
            transformation_matrix = pd.read_csv(
                path_transformation_matrix, header=None, sep=" "
            ).values
        except (FileNotFoundError, urllib.error.HTTPError, urllib.error.URLError):
            transformation_matrix = np.eye(3)  # Fallback for testing
            warnings.warn(
                f"Transformation matrix not found at {path_transformation_matrix}. Using identity.",
                stacklevel=2,
            )

        self._transformation_matrix = transformation_matrix
        try:
            self._inv_transform = np.linalg.inv(transformation_matrix)
        except np.linalg.LinAlgError as e:
            self._inv_transform = np.eye(3)
            warnings.warn(
                f"Matrix inversion failed for transformation_matrix: {e}. Using identity matrix as fallback.",
                stacklevel=2,
            )

        def _df_to_bytes(df):
            import io

            import pyarrow as pa
            import pyarrow.parquet as pq

            df.columns = df.columns.map(str)
            buf = io.BytesIO()
            pq.write_table(pa.Table.from_pandas(df), buf, compression="zstd")
            return buf.getvalue()

        if adata is not None:
            # if cell_id is in the adata.obs, use it as index
            if "cell_id" in adata.obs.columns:
                adata.obs.set_index("cell_id", inplace=True)

            meta_cell_df = adata.obs[cell_attr].copy()

            if meta_cell_df.index.name is None:
                meta_cell_df.index.name = "cell_id"

            pq_meta_cell = _df_to_bytes(meta_cell_df)

            if "leiden" in adata.obs.columns:
                cluster_counts = adata.obs["leiden"].value_counts().sort_index()
                colors = adata.uns.get("leiden_colors")

                if colors is None:
                    with suppress(Exception):
                        sc.pl.umap(adata, color="leiden", show=False)
                        plt.close()
                        colors = adata.uns.get("leiden_colors")

                # backup color definition
                if colors is None:
                    n = len(cluster_counts)
                    colors = [_hsv_to_hex(i / n) for i in range(n)]

                meta_cluster_df = pd.DataFrame(
                    {
                        "color": list(colors)[: len(cluster_counts)],
                        "count": cluster_counts.values,
                    },
                    index=cluster_counts.index,
                )

                pq_meta_cluster = _df_to_bytes(meta_cluster_df)

            if "X_umap" in adata.obsm:
                umap_df = (
                    pd.DataFrame(adata.obsm["X_umap"], index=adata.obs.index)
                    .reset_index()
                    .rename(columns={"index": "cell_id", 0: "umap_0", 1: "umap_1"})
                )
                pq_umap = _df_to_bytes(umap_df)

        if isinstance(meta_cell_df, pd.DataFrame):
            pq_meta_cell = _df_to_bytes(meta_cell_df.reset_index())

        if isinstance(meta_cluster, pd.DataFrame):
            pq_meta_cluster = _df_to_bytes(meta_cluster.reset_index())
            kwargs.pop("meta_cluster")
            meta_cluster_df = meta_cluster

        if isinstance(umap_df, pd.DataFrame):
            pq_umap = _df_to_bytes(umap_df)

        if isinstance(meta_nbhd_df, pd.DataFrame):
            pq_meta_nbhd = _df_to_bytes(meta_nbhd_df.reset_index())

        parquet_traits = {}
        if pq_meta_cell is not None:
            parquet_traits["meta_cell_parquet"] = traitlets.Bytes(pq_meta_cell).tag(sync=True)
        if pq_meta_cluster is not None:
            parquet_traits["meta_cluster_parquet"] = traitlets.Bytes(pq_meta_cluster).tag(sync=True)
        if pq_umap is not None:
            parquet_traits["umap_parquet"] = traitlets.Bytes(pq_umap).tag(sync=True)
        if pq_meta_nbhd is not None:
            parquet_traits["meta_nbhd_parquet"] = traitlets.Bytes(pq_meta_nbhd).tag(sync=True)

        if parquet_traits:
            self.add_traits(**parquet_traits)

        super().__init__(**kwargs)

        # store DataFrames locally without syncing to the frontend
        self.meta_cell = meta_cell_df
        self.meta_nbhd = meta_nbhd_df
        self.nbhd = nbhd_gdf
        self.nbhd_edit = nbhd_edit
        self.umap = umap_df
        if meta_cluster_df is not None:
            self.meta_cluster_df = meta_cluster_df

        # compute geojson for initial nbhd if provided
        if self.nbhd is not None:
            if "geometry_pixel" not in self.nbhd.columns:
                # Assuming `transformation_matrix` is your 3x3 numpy array
                a, b, tx = transformation_matrix[0]
                c, d, ty = transformation_matrix[1]

                coeffs = [a, b, c, d, tx, ty]

                self.nbhd["geometry_pixel"] = self.nbhd.geometry.apply(
                    lambda geom: affine_transform(geom, coeffs)
                )

            gdf_viz = deepcopy(self.nbhd)
            gdf_viz["geometry"] = gdf_viz["geometry_pixel"]
            gdf_viz.drop(columns=["geometry_pixel"], inplace=True)

            self.nbhd_geojson = json.loads(gdf_viz.to_json())
        elif self.nbhd_edit:
            self.nbhd_geojson = {"type": "FeatureCollection", "features": []}

    # @traitlets.observe("nbhd")
    # def _on_nbhd_change(self, change):
    #     new = change["new"]
    #     if new is None:
    #         self.nbhd_geojson = {"type": "FeatureCollection", "features": []}
    #     else:
    #         self.nbhd_geojson = json.loads(new.to_json())

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

    @traitlets.observe("nbhd_geojson")
    def _on_nbhd_geojson_change(self, change):
        """Update ``nbhd`` GeoDataFrame when the GeoJSON changes."""
        if not getattr(self, "nbhd_edit", False):
            return

        new = change["new"]
        if not new:
            self.nbhd = gpd.GeoDataFrame(columns=["name", "geometry"], geometry="geometry")
            return

        gdf = gpd.GeoDataFrame.from_features(new.get("features", []))

        try:
            a, b, tx = self._inv_transform[0]
            c, d, ty = self._inv_transform[1]
            coeffs = [a, b, c, d, tx, ty]
            gdf["geometry"] = gdf.geometry.apply(lambda geom: affine_transform(geom, coeffs))
        except Exception:
            pass

        self.nbhd = gdf

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class Enrich(anywidget.AnyWidget):
    """
    A widget for interactive enrichment analysis using the Enrichr API.
    This widget allows users to select a gene list, choose an enrichment library,
    and specify the number of terms to display.
    Automatically replaces older widgets with the same name to prevent notebook bloat.
    Args:
        value (int): The value traitlet.
        component (str): The component traitlet.
        gene_list (list): The list of genes to analyze.
        available_libs (list): The list of available enrichment libraries.
        inst_lib (str): The selected enrichment library.
        num_terms (int): The number of terms to display.
    """

    _esm = Path(__file__).parent / "../static" / "widget.js"
    _css = Path(__file__).parent / "../static" / "widget.css"

    value = traitlets.Int(0).tag(sync=True)
    width = traitlets.Int(650).tag(sync=True)
    height = traitlets.Int(650).tag(sync=True)

    component = traitlets.Unicode("Enrich").tag(sync=True)

    # gene list
    gene_list = traitlets.List(default_value=[]).tag(sync=True)

    # optional background gene list
    background_list = traitlets.List(allow_none=True, default_value=None).tag(sync=True)

    # available enrichment libraries
    available_libs = traitlets.List(
        [
            "CellMarker_2024",
            "ARCHS4_Tissues",
            "GO_Biological_Process_2025",
            "GO_Cellular_Component_2025",
            "GO_Molecular_Function_2025",
            "GTEx_Tissue_Expression_Up",
            "KEGG_2019_Human",
            "ChEA_2022",
            "MGI_Mammalian_Phenotype_Level_4_2024",
            "Disease_Perturbations_from_GEO_up",
            "Ligand_Perturbations_from_GEO_up",
            "LINCS_L1000_Chem_Pert_down",
            "Ligand_Perturbations_from_GEO_down",
        ]
    ).tag(sync=True)

    # enrichment library
    inst_lib = traitlets.Unicode("CellMarker_2024").tag(sync=True)

    # number of terms
    num_terms = traitlets.Int(50).tag(sync=True)

    def __init__(self, **kwargs):
        name = kwargs.pop("name", "default")
        old_widget = _enrich_registry.get(name)
        if old_widget:
            with suppress(Exception):
                old_widget.close()

        kwargs["name"] = name
        super().__init__(**kwargs)
        _enrich_registry[name] = self

    def close(self):  # pragma: no cover - cleanup depends on JS
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class Clustergram(anywidget.AnyWidget):
    """
    A widget for interactive visualization of a hierarchically clustered matrix.

    Automatically replaces older widgets with the same name to prevent notebook bloat.

    Args:
        value (int): The value traitlet.
        component (str): The component traitlet.
        network (dict): **Deprecated.** Use ``matrix`` or ``parquet_data``.
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
    selected_genes = traitlets.List(default_value=[]).tag(sync=True)
    top_n_genes = traitlets.Int(50).tag(sync=True)

    def __init__(self, **kwargs):
        pq_data = kwargs.pop("parquet_data", None)

        if "network" in kwargs:
            warnings.warn(
                "`network` argument is deprecated. Use `matrix` or `parquet_data` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

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

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()
