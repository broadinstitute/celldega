"""Module for NBHD class and related calculations."""

# Standard library imports
from itertools import combinations
from typing import Any

from anndata import AnnData

# Third-party imports
import geopandas as gpd
import pandas as pd
from skimage.io import imread

from celldega.pre.boundary_tile import batch_transform_geometries

from .utils import _get_gdf_cell, _get_gdf_trx
from .zonal_stats import calc_img_zonal_stats


def calc_nbhd_by_gene_cell_derived(
    adata: AnnData,
    gdf_nbhd: gpd.GeoDataFrame,
    cd_mode: str = "CD/LCD",
    unique_nbhd_col: str = "name",
) -> gpd.GeoDataFrame | dict[Any, gpd.GeoDataFrame]:
    """
    Calculate the mean expression of cells within a neighborhood (CD)
    or the mean expression of cells from a given Leiden cluster (LCD).
    """
    gene_list = adata.var.index

    gene_exp = pd.DataFrame(
        adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X,
        columns=gene_list,
        index=adata.obs_names,
    )

    gdf_cell = gpd.GeoDataFrame(
        data={"cluster": adata.obs["leiden"], **gene_exp},
        geometry=gpd.points_from_xy(*adata.obsm["spatial"].T[:2]),
    )

    def compute_cd(gdf_cell_subset: gpd.GeoDataFrame) -> pd.DataFrame:
        joined = gdf_cell_subset.sjoin(
            gdf_nbhd[[unique_nbhd_col, "geometry"]],
            how="left",
            predicate="within",
        )
        joined.drop(columns=["index_right", "cat", "geometry"], inplace=True, errors="ignore")

        df_nbhd_join = gdf_nbhd[[unique_nbhd_col]]
        for gene in gene_list:
            avg = joined.groupby(unique_nbhd_col)[gene].mean().reset_index()
            avg.columns = [unique_nbhd_col, gene]
            df_nbhd_join = df_nbhd_join.merge(avg, on=unique_nbhd_col, how="left")

        df_nbhd_join.rename(columns={unique_nbhd_col: "nbhd_id"}, inplace=True)
        df_nbhd_join.set_index("nbhd_id", inplace=True)

        return df_nbhd_join

    if cd_mode == "LCD":
        print("Calculating NBG-LCD")
        nbhd_by_cluster: dict[Any, pd.DataFrame] = {}
        for cluster in gdf_cell["cluster"].unique():
            cluster_cells = gdf_cell[gdf_cell["cluster"] == cluster]
            nbhd_by_cluster[cluster] = compute_cd(cluster_cells)
        return nbhd_by_cluster

    if cd_mode == "CD":
        print("Calculating NBG-CD")
        return compute_cd(gdf_cell)

    raise ValueError("cd_mode must be 'CD' or 'LCD'")


def calc_nbhd_by_gene_cell_free(
    data_dir: str,
    gdf_nbhd: gpd.GeoDataFrame,
    unique_nbhd_col: str = "name",
) -> pd.DataFrame:
    """
    Calculates the neighborhood by gene expression.
    """
    print("Calculating NBG-CF")
    df_trx = pd.read_parquet(
        f"{data_dir}/transcripts.parquet",
        columns=["feature_name", "x_location", "y_location", "cell_id"],
        engine="pyarrow",
    )
    geometry = gpd.points_from_xy(df_trx["x_location"], df_trx["y_location"])
    gdf_trx = gpd.GeoDataFrame(df_trx[["feature_name"]], geometry=geometry)
    gdf_trx = gdf_trx.sjoin(gdf_nbhd[[unique_nbhd_col, "geometry"]], how="left", predicate="within")
    gdf_trx.rename(columns={unique_nbhd_col: "nbhd_id"}, inplace=True)
    return (
        gdf_trx.groupby(["nbhd_id", "feature_name"])
        .size()
        .unstack(fill_value=0)
        .rename_axis("nbhd_id")
        .rename_axis(None, axis=1)
        .reindex(gdf_nbhd[unique_nbhd_col])
        .fillna(0)
        .astype(int)
    )


def calc_nbi(
    file_path: str,
    path_landscape_files: str,
    gdf_nbhd: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Calculate neighborhood image-based indices (NBI) given paths and a GeoDataFrame.
    """
    print("Calculating NBI...")

    img = imread(file_path)
    path_transformation_matrix = f"{path_landscape_files}/micron_to_image_transform.csv"
    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

    gdf_nbhd_pixel = gdf_nbhd.copy()
    gdf_nbhd_pixel["geometry"] = batch_transform_geometries(
        gdf_nbhd_pixel["geometry"], transformation_matrix, 1
    )

    return (
        calc_img_zonal_stats(
            gdf_nbhd_pixel,
            img,
            unique_polygon_col_name="name",
            channel_names={0: "dapi", 1: "bound", 2: "rna", 3: "prot"},
            stats_funcs=["mean", "median", "std"],
        )
        .rename(columns={"polygon_id": "nbhd_id"})
        .set_index("nbhd_id")
    )


class NBHD:
    """A class representing neighborhoods with associated derived data matrices."""

    def __init__(
        self,
        gdf: gpd.GeoDataFrame,
        nbhd_type: str,
        adata: AnnData,
        data_dir: str,
        path_landscape_files: str,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.gdf = gdf.copy()
        self.nbhd_type = nbhd_type
        self.adata = adata
        self.data_dir = data_dir
        self.path_landscape_files = path_landscape_files
        self.source = source
        self.name = name
        self.meta = meta or {}

        self.derived: dict[str, Any] = {
            "NBI": None,
            "NBG-CF": None,
            "NBG-CD": None,
            "NBG-LCD": {},
            "NBP": {},
            "NBN-O": None,
            "NBN-B": None,
        }

    def set_derived(self, key: str, subkey: str | None = None) -> None:
        """
        Set a derived data matrix.
        """
        if key == "NBG-CD":
            data = calc_nbhd_by_gene_cell_derived(self.adata, self.gdf, "CD")
        elif key == "NBG-LCD":
            data = calc_nbhd_by_gene_cell_derived(self.adata, self.gdf, "LCD")
        elif key == "NBG-CF":
            data = calc_nbhd_by_gene_cell_free(self.data_dir, self.gdf)
        elif key == "NBP":
            # calc_nbp now takes adata and gdf_nbhd, returns AnnData
            data = {"pct": calc_nbp(self.adata, self.gdf, category="leiden", output="percentage")}
            data["abs"] = calc_nbp(self.adata, self.gdf, category="leiden", output="counts")
        elif key == "NBM":
            gdf_trx = _get_gdf_trx(self.data_dir)
            gdf_cell = _get_gdf_cell(self.adata)
            data = get_nbhd_meta(self.gdf, "name", gdf_trx, gdf_cell)
        elif key == "NBN-O":
            if self.nbhd_type == "ALPH":
                nb = self.gdf[["name", "geometry"]]
                print("Calculating neighborhood overlap")
                data = calc_nbhd_overlap(nb)
            else:
                raise ValueError("NBN-O can be derived for ALPH only")
        elif key == "NBN-B":
            if self.nbhd_type == "ALPH":
                raise ValueError("NBN-B can not be derived for nbhd having overlap")
            nb = self.gdf[["name", "geometry"]]
            print("Calculating neighborhood bordering")
            data = calc_nbhd_bordering(nb)
        elif key == "NBI":
            data = calc_nbi(
                f"{self.data_dir}/morphology_focus/morphology_focus_0000.ome.tif",
                self.path_landscape_files,
                self.gdf,
            )
        else:
            raise ValueError(f"Unknown derived key: {key}")

        if key in {"NBP", "NBG-LCD"}:
            for subkey in data:
                self.derived[key][subkey] = data[subkey]
        else:
            self.derived[key] = data

        print(f"{key} is derived and attached to nbhd")

    def _add_geo(self, df: pd.DataFrame) -> pd.DataFrame:
        return (
            self.gdf[["name", "geometry"]]
            .set_index("name")
            .join(df, how="left")
            .fillna(0)
            .reset_index()
            .rename(columns={"name": "nbhd_id"})
        )

    def get_derived(self, key: str, subkey: str | None = None) -> pd.DataFrame:
        if key in {"NBP", "NBG-LCD"}:
            df = self.derived[key].get(subkey)
            return self._add_geo(df)
        df = self.derived.get(key)
        return self._add_geo(df)

    def to_geodataframe(self) -> gpd.GeoDataFrame:
        return self.gdf

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.nbhd_type,
            "n_regions": len(self.gdf),
            "derived": {k: self._derived_summary(k) for k in self.derived},
            "meta": self.meta,
        }

    def _derived_summary(self, key: str) -> tuple | dict[str, tuple] | None:
        val = self.derived.get(key)
        if val is None:
            return None
        if key in ["NBP", "NBG-LCD"]:
            if key == "NBP":
                subkeys = ["abs", "pct"]
            elif key == "NBG-LCD":
                subkeys = sorted(self.adata.obs["leiden"].unique().tolist())
            summary = {}
            for subkey in subkeys:
                subval = val.get(subkey)
                summary[subkey] = subval.shape if hasattr(subval, "shape") else None
            return summary
        return val.shape if hasattr(val, "shape") else None


def calc_nbp(
    adata: AnnData,
    gdf_nbhd: gpd.GeoDataFrame,
    category: str = "leiden",
    nbhd_col: str = "name",
    min_cells: int = 5,
    output: str = "percentage",
) -> AnnData:
    """
    Calculate cell-level population distribution of neighborhoods.

    Computes a neighborhood-by-population matrix showing the distribution of cell
    categories (e.g., clusters, cell types) within each neighborhood.

    Parameters
    ----------
    adata : AnnData
        AnnData object containing cell data. Must have spatial coordinates in
        `obsm["spatial"]` and the category column in `obs`.
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `nbhd_col` for neighborhood identifiers.
    category : str, default "leiden"
        Column name in `adata.obs` containing cell category labels (e.g., "leiden",
        "cell_type", "cluster").
    nbhd_col : str, default "name"
        Column name in `gdf_nbhd` containing neighborhood identifiers.
    min_cells : int, default 5
        Minimum number of cells required within a neighborhood to include it in
        the output. Neighborhoods with fewer cells are filtered out.
    output : str, default "percentage"
        Type of values in the output matrix:
        - "percentage": Fraction of cells per category (sums to 1 per neighborhood)
        - "counts": Raw cell counts per category

    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_categories) where:
        - `X`: Matrix of population distributions (percentages or counts)
        - `obs`: DataFrame indexed by neighborhood names
        - `var`: DataFrame indexed by category names
        - `obs["n_cells"]`: Total cell count per neighborhood
        - `uns["gdf_nbhd"]`: Filtered GeoDataFrame of neighborhoods

    Examples
    --------
    >>> adata_nbp = dega.nbhd.calc_nbp(adata, gdf_alpha, category="leiden")
    >>> adata_nbp.shape
    (42, 18)  # 42 neighborhoods, 18 clusters
    >>> adata_nbp.uns["gdf_nbhd"]  # Access filtered geometries
    """
    print("Calculating NBP")

    # Validate inputs
    required_nbhd = {"geometry", nbhd_col}
    if not required_nbhd.issubset(gdf_nbhd.columns):
        raise ValueError(
            f"gdf_nbhd missing required columns: {required_nbhd - set(gdf_nbhd.columns)}"
        )
    if category not in adata.obs.columns:
        raise ValueError(f"adata.obs missing required '{category}' column")
    if "spatial" not in adata.obsm:
        raise ValueError("adata.obsm missing 'spatial' coordinates")

    # Build GeoDataFrame from adata with the specified category
    # No CRS set - using micron imaging coordinates, not geospatial
    gdf_cell = gpd.GeoDataFrame(
        {category: adata.obs[category].values},
        geometry=gpd.points_from_xy(*adata.obsm["spatial"].T[:2]),
    )

    # Spatial join: assign each cell to a neighborhood
    sjoin_df = gdf_cell.sjoin(gdf_nbhd[[nbhd_col, "geometry"]], how="left", predicate="within")

    # Filter neighborhoods with at least min_cells
    cell_counts_per_nbhd = sjoin_df[nbhd_col].value_counts()
    valid_nbhd_names = cell_counts_per_nbhd[cell_counts_per_nbhd >= min_cells].index
    sjoin_df = sjoin_df[sjoin_df[nbhd_col].isin(valid_nbhd_names)]

    # Count cells per (neighborhood, cluster)
    counts = (
        sjoin_df.groupby([nbhd_col, category])
        .size()
        .unstack(fill_value=0)
        .pipe(lambda df: df.set_axis(df.columns.astype(str), axis=1))
    )

    # Reindex to preserve order of filtered gdf_nbhd
    filtered_gdf_nbhd = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhd_names)].reset_index(drop=True)
    counts = counts.reindex(filtered_gdf_nbhd[nbhd_col]).fillna(0).astype(int)

    # Calculate output values
    if output == "percentage":
        values = counts.div(counts.sum(axis=1), axis=0).fillna(0).values
    else:
        values = counts.values

    # Build AnnData
    adata_nbp = AnnData(
        X=values,
        obs=pd.DataFrame(index=counts.index),
        var=pd.DataFrame(index=counts.columns),
    )
    adata_nbp.obs["n_cells"] = counts.sum(axis=1).values
    adata_nbp.uns["gdf_nbhd"] = filtered_gdf_nbhd
    adata_nbp.uns["category"] = category

    # Add category as a var column (columns represent categories)
    adata_nbp.var[category] = adata_nbp.var.index.astype(str)

    # Also add category to obs - neighborhoods are named by their cluster
    # Look up category from gdf_nbhd if available
    if "cat" in filtered_gdf_nbhd.columns:
        nbhd_cat_lookup = dict(
            zip(filtered_gdf_nbhd[nbhd_col], filtered_gdf_nbhd["cat"].astype(str), strict=False)
        )
        adata_nbp.obs[category] = [nbhd_cat_lookup.get(n, str(n)) for n in adata_nbp.obs.index]
    else:
        # Default: use the index (neighborhood name) as the category
        adata_nbp.obs[category] = adata_nbp.obs.index.astype(str)

    # Copy colors from source adata if available
    color_key = f"{category}_colors"
    color_dict: dict[str, str] = {}
    if color_key in adata.uns:
        # Map colors to the category values
        src_colors = adata.uns[color_key]
        if hasattr(adata.obs[category], "cat"):
            src_categories = list(adata.obs[category].cat.categories.astype(str))
        else:
            src_categories = list(adata.obs[category].unique().astype(str))

        color_dict = {
            str(cat): src_colors[i] for i, cat in enumerate(src_categories) if i < len(src_colors)
        }

        # Assign colors to var (columns)
        adata_nbp.var["color"] = [color_dict.get(str(c), "#808080") for c in adata_nbp.var.index]
        adata_nbp.uns[color_key] = [color_dict.get(str(c), "#808080") for c in adata_nbp.var.index]

        # Also assign colors to obs (rows/neighborhoods)
        adata_nbp.obs["color"] = [
            color_dict.get(str(c), "#808080") for c in adata_nbp.obs[category]
        ]

    return adata_nbp


def get_nbhd_meta(
    gdf_nbhd: gpd.GeoDataFrame,
    unique_nbhd_col: str,
    gdf_trx: gpd.GeoDataFrame,
    gdf_cell: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Compute neighborhood-level summary statistics including transcript and cell assignments,
    along with area and perimeter from geometry.
    """
    print("Calculating NBM")
    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd = gdf_nbhd.set_index(unique_nbhd_col)
    gdf_nbhd[unique_nbhd_col] = gdf_nbhd.index
    summary = pd.DataFrame(index=gdf_nbhd.index)
    summary.index.name = "nbhd_id"
    summary["area_squm"] = gdf_nbhd.geometry.area.round(2)
    summary["perimeter_um"] = gdf_nbhd.geometry.length.round(2)
    gdf_trx = gdf_trx.sjoin(gdf_nbhd[[unique_nbhd_col, "geometry"]], how="left", predicate="within")
    trx_summary = gdf_trx.groupby(unique_nbhd_col).agg(
        total_trx=("cell_id", "size"),
        unassigned_trx_count=("cell_id", lambda x: (x == "UNASSIGNED").sum()),
        assigned_trx_count=("cell_id", lambda x: (x != "UNASSIGNED").sum()),
    )
    trx_summary = trx_summary.reindex(gdf_nbhd.index).fillna(0)
    trx_summary["assigned_trx_pct"] = trx_summary["assigned_trx_count"] / trx_summary[
        "total_trx"
    ].replace(0, 1)
    trx_summary["unassigned_trx_pct"] = trx_summary["unassigned_trx_count"] / trx_summary[
        "total_trx"
    ].replace(0, 1)
    gdf_c = gdf_cell[["geometry"]].sjoin(
        gdf_nbhd[[unique_nbhd_col, "geometry"]], how="left", predicate="within"
    )
    cell_counts = gdf_c.groupby(unique_nbhd_col).size().rename("cell_count")
    cell_counts = cell_counts.reindex(gdf_nbhd.index).fillna(0)
    return summary.join(trx_summary).join(cell_counts)


def calc_nbhd_overlap(
    gdf_nbhd: gpd.GeoDataFrame,
    metric: str = "iou",
    name_col: str = "name",
    category: str = "leiden",
) -> AnnData:
    """
    Calculate pairwise overlap between all neighborhoods as a neighborhood-by-neighborhood matrix.

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `name_col` for neighborhood identifiers.
    metric : str, default "iou"
        The overlap metric to compute:
        - "iou": Intersection over Union. Value = intersection_area / union_area.
          Symmetric measure ranging from 0 (no overlap) to 1 (identical geometries).
        - "ioa": Intersection over Area (of self/row). Value = intersection_area / row_area.
          Asymmetric measure showing what fraction of the row neighborhood overlaps
          with the column neighborhood. Useful for containment analysis.
        - "intersection": Raw intersection area in square units.
    name_col : str, default "name"
        Column name containing neighborhood identifiers.
    category : str, default "leiden"
        Name of the category that neighborhoods represent (e.g., "leiden", "cell_type").
        This is used to name the category column in obs/var and the colors in uns.

    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_neighborhoods) where:
        - `X`: Matrix of overlap values
        - `obs`: DataFrame indexed by neighborhood names (rows)
        - `var`: DataFrame indexed by neighborhood names (columns)
        - `obs["area"]`: Area of each neighborhood
        - `obs[category]`: Category value for each neighborhood
        - `uns["metric"]`: The metric used for computation
        - `uns["gdf_nbhd"]`: Input GeoDataFrame for reference

    Examples
    --------
    >>> adata_iou = dega.nbhd.calc_nbhd_overlap(gdf_nbhd, metric="iou")
    >>> adata_ioa = dega.nbhd.calc_nbhd_overlap(gdf_nbhd, metric="ioa")
    >>> mat = dega.clust.Matrix(adata_iou, row_entity="nbhd", col_entity="nbhd")
    """
    print(f"Calculating NBN-O ({metric})")

    valid_metrics = {"iou", "ioa", "intersection"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got '{metric}'")

    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)

    names = gdf_nbhd[name_col].tolist()

    # Pre-compute areas for efficiency
    areas = {row[name_col]: row["geometry"].area for _, row in gdf_nbhd.iterrows()}

    # Initialize matrix with zeros
    matrix = pd.DataFrame(0.0, index=names, columns=names)

    # Set diagonal values
    for name in names:
        if metric in ("iou", "ioa"):
            matrix.loc[name, name] = 1.0
        else:  # intersection
            matrix.loc[name, name] = round(areas[name], 2)

    # Build a lookup for geometries
    geom_lookup = {row[name_col]: row["geometry"] for _, row in gdf_nbhd.iterrows()}

    # Compute pairwise overlaps
    for nb1, nb2 in combinations(names, 2):
        geom1 = geom_lookup[nb1]
        geom2 = geom_lookup[nb2]
        intersection = geom1.intersection(geom2)

        if intersection.is_empty or intersection.area == 0:
            continue

        intersection_area = intersection.area
        area1 = areas[nb1]
        area2 = areas[nb2]

        if metric == "iou":
            union_area = geom1.union(geom2).area
            value = intersection_area / union_area if union_area > 0 else 0.0
            matrix.loc[nb1, nb2] = round(value, 4)
            matrix.loc[nb2, nb1] = round(value, 4)  # Symmetric
        elif metric == "ioa":
            # Asymmetric: row's perspective (what fraction of row overlaps with col)
            value_1_to_2 = intersection_area / area1 if area1 > 0 else 0.0
            value_2_to_1 = intersection_area / area2 if area2 > 0 else 0.0
            matrix.loc[nb1, nb2] = round(value_1_to_2, 4)
            matrix.loc[nb2, nb1] = round(value_2_to_1, 4)
        else:  # intersection
            matrix.loc[nb1, nb2] = round(intersection_area, 2)
            matrix.loc[nb2, nb1] = round(intersection_area, 2)  # Symmetric

    # Build AnnData
    adata_nbn = AnnData(
        X=matrix.values,
        obs=pd.DataFrame(index=matrix.index),
        var=pd.DataFrame(index=matrix.columns),
    )
    adata_nbn.obs["area"] = [areas[n] for n in matrix.index]
    adata_nbn.uns["metric"] = metric
    adata_nbn.uns["gdf_nbhd"] = gdf_nbhd
    adata_nbn.uns["category"] = category

    # Add category and color metadata from gdf_nbhd if available
    # Look up by name_col to get cat and color for each neighborhood
    nbhd_lookup = gdf_nbhd.set_index(name_col)

    if "cat" in gdf_nbhd.columns:
        # Use the category parameter name (e.g., "leiden") instead of "cat"
        adata_nbn.obs[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.index
        ]
        adata_nbn.var[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.columns
        ]

    if "color" in gdf_nbhd.columns:
        obs_colors = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.index
        ]
        adata_nbn.obs["color"] = obs_colors
        adata_nbn.var["color"] = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.columns
        ]
        # Store colors in uns using the category name (e.g., "leiden_colors")
        if "cat" in gdf_nbhd.columns:
            unique_cats = adata_nbn.obs[category].unique()
            cat_color_map = dict(zip(adata_nbn.obs[category], obs_colors, strict=False))
            adata_nbn.uns[f"{category}_colors"] = [
                cat_color_map.get(c, "#808080") for c in unique_cats
            ]

    return adata_nbn


def calc_nbhd_bordering(
    gdf_nbhd: gpd.GeoDataFrame,
    metric: str = "border_ratio",
    name_col: str = "name",
    category: str = "leiden",
) -> AnnData:
    """
    Calculate pairwise border relationships between neighborhoods as a neighborhood-by-neighborhood matrix.

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `name_col` for neighborhood identifiers.
    metric : str, default "border_ratio"
        The border metric to compute:
        - "border_ratio": Border length over self (row) perimeter.
          Value = shared_border_length / row_perimeter.
          Asymmetric measure showing what fraction of the row neighborhood's
          perimeter is shared with the column neighborhood.
        - "border_length": Raw shared border length in linear units.
          Symmetric measure of the absolute length of shared boundary.
        - "binary": Binary adjacency (1 if touching, 0 otherwise).
          Symmetric measure indicating whether neighborhoods share a border.
    name_col : str, default "name"
        Column name containing neighborhood identifiers.
    category : str, default "leiden"
        Name of the category that neighborhoods represent (e.g., "leiden", "cell_type").
        This is used to name the category column in obs/var and the colors in uns.

    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_neighborhoods) where:
        - `X`: Matrix of border metric values
        - `obs`: DataFrame indexed by neighborhood names (rows)
        - `var`: DataFrame indexed by neighborhood names (columns)
        - `obs["perimeter"]`: Perimeter of each neighborhood
        - `obs[category]`: Category value for each neighborhood
        - `uns["metric"]`: The metric used for computation
        - `uns["gdf_nbhd"]`: Input GeoDataFrame for reference

    Notes
    -----
    Shared border length is computed as the length of the intersection of the
    two neighborhood boundaries (perimeters). This works for neighborhoods that
    touch but don't overlap. For overlapping neighborhoods, consider using
    `calc_nbhd_overlap` instead.

    Examples
    --------
    >>> adata_border = dega.nbhd.calc_nbhd_bordering(gdf_nbhd, metric="border_ratio")
    >>> adata_adj = dega.nbhd.calc_nbhd_bordering(gdf_nbhd, metric="binary")
    >>> mat = dega.clust.Matrix(adata_border, row_entity="nbhd", col_entity="nbhd")
    """
    print(f"Calculating NBN-B ({metric})")

    valid_metrics = {"border_ratio", "border_length", "binary"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got '{metric}'")

    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)

    names = gdf_nbhd[name_col].tolist()

    # Pre-compute perimeters for efficiency
    perimeters = {row[name_col]: row["geometry"].length for _, row in gdf_nbhd.iterrows()}

    # Build a lookup for geometries
    geom_lookup = {row[name_col]: row["geometry"] for _, row in gdf_nbhd.iterrows()}

    # Initialize matrix with zeros
    matrix = pd.DataFrame(0.0, index=names, columns=names)

    # Use spatial index to find touching pairs efficiently
    gdf_touches = gpd.sjoin(gdf_nbhd, gdf_nbhd, how="inner", predicate="touches")
    gdf_touches = gdf_touches[gdf_touches[f"{name_col}_left"] != gdf_touches[f"{name_col}_right"]]

    # Get unique pairs
    seen_pairs: set[tuple[str, str]] = set()
    for _, row in gdf_touches.iterrows():
        nb1 = row[f"{name_col}_left"]
        nb2 = row[f"{name_col}_right"]

        # Skip if we've already processed this pair
        pair_key = tuple(sorted((nb1, nb2)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        geom1 = geom_lookup[nb1]
        geom2 = geom_lookup[nb2]

        # Compute shared border length as intersection of boundaries
        boundary1 = geom1.boundary
        boundary2 = geom2.boundary
        shared_border = boundary1.intersection(boundary2)
        border_length = shared_border.length if not shared_border.is_empty else 0.0

        if metric == "binary":
            matrix.loc[nb1, nb2] = 1.0
            matrix.loc[nb2, nb1] = 1.0
        elif metric == "border_length":
            matrix.loc[nb1, nb2] = round(border_length, 2)
            matrix.loc[nb2, nb1] = round(border_length, 2)  # Symmetric
        elif metric == "border_ratio":
            # Asymmetric: what fraction of each neighborhood's perimeter is shared
            perim1 = perimeters[nb1]
            perim2 = perimeters[nb2]
            ratio_1 = border_length / perim1 if perim1 > 0 else 0.0
            ratio_2 = border_length / perim2 if perim2 > 0 else 0.0
            matrix.loc[nb1, nb2] = round(ratio_1, 4)
            matrix.loc[nb2, nb1] = round(ratio_2, 4)

    # Build AnnData
    adata_nbn = AnnData(
        X=matrix.values,
        obs=pd.DataFrame(index=matrix.index),
        var=pd.DataFrame(index=matrix.columns),
    )
    adata_nbn.obs["perimeter"] = [perimeters[n] for n in matrix.index]
    adata_nbn.uns["metric"] = metric
    adata_nbn.uns["gdf_nbhd"] = gdf_nbhd
    adata_nbn.uns["category"] = category

    # Add category and color metadata from gdf_nbhd if available
    nbhd_lookup = gdf_nbhd.set_index(name_col)

    if "cat" in gdf_nbhd.columns:
        # Use the category parameter name (e.g., "leiden") instead of "cat"
        adata_nbn.obs[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.index
        ]
        adata_nbn.var[category] = [
            str(nbhd_lookup.loc[n, "cat"]) if n in nbhd_lookup.index else str(n)
            for n in matrix.columns
        ]

    if "color" in gdf_nbhd.columns:
        obs_colors = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.index
        ]
        adata_nbn.obs["color"] = obs_colors
        adata_nbn.var["color"] = [
            nbhd_lookup.loc[n, "color"] if n in nbhd_lookup.index else "#808080"
            for n in matrix.columns
        ]
        # Store colors in uns using the category name (e.g., "leiden_colors")
        if "cat" in gdf_nbhd.columns:
            unique_cats = adata_nbn.obs[category].unique()
            cat_color_map = dict(zip(adata_nbn.obs[category], obs_colors, strict=False))
            adata_nbn.uns[f"{category}_colors"] = [
                cat_color_map.get(c, "#808080") for c in unique_cats
            ]

    return adata_nbn
