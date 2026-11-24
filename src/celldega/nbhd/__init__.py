"""Neighborhoods: build tissue regions from cells, and summarize what is in them.

Neighborhoods are ``GeoDataFrame`` objects (one row per neighborhood). Build
them with ``alpha_shape_cell_clusters`` (concave hulls around each cluster's
cells), ``generate_hextile`` (a hexagonal grid), ``hextile_niche`` (hexagons
merged by cluster) or ``calc_gradient`` (rings in and out of a region), or draw
them on a ``Landscape``. Then summarize them against cell-level ``AnnData`` or
``MuData`` into neighborhood-level ``AnnData`` ready for a Clustergram:
``calc_nbhd_by_pop`` (composition), ``calc_nbhd_by_gene`` (expression),
``calc_nbhd_overlap`` and ``calc_nbhd_bordering`` (relations between
neighborhoods). ``NeighborhoodCollection`` stores a set of neighborhoods with
their geometry and these summaries.
"""

from .alpha_shapes import (
    alpha_shape,
    alpha_shape_cell_clusters,
    alpha_shape_cell_clusters_by_slice,
    filter_alpha_shapes,
)
from .collection import NeighborhoodCollection
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
    "NeighborhoodCollection",
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
