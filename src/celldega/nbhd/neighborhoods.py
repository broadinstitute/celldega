"""Module for NBHD class and related calculations."""

# Standard library imports
from itertools import combinations
from typing import Any

from anndata import AnnData

# Third-party imports
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse
from skimage.io import imread

from celldega.collections import NeighborhoodCollection
from celldega.pre.boundary_tile import batch_transform_geometries
from celldega.pre.image_info import resolve_xenium_morphology_ome_path

from .utils import _get_gdf_cell, _get_gdf_trx
from .zonal_stats import calc_img_zonal_stats


def calc_nbhd_by_gene(
    gdf_nbhd: gpd.GeoDataFrame,
    by: str = "cell",
    adata: AnnData | None = None,
    data_dir: str | None = None,
    nbhd_col: str = "name",
    min_cells: int = 1,
) -> AnnData:
    """
    Calculate neighborhood-by-gene expression matrix.

    Computes gene expression values for each neighborhood, either from cell-level
    expression data (mean expression of cells within each neighborhood) or from
    raw transcript counts (cell-free mode).

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        GeoDataFrame containing neighborhood geometries. Must have a geometry column
        and a column specified by `nbhd_col` for neighborhood identifiers.
    by : str, default "cell"
        Method for calculating gene expression:
        - "cell": Mean expression of cells within each neighborhood (requires `adata`)
        - "cell-free": Transcript counts within each neighborhood (requires `data_dir`)
    adata : AnnData, optional
        AnnData object with cell data. Required when `by="cell"`. Must have spatial
        coordinates in `obsm["spatial"]`.
    data_dir : str, optional
        Path to directory containing `transcripts.parquet`. Required when
        `by="cell-free"`.
    nbhd_col : str, default "name"
        Column in `gdf_nbhd` containing neighborhood identifiers.
    min_cells : int, default 1
        Minimum number of cells/transcripts required within a neighborhood to
        include it in the output. Only applies when `by="cell"`.

    Returns
    -------
    AnnData
        AnnData object with shape (n_neighborhoods, n_genes) where:
        - `X`: Matrix of gene expression values (mean for cell-derived, counts for cell-free)
        - `obs`: DataFrame indexed by neighborhood names
        - `var`: DataFrame indexed by gene names
        - `obs["n_cells"]`: Cell count per neighborhood (when `by="cell"`)
        - `uns["by"]`: Method used ("cell" or "cell-free")

    Examples
    --------
    >>> # Cell-derived gene expression per neighborhood
    >>> adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_alpha, by="cell", adata=adata)
    >>>
    >>> # Cell-free transcript counts per neighborhood
    >>> adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_alpha, by="cell-free", data_dir="./data")
    >>>
    >>> # For cluster-specific analysis, pre-filter the AnnData
    >>> adata_cluster0 = adata[adata.obs["leiden"] == "0"]
    >>> adata_nbg = dega.nbhd.calc_nbhd_by_gene(gdf_alpha, by="cell", adata=adata_cluster0)

    Notes
    -----
    For cluster-specific gene expression analysis, filter your AnnData object
    to include only cells from the desired cluster before calling this function.
    """
    if by == "cell":
        if adata is None:
            raise ValueError("adata is required when by='cell'")

        print("Calculating neighborhood-by-gene (cell-derived)")

        gene_list = adata.var.index
        gene_exp = pd.DataFrame(
            adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X,
            columns=gene_list,
            index=adata.obs_names,
        )

        gdf_cell = gpd.GeoDataFrame(
            data=gene_exp,
            geometry=gpd.points_from_xy(*adata.obsm["spatial"].T[:2]),
        )

        # Spatial join cells to neighborhoods
        joined = gdf_cell.sjoin(
            gdf_nbhd[[nbhd_col, "geometry"]],
            how="left",
            predicate="within",
        )
        joined.drop(columns=["index_right", "geometry"], inplace=True, errors="ignore")

        # Count cells per neighborhood for filtering
        cell_counts = joined[nbhd_col].value_counts()
        valid_nbhds = cell_counts[cell_counts >= min_cells].index
        joined = joined[joined[nbhd_col].isin(valid_nbhds)]

        # Compute mean expression per neighborhood
        df_result = joined.groupby(nbhd_col)[list(gene_list)].mean()

        # Filter gdf_nbhd to only include valid neighborhoods
        filtered_gdf = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhds)].reset_index(drop=True)

        # Reindex to preserve order
        df_result = df_result.reindex(filtered_gdf[nbhd_col]).fillna(0)

        # Build AnnData
        adata_nbg = AnnData(
            X=df_result.values,
            obs=pd.DataFrame(index=df_result.index),
            var=pd.DataFrame(index=df_result.columns),
        )

        # Add cell counts
        adata_nbg.obs["n_cells"] = [cell_counts.get(n, 0) for n in adata_nbg.obs.index]

    elif by == "cell-free":
        if data_dir is None:
            raise ValueError("data_dir is required when by='cell-free'")

        print("Calculating neighborhood-by-gene (cell-free)")

        df_trx = pd.read_parquet(
            f"{data_dir}/transcripts.parquet",
            columns=["feature_name", "x_location", "y_location"],
            engine="pyarrow",
        )
        geometry = gpd.points_from_xy(df_trx["x_location"], df_trx["y_location"])
        gdf_trx = gpd.GeoDataFrame(df_trx[["feature_name"]], geometry=geometry)
        gdf_trx = gdf_trx.sjoin(gdf_nbhd[[nbhd_col, "geometry"]], how="left", predicate="within")

        df_result = (
            gdf_trx.groupby([nbhd_col, "feature_name"])
            .size()
            .unstack(fill_value=0)
            .rename_axis(None, axis=1)
            .reindex(gdf_nbhd[nbhd_col])
            .fillna(0)
            .astype(int)
        )

        # Filter by min_cells (here it's min transcripts total)
        trx_counts = df_result.sum(axis=1)
        valid_nbhds = trx_counts[trx_counts >= min_cells].index
        df_result = df_result.loc[valid_nbhds]

        filtered_gdf = gdf_nbhd[gdf_nbhd[nbhd_col].isin(valid_nbhds)].reset_index(drop=True)

        # Build AnnData
        adata_nbg = AnnData(
            X=df_result.values,
            obs=pd.DataFrame(index=df_result.index),
            var=pd.DataFrame(index=df_result.columns),
        )

        # Add transcript counts
        adata_nbg.obs["n_transcripts"] = trx_counts.loc[valid_nbhds].values

    else:
        raise ValueError("by must be 'cell' or 'cell-free'")

    # Store metadata common to both modes
    adata_nbg.uns["by"] = by

    # Add neighborhood category and colors from gdf_nbhd if available
    if "cat" in filtered_gdf.columns:
        nbhd_cat_lookup = dict(
            zip(filtered_gdf[nbhd_col], filtered_gdf["cat"].astype(str), strict=False)
        )
        adata_nbg.obs["cat"] = [nbhd_cat_lookup.get(n, str(n)) for n in adata_nbg.obs.index]

    if "color" in filtered_gdf.columns:
        nbhd_color_lookup = dict(zip(filtered_gdf[nbhd_col], filtered_gdf["color"], strict=False))
        adata_nbg.obs["color"] = [nbhd_color_lookup.get(n, "#808080") for n in adata_nbg.obs.index]
        # Store colors in uns as well
        adata_nbg.uns["nbhd_colors"] = [
            nbhd_color_lookup.get(n, "#808080") for n in adata_nbg.obs.index
        ]

    return adata_nbg


def calc_nbhd_by_image(
    file_path: str,
    path_landscape_files: str,
    gdf_nbhd: gpd.GeoDataFrame,
    nbhd_col: str = "name",
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
            unique_polygon_col_name=nbhd_col,
            channel_names={0: "dapi", 1: "bound", 2: "rna", 3: "prot"},
            stats_funcs=["mean", "median", "std"],
        )
        .rename(columns={"polygon_id": "nbhd_id"})
        .set_index("nbhd_id")
    )


def _resolve_nbhd_col(gdf: gpd.GeoDataFrame, nbhd_col: str = "name") -> str:
    if nbhd_col in gdf.columns:
        return nbhd_col

    for candidate in ("neighborhood_id", "nbhd_id"):
        if candidate in gdf.columns:
            return candidate

    raise ValueError(
        f"gdf must include '{nbhd_col}', 'neighborhood_id', or 'nbhd_id' to identify neighborhoods"
    )


def _collection_from_gdf(
    gdf: gpd.GeoDataFrame,
    nbhd_type: str,
    nbhd_col: str = "name",
    provenance: dict[str, Any] | None = None,
    uns: dict[str, Any] | None = None,
) -> NeighborhoodCollection:
    resolved_nbhd_col = _resolve_nbhd_col(gdf, nbhd_col)
    geometry = gdf.copy()
    geometry.index = geometry[resolved_nbhd_col].astype(str)

    if not geometry.index.is_unique:
        raise ValueError(f"Neighborhood IDs in '{resolved_nbhd_col}' must be unique")

    obs = pd.DataFrame(geometry.drop(columns="geometry", errors="ignore"))
    obs.index = geometry.index.copy()
    obs.index.name = "neighborhood_id"

    if "neighborhood_id" not in obs.columns:
        obs.insert(0, "neighborhood_id", obs.index)
    if "neighborhood_type" not in obs.columns:
        obs["neighborhood_type"] = nbhd_type
    if "method" not in obs.columns:
        obs["method"] = nbhd_type

    geom = geometry.geometry
    if "area" not in obs.columns:
        obs["area"] = geom.area
    if "area_um2" not in obs.columns:
        obs["area_um2"] = geom.area
    if "centroid_x" not in obs.columns:
        obs["centroid_x"] = geom.centroid.x
    if "centroid_y" not in obs.columns:
        obs["centroid_y"] = geom.centroid.y

    return NeighborhoodCollection(
        obs=obs,
        geometry=geometry,
        provenance=provenance or {},
        uns=uns or {},
    )


def _align_space_to_collection(
    adata: AnnData,
    collection: NeighborhoodCollection,
) -> AnnData:
    target_index = collection.obs.index.astype(str)
    source_index = pd.Index(adata.obs_names.astype(str))

    if list(source_index) == list(target_index):
        return adata

    shape = (len(target_index), adata.n_vars)
    source_lookup = {name: i for i, name in enumerate(source_index)}
    target_rows = [i for i, name in enumerate(target_index) if name in source_lookup]
    source_rows = [source_lookup[name] for name in target_index if name in source_lookup]

    if sparse.issparse(adata.X):
        X = sparse.lil_matrix(shape, dtype=adata.X.dtype)
        if source_rows:
            X[target_rows, :] = adata.X[source_rows, :]
        X = X.tocsr()
    else:
        X = np.zeros(shape, dtype=adata.X.dtype)
        if source_rows:
            X[target_rows, :] = np.asarray(adata.X[source_rows, :])

    obs = collection.obs.copy()
    space_obs = adata.obs.copy()
    space_obs.index = source_index

    for col in space_obs.columns:
        values = space_obs[col].reindex(target_index)
        if pd.api.types.is_numeric_dtype(space_obs[col]) or col.startswith("n_"):
            values = values.fillna(0)
        obs[col] = values

    return AnnData(X=X, obs=obs, var=adata.var.copy(), uns=dict(adata.uns))


def _dataframe_to_space(
    df: pd.DataFrame,
    collection: NeighborhoodCollection,
    uns: dict[str, Any] | None = None,
) -> AnnData:
    feature_df = df.drop(columns="geometry", errors="ignore").copy()
    feature_df.index = feature_df.index.astype(str)
    adata = AnnData(
        X=feature_df.fillna(0).values,
        obs=pd.DataFrame(index=feature_df.index),
        var=pd.DataFrame(index=feature_df.columns.astype(str)),
        uns=uns or {},
    )
    return _align_space_to_collection(adata, collection)


def _relation_from_square_adata(
    adata: AnnData,
    collection: NeighborhoodCollection,
) -> sparse.csr_matrix:
    target_index = collection.obs.index.astype(str)
    values = adata.X.toarray() if sparse.issparse(adata.X) else np.asarray(adata.X)
    matrix = pd.DataFrame(
        values,
        index=pd.Index(adata.obs_names.astype(str)),
        columns=pd.Index(adata.var_names.astype(str)),
    )
    matrix = matrix.reindex(index=target_index, columns=target_index).fillna(0)
    return sparse.csr_matrix(matrix.values)


class NBHD:
    """Neighborhood geometry plus collection-backed modalities.

    ``NBHD`` keeps the existing convenience API for derived matrices while also
    maintaining a MuData-backed ``NeighborhoodCollection`` in ``collection``.
    New feature constructors attach aligned modalities and relations to that
    collection:

    - ``construct_gene_space`` stores neighborhood-by-gene data.
    - ``construct_population_space`` stores neighborhood-by-population data.
    - ``construct_image_space`` stores neighborhood-by-image-feature data.
    - ``construct_overlap_relation`` and ``construct_bordering_relation`` store
      neighborhood-by-neighborhood sparse relations.
    """

    def __init__(
        self,
        gdf: gpd.GeoDataFrame,
        nbhd_type: str,
        adata: AnnData | None = None,
        data_dir: str | None = None,
        path_landscape_files: str | None = None,
        source: str | dict[str, Any] | None = None,
        name: str | None = None,
        meta: dict[str, Any] | None = None,
        nbhd_col: str = "name",
    ) -> None:
        self.gdf = gdf.copy()
        self.nbhd_type = nbhd_type
        self.adata = adata
        self.data_dir = data_dir
        self.path_landscape_files = path_landscape_files
        self.source = source
        self.name = name
        self.meta = meta or {}
        self.nbhd_col = _resolve_nbhd_col(self.gdf, nbhd_col)
        provenance = {"source": source} if source is not None else {}
        self.collection = _collection_from_gdf(
            self.gdf,
            nbhd_type=nbhd_type,
            nbhd_col=self.nbhd_col,
            provenance=provenance,
            uns={"name": name, **self.meta},
        )

        self.derived: dict[str, Any] = {
            "NBI": None,
            "NBG-CF": None,
            "NBG-CD": None,
            "NBP": {},
            "NBN-O": None,
            "NBN-B": None,
        }

    @property
    def neighborhood_collection(self) -> NeighborhoodCollection:
        """Alias for ``collection`` for explicit call sites."""
        return self.collection

    def to_collection(self) -> NeighborhoodCollection:
        """Return the underlying ``NeighborhoodCollection``."""
        return self.collection

    def construct_gene_space(
        self,
        by: str = "cell",
        key: str | None = None,
        min_cells: int = 1,
    ) -> AnnData:
        """Construct and attach a neighborhood-by-gene space.

        Args:
            by: ``"cell"`` for cell-derived mean expression or
                ``"cell-free"`` for transcript counts.
            key: Modality key in ``collection.mod``. Defaults to ``"gene"`` for
                cell-derived expression and ``"gene_cell_free"`` for
                transcript-derived counts.
            min_cells: Minimum cells or transcripts required by the legacy
                calculator before alignment back to the collection.
        """
        if by == "cell" and self.adata is None:
            raise ValueError("adata is required to construct a cell-derived gene space")
        if by == "cell-free" and self.data_dir is None:
            raise ValueError("data_dir is required to construct a cell-free gene space")

        space_key = key or ("gene" if by == "cell" else "gene_cell_free")
        adata = calc_nbhd_by_gene(
            self.gdf,
            by=by,
            adata=self.adata,
            data_dir=self.data_dir,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
        )
        adata = _align_space_to_collection(adata, self.collection)
        return self.collection.add_mod(space_key, adata, entity_type="gene")

    def construct_population_space(
        self,
        category: str = "leiden",
        key: str = "population",
        min_cells: int = 5,
        output: str = "percentage",
    ) -> AnnData:
        """Construct and attach a neighborhood-by-population space."""
        if self.adata is None:
            raise ValueError("adata is required to construct a population space")

        adata = calc_nbhd_by_pop(
            self.adata,
            self.gdf,
            category=category,
            nbhd_col=self.nbhd_col,
            min_cells=min_cells,
            output=output,
        )
        adata = _align_space_to_collection(adata, self.collection)
        return self.collection.add_mod(key, adata, entity_type="cell_population")

    def construct_image_space(self, key: str = "image") -> AnnData:
        """Construct and attach a neighborhood-by-image-feature space."""
        if self.data_dir is None:
            raise ValueError("data_dir is required to resolve the morphology image")
        if self.path_landscape_files is None:
            raise ValueError("path_landscape_files is required to construct an image space")

        df = calc_nbhd_by_image(
            str(resolve_xenium_morphology_ome_path(self.data_dir)),
            self.path_landscape_files,
            self.gdf,
            nbhd_col=self.nbhd_col,
        )
        adata = _dataframe_to_space(df, self.collection, uns={"feature_type": "image"})
        return self.collection.add_mod(key, adata, entity_type="image_feature")

    def construct_overlap_relation(
        self,
        metric: str = "iou",
        key: str = "overlap",
        category: str = "leiden",
    ) -> sparse.csr_matrix:
        """Construct and attach a neighborhood-by-neighborhood overlap relation."""
        relation_adata = calc_nbhd_overlap(
            self.gdf[[self.nbhd_col, "geometry"]],
            metric=metric,
            name_col=self.nbhd_col,
            category=category,
        )
        relation = _relation_from_square_adata(relation_adata, self.collection)
        self.collection.relations[key] = relation
        return relation

    def construct_bordering_relation(
        self,
        metric: str = "border_ratio",
        key: str = "bordering",
        category: str = "leiden",
    ) -> sparse.csr_matrix:
        """Construct and attach a neighborhood-by-neighborhood bordering relation."""
        relation_adata = calc_nbhd_bordering(
            self.gdf[[self.nbhd_col, "geometry"]],
            metric=metric,
            name_col=self.nbhd_col,
            category=category,
        )
        relation = _relation_from_square_adata(relation_adata, self.collection)
        self.collection.relations[key] = relation
        return relation

    def set_derived(self, key: str, subkey: str | None = None) -> None:
        """
        Set a derived data matrix and attach it to the collection when possible.
        """
        if key == "NBG-CD":
            data = self.construct_gene_space(by="cell", key="gene")
        elif key == "NBG-CF":
            data = self.construct_gene_space(by="cell-free", key="gene_cell_free")
        elif key == "NBP":
            data = {
                "pct": self.construct_population_space(
                    category="leiden",
                    key="population",
                    output="percentage",
                )
            }
            data["abs"] = self.construct_population_space(
                category="leiden",
                key="population_counts",
                output="counts",
            )
        elif key == "NBM":
            if self.data_dir is None or self.adata is None:
                raise ValueError("data_dir and adata are required to derive NBM")
            gdf_trx = _get_gdf_trx(self.data_dir)
            gdf_cell = _get_gdf_cell(self.adata)
            data = get_nbhd_meta(self.gdf, self.nbhd_col, gdf_trx, gdf_cell)
            data.index = data.index.astype(str)
            self.collection.obs = self.collection.obs.join(data, how="left")
        elif key == "NBN-O":
            if self.nbhd_type == "ALPH":
                print("Calculating neighborhood overlap")
                data = calc_nbhd_overlap(
                    self.gdf[[self.nbhd_col, "geometry"]],
                    name_col=self.nbhd_col,
                )
                self.collection.relations["overlap"] = _relation_from_square_adata(
                    data,
                    self.collection,
                )
            else:
                raise ValueError("NBN-O can be derived for ALPH only")
        elif key == "NBN-B":
            if self.nbhd_type == "ALPH":
                raise ValueError("NBN-B can not be derived for nbhd having overlap")
            print("Calculating neighborhood bordering")
            data = calc_nbhd_bordering(
                self.gdf[[self.nbhd_col, "geometry"]],
                name_col=self.nbhd_col,
            )
            self.collection.relations["bordering"] = _relation_from_square_adata(
                data,
                self.collection,
            )
        elif key == "NBI":
            if self.data_dir is None:
                raise ValueError("data_dir is required to resolve the morphology image")
            if self.path_landscape_files is None:
                raise ValueError("path_landscape_files is required to derive NBI")
            data = calc_nbhd_by_image(
                str(resolve_xenium_morphology_ome_path(self.data_dir)),
                self.path_landscape_files,
                self.gdf,
                nbhd_col=self.nbhd_col,
            )
            self.collection.add_mod(
                "image",
                _dataframe_to_space(data, self.collection, uns={"feature_type": "image"}),
                entity_type="image_feature",
            )
        else:
            raise ValueError(f"Unknown derived key: {key}")

        if key == "NBP":
            for subkey in data:
                self.derived[key][subkey] = data[subkey]
        else:
            self.derived[key] = data

        print(f"{key} is derived and attached to nbhd")

    def _add_geo(self, df: pd.DataFrame) -> pd.DataFrame:
        if isinstance(df, AnnData):
            X = df.X.toarray() if sparse.issparse(df.X) else df.X
            df = pd.DataFrame(X, index=df.obs_names, columns=df.var_names)
        elif sparse.issparse(df):
            df = pd.DataFrame(df.toarray(), index=self.collection.obs.index)
        return (
            self.gdf[[self.nbhd_col, "geometry"]]
            .set_index(self.nbhd_col)
            .join(df, how="left")
            .fillna(0)
            .reset_index()
            .rename(columns={self.nbhd_col: "nbhd_id"})
        )

    def get_derived(self, key: str, subkey: str | None = None) -> pd.DataFrame:
        if key == "NBP":
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
            "modalities": {k: v.shape for k, v in self.collection.mod.items()},
            "relations": {k: v.shape for k, v in self.collection.relations.items()},
            "meta": self.meta,
        }

    def _derived_summary(self, key: str) -> tuple | dict[str, tuple] | None:
        val = self.derived.get(key)
        if val is None:
            return None
        if key == "NBP":
            subkeys = ["abs", "pct"]
            summary = {}
            for subkey in subkeys:
                subval = val.get(subkey)
                summary[subkey] = subval.shape if hasattr(subval, "shape") else None
            return summary
        return val.shape if hasattr(val, "shape") else None


def calc_nbhd_by_pop(
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

    Examples
    --------
    >>> adata_nbp = dega.nbhd.calc_nbhd_by_pop(adata, gdf_alpha, category="leiden")
    >>> adata_nbp.shape
    (42, 18)  # 42 neighborhoods, 18 clusters
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
    Calculate pairwise border relationships between neighborhoods.

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
