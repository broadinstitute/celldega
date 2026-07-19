"""Module for performing neighborhood analysis."""

from .alpha_shapes import (
    alpha_shape,
    alpha_shape_cell_clusters,
    alpha_shape_cell_clusters_by_slice,
    alpha_shape_gene_expression_by_slice,
    filter_alpha_shapes,
    iter_gene_alpha_shapes_by_slice,
)
from .collection import NeighborhoodCollection
from .gradient import _get_micron_per_pixel
from .hextile import generate_hextile, hextile_niche
from .utils import (
    _add_centroids_to_obsm,
    _dissolve_by_category,
    _get_df_cell,
    _get_gdf_cell,
    _get_gdf_trx,
    _stamp_z,
)


__all__ = [
    "NeighborhoodCollection",
    "_add_centroids_to_obsm",
    "_dissolve_by_category",
    "_get_df_cell",
    "_get_gdf_cell",
    "_get_gdf_trx",
    "_stamp_z",
    "alpha_shape",
    "alpha_shape_cell_clusters",
    "alpha_shape_cell_clusters_by_slice",
    "alpha_shape_gene_expression_by_slice",
    "filter_alpha_shapes",
    "generate_hextile",
    "hextile_niche",
    "iter_gene_alpha_shapes_by_slice",
]
