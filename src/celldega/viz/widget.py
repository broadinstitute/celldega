"""
Widget module for interactive visualization components.
"""

import colorsys
from collections.abc import Mapping, Sequence
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

_DEFAULT_MANUAL_ATTRIBUTE_TITLES = {
    "row": "manual_cat",
    "col": "manual_cat",
}
_MANUAL_FILL_VALUE = "N.A."
_MANUAL_FILL_COLOR = "#d1d5db"


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

    @traitlets.observe("manual_cat_js")
    def _on_manual_cat_js(self, change) -> None:
        """
        Mirror JS-originated manual category payload into the existing
        `manual_cat` trait so all the current plumbing keeps working.

        JS should set `manual_cat_js` only; Python code should continue
        to read/use `manual_cat` as before.
        """
        if self._manual_sync_block:
            return

        new_val = change.get("new") or "{}"
        # Prevent any echo loops while we write manual_cat
        self._manual_sync_block = True
        try:
            self.manual_cat = new_val
        finally:
            self._manual_sync_block = False


    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()


class DataFrameTrait(traitlets.TraitType):
    """Traitlet that synchronizes a pandas ``DataFrame`` with the frontend."""

    default_value = None
    info_text = "pandas.DataFrame or None"

    def validate(self, obj, value):
        if value is None:
            return None
        if isinstance(value, pd.DataFrame):
            return value
        raise traitlets.TraitError(
            "Expected a pandas DataFrame or None, got %r" % (type(value),)
        )

    @staticmethod
    def _ensure_serializable(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if df.index.name is None:
            df.index.name = "index"
        return df.where(df.notna(), None)

    def to_json(self, value, obj):  # noqa: D401 - traitlets signature
        if value is None:
            return None

        df = self._ensure_serializable(value.copy())
        data = {col: df[col].tolist() for col in df.columns}

        return {
            "columns": list(df.columns),
            "index": df.index.astype(str).tolist(),
            "index_name": df.index.name,
            "data": data,
        }

    def from_json(self, value, obj):  # noqa: D401 - traitlets signature
        if value is None:
            return None

        columns = value.get("columns", [])
        index = value.get("index", [])
        data = value.get("data", {})

        df = pd.DataFrame({col: data.get(col, [None] * len(index)) for col in columns})
        if value.get("index_name") is not None:
            df.index.name = value["index_name"]
        df.index = pd.Index(index)
        if columns:
            df = df.reindex(columns=columns)
        return df

    def equal(self, old, new):  # noqa: D401 - traitlets signature
        if old is None or new is None:
            return old is None and new is None
        if isinstance(old, pd.DataFrame) and isinstance(new, pd.DataFrame):
            return old.equals(new)
        return old is new


class ManualAttributeTrait(traitlets.Unicode):
    """Traitlet for configuring manual attribute names via bools or strings."""

    def __init__(self, *, default_name: str, **kwargs):
        self._default_name = default_name
        super().__init__(default_value="", **kwargs)

    def validate(self, obj, value):  # noqa: D401 - traitlets signature
        if value is None:
            return ""
        if isinstance(value, bool):
            return self._default_name if value else ""
        if isinstance(value, str):
            return super().validate(obj, value.strip())
        return super().validate(obj, str(value).strip())


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

    term_genes = traitlets.List(default_value=[]).tag(sync=True)
    selected_term = traitlets.Unicode("Select Term").tag(sync=True)
    focused_gene = traitlets.Unicode("").tag(sync=True)

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
    row_names = traitlets.List(default_value=[]).tag(sync=True)
    col_names = traitlets.List(default_value=[]).tag(sync=True)

    row_attributes_df = DataFrameTrait(allow_none=True).tag(sync=True)
    col_attributes_df = DataFrameTrait(allow_none=True).tag(sync=True)

    row_attribute_colors = traitlets.Dict(default_value={}).tag(sync=True)
    col_attribute_colors = traitlets.Dict(default_value={}).tag(sync=True)
    manual_row_cat = ManualAttributeTrait(
        default_name=_DEFAULT_MANUAL_ATTRIBUTE_TITLES["row"]
    ).tag(sync=True)
    manual_col_cat = ManualAttributeTrait(
        default_name=_DEFAULT_MANUAL_ATTRIBUTE_TITLES["col"]
    ).tag(sync=True)
    category_colors = traitlets.Dict(default_value={}).tag(sync=True)

    # NEW: raw JS -> PY payload
    manual_cat_js = traitlets.Unicode("").tag(sync=True)

    manual_cat = traitlets.Unicode("{}").tag(sync=True)
    manual_cat_config = traitlets.Unicode("{}").tag(sync=True)

    def __init__(self, **kwargs):
        pq_data = kwargs.pop("parquet_data", None)

        if "network" in kwargs:
            warnings.warn(
                "`network` argument is deprecated. Use `matrix` or `parquet_data` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Allow fallback via a 'matrix' kwarg
        manual_row_flag = kwargs.pop("manual_row_cat", "")
        manual_col_flag = kwargs.pop("manual_col_cat", "")

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
        kwargs["manual_row_cat"] = manual_row_flag
        kwargs["manual_col_cat"] = manual_col_flag
        super().__init__(**kwargs)
        _clustergram_registry[name] = self

        self._manual_sync_block = False
        self._manual_categories = {"row": set(), "col": set()}
        self._manual_config = {"row": None, "col": None}
        self._manual_attribute_titles = {
            "row": self.manual_row_cat or _DEFAULT_MANUAL_ATTRIBUTE_TITLES["row"],
            "col": self.manual_col_cat or _DEFAULT_MANUAL_ATTRIBUTE_TITLES["col"],
        }
        self._manual_axis_enabled = {
            "row": bool(self.manual_row_cat),
            "col": bool(self.manual_col_cat),
        }

        base_colors = dict(self.network_meta.get("global_cat_colors", {}))
        if getattr(self, "category_colors", None):
            base_colors.update(self.category_colors)
        self._category_colors = base_colors
        self.category_colors = deepcopy(self._category_colors)

        self.observe(self._on_manual_cat_change, names="manual_cat")
        self.observe(self._on_manual_config_change, names="manual_cat_config")
        self.observe(self._on_manual_axis_flag_change, names="manual_row_cat")
        self.observe(self._on_manual_axis_flag_change, names="manual_col_cat")
        self.observe(self._on_axis_names_change, names="row_names")
        self.observe(self._on_axis_names_change, names="col_names")

        # Initialize manual category state from existing trait values
        self._on_manual_config_change({"new": self.manual_cat_config})
        self._on_manual_cat_change({"new": self.manual_cat})
        self._maybe_initialize_manual_axis("row")
        self._maybe_initialize_manual_axis("col")

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()

    @staticmethod
    def _normalize_axis(axis: str) -> str:
        axis_lower = str(axis).lower()
        if axis_lower.startswith("col"):
            return "col"
        if axis_lower.startswith("row"):
            return "row"
        raise ValueError("axis must be 'row' or 'col'")

    def _axis_index(self, axis: str) -> pd.Index:
        names = getattr(self, f"{axis}_names", []) or []
        return pd.Index([str(name) for name in names], name=f"{axis}_id")

    def _get_axis_dataframe(self, axis: str) -> pd.DataFrame:
        existing = getattr(self, f"{axis}_attributes_df")
        index = self._axis_index(axis)
        if existing is None or existing.empty:
            return pd.DataFrame(index=index)
        return existing.reindex(index)

    def _set_axis_dataframe(self, axis: str, dataframe: pd.DataFrame) -> None:
        if dataframe.empty:
            setattr(self, f"{axis}_attributes_df", None)
        else:
            setattr(self, f"{axis}_attributes_df", dataframe)

    def _record_category_colors(self, mapping: Mapping | None) -> None:
        if not mapping:
            return

        updated = False
        for name, color in mapping.items():
            if name is None or color is None:
                continue
            normalized_name = str(name)
            normalized_color = str(color)
            if self._category_colors.get(normalized_name) != normalized_color:
                self._category_colors[normalized_name] = normalized_color
                updated = True

        if updated:
            self.category_colors = deepcopy(self._category_colors)

    def _default_manual_attribute_name(self, axis: str) -> str | None:
        """Return the configured manual attribute name for an axis, if any."""

        normalized_axis = self._normalize_axis(axis)
        entry = (self._manual_config or {}).get(normalized_axis)
        if entry is None and self._manual_axis_enabled.get(normalized_axis):
            entry = self._ensure_manual_config_entry(normalized_axis)
        attribute = (entry or {}).get("attribute")
        if attribute:
            return str(attribute)
        if self._manual_axis_enabled.get(normalized_axis):
            return self._manual_attribute_titles.get(normalized_axis)
        return None

    def _is_default_manual_attribute(self, axis: str, attribute: str | None) -> bool:
        if attribute is None:
            return False
        manual_name = self._default_manual_attribute_name(axis)
        return bool(manual_name and str(attribute) == manual_name)

    def _fill_manual_attribute_defaults(
        self,
        axis: str,
        attribute: str,
        dataframe: pd.DataFrame,
        colors: dict[str, dict[str, str]],
    ) -> None:
        if not self._is_default_manual_attribute(axis, attribute):
            return

        if attribute not in dataframe.columns:
            dataframe[attribute] = _MANUAL_FILL_VALUE
        else:
            dataframe[attribute] = dataframe[attribute].where(
                dataframe[attribute].notna(), _MANUAL_FILL_VALUE
            )

        attr_colors = dict(colors.get(attribute) or {})
        if attr_colors.get(_MANUAL_FILL_VALUE) != _MANUAL_FILL_COLOR:
            attr_colors[_MANUAL_FILL_VALUE] = _MANUAL_FILL_COLOR
            colors[attribute] = attr_colors
            self._record_category_colors({_MANUAL_FILL_VALUE: _MANUAL_FILL_COLOR})

    def _ensure_manual_config_entry(self, axis: str) -> dict[str, object]:
        normalized_axis = self._normalize_axis(axis)
        config = self._load_manual_config(self.manual_cat_config)
        entry = dict(config.get(normalized_axis) or {})
        changed = False

        if not entry.get("attribute"):
            entry["attribute"] = self._manual_attribute_titles[normalized_axis]
            changed = True

        if entry.get("preferred") is None:
            entry["preferred"] = []
            changed = True

        if "locked" not in entry:
            entry["locked"] = True
            changed = True

        if config.get(normalized_axis) != entry:
            config[normalized_axis] = entry
            changed = True

        if changed:
            self.manual_cat_config = json.dumps(config)

        self._manual_config = config
        return entry

    def _maybe_initialize_manual_axis(self, axis: str) -> None:
        normalized_axis = self._normalize_axis(axis)
        if not self._manual_axis_enabled.get(normalized_axis):
            return

        config_entry = self._ensure_manual_config_entry(normalized_axis)
        attribute = (
            config_entry.get("attribute")
            or self._manual_attribute_titles[normalized_axis]
        )

        index = self._axis_index(normalized_axis)
        if index.empty:
            return

        dataframe = self._get_axis_dataframe(normalized_axis)
        dataframe = dataframe.reindex(index)
        if attribute not in dataframe.columns:
            dataframe[attribute] = _MANUAL_FILL_VALUE
        else:
            dataframe[attribute] = dataframe[attribute].where(
                dataframe[attribute].notna(), _MANUAL_FILL_VALUE
            )

        colors = dict(getattr(self, f"{normalized_axis}_attribute_colors") or {})
        attr_colors = dict(colors.get(attribute) or {})
        attr_colors.setdefault(_MANUAL_FILL_VALUE, _MANUAL_FILL_COLOR)
        colors[attribute] = attr_colors

        self._manual_categories[normalized_axis].add(attribute)

        self._manual_sync_block = True
        try:
            self._set_axis_dataframe(normalized_axis, dataframe)
            setattr(self, f"{normalized_axis}_attribute_colors", colors)
            self.manual_cat = json.dumps(self._export_manual_payload())
        finally:
            self._manual_sync_block = False

        self._record_category_colors({_MANUAL_FILL_VALUE: attr_colors[_MANUAL_FILL_VALUE]})

    def _on_manual_axis_flag_change(self, change) -> None:
        axis = "row" if change["name"] == "manual_row_cat" else "col"
        value = str(change["new"] or "").strip()
        self._manual_attribute_titles[axis] = (
            value or _DEFAULT_MANUAL_ATTRIBUTE_TITLES[axis]
        )
        self._manual_axis_enabled[axis] = bool(value)
        if value:
            self._ensure_manual_config_entry(axis)
            self._maybe_initialize_manual_axis(axis)

    def _on_axis_names_change(self, change) -> None:
        axis = "row" if change["name"] == "row_names" else "col"
        self._maybe_initialize_manual_axis(axis)

    def _parse_manual_payload(self, payload) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
        result: dict[str, dict[str, dict[str, dict[str, str]]]] = {"row": {}, "col": {}}

        if payload is None:
            return result

        if isinstance(payload, str):
            try:
                payload = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                return result

        if not isinstance(payload, dict):
            return result

        for axis in ("row", "col"):
            axis_payload = payload.get(axis, {})
            if not isinstance(axis_payload, dict):
                continue

            normalized_axis: dict[str, dict[str, dict[str, str]]] = {}
            for attr_name, entry in axis_payload.items():
                values: Mapping | None
                colors: Mapping | None
                if isinstance(entry, dict) and (
                    "values" in entry or "colors" in entry
                ):
                    values = entry.get("values", {})
                    colors = entry.get("colors", {})
                else:
                    values = entry
                    colors = {}

                if not isinstance(values, Mapping):
                    values = {}
                if not isinstance(colors, Mapping):
                    colors = {}

                normalized_axis[str(attr_name)] = {
                    "values": {
                        str(key): None if val is None else str(val)
                        for key, val in values.items()
                    },
                    "colors": {
                        str(key): str(val)
                        for key, val in colors.items()
                        if val is not None
                    },
                }

            result[axis] = normalized_axis

        return result

    def _export_manual_payload(self) -> dict[str, dict[str, dict[str, dict[str, str]]]]:
        export: dict[str, dict[str, dict[str, dict[str, str]]]] = {"row": {}, "col": {}}

        for axis in ("row", "col"):
            dataframe = getattr(self, f"{axis}_attributes_df")
            if dataframe is None or dataframe.empty:
                continue

            colors = getattr(self, f"{axis}_attribute_colors") or {}
            for attribute in self._manual_categories[axis]:
                if attribute not in dataframe.columns:
                    continue
                series = dataframe[attribute].dropna()
                if series.empty:
                    continue

                export[axis][attribute] = {
                    "values": {
                        str(index): str(value)
                        for index, value in series.items()
                    },
                    "colors": {
                        str(name): str(color)
                        for name, color in (colors.get(attribute) or {}).items()
                    },
                }

        return export

    def _apply_manual_payload(self, payload) -> None:
        parsed = self._parse_manual_payload(payload)

        for axis in ("row", "col"):
            axis_payload = parsed.get(axis, {})
            dataframe = self._get_axis_dataframe(axis)
            colors = dict(getattr(self, f"{axis}_attribute_colors") or {})

            incoming_attributes = set(axis_payload.keys())
            default_attribute = self._default_manual_attribute_name(axis)
            if default_attribute:
                incoming_attributes.add(default_attribute)
            previous_attributes = set(self._manual_categories[axis])

            for attribute in previous_attributes - incoming_attributes:
                if self._is_default_manual_attribute(axis, attribute):
                    continue
                if attribute in dataframe.columns:
                    dataframe = dataframe.drop(columns=[attribute])
                colors.pop(attribute, None)

            for attribute, entry in axis_payload.items():
                values = entry.get("values", {})
                colors_map = entry.get("colors", {})

                series = pd.Series(
                    {
                        str(index): None if value is None else str(value)
                        for index, value in values.items()
                    }
                )

                dataframe[attribute] = None
                if not series.empty:
                    series.index = series.index.map(str)
                    aligned = dataframe.index.intersection(series.index)
                    dataframe.loc[aligned, attribute] = series.loc[aligned]

                if colors_map:
                    colors[attribute] = {
                        str(name): str(color)
                        for name, color in colors_map.items()
                    }
                    self._record_category_colors(colors_map)

                self._fill_manual_attribute_defaults(axis, attribute, dataframe, colors)

            if default_attribute:
                self._fill_manual_attribute_defaults(
                    axis, default_attribute, dataframe, colors
                )

            # Remove columns that are entirely null
            for attribute in list(incoming_attributes):
                if attribute in dataframe.columns and dataframe[attribute].isna().all():
                    if self._is_default_manual_attribute(axis, attribute):
                        continue
                    dataframe = dataframe.drop(columns=[attribute])
                    colors.pop(attribute, None)
                    incoming_attributes.discard(attribute)

            self._manual_categories[axis] = incoming_attributes
            self._set_axis_dataframe(axis, dataframe)
            setattr(self, f"{axis}_attribute_colors", colors)

    def _normalize_preferred(
        self,
        preferred,
    ) -> list[dict[str, str]]:
        if preferred is None:
            return []

        if isinstance(preferred, pd.DataFrame):
            normalized: list[dict[str, str]] = []
            for index, row in preferred.iterrows():
                color_value = row.get("color", "")
                normalized.append(
                    {
                        "name": str(index),
                        "color": str(color_value) if color_value is not None else "",
                    }
                )
            return normalized

        if isinstance(preferred, Mapping):
            return [
                {"name": str(name), "color": str(color)}
                for name, color in preferred.items()
            ]

        if isinstance(preferred, Sequence) and not isinstance(preferred, (str, bytes)):
            normalized: list[dict[str, str]] = []
            for entry in preferred:
                if isinstance(entry, Mapping) and "name" in entry:
                    normalized.append(
                        {
                            "name": str(entry["name"]),
                            "color": str(entry.get("color", "")),
                        }
                    )
                else:
                    normalized.append({"name": str(entry), "color": ""})
            return normalized

        raise TypeError(
            "preferred categories must be a pandas DataFrame, mapping, or sequence"
        )

    def _load_manual_config(self, value) -> dict[str, dict[str, str] | None]:
        if isinstance(value, str):
            try:
                parsed = json.loads(value) if value else {}
            except json.JSONDecodeError:
                parsed = {}
        elif isinstance(value, dict):
            parsed = value
        else:
            parsed = {}

        config: dict[str, dict[str, str] | None] = {"row": None, "col": None}
        for axis in ("row", "col"):
            entry = parsed.get(axis)
            if not isinstance(entry, dict):
                continue

            attribute = entry.get("attribute")
            preferred = entry.get("preferred", [])
            normalized_preferred: list[dict[str, str]] = []
            if isinstance(preferred, list):
                for item in preferred:
                    if isinstance(item, dict) and "name" in item:
                        normalized_preferred.append(
                            {
                                "name": str(item["name"]),
                                "color": str(item.get("color", "")),
                            }
                        )

            config[axis] = {
                "attribute": str(attribute) if attribute is not None else None,
                "preferred": normalized_preferred,
                "locked": bool(entry.get("locked")),
            }

        return config

    def _on_manual_cat_change(self, change) -> None:
        if self._manual_sync_block:
            return

        payload = change.get("new") if isinstance(change, dict) else change
        self._apply_manual_payload(payload)

    def _on_manual_config_change(self, change) -> None:
        value = change.get("new") if isinstance(change, dict) else change
        self._manual_config = self._load_manual_config(value)

    def set_manual_category(
        self,
        *,
        row: str | None = None,
        col: str | None = None,
        preferred_cats=None,
        row_preferred=None,
        col_preferred=None,
        row_locked: bool | None = None,
        col_locked: bool | None = None,
    ) -> None:
        """Configure the manual category editor defaults for rows and columns."""

        config = self._load_manual_config(self.manual_cat_config)

        if row is not None:
            preferred = (
                self._normalize_preferred(row_preferred)
                if row_preferred is not None
                else self._normalize_preferred(preferred_cats)
            )
            config["row"] = {
                "attribute": str(row),
                "preferred": preferred,
                "locked": bool(row_locked) if row_locked is not None else bool(config.get("row", {}).get("locked")),
            }

        if col is not None:
            preferred = (
                self._normalize_preferred(col_preferred)
                if col_preferred is not None
                else self._normalize_preferred(preferred_cats)
            )
            config["col"] = {
                "attribute": str(col),
                "preferred": preferred,
                "locked": bool(col_locked) if col_locked is not None else bool(config.get("col", {}).get("locked")),
            }

        self.manual_cat_config = json.dumps(config)

    def apply_manual_category(
        self,
        axis: str,
        attribute: str,
        assignments,
        colors: Mapping[str, str] | None = None,
    ) -> None:
        """Assign manual categories for the specified axis."""

        axis_name = self._normalize_axis(axis)
        dataframe = self._get_axis_dataframe(axis_name)
        color_map = dict(getattr(self, f"{axis_name}_attribute_colors") or {})

        if isinstance(assignments, pd.Series):
            mapping = {
                str(index): None if value is None else str(value)
                for index, value in assignments.items()
            }
        elif isinstance(assignments, Mapping):
            mapping = {
                str(index): None if value is None else str(value)
                for index, value in assignments.items()
            }
        else:
            raise TypeError("assignments must be a pandas Series or mapping")

        series = pd.Series(mapping)
        if attribute not in dataframe.columns:
            dataframe[attribute] = None

        if not series.empty:
            series.index = series.index.map(str)
            aligned = dataframe.index.intersection(series.index)
            dataframe.loc[aligned, attribute] = series.loc[aligned]

        if colors:
            color_map[attribute] = {
                **color_map.get(attribute, {}),
                **{str(name): str(color) for name, color in colors.items()},
            }
            self._record_category_colors(colors)

        self._fill_manual_attribute_defaults(axis_name, attribute, dataframe, color_map)

        if (
            attribute in dataframe.columns
            and dataframe[attribute].isna().all()
            and not self._is_default_manual_attribute(axis_name, attribute)
        ):
            dataframe = dataframe.drop(columns=[attribute])
            color_map.pop(attribute, None)
            self._manual_categories[axis_name].discard(attribute)
        else:
            self._manual_categories[axis_name].add(attribute)

        self._manual_sync_block = True
        try:
            self._set_axis_dataframe(axis_name, dataframe)
            setattr(self, f"{axis_name}_attribute_colors", color_map)
            self.manual_cat = json.dumps(self._export_manual_payload())
        finally:
            self._manual_sync_block = False

    def clear_manual_category(
        self,
        axis: str,
        attribute: str | None = None,
    ) -> None:
        """Clear manual category assignments for an axis."""

        axis_name = self._normalize_axis(axis)
        dataframe = self._get_axis_dataframe(axis_name)
        color_map = dict(getattr(self, f"{axis_name}_attribute_colors") or {})

        if attribute is None:
            targets = list(self._manual_categories[axis_name])
        else:
            targets = [str(attribute)]

        for attr in targets:
            if self._is_default_manual_attribute(axis_name, attr):
                if attr not in dataframe.columns:
                    dataframe[attr] = None
                self._fill_manual_attribute_defaults(axis_name, attr, dataframe, color_map)
                self._manual_categories[axis_name].add(attr)
                continue

            if attr in dataframe.columns:
                dataframe = dataframe.drop(columns=[attr])
            color_map.pop(attr, None)
            self._manual_categories[axis_name].discard(attr)

        self._manual_sync_block = True
        try:
            self._set_axis_dataframe(axis_name, dataframe)
            setattr(self, f"{axis_name}_attribute_colors", color_map)
            self.manual_cat = json.dumps(self._export_manual_payload())
        finally:
            self._manual_sync_block = False

    def get_manual_category(
        self, axis: str, attribute: str | None = None
    ) -> pd.Series:
        """Return manual category assignments for an axis/attribute."""

        axis_name = self._normalize_axis(axis)
        target_attribute = (
            str(attribute)
            if attribute is not None
            else self._default_manual_attribute_name(axis_name)
        )
        if not target_attribute:
            raise KeyError(
                f"Manual attribute is not configured for axis '{axis_name}'"
            )

        dataframe = getattr(self, f"{axis_name}_attributes_df")
        if dataframe is None or target_attribute not in dataframe.columns:
            raise KeyError(
                f"Manual attribute '{target_attribute}' not found for axis '{axis_name}'"
            )

        series = dataframe[target_attribute].dropna()
        if self._is_default_manual_attribute(axis_name, target_attribute):
            series = series[series != _MANUAL_FILL_VALUE]

        series.index = series.index.map(str)
        return series
