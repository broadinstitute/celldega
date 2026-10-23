"""Helper and utility functions."""

# Standard library imports
from collections.abc import Sequence
from typing import Any

# Third-party imports
from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, base
from shapely.ops import transform


_NBHD_ID_FALLBACKS = ("neighborhood_id", "nbhd_id")


def _resolve_nbhd_col(
    gdf: gpd.GeoDataFrame,
    nbhd_col: str | None = "name",
    fallbacks: Sequence[str] = (),
) -> str:
    """Return the column identifying each neighborhood in ``gdf``.

    Falls back from ``nbhd_col`` (default ``"name"``) to ``fallbacks``, then
    ``neighborhood_id`` and ``nbhd_id``.
    """
    requested = nbhd_col or "name"
    for candidate in (requested, *fallbacks, *_NBHD_ID_FALLBACKS):
        if candidate in gdf.columns:
            return candidate
    raise ValueError(f"gdf_nbhd missing required columns: {{'{requested}'}}")


def _nbhd_geometry(nbhd: Any) -> gpd.GeoDataFrame | None:
    """The neighborhood GeoDataFrame behind ``nbhd``, or ``None``.

    ``nbhd`` itself when it is a GeoDataFrame, else ``nbhd.to_geodataframe()``,
    else a ``geometry``/``gdf`` GeoDataFrame attribute.
    """
    if isinstance(nbhd, gpd.GeoDataFrame):
        return nbhd
    to_geodataframe = getattr(nbhd, "to_geodataframe", None)
    if callable(to_geodataframe):
        gdf = to_geodataframe()
        return gdf if isinstance(gdf, gpd.GeoDataFrame) else None
    for attr in ("geometry", "gdf"):
        candidate = getattr(nbhd, attr, None)
        if isinstance(candidate, gpd.GeoDataFrame):
            return candidate
    return None


def _as_nbhd_gdf(
    nbhd: Any,
    nbhd_col: str | None = None,
    *,
    validate: bool = True,
) -> tuple[gpd.GeoDataFrame, str]:
    """Resolve neighborhood geometry and its id column from ``nbhd``.

    Accepts a ``GeoDataFrame`` or any object exposing ``to_geodataframe()`` or a
    ``geometry``/``gdf`` ``GeoDataFrame`` attribute (e.g. a
    ``dega_collection.NeighborhoodCollection``). For such objects their
    ``nbhd_col`` attribute is tried when the requested column is absent.

    Parameters
    ----------
    nbhd : GeoDataFrame or neighborhood-like object
        Neighborhood geometry, one row per neighborhood.
    nbhd_col : str, optional
        Column identifying each neighborhood; falls back to ``neighborhood_id``
        and ``nbhd_id`` when absent.
    validate : bool, default True
        Raise if the geometry column is missing or neighborhood ids are not unique.

    Returns
    -------
    tuple[GeoDataFrame, str]
        The neighborhood GeoDataFrame (not copied) and its resolved id column.
    """
    gdf = _nbhd_geometry(nbhd)
    if gdf is None:
        raise TypeError(
            "neighborhoods must be a GeoDataFrame or an object exposing "
            f"to_geodataframe(), got {type(nbhd).__name__}"
        )
    object_col = getattr(nbhd, "nbhd_col", None) if gdf is not nbhd else None
    resolved = _resolve_nbhd_col(gdf, nbhd_col, fallbacks=(object_col,) if object_col else ())
    if validate:
        if "geometry" not in gdf.columns:
            raise ValueError("gdf_nbhd missing required columns: {'geometry'}")
        if not gdf[resolved].astype(str).is_unique:
            raise ValueError(f"Neighborhood IDs in '{resolved}' must be unique")
    return gdf, resolved


def _unwrap_mudata(data: Any) -> Any:
    """Return the MuData held by a wrapper exposing ``mdata``, else ``data``."""
    inner = getattr(data, "mdata", None)
    return inner if inner is not None else data


def _is_multimodal(data: Any) -> bool:
    """True for MuData (or MuData-like objects with ``mod``), False for AnnData."""
    return not isinstance(data, AnnData) and hasattr(data, "mod")


def _cell_coords(
    data: Any,
    *,
    spatial_key: str = "spatial",
    modality: str | None = None,
) -> pd.DataFrame:
    """Cell x/y coordinates (columns ``x``, ``y``) indexed by cell id.

    For an ``AnnData`` they come from ``obsm[spatial_key]``. For a ``MuData`` they
    come from the ``modality`` (if given), the global ``obsm``, or the first
    modality that has them, indexed by that object's ``obs_names``.
    """
    data = _unwrap_mudata(data)
    if _is_multimodal(data):
        sources = [data.mod[modality]] if modality is not None else []
        sources += [data, *(data.mod[name] for name in data.mod if name != modality)]
    else:
        sources = [data]

    for source in sources:
        obsm = getattr(source, "obsm", None)
        if obsm is None or spatial_key not in obsm:
            continue
        xy = np.asarray(obsm[spatial_key])
        if xy.ndim == 2 and xy.shape[1] >= 2 and np.issubdtype(xy.dtype, np.number):
            return pd.DataFrame(
                xy[:, :2].astype(float),
                index=pd.Index(source.obs_names.astype(str)),
                columns=["x", "y"],
            )
    raise ValueError(f"adata.obsm missing '{spatial_key}' coordinates")


def _cell_obs_column(data: Any, column: str, *, modality: str | None = None) -> pd.Series:
    """A cell-level ``obs`` column, indexed by cell id.

    For a ``MuData`` the global ``obs`` is searched first (``column``, then
    ``"<modality>:<column>"``), then the modalities' own ``obs``.
    """
    data = _unwrap_mudata(data)
    if _is_multimodal(data):
        modalities = [modality] if modality is not None else list(data.mod)
        for key in (column, *(f"{name}:{column}" for name in modalities)):
            if key in data.obs.columns:
                series = data.obs[key]
                break
        else:
            for name in modalities:
                if column in data.mod[name].obs.columns:
                    series = data.mod[name].obs[column]
                    break
            else:
                raise ValueError(f"adata.obs missing required '{column}' column")
    else:
        if column not in data.obs.columns:
            raise ValueError(f"adata.obs missing required '{column}' column")
        series = data.obs[column]

    series = series.copy()
    series.index = series.index.astype(str)
    return series


def _category_colors(data: Any, category: str, *, modality: str | None = None) -> dict[str, str]:
    """Map each ``category`` value to its color from ``uns[f"{category}_colors"]``.

    Colors follow the categorical order when the column is categorical, and
    first-appearance order otherwise (scanpy's convention). Returns an empty
    dict when no palette is stored.
    """
    data = _unwrap_mudata(data)
    color_key = f"{category}_colors"
    unses = [data.uns]
    if _is_multimodal(data):
        modalities = [modality] if modality is not None else list(data.mod)
        unses += [data.mod[name].uns for name in modalities]

    colors = next((list(uns[color_key]) for uns in unses if color_key in uns), None)
    if colors is None:
        return {}

    labels = _cell_obs_column(data, category, modality=modality)
    if isinstance(labels.dtype, pd.CategoricalDtype):
        categories = list(labels.cat.categories)
    else:
        categories = list(pd.unique(labels.dropna()))
    return {str(cat): str(colors[i]) for i, cat in enumerate(categories) if i < len(colors)}


def _dissolve_by_category(gdf_nbhd: gpd.GeoDataFrame, category: str = "leiden") -> gpd.GeoDataFrame:
    """
    Dissolve neighborhood geometries by a categorical column.

    Parameters
    ----------
    gdf_nbhd : gpd.GeoDataFrame
        A GeoDataFrame containing neighborhood geometries and a categorical column.

    category : str, optional
        The name of the column to dissolve by. All geometries sharing the same
        category value will be merged into a single geometry. Default is "leiden".

    Returns
    -------
    gpd.GeoDataFrame
        A new GeoDataFrame where geometries have been dissolved (merged) by the
        specified category, preserving category labels as attributes.
    """

    return gdf_nbhd.dissolve(by=category, as_index=False)


def _add_centroids_to_obsm(
    adata: Any,
    gdf: gpd.GeoDataFrame,
    key: str = "spatial",
) -> None:
    """
    Computes centroid x, y coordinates from a GeoDataFrame and stores them in adata.obsm.
    """
    if len(adata) != len(gdf):
        raise ValueError("Number of rows in adata and gdf must match.")

    centroids = gdf.geometry.centroid
    spatial_coords = np.vstack([centroids.x.values, centroids.y.values]).T
    adata.obsm[key] = spatial_coords


def _classify_polygons_contains_check(
    polygons: gpd.GeoSeries | Sequence[base.BaseGeometry],
    points: Sequence[Any],
) -> gpd.GeoSeries:
    """
    Classifies polygons as "real" or "fake" based on whether they contain any points inside.

    Parameters
    ----------
    polygons : GeoSeries of polygons (GeoPandas)
    points : Array-like of point coordinates (e.g., numpy array or list of tuples)

    Returns
    -------
    GeoSeries of curated polygons.
    """
    points_gdf = gpd.GeoDataFrame(geometry=[Point(p) for p in points])
    gdf_poly = gpd.GeoDataFrame(geometry=polygons)
    joined = gpd.sjoin(points_gdf, gdf_poly, predicate="within")
    real_polygons_indices = joined["index_right"].unique()
    curated_polygons = gdf_poly.iloc[real_polygons_indices]
    # Use .get() for a more concise and idiomatic way to handle the conditional return
    return curated_polygons.get("geometry", curated_polygons)


def _get_df_cell(adata: Any) -> pd.DataFrame:
    """
    Load cell-level cluster and spatial coordinates from an h5ad file as a DataFrame.
    """
    df_cell = pd.DataFrame(
        {
            "cluster": adata.obs["leiden"],
            "x": adata.obsm["spatial"][:, 0],
            "y": adata.obsm["spatial"][:, 1],
        }
    )
    df_cell["geometry"] = df_cell.apply(
        lambda row: [round(row["x"], 3), round(row["y"], 3)], axis=1
    )
    return df_cell


def _get_gdf_cell(adata: Any) -> gpd.GeoDataFrame:
    """
    Load cell-level cluster and spatial coordinates from an h5ad file as a GeoDataFrame.

    No CRS is set since coordinates are in micron imaging space, not geospatial.
    """
    return gpd.GeoDataFrame(
        {"cluster": adata.obs["leiden"]},
        geometry=gpd.points_from_xy(*adata.obsm["spatial"].T[:2]),
    )


def read_transcripts(data_dir: str, *, cell_id: bool = True) -> gpd.GeoDataFrame:
    """
    Load ``transcripts.parquet`` as a GeoDataFrame of transcript points.

    No CRS is set since coordinates are in micron imaging space, not geospatial.

    Parameters
    ----------
    data_dir : str
        Directory containing ``transcripts.parquet`` (Xenium column names
        ``feature_name``, ``x_location``, ``y_location``, ``cell_id``).
    cell_id : bool, default True
        Also load the ``cell_id`` column (needed for transcript assignment).

    Returns
    -------
    gpd.GeoDataFrame
        Columns ``feature_name`` (and ``cell_id``) plus point ``geometry``.
    """
    columns = ["feature_name", "x_location", "y_location"]
    if cell_id:
        columns.append("cell_id")
    df_trx = pd.read_parquet(f"{data_dir}/transcripts.parquet", columns=columns, engine="pyarrow")
    geometry = gpd.points_from_xy(df_trx["x_location"], df_trx["y_location"])
    keep = ["feature_name", "cell_id"] if cell_id else ["feature_name"]
    return gpd.GeoDataFrame(df_trx[keep], geometry=geometry)


def stamp_z(
    geometry: base.BaseGeometry | None,
    z: float,
) -> base.BaseGeometry | None:
    """
    Stamp a constant Z onto every vertex of a 2D geometry.

    Used to place a 2D alpha-shape polygon (or any other geometry) at a fixed
    height in a 3D scene, e.g. one alpha shape per (slice, cluster) placed at
    its slice's Z coordinate. Any desired per-geometry offset (e.g. a small
    jitter to avoid z-fighting between coplanar overlapping polygons within a
    slice) should already be folded into `z`.

    Parameters
    ----------
    geometry : Shapely geometry object (e.g., Polygon, MultiPolygon), or None.
    z : float
        Constant Z value to assign to every vertex.

    Returns
    -------
    Shapely geometry with a Z ordinate on every vertex, or None.
    """
    if geometry is None:
        return None

    def add_z(x: float, y: float, _z: float | None = None) -> tuple[float, float, float]:
        return (x, y, np.full_like(x, z))

    return transform(add_z, geometry)


def _round_coordinates(
    geometry: base.BaseGeometry | None, precision: int = 2
) -> base.BaseGeometry | None:
    """
    Round the coordinates of a Shapely geometry to the specified precision.

    Parameters
    ----------
    geometry : Shapely geometry object (e.g., Polygon, MultiPolygon).
    precision : int
        Number of decimal places to round to.

    Returns
    -------
    Rounded Shapely geometry or None.
    """
    if geometry is None:
        return None

    def round_coords(
        x: float, y: float, z: float | None = None
    ) -> tuple[float, float] | tuple[float, float, float]:
        if z is not None:
            return (round(x, precision), round(y, precision), round(z, precision))
        return (round(x, precision), round(y, precision))

    return transform(round_coords, geometry)
