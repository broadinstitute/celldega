"""
Module for pre-processing to generate LandscapeFiles from ST data.
"""

from .boundary_tile import (
    _round_nested_coord_list,
    make_cell_boundary_tiles,
    make_cell_boundary_tiles_row_groups,
)
from .cell_clusters import (
    _load_xenium_cluster_data,
    _save_cluster_data,
    add_clustering_from_adata,
    cluster_gene_expression,
    create_cluster_and_meta_cluster,
)
from .colors import _create_cluster_colors, _hsv_to_hex
from .deepzoom import write_deepzoom_pyramid
from .geometry import _to_coords, _to_geometry
from .image_info import get_image_info, resolve_xenium_morphology_ome_path
from .image_parquet import pack_image_tiles_to_parquet
from .image_tiles import (
    _convert_to_jpeg,
    _convert_to_png,
    _convert_to_webp,
    _process_image_channel,
    _reduce_image_size,
    create_image_tiles,
    create_image_tiles_h_and_e,
    create_image_tiles_merscope,
    create_image_tiles_xenium,
    make_deepzoom_pyramid,
    remove_intermediate_files,
)
from .landscape import (
    calc_meta_gene_data,
    read_cbg_mtx,
    save_cbg_gene_parquets,
    save_cbg_gene_parquets_row_groups,
)
from .landscape_parameters import get_max_zoom_level, save_landscape_parameters
from .meta_cell import (
    _convert_long_id_to_short,
    _load_meta_cell_by_technology,
    make_meta_cell_image_coord,
    make_meta_gene,
)
from .nbhd_cloud import (
    write_cell_clusters_meta,
    write_gene_cell_scatter,
    write_gene_shapes,
    write_gene_shapes_streaming,
    write_meta_gene_for_nbhd_cloud,
    write_meta_slice,
    write_nbhd_cloud_cells,
    write_nbhd_cloud_dataset,
    write_nbhd_cloud_shapes_and_features,
)
from .raw_bundle import (
    _check_required_files,
    _xenium_unzipper,
    write_identity_transform,
    write_xenium_transform,
)
from .sbg_tile import write_pseudotranscripts_from_sbg
from .trx_tile import make_trx_tiles, make_trx_tiles_row_groups
from .workflows import add_custom_segmentation, make_chromium_from_anndata


def main(*args, **kwargs):
    """Run the command-line pre-processing pipeline.

    The import stays inside the body on purpose: ``run_pre_processing`` does
    ``import celldega as dega`` at module scope, so importing it here would create a
    partially-initialised-package cycle through ``celldega/__init__.py``.
    """
    from .run_pre_processing import main as _main

    return _main(*args, **kwargs)


# Every public function of the package is listed, not just the historical subset.
# docs/python/pre/api.md renders `::: celldega.pre`, and mkdocstrings only documents an
# *imported* member when it appears here -- so now that the implementation lives in
# submodules, an omission silently drops the function from the published API page.
__all__ = [
    "_to_geometry",
    "add_clustering_from_adata",
    "add_custom_segmentation",
    "boundary_tile",
    "calc_meta_gene_data",
    "cell_clusters",
    "cluster_gene_expression",
    "colors",
    "create_cluster_and_meta_cluster",
    "create_image_tiles",
    "create_image_tiles_h_and_e",
    "create_image_tiles_merscope",
    "create_image_tiles_xenium",
    "deepzoom",
    "geometry",
    "get_image_info",
    "get_max_zoom_level",
    "image_info",
    "image_parquet",
    "image_tiles",
    "landscape",
    "landscape_parameters",
    "main",
    "make_cell_boundary_tiles",
    "make_cell_boundary_tiles_row_groups",
    "make_chromium_from_anndata",
    "make_deepzoom_pyramid",
    "make_meta_cell_image_coord",
    "make_meta_gene",
    "make_trx_tiles",
    "make_trx_tiles_row_groups",
    "meta_cell",
    "nbhd_cloud",
    "pack_image_tiles_to_parquet",
    "raw_bundle",
    "read_cbg_mtx",
    "remove_intermediate_files",
    "resolve_xenium_morphology_ome_path",
    "save_cbg_gene_parquets",
    "save_cbg_gene_parquets_row_groups",
    "save_landscape_parameters",
    "sbg_tile",
    "trx_tile",
    "workflows",
    "write_cell_clusters_meta",
    "write_deepzoom_pyramid",
    "write_gene_cell_scatter",
    "write_gene_shapes",
    "write_gene_shapes_streaming",
    "write_identity_transform",
    "write_meta_gene_for_nbhd_cloud",
    "write_meta_slice",
    "write_nbhd_cloud_cells",
    "write_nbhd_cloud_dataset",
    "write_nbhd_cloud_shapes_and_features",
    "write_pseudotranscripts_from_sbg",
    "write_xenium_transform",
]
