"""Widget module for interactive visualization components."""

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

_DEFAULT_MANUAL_ATTRIBUTE_TITLES = {
    "row": "manual_cat",
    "col": "manual_cat",
}
_MANUAL_FILL_VALUE = "N.A."


def _hsv_to_hex(h: float) -> str:
    """Convert HSV color to hex string."""
    r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.9)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class Landscape(anywidget.AnyWidget):
    """
    A widget for interactive visualization of spatial omics data. This widget
    currently supports iST (Xenium and MERSCOPE) and sST (Visium HD data, with and
    without cell segmentation).

    Args:
        ini_x (float): The initial x-coordinate of the view.
        ini_y (float): The initial y-coordinate of the view.
        ini_zoom (float): The initial zoom level of the view.
        rotation_orbit (float, optional): Rotating angle around orbit axis for
            point-cloud views.
        rotation_x (float, optional): Rotating angle around X axis for
            point-cloud views.
        token (str): The token traitlet.
        base_url (str): The base URL for the widget.
        AnnData (AnnData, optional): AnnData object to derive metadata from.
        dataset_name (str, optional): The name of the dataset to visualize. This
            will show up in the user interface bar.

    The AnnData input automatically extracts cell attributes (e.g., ``leiden``
    clusters), the corresponding colors (or derives them when missing), and any
    available UMAP coordinates.
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
    selected_cells = traitlets.List(
        trait=traitlets.Unicode(), default_value=[]
    ).tag(sync=True)
    landscape_state = traitlets.Unicode("spatial").tag(sync=True)

    update_trigger = traitlets.Dict().tag(sync=True)
    cell_clusters = traitlets.Dict({}).tag(sync=True)

    # AnnData obs columns (cell attributes)
    cell_attr = traitlets.List(
        trait=traitlets.Unicode(),
        default_value=["leiden"],
    ).tag(sync=True)

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
                f"Matrix inversion failed for transformation_matrix: {e}. "
                "Using identity matrix as fallback.",
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

    def trigger_update(self, new_value):
        """Update the update_trigger traitlet with a new value."""
        self.update_trigger = new_value

    def update_cell_clusters(self, new_clusters):
        """Update cell clusters with new data."""
        self.cell_clusters = new_clusters

    def highlight_cells(self, cell_ids):
        """Highlight specific cells by their identifiers."""

        self.selected_cells = list(cell_ids)

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


class ManualAttributeTrait(traitlets.Unicode):
    """Traitlet for configuring manual attribute names via bools or strings."""

    def __init__(self, *, default_name: str, **kwargs):
        self._default_name = default_name
        super().__init__(default_value="", **kwargs)

    def validate(self, obj, value):
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

    Allows users to select a gene list, choose an enrichment library, and specify
    the number of terms to display. Automatically replaces older widgets with the
    same name to prevent notebook bloat.
    """

    _esm = Path(__file__).parent / "../static" / "widget.js"
    _css = Path(__file__).parent / "../static" / "widget.css"

    value = traitlets.Int(0).tag(sync=True)
    width = traitlets.Int(650).tag(sync=True)
    height = traitlets.Int(650).tag(sync=True)

    component = traitlets.Unicode("Enrich").tag(sync=True)

    gene_list = traitlets.List(default_value=[]).tag(sync=True)
    background_list = traitlets.List(allow_none=True, default_value=None).tag(sync=True)

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

    inst_lib = traitlets.Unicode("CellMarker_2024").tag(sync=True)
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
    Minimal version of the Clustergram widget.

    - Frontend still gets: matrix/parquet data, row/col names, manual_cat,
      manual_cat_config, etc.
    - Manual categories are treated as a simple JSON string.
    - All the old DataFrame-based manual_cat plumbing is removed.
    """

    _esm = Path(__file__).parent / "../static" / "widget.js"
    _css = Path(__file__).parent / "../static" / "widget.css"

    # --- core traits used by JS -------------------------------------------------
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

    # backend-only DataFrames derived from `manual_cat`
    row_manual_df = traitlets.Instance(pd.DataFrame, allow_none=True)
    col_manual_df = traitlets.Instance(pd.DataFrame, allow_none=True)
    row_manual_colors_df = traitlets.Instance(pd.DataFrame, allow_none=True)
    col_manual_colors_df = traitlets.Instance(pd.DataFrame, allow_none=True)

    # Flags that control whether manual categories are shown in the UI.
    manual_row_cat = ManualAttributeTrait(default_name=_DEFAULT_MANUAL_ATTRIBUTE_TITLES["row"]).tag(
        sync=True
    )
    manual_col_cat = ManualAttributeTrait(default_name=_DEFAULT_MANUAL_ATTRIBUTE_TITLES["col"]).tag(
        sync=True
    )

    # Global color registry (JS may write here; Python can also seed it)
    category_colors = traitlets.Dict(default_value={}).tag(sync=True)

    # Canonical manual category payload as JSON string.
    manual_cat = traitlets.Unicode("{}").tag(sync=True)

    # Small JSON object describing default attribute names, preferred
    # categories, etc.
    manual_cat_config = traitlets.Unicode("{}").tag(sync=True)

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        parquet_data : dict, optional
            Pre-exported parquet payload from your matrix object.
        matrix : object, optional
            If provided and has .export_viz_parquet(), we'll call that.
        network : dict, optional
            Deprecated path, kept only for backwards-compatibility.
        """
        pq_data = kwargs.pop("parquet_data", None)

        if "network" in kwargs:
            warnings.warn(
                "`network` argument is deprecated. Use `matrix` or `parquet_data` instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        manual_row_flag = kwargs.pop("manual_row_cat", "")
        manual_col_flag = kwargs.pop("manual_col_cat", "")

        if pq_data is None:
            matrix = kwargs.pop("matrix", None)
            if matrix is not None:
                pq_data = matrix.export_viz_parquet()
            elif "network" not in kwargs:
                raise ValueError(
                    "You must pass either `network`, `parquet_data`, or `matrix` (for fallback). "
                    "If both `network` and `matrix` are provided, `matrix` will be prioritized."
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

        # ------------------------------------------------------------------
        # Initialize a simple manual_cat_config from the flags, if the user
        # didn't pass anything explicit.
        # ------------------------------------------------------------------
        config = {"row": None, "col": None}

        if manual_row_flag:
            config["row"] = {
                "attribute": str(manual_row_flag),
                "preferred": [],
                "locked": True,
            }

        if manual_col_flag:
            config["col"] = {
                "attribute": str(manual_col_flag),
                "preferred": [],
                "locked": True,
            }

        # Only overwrite if it's still the default "{}" / empty
        if (config["row"] is not None or config["col"] is not None) and (
            not self.manual_cat_config or self.manual_cat_config == "{}"
        ):
            self.manual_cat_config = json.dumps(config)

        # Seed category_colors from network_meta if available
        base_colors = dict(self.network_meta.get("global_cat_colors", {}))
        if getattr(self, "category_colors", None):
            base_colors.update(self.category_colors)
        self._category_colors = base_colors
        self.category_colors = deepcopy(self._category_colors)

    @property
    def manual_cat_dict(self) -> dict:
        """Convenience accessor: parsed JSON from manual_cat."""
        try:
            return json.loads(self.manual_cat or "{}")
        except json.JSONDecodeError:
            return {}

    # ------------------------------------------------------------------
    # PY-only DataFrames derived from manual_cat JSON
    # ------------------------------------------------------------------
    @traitlets.observe("manual_cat")
    def _on_manual_cat(self, change) -> None:
        """Rebuild backend DataFrames when manual_cat JSON changes."""
        raw = change.get("new") or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}

        self._update_manual_cat_frames(payload)

    def _update_manual_cat_frames(self, payload: dict) -> None:
        """
        Build four DataFrames from the manual_cat payload:

        - row_manual_df: index=row_id, columns=attributes, values=category strings
        - col_manual_df: index=col_id, columns=attributes, values=category strings
        - row_manual_colors_df: index=category, columns=attributes, values=hex colors
        - col_manual_colors_df: index=category, columns=attributes, values=hex colors
        """
        for axis in ("row", "col"):
            axis_payload = payload.get(axis) or {}
            if not axis_payload:
                setattr(self, f"{axis}_manual_df", None)
                setattr(self, f"{axis}_manual_colors_df", None)
                continue

            # union of all indices for this axis
            index_labels = sorted(
                {str(name) for attr in axis_payload.values() for name in (attr.get("values") or {})}
            )

            if index_labels:
                idx = pd.Index(index_labels, name=f"{axis}_id")
                data = {}
                for attr_name, spec in axis_payload.items():
                    values = spec.get("values") or {}
                    series = pd.Series(
                        [values.get(label, _MANUAL_FILL_VALUE) for label in index_labels],
                        index=idx,
                        dtype=object,
                    )
                    data[str(attr_name)] = series
                manual_df = pd.DataFrame(data, index=idx)
            else:
                manual_df = None

            # colors: category -> hex per attribute
            cat_labels = sorted(
                {str(cat) for attr in axis_payload.values() for cat in (attr.get("colors") or {})}
            )

            if cat_labels:
                cat_idx = pd.Index(cat_labels, name="category")
                color_data = {}
                for attr_name, spec in axis_payload.items():
                    cmap = spec.get("colors") or {}
                    series = pd.Series(
                        [cmap.get(cat, None) for cat in cat_labels],
                        index=cat_idx,
                        dtype=object,
                    )
                    color_data[str(attr_name)] = series
                colors_df = pd.DataFrame(color_data, index=cat_idx)
            else:
                colors_df = None

            setattr(self, f"{axis}_manual_df", manual_df)
            setattr(self, f"{axis}_manual_colors_df", colors_df)

    def close(self):  # pragma: no cover - cleanup depends on JS
        """Close the widget and notify the frontend to release resources."""
        with suppress(Exception):
            self.send({"event": "finalize"})
        super().close()
