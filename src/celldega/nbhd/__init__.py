"""Module for performing neighborhood analysis."""

from .alpha_shapes import alpha_shape, alpha_shape_cell_clusters, filter_alpha_shapes
from .collection import NeighborhoodCollection
from .gradient import _get_micron_per_pixel
from .hextile import generate_hextile, hextile_niche
from .utils import (
    _add_centroids_to_obsm,
    _dissolve_by_category,
    _get_df_cell,
    _get_gdf_cell,
    _get_gdf_trx,
    df_to_anndata,
    make_column_names_unique_fast,
    safe_polygon,
    simple_format,
    transform_polygon,
)


__all__ = [
    "NeighborhoodCollection",
    "_add_centroids_to_obsm",
    "_dissolve_by_category",
    "_get_df_cell",
    "_get_gdf_cell",
    "_get_gdf_trx",
    "alpha_shape",
    "alpha_shape_cell_clusters",
    "df_to_anndata",
    "filter_alpha_shapes",
    "generate_hextile",
    "hextile_niche",
    "make_column_names_unique_fast",
    "safe_polygon",
    "simple_format",
    "transform_polygon",
]
