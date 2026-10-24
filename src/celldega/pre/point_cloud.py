"""Write cell-level AnnData to point-cloud DegaFiles for the ``CellCloud`` widget.

A point-cloud DegaFiles directory holds cell positions in
``cell_metadata.parquet`` (columns ``name`` + ``geometry``, where ``geometry``
is a fixed-size ``[x, y, z]`` list), optional clusters in ``cell_clusters/``,
optional gene expression in ``cbg/`` + ``meta_gene.parquet`` (keyed by cell
name, since point clouds use ``use_int_index=false``), and a manifest written
as both ``cell_cloud.json`` and ``landscape_parameters.json``.

Named position variants (e.g. several 3D alignments of the same cells) are
written as ``cell_metadata_<name>.parquet`` and listed under ``"alignments"``
in the manifest; view one with ``CellCloud(base_url=..., alignment="<name>")``.

Two modes, chosen automatically from whether the target already contains a
manifest:

* **create** — a fresh directory. Writes the positions, clusters from
  ``obs[cluster_key]``, gene expression when ``adata`` carries an expression
  matrix, and a minimal point-cloud manifest.
* **append** — an existing point-cloud DegaFiles. Only a named position
  variant is written and registered; existing ``cell_clusters/``, ``cbg/`` and
  ``meta_gene.parquet`` are reused (clusters are matched to cells by name,
  not row order).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from scipy.sparse import issparse


#: Manifest filenames of a point-cloud DegaFiles. The ``CellCloud`` widget
#: fetches ``cell_cloud.json``; ``landscape_parameters.json`` is written too so
#: older loaders keep working.
POINT_CLOUD_MANIFEST_NAMES = ("landscape_parameters.json", "cell_cloud.json")

# Variant names become a filename suffix (cell_metadata_<name>.parquet) and a
# JSON/JS identifier, so keep them to a conservative, filesystem-safe slug.
_VALID_VARIANT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validate_variant_name(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string.")
    if name == "default":
        raise ValueError("name 'default' is reserved for the base cell_metadata.parquet.")
    if not _VALID_VARIANT_NAME.match(name):
        raise ValueError(
            f"Invalid name {name!r}: use only letters, digits, '.', '_', '-' "
            "(and start with a letter or digit)."
        )
    return name


def _build_coordinates(adata: Any, z_key: str | None) -> np.ndarray:
    """Return an ``(n, 3)`` float array of ``[x, y, z]`` centroids."""
    spatial = adata.obsm.get("spatial")
    if spatial is None:
        raise ValueError("adata.obsm['spatial'] is required to write cell positions.")
    spatial = np.asarray(spatial, dtype=float)
    if spatial.ndim != 2 or spatial.shape[1] < 2:
        raise ValueError("adata.obsm['spatial'] must be an (n, >=2) array of coordinates.")

    xy = spatial[:, :2]

    if z_key is not None and z_key in adata.obs.columns:
        z = np.asarray(adata.obs[z_key], dtype=float)
    elif spatial.shape[1] >= 3:
        z = spatial[:, 2]
    else:
        z = np.zeros(adata.n_obs, dtype=float)

    if z.shape[0] != xy.shape[0]:
        raise ValueError("z coordinate length does not match the number of cells.")

    return np.column_stack([xy, z]).astype(np.float32)


def _write_cell_metadata(path: Path, names: Any, coords: np.ndarray) -> None:
    """Write a ``name`` + ``geometry`` (fixed-size ``[x, y, z]``) parquet file."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    flat = np.ascontiguousarray(coords, dtype=np.float32).reshape(-1)
    geometry = pa.FixedSizeListArray.from_arrays(pa.array(flat, type=pa.float32()), list_size=3)
    table = pa.table(
        {
            "name": pa.array([str(n) for n in names], type=pa.string()),
            "geometry": geometry,
        }
    )
    pq.write_table(table, path, compression="snappy")


def _expression_matrix(adata: Any) -> Any:
    return adata.layers.get("counts", adata.X)


def _has_expression(adata: Any) -> bool:
    """True if ``adata`` carries a non-empty expression matrix to export.

    A placeholder all-zero matrix (e.g. AnnData's default single dummy column)
    has nothing to color by, so it does not count.
    """
    if adata.n_vars == 0:
        return False
    x = _expression_matrix(adata)
    if x is None:
        return False
    if issparse(x):
        return x.nnz > 0
    return bool(np.any(np.asarray(x) != 0))


def _write_cbg_and_meta_gene(dega_files_dir: Path, adata: Any) -> None:
    """Write name-indexed per-gene ``cbg/`` parquets + ``meta_gene.parquet``.

    Point-cloud DegaFiles use ``use_int_index=false``, so gene expression is
    keyed by cell *name* (pandas writes the index as ``__index_level_0__``,
    which the gene-expression reader accepts) rather than an integer row index.
    """
    from celldega.pre import make_meta_gene

    x = _expression_matrix(adata)
    if issparse(x):
        cbg = pd.DataFrame.sparse.from_spmatrix(x, index=adata.obs_names, columns=adata.var_names)
    else:
        cbg = pd.DataFrame(np.asarray(x), index=adata.obs_names, columns=adata.var_names)

    cbg_dir = dega_files_dir / "cbg"
    cbg_dir.mkdir(exist_ok=True)
    for gene in cbg.columns:
        # Densify the column (a sparse DataFrame column can't be replaced in
        # place) before dropping zeros so each gene file lists only expressing
        # cells, keyed by cell name.
        inst_df = pd.DataFrame(np.asarray(cbg[[gene]].values), columns=[gene], index=cbg.index)
        inst_df.replace(0, pd.NA, inplace=True)
        inst_df.dropna(how="all", inplace=True)
        if not inst_df.empty:
            inst_df.index.name = None
            inst_df.to_parquet(cbg_dir / f"{gene}.parquet", index=True)

    make_meta_gene(cbg, dega_files_dir / "meta_gene.parquet")


def _write_manifests(dega_files_dir: Path, params: dict) -> None:
    """Write ``params`` under every point-cloud manifest filename."""
    for manifest_name in POINT_CLOUD_MANIFEST_NAMES:
        with (dega_files_dir / manifest_name).open("w") as f:
            json.dump(params, f, indent=2)


def _register_variant(params_path: Path, name: str) -> list[str]:
    """Add ``name`` to the manifest's ``"alignments"`` list."""
    with params_path.open() as f:
        params = json.load(f)

    variants = params.get("alignments")
    if not isinstance(variants, list):
        variants = []
    if name not in variants:
        variants.append(name)
    params["alignments"] = variants

    _write_manifests(params_path.parent, params)
    return variants


def _new_manifest(name: str | None) -> dict:
    """Minimal point-cloud manifest (create mode)."""
    return {
        "technology": "point-cloud",
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": None,
        "tile_size": 1,
        "image_info": [],
        "image_format": ".webp",
        "use_int_index": False,
        "alignments": [name] if name is not None else [],
    }


def write_point_cloud_dataset(
    adata: Any,
    path_dega_files: str | Path,
    *,
    name: str | None = None,
    z_key: str | None = "Z",
    cluster_key: str | None = None,
    write_genes: bool | None = None,
    write_base_metadata: bool | None = None,
    overwrite: bool = False,
) -> Path:
    """Write cell positions (and clusters/genes) to a point-cloud DegaFiles.

    Parameters
    ----------
    adata : AnnData
        Cell-level AnnData. ``obsm["spatial"]`` provides x/y (its first two
        columns); z is taken from ``obs[z_key]`` if present, else from a third
        ``spatial`` column, else 0. Cell names come from ``obs_names``.
    path_dega_files : str or Path
        Target point-cloud DegaFiles directory. If it already contains a
        manifest the writer *appends* a named position variant; otherwise it
        *creates* a fresh point-cloud directory.
    name : str, optional
        Name of a position variant (e.g. one alignment of the cells). Positions
        are written to ``cell_metadata_<name>.parquet`` and the name is listed
        under ``"alignments"`` in the manifest; view it with
        ``CellCloud(..., alignment="<name>")``. Required in append mode. When
        omitted, only the base ``cell_metadata.parquet`` is written.
    z_key : str, optional, default "Z"
        ``obs`` column holding the z (depth) coordinate.
    cluster_key : str, optional
        Only used in *create* mode: ``obs`` column to export as clusters (with
        colors from ``uns[f"{cluster_key}_colors"]`` when available).
    write_genes : bool, optional
        Only used in *create* mode. Whether to export gene expression to
        ``cbg/`` + ``meta_gene.parquet`` (keyed by cell name). Defaults to
        ``True`` when ``adata`` carries an expression matrix
        (``layers['counts']`` or ``X``).
    write_base_metadata : bool, optional
        Whether to also (over)write the base ``cell_metadata.parquet`` with these
        positions. Defaults to ``True`` in create mode and ``False`` in append
        mode (so an append never clobbers the existing default positions).
    overwrite : bool, default False
        Allow overwriting an existing ``cell_metadata_<name>.parquet``, or an
        existing dataset when no ``name`` is given.

    Returns
    -------
    pathlib.Path
        Path to the written positions file (the named variant when ``name`` is
        given, else ``cell_metadata.parquet``).
    """
    if name is not None:
        _validate_variant_name(name)
    dega_files_dir = Path(path_dega_files)

    params_path = dega_files_dir / "landscape_parameters.json"
    append_mode = params_path.exists() or (dega_files_dir / "cell_cloud.json").exists()

    if append_mode and name is None and not overwrite:
        raise FileExistsError(
            f"{dega_files_dir} already holds a point-cloud dataset. Pass name=... to add "
            "a position variant, or overwrite=True to rewrite it."
        )
    if append_mode and name is None:
        append_mode = False

    # Validate everything before writing, so a failed call leaves nothing behind
    coords = _build_coordinates(adata, z_key)
    if not append_mode:
        if cluster_key is not None and cluster_key not in adata.obs.columns:
            raise ValueError(f"cluster_key {cluster_key!r} not found in adata.obs")
        if write_genes is None:
            write_genes = _has_expression(adata)
        if write_genes and not _has_expression(adata):
            raise ValueError(
                "write_genes=True but adata has no expression matrix (X / layers['counts'])."
            )
        dega_files_dir.mkdir(parents=True, exist_ok=True)
    names = adata.obs_names

    base_path = dega_files_dir / "cell_metadata.parquet"
    written = base_path
    if name is not None:
        written = dega_files_dir / f"cell_metadata_{name}.parquet"
        if written.exists() and not overwrite:
            raise FileExistsError(
                f"{written.name} already exists. Pass overwrite=True to replace it."
            )
        _write_cell_metadata(written, names, coords)

    if write_base_metadata is None:
        write_base_metadata = not append_mode
    if write_base_metadata:
        _write_cell_metadata(base_path, names, coords)

    if append_mode:
        if not params_path.exists():
            with (dega_files_dir / "cell_cloud.json").open() as f:
                _write_manifests(dega_files_dir, json.load(f))
        _register_variant(params_path, name)
        return written

    if cluster_key is not None:
        from celldega.pre import add_clustering_from_adata

        add_clustering_from_adata(adata, dega_files_dir, cluster_key=cluster_key)
    if write_genes:
        _write_cbg_and_meta_gene(dega_files_dir, adata)
    # The manifest goes last: a directory without one is never mistaken for a
    # complete dataset (a retry runs in create mode again).
    _write_manifests(dega_files_dir, _new_manifest(name))

    return written
