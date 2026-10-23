"""Neighborhood generation and calculation.

Neighborhoods are ``GeoDataFrame`` objects (one row per neighborhood) built
from cells (alpha shapes, hextiles, gradient rings) and summarized against
cell-level ``AnnData``/``MuData`` into new neighborhood-level ``AnnData``.
"""

from .alpha_shapes import (
    alpha_shape,
    alpha_shape_cell_clusters,
    alpha_shape_cell_clusters_by_slice,
    filter_alpha_shapes,
)
from .gradient import _get_micron_per_pixel, calc_gradient
from .hextile import generate_hextile, hextile_niche
from .neighborhoods import (
    calc_nbhd_bordering,
    calc_nbhd_by_gene,
    calc_nbhd_by_pop,
    calc_nbhd_overlap,
    calc_nbhd_transcript_assignment,
)
from .utils import (
    _add_centroids_to_obsm,
    _dissolve_by_category,
    _get_df_cell,
    _get_gdf_cell,
    read_transcripts,
    stamp_z,
)
from .zonal_stats import calc_img_zonal_stats


__all__ = [
    "_add_centroids_to_obsm",
    "_dissolve_by_category",
    "_get_df_cell",
    "_get_gdf_cell",
    "alpha_shape",
    "alpha_shape_cell_clusters",
    "alpha_shape_cell_clusters_by_slice",
    "calc_gradient",
    "calc_img_zonal_stats",
    "calc_nbhd_bordering",
    "calc_nbhd_by_gene",
    "calc_nbhd_by_pop",
    "calc_nbhd_overlap",
    "calc_nbhd_transcript_assignment",
    "filter_alpha_shapes",
    "generate_hextile",
    "hextile_niche",
    "read_transcripts",
    "stamp_z",
]
