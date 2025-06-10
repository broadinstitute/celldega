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


def calc_nbg_cd(
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
        crs="EPSG:4326",
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


def calc_nbg_cf(
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
    gdf_trx = gpd.GeoDataFrame(df_trx[["feature_name"]], geometry=geometry, crs="EPSG:4326")
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
            data = calc_nbg_cd(self.adata, self.gdf, "CD")
        elif key == "NBG-LCD":
            data = calc_nbg_cd(self.adata, self.gdf, "LCD")
        elif key == "NBG-CF":
            data = calc_nbg_cf(self.data_dir, self.gdf)
        elif key == "NBP":
            data = {}
            gdf_cell = _get_gdf_cell(self.adata)
            data["abs"], data["pct"] = calc_nbp(gdf_cell, self.gdf)
        elif key == "NBM":
            gdf_trx = _get_gdf_trx(self.data_dir)
            gdf_cell = _get_gdf_cell(self.adata)
            data = get_nbhd_meta(self.gdf, "name", gdf_trx, gdf_cell)
        elif key == "NBN-O":
            if self.nbhd_type == "ALPH":
                nb = self.gdf[["name", "geometry"]]
                print("Calculating neighborhood overlap")
                data = calc_nb_overlap(nb)
            else:
                raise ValueError("NBN-O can be derived for ALPH only")
        elif key == "NBN-B":
            if self.nbhd_type == "ALPH":
                raise ValueError("NBN-B can not be derived for nbhd having overlap")
            nb = self.gdf[["name", "geometry"]]
            print("Calculating neighborhood bordering")
            data = calc_nb_bordering(nb)
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
    gdf_cell: gpd.GeoDataFrame,
    gdf_nbhd: gpd.GeoDataFrame,
    nbhd_col: str = "name",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate cell counts and percentages per cluster within neighborhoods.
    Returns two DataFrames:
    1. Raw counts per neighborhood-cluster combination
    2. Percentage distribution of clusters within each neighborhood
    """
    print("Calculating NBP")
    required = {"geometry", nbhd_col}
    if not required.issubset(gdf_nbhd.columns):
        raise ValueError(f"gdf_nbhd missing required columns: {required - set(gdf_nbhd.columns)}")
    if not {"geometry", "cluster"}.issubset(gdf_cell.columns):
        raise ValueError("gdf_cell missing required 'geometry' or 'cluster' column")

    counts = (
        gdf_cell.sjoin(gdf_nbhd[[nbhd_col, "geometry"]], how="left", predicate="within")
        .groupby([nbhd_col, "cluster"])
        .size()
        .unstack(fill_value=0)
        .pipe(lambda df: df.set_axis(df.columns.astype(str), axis=1))
    )
    counts = counts.reindex(gdf_nbhd[nbhd_col]).fillna(0).astype(int)
    percentages = counts.div(counts.sum(axis=1), axis=0).fillna(0) * 100
    return counts, percentages


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


def calc_nb_overlap(
    gdf_nbhd: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Calculate the pairwise overlap between all neighborhoods, including overlap area and geometry.
    Skips intersections that are empty or have zero area.
    """
    print("Calculating NBN-O")
    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)
    results = []
    for nb1, nb2 in combinations(gdf_nbhd["name"], 2):
        geom1 = gdf_nbhd.loc[gdf_nbhd["name"] == nb1, "geometry"].values[0]
        geom2 = gdf_nbhd.loc[gdf_nbhd["name"] == nb2, "geometry"].values[0]
        intersection = geom1.intersection(geom2)
        if not intersection.is_empty and intersection.area > 0:
            results.append(
                {
                    "nbhd_1": nb1,
                    "nbhd_2": nb2,
                    "overlap_area": round(intersection.area, 2),
                    "geometry": intersection,
                }
            )
    if results:
        return gpd.GeoDataFrame(results, geometry="geometry", crs=gdf_nbhd.crs)
    return gpd.GeoDataFrame(
        columns=["nbhd_1", "nbhd_2", "overlap_area", "geometry"],
        geometry="geometry",
        crs=gdf_nbhd.crs,
    )


def calc_nb_bordering(
    gdf_nbhd: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Identify pairs of neighborhoods that share a border (touch), using spatial indexing for efficiency.
    """
    print("Calculating NBN-B")
    gdf_nbhd = gdf_nbhd.copy()
    gdf_nbhd["geometry"] = gdf_nbhd["geometry"].buffer(0)
    gdf_touches = gpd.sjoin(gdf_nbhd, gdf_nbhd, how="inner", predicate="touches")
    gdf_touches = gdf_touches[gdf_touches["name_left"] != gdf_touches["name_right"]]
    gdf_touches["pair"] = gdf_touches.apply(
        lambda row: tuple(sorted((row["name_left"], row["name_right"]))), axis=1
    )
    gdf_touches = gdf_touches.drop_duplicates(subset="pair")
    return (
        gdf_touches[["name_left", "name_right"]]
        .rename(columns={"name_left": "nbhd_1", "name_right": "nbhd_2"})
        .reset_index(drop=True)
    )
