"""Write aligned 3D cell centroids to point-cloud DegaFiles as named alignments.

A point-cloud :class:`~celldega.viz.Landscape` reads cell positions from a
``cell_metadata.parquet`` (columns ``name`` + ``geometry``, where ``geometry``
is a length-3 ``[x, y, z]`` list). This module writes an *aligned* AnnData
(x/y from ``obsm["spatial"]``, z from an ``obs`` column such as the ``"Z"``
assigned by :func:`~celldega.align.serial_slices.align_serial_slices`) into a
point-cloud DegaFiles directory as a named variant
``cell_metadata_<alignment_name>.parquet`` and registers that name under a new
``"alignments"`` key in ``landscape_parameters.json``.

Two modes, chosen automatically from whether the target already contains a
``landscape_parameters.json``:

* **append** — an existing point-cloud DegaFiles (with clusters/genes). Only the
  positions file is written and the alignment is registered; existing
  ``cell_clusters/``, ``cbg/`` and ``meta_gene.parquet`` are left untouched, so
  the new alignment reuses all existing cluster and gene data (clusters are
  matched to cells by name, not row order). This is the primary use case.
* **create** — a fresh directory. Writes the positions, a base
  ``cell_metadata.parquet`` (so a plain, alignment-less view also works),
  optional clusters from ``obs[cluster_key]``, gene expression to ``cbg/`` +
  ``meta_gene.parquet`` when ``adata`` carries an expression matrix (keyed by
  cell name, since point clouds use ``use_int_index=false``), and a minimal
  point-cloud ``landscape_parameters.json``.

View a written alignment with
``Landscape(technology="point-cloud", base_url=..., alignment="<alignment_name>")``.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import numpy as np


# Alignment names become a filename suffix (cell_metadata_<name>.parquet) and a
# JSON/JS identifier, so keep them to a conservative, filesystem-safe slug.
_VALID_ALIGNMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validate_alignment_name(alignment_name: str) -> str:
    if not isinstance(alignment_name, str) or not alignment_name:
        raise ValueError("alignment_name must be a non-empty string.")
    if alignment_name == "default":
        raise ValueError("alignment_name 'default' is reserved for the base cell_metadata.parquet.")
    if not _VALID_ALIGNMENT_NAME.match(alignment_name):
        raise ValueError(
            f"Invalid alignment_name {alignment_name!r}: use only letters, digits, "
            "'.', '_', '-' (and start with a letter or digit)."
        )
    return alignment_name


def _build_coordinates(adata, z_key: str) -> np.ndarray:
    """Return an ``(n, 3)`` float array of aligned ``[x, y, z]`` centroids."""
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


def _write_cell_metadata(path: Path, names, coords: np.ndarray) -> None:
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


def _has_expression(adata) -> bool:
    """True if ``adata`` carries a non-empty expression matrix to export.

    A placeholder all-zero matrix (e.g. AnnData's default single dummy column)
    has nothing to color by, so it does not count.
    """
    from scipy.sparse import issparse

    if adata.n_vars == 0:
        return False
    x = adata.layers.get("counts") if "counts" in adata.layers else adata.X
    if x is None:
        return False
    if issparse(x):
        return x.nnz > 0
    return bool(np.any(np.asarray(x) != 0))


def _cbg_from_adata(adata):
    """Cells-by-genes DataFrame (sparse when the source matrix is sparse)."""
    import pandas as pd
    from scipy.sparse import issparse

    x = adata.layers.get("counts") if "counts" in adata.layers else adata.X
    if issparse(x):
        return pd.DataFrame.sparse.from_spmatrix(x, index=adata.obs_names, columns=adata.var_names)
    return pd.DataFrame(np.asarray(x), index=adata.obs_names, columns=adata.var_names)


def _write_cbg_and_meta_gene(dega_files_dir: Path, adata) -> None:
    """Write name-indexed per-gene ``cbg/`` parquets + ``meta_gene.parquet``.

    Point-cloud DegaFiles use ``use_int_index=false``, so gene expression is
    keyed by cell *name* (pandas writes the index as ``__index_level_0__``,
    which the gene-expression reader accepts) rather than an integer row index —
    hence this does not reuse :func:`celldega.pre.save_cbg_gene_parquets` (which
    remaps to integer indices via boundary metadata this dataset lacks).
    """
    import pandas as pd

    from celldega.pre import make_meta_gene

    cbg = _cbg_from_adata(adata)

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


# Manifest filenames written for a point-cloud DegaFiles. The ``CellCloud``
# widget fetches ``cell_cloud.json``; ``landscape_parameters.json`` is still
# written so pre-rename loaders (and DegaFiles built before ``CellCloud``) keep
# working during the transition.
_POINT_CLOUD_MANIFEST_NAMES = ("landscape_parameters.json", "cell_cloud.json")


def _write_point_cloud_manifests(dega_files_dir: Path, params: dict) -> None:
    """Write ``params`` under every point-cloud manifest filename."""
    for name in _POINT_CLOUD_MANIFEST_NAMES:
        with (dega_files_dir / name).open("w") as f:
            json.dump(params, f, indent=2)


def _register_alignment(params_path: Path, alignment_name: str) -> list[str]:
    """Add ``alignment_name`` to the ``"alignments"`` list in landscape params."""
    with params_path.open() as f:
        params = json.load(f)

    alignments = params.get("alignments")
    if not isinstance(alignments, list):
        alignments = []
    if alignment_name not in alignments:
        alignments.append(alignment_name)
    params["alignments"] = alignments

    _write_point_cloud_manifests(params_path.parent, params)

    return alignments


def _write_point_cloud_landscape_parameters(params_path: Path, alignment_name: str) -> None:
    """Write a minimal point-cloud manifest (create mode)."""
    params = {
        "technology": "point-cloud",
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": None,
        "tile_size": 1,
        "image_info": [],
        "image_format": ".webp",
        "use_int_index": False,
        "alignments": [alignment_name],
    }
    _write_point_cloud_manifests(params_path.parent, params)


def write_alignment_point_cloud(
    adata,
    dega_files_dir,
    alignment_name,
    *,
    z_key: str = "Z",
    cluster_key: str | None = None,
    write_genes: bool | None = None,
    write_base_metadata: bool | None = None,
    overwrite: bool = False,
) -> Path:
    """Write aligned 3D cell centroids to a point-cloud DegaFiles as a named alignment.

    Parameters
    ----------
    adata : AnnData
        Aligned AnnData. ``obsm["spatial"]`` provides x/y (its first two
        columns); z is taken from ``obs[z_key]`` if present, else from a third
        ``spatial`` column, else 0. Cell names come from ``obs_names``.
    dega_files_dir : str or Path
        Target point-cloud DegaFiles directory. If it already contains
        ``landscape_parameters.json`` the writer *appends* (positions +
        registration only); otherwise it *creates* a fresh point-cloud
        directory.
    alignment_name : str
        Name of this alignment variant. The positions are written to
        ``cell_metadata_<alignment_name>.parquet`` and the name is registered in
        ``landscape_parameters.json`` under ``"alignments"``. View it with
        ``Landscape(..., alignment="<alignment_name>")``.
    z_key : str, default "Z"
        ``obs`` column holding the per-slice z (depth) coordinate.
    cluster_key : str, optional
        Only used in *create* mode: ``obs`` column to export as clusters (with
        colors from ``uns[f"{cluster_key}_colors"]`` when available). Ignored in
        append mode, where existing clusters are reused.
    write_genes : bool, optional
        Only used in *create* mode. Whether to export gene expression to
        ``cbg/`` + ``meta_gene.parquet`` (keyed by cell name). Defaults to
        ``True`` when ``adata`` carries an expression matrix
        (``layers['counts']`` or ``X``) and ``False`` otherwise. Ignored in
        append mode, where existing gene data is reused.
    write_base_metadata : bool, optional
        Whether to also (over)write the base ``cell_metadata.parquet`` with these
        positions. Defaults to ``True`` in create mode and ``False`` in append
        mode (so an append never clobbers the existing default positions).
    overwrite : bool, default False
        Allow overwriting an existing ``cell_metadata_<alignment_name>.parquet``.

    Returns
    -------
    pathlib.Path
        Path to the written ``cell_metadata_<alignment_name>.parquet``.
    """
    _validate_alignment_name(alignment_name)
    dega_files_dir = Path(dega_files_dir)

    params_path = dega_files_dir / "landscape_parameters.json"
    append_mode = params_path.exists()

    if not append_mode:
        dega_files_dir.mkdir(parents=True, exist_ok=True)

    coords = _build_coordinates(adata, z_key)
    names = adata.obs_names

    variant_path = dega_files_dir / f"cell_metadata_{alignment_name}.parquet"
    if variant_path.exists() and not overwrite:
        raise FileExistsError(
            f"{variant_path.name} already exists. Pass overwrite=True to replace it."
        )
    _write_cell_metadata(variant_path, names, coords)

    if write_base_metadata is None:
        write_base_metadata = not append_mode
    if write_base_metadata:
        _write_cell_metadata(dega_files_dir / "cell_metadata.parquet", names, coords)

    if append_mode:
        _register_alignment(params_path, alignment_name)
    else:
        _write_point_cloud_landscape_parameters(params_path, alignment_name)
        if cluster_key is not None:
            from celldega.pre import add_clustering_from_adata

            add_clustering_from_adata(adata, dega_files_dir, cluster_key=cluster_key)
        # Gene expression is written when available (or when explicitly
        # requested) so a freshly-created point cloud can be colored by gene,
        # not just by cluster.
        if write_genes is None:
            write_genes = _has_expression(adata)
        if write_genes:
            if not _has_expression(adata):
                raise ValueError(
                    "write_genes=True but adata has no expression matrix (X / layers['counts'])."
                )
            _write_cbg_and_meta_gene(dega_files_dir, adata)

    return variant_path
