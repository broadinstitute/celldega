"""`celldega.pre` keeps its import surface stable while the package is reorganised.

The implementation is being moved out of ``pre/__init__.py`` into named submodules. That
move must be invisible to callers: 17 notebooks reach these names through attribute access
(``dega.pre.make_meta_gene``), ``celldega.qc`` imports some of them eagerly at module
import time, and ``celldega.align`` imports others lazily from inside function bodies.

This file is the guard for that. It is deliberately written against the *pre-refactor*
package so that every subsequent move is verified by it staying green.

Names are listed explicitly rather than snapshotted to a fixture file, so that removing one
requires editing this list — which is the point at which someone has to justify the break.
"""

import importlib
import inspect

import pytest

import celldega.pre as pre


# Public functions reachable as ``celldega.pre.<name>``. Grouped by the submodule that owns
# them after the reorganisation, so a reviewer can see what each move is responsible for.
PUBLIC_BY_OWNER = {
    "cell_clusters": [
        "add_clustering_from_adata",
        "cluster_gene_expression",
        "create_cluster_and_meta_cluster",
    ],
    "image_tiles": [
        "create_image_tiles",
        "create_image_tiles_h_and_e",
        "create_image_tiles_merscope",
        "create_image_tiles_xenium",
        "make_deepzoom_pyramid",
        "remove_intermediate_files",
    ],
    "image_parquet": [
        "get_max_zoom_level",
        "pack_image_tiles_to_parquet",
    ],
    "deepzoom": [
        "write_deepzoom_pyramid",
    ],
    "meta_cell": [
        "make_meta_cell_image_coord",
        "make_meta_gene",
    ],
    "landscape_parameters": [
        "save_landscape_parameters",
    ],
    "workflows": [
        "add_custom_segmentation",
        "make_chromium_from_anndata",
    ],
    "raw_bundle": [
        "write_identity_transform",
        "write_xenium_transform",
    ],
    # Already-separate submodules, re-exported by the facade today and after.
    "image_info": [
        "get_image_info",
        "resolve_xenium_morphology_ome_path",
    ],
    "landscape": [
        "calc_meta_gene_data",
        "read_cbg_mtx",
        "save_cbg_gene_parquets",
        "save_cbg_gene_parquets_row_groups",
    ],
    "boundary_tile": [
        "make_cell_boundary_tiles",
        "make_cell_boundary_tiles_row_groups",
    ],
    "trx_tile": [
        "make_trx_tiles",
        "make_trx_tiles_row_groups",
    ],
    "sbg_tile": [
        "write_pseudotranscripts_from_sbg",
    ],
    "nbhd_cloud": [
        "write_cell_clusters_meta",
        "write_gene_cell_scatter",
        "write_gene_shapes",
        "write_gene_shapes_streaming",
        "write_meta_gene_for_nbhd_cloud",
        "write_meta_slice",
        "write_nbhd_cloud_cells",
        "write_nbhd_cloud_dataset",
        "write_nbhd_cloud_shapes_and_features",
    ],
}

PUBLIC_NAMES = sorted(n for names in PUBLIC_BY_OWNER.values() for n in names)

# Underscore-prefixed names that external code already depends on, so they cannot be
# dropped by the move even though the leading underscore says "private".
PRIVATE_NAMES_IN_USE = {
    # `from celldega.pre import _to_geometry` in 4 BNB notebooks; also the only private
    # name in the current __all__.
    "_to_geometry": "notebooks/BNB_*.ipynb",
    "_to_coords": "notebooks/nbhd_class_eda.ipynb",
    "_convert_to_png": "notebooks/Visium-HD_Landscape_Pre-process.ipynb",
    # The CLI pipeline reaches these through the package facade rather than importing the
    # submodule, so they must stay attributes of celldega.pre:
    #   grep -rn 'dega\.pre\._' src/  ->  exactly these two.
    "_xenium_unzipper": "src/celldega/pre/run_pre_processing.py:207",
    "_check_required_files": "src/celldega/pre/run_pre_processing.py:216",
}

# Submodules that must stay importable as ``celldega.pre.<name>``.
SUBMODULES = [
    "boundary_tile",
    "image_info",
    "landscape",
    "nbhd_cloud",
    "run_pre_processing",
    "sbg_tile",
    "trx_tile",
]


# --- names stay reachable ----------------------------------------------------


@pytest.mark.parametrize("name", PUBLIC_NAMES)
def test_public_name_is_reachable_on_the_package(name: str) -> None:
    """Notebooks use attribute access (``dega.pre.X``), which bypasses ``__all__``."""
    assert callable(getattr(pre, name)), name


@pytest.mark.parametrize(("name", "used_by"), sorted(PRIVATE_NAMES_IN_USE.items()))
def test_private_name_in_external_use_is_reachable(name: str, used_by: str) -> None:
    assert callable(getattr(pre, name)), f"{name} is used by {used_by}"


@pytest.mark.parametrize("name", SUBMODULES)
def test_submodule_is_importable(name: str) -> None:
    """``celldega.qc`` and the notebooks import these paths directly."""
    assert importlib.import_module(f"celldega.pre.{name}") is not None


# --- signatures stay stable --------------------------------------------------

# Signatures that appear in the mkdocs-published notebooks. A change here breaks a
# documented call site, so it should be a deliberate edit rather than a side effect.
PUBLISHED_SIGNATURES = {
    "make_chromium_from_anndata": ["adata", "path_dega_files"],
    "make_meta_gene": ["cbg", "path_output"],
    "write_identity_transform": ["path_dega_files"],
    "get_image_info": ["technology", "image_tile_layer"],
}


@pytest.mark.parametrize(("name", "expected"), sorted(PUBLISHED_SIGNATURES.items()))
def test_published_signature_is_unchanged(name: str, expected: list[str]) -> None:
    params = list(inspect.signature(getattr(pre, name)).parameters)
    assert params[: len(expected)] == expected


# --- the facade's own contract -----------------------------------------------


def test_main_is_present_and_lazy() -> None:
    """``pre.main`` must import run_pre_processing inside its body.

    ``run_pre_processing.py`` does ``import celldega as dega`` at module scope, so hoisting
    that import into the facade reintroduces a partially-initialised-package cycle through
    ``celldega/__init__.py``.
    """
    source = inspect.getsource(pre.main)
    assert "from .run_pre_processing import" in source


def test_star_import_exposes_only_declared_names() -> None:
    namespace: dict[str, object] = {}
    exec("from celldega.pre import *", namespace)
    namespace.pop("__builtins__", None)
    assert set(namespace) == set(pre.__all__)


def test_all_entries_resolve() -> None:
    """Every ``__all__`` entry must exist — otherwise ``import *`` raises AttributeError."""
    missing = [n for n in pre.__all__ if not hasattr(pre, n)]
    assert missing == []


def test_celldega_reexports_the_landscape_submodule() -> None:
    """``celldega/__init__.py:11`` re-exports this, and it is in ``celldega.__all__``."""
    import celldega

    assert celldega.landscape is pre.landscape


# --- published documentation surface -----------------------------------------


def _griffe_public_members() -> set[str]:
    """What ``::: celldega.pre`` in docs/python/pre/api.md resolves to.

    mkdocstrings renders an *imported* member only when it is listed in ``__all__``, so
    once implementation moves out of ``__init__.py`` every moved function becomes an alias
    and silently drops off the API page unless ``__all__`` is corrected. Asserting this
    here rather than via ``mkdocs build --strict`` is deliberate: a strict build already
    fails on the current tree over unrelated docstring defects, so it gives no signal.
    """
    griffe = pytest.importorskip("griffe")
    module = griffe.load("celldega.pre", search_paths=["src"])
    return {name for name, obj in module.members.items() if obj.is_public}


def test_every_public_name_reaches_the_docs() -> None:
    missing = sorted(set(PUBLIC_NAMES) - _griffe_public_members())
    assert missing == []


def test_docs_surface_does_not_shrink() -> None:
    """Whatever the refactor does, it must not remove names from the published page."""
    already_published = {
        "add_clustering_from_adata",
        "get_image_info",
        "main",
        "make_trx_tiles",
        "read_cbg_mtx",
        "resolve_xenium_morphology_ome_path",
        "write_cell_clusters_meta",
        "write_gene_cell_scatter",
        "write_gene_shapes",
        "write_gene_shapes_streaming",
        "write_identity_transform",
        "write_meta_gene_for_nbhd_cloud",
        "write_meta_slice",
        "write_nbhd_cloud_cells",
        "write_nbhd_cloud_dataset",
        "write_nbhd_cloud_shapes_and_features",
    }
    assert already_published <= _griffe_public_members()
