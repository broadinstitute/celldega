"""Write cell-level AnnData to point-cloud DegaFiles for the ``CellCloud`` widget.

A point-cloud DegaFiles directory holds cell positions in
``cell_metadata.parquet`` (columns ``name`` + ``geometry``, where ``geometry``
is a fixed-size ``[x, y, z]`` list), optional clusters in ``cell_clusters/``,
optional gene expression in ``cbg/`` + ``meta_gene.parquet``, and a manifest written
as both ``cell_cloud.json`` and ``landscape_parameters.json``. The default
format uses string cell names. Opt into ``use_int_index=True`` to store original
names once in ``cell_ids.parquet`` and use zero-based numeric indices in the
repeated geometry, cluster, and expression tables. ``coordinate_resolution=1``
rounds micron coordinates to int32 for substantially smaller compressed files.

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
  ``meta_gene.parquet`` are reused. Integer-indexed variants are reordered to
  the original cell order and reject missing, additional, or duplicate IDs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from scipy.sparse import csc_matrix, issparse


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

    return np.column_stack([xy, z])


def _write_cell_metadata(
    path: Path,
    names: Any,
    coords: np.ndarray,
    *,
    use_int_index: bool = False,
    compression: str = "snappy",
    compression_level: int | None = None,
) -> None:
    """Write a ``name`` + ``geometry`` (fixed-size ``[x, y, z]``) parquet file."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    flat = np.ascontiguousarray(coords).reshape(-1)
    geometry = pa.FixedSizeListArray.from_arrays(pa.array(flat), list_size=3)
    ids = pa.array(np.arange(len(names), dtype=np.uint32)) if use_int_index else pa.array(names)
    table = pa.table({"name": ids, "geometry": geometry})
    pq.write_table(
        table,
        path,
        **_parquet_options(
            compression, compression_level, index_column="name" if use_int_index else None
        ),
    )


def _rounded_coordinates(coords: Any, resolution: float | None) -> np.ndarray:
    """Quantize physical coordinates without changing their units."""
    coords = np.asarray(coords)
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError("coordinates must have shape (n_cells, 3)")
    if not np.isfinite(coords).all():
        raise ValueError("coordinates must be finite")
    if resolution is None:
        return coords.astype(np.float32)
    if not np.isfinite(resolution) or resolution <= 0:
        raise ValueError("coordinate_resolution must be finite and positive")
    rounded = np.rint(coords.astype(np.float64) / resolution) * resolution
    if not np.isfinite(rounded).all():
        raise ValueError("rounded coordinates must be finite")
    if float(resolution).is_integer():
        bounds = np.iinfo(np.int32)
        if rounded.min(initial=0) < bounds.min or rounded.max(initial=0) > bounds.max:
            raise ValueError("rounded coordinates exceed the int32 range")
        return rounded.astype(np.int32)
    return rounded.astype(np.float32)


def _cell_names(adata: Any) -> pd.Index:
    names = pd.Index(adata.obs_names.astype(str))
    if not names.is_unique:
        raise ValueError("obs_names must be unique to preserve cell identity")
    return names


def _write_cell_ids(
    path: Path, names: pd.Index, compression: str, compression_level: int | None
) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(
        pa.table({"name": pa.array(names)}),
        path,
        use_dictionary=False,
        **_parquet_options(compression, compression_level),
    )


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


def _gene_statistics(x: Any, genes: Any) -> pd.DataFrame:
    """Compute metadata one sparse column at a time, including implicit zeros."""
    from celldega.pre import _create_cluster_colors

    n = x.shape[0]
    x = x.tocsc(copy=False) if issparse(x) else np.asarray(x)
    means, deviations, maxima, fractions = [], [], [], []
    for g in range(x.shape[1]):
        values = x.data[x.indptr[g] : x.indptr[g + 1]] if issparse(x) else x[:, g]
        values = np.asarray(values, dtype=np.float64)
        mean = float(values.sum() / n) if n else 0.0
        variance = max(float(np.dot(values, values) / n) - mean**2, 0.0) if n else 0.0
        means.append(mean)
        deviations.append(np.sqrt(variance))
        maximum = float(values.max()) if len(values) else 0.0
        maxima.append(max(maximum, 0.0) if len(values) < n else maximum)
        fractions.append(float(np.count_nonzero(values) / n) if n else 0.0)
    metadata = pd.DataFrame(
        {
            "mean": means,
            "std": deviations,
            "max": maxima,
            "non-zero": fractions,
            "color": _create_cluster_colors(list(genes)),
        },
        index=genes,
    )
    metadata.index.name = None
    return metadata


def _parquet_options(
    compression: str, compression_level: int | None, *, index_column: str | None = None
) -> dict:
    options = {"compression": compression}
    if compression_level is not None:
        options["compression_level"] = compression_level
    if index_column is not None:
        # Canonical IDs and sparse gene-row indices are monotonic integers.
        options.update(use_dictionary=False, column_encoding={index_column: "DELTA_BINARY_PACKED"})
    return options


def _write_cbg_and_meta_gene(
    dega_files_dir: Path,
    adata: Any,
    *,
    use_int_index: bool = False,
    compression: str = "snappy",
    compression_level: int | None = None,
) -> None:
    """Write one sparse column at a time, with names or canonical numeric IDs."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    x = _expression_matrix(adata)
    if hasattr(x, "to_memory"):
        x = x.to_memory()
    x = x.tocsc(copy=False) if issparse(x) else np.asarray(x)
    if issparse(x) and not x.has_canonical_format:
        x = x.copy()
        x.sum_duplicates()
        x.sort_indices()
    cbg_dir = dega_files_dir / "cbg"
    cbg_dir.mkdir(exist_ok=True)
    names = np.asarray(adata.obs_names)
    for g, gene in enumerate(adata.var_names):
        if issparse(x):
            start, stop = x.indptr[g : g + 2]
            rows, values = x.indices[start:stop], x.data[start:stop]
            nonzero = values != 0
            rows, values = rows[nonzero], values[nonzero]
        else:
            rows = np.flatnonzero(x[:, g])
            values = x[rows, g]
        if len(rows):
            ids = rows.astype(np.uint32) if use_int_index else names[rows]
            if use_int_index:
                table = pa.table({str(gene): pa.array(values), "__index_level_0__": pa.array(ids)})
            else:
                frame = pd.DataFrame({str(gene): values}, index=ids)
                frame.index.name = None
                table = pa.Table.from_pandas(frame, preserve_index=True)
            pq.write_table(
                table,
                cbg_dir / f"{gene}.parquet",
                **_parquet_options(
                    compression,
                    compression_level,
                    index_column="__index_level_0__" if use_int_index else None,
                ),
            )
    _gene_statistics(x, adata.var_names).sort_index().to_parquet(
        dega_files_dir / "meta_gene.parquet", **_parquet_options(compression, compression_level)
    )


def _write_indexed_clusters(
    path: Path, adata: Any, cluster_key: str, compression: str, compression_level: int | None
) -> None:
    """Keep repeated clustering keys numeric; retain original IDs in one sidecar."""
    from celldega.pre import _create_cluster_colors

    values = adata.obs[cluster_key].astype("string")
    df = pd.DataFrame(
        {"name": np.arange(adata.n_obs, dtype=np.uint32), "cluster": pd.Categorical(values)}
    )
    path.mkdir(exist_ok=True)
    df.to_parquet(
        path / "cluster.parquet",
        index=False,
        **_parquet_options(compression, compression_level, index_column="name"),
    )
    counts = values.value_counts().sort_index()
    palette = adata.uns.get(f"{cluster_key}_colors")
    if palette is not None and isinstance(adata.obs[cluster_key].dtype, pd.CategoricalDtype):
        color_map = dict(
            zip(adata.obs[cluster_key].cat.categories.astype(str), palette, strict=False)
        )
    else:
        color_map = dict(
            zip(
                counts.index,
                palette if palette is not None else _create_cluster_colors(list(counts.index)),
                strict=False,
            )
        )
    meta = pd.DataFrame(
        {
            "color": [color_map.get(str(c), "#808080") for c in counts.index],
            "count": counts.to_numpy(),
        },
        index=counts.index,
    )
    meta.index.name = None
    meta.to_parquet(
        path / "meta_cluster.parquet", **_parquet_options(compression, compression_level)
    )


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


def _new_manifest(
    name: str | None, use_int_index: bool = False, coordinate_resolution: float | None = None
) -> dict:
    """Minimal point-cloud manifest (create mode)."""
    params = {
        "technology": "point-cloud",
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": None,
        "tile_size": 1,
        "image_info": [],
        "image_format": ".webp",
        "use_int_index": use_int_index,
        "alignments": [name] if name is not None else [],
    }
    if use_int_index:
        params["cell_ids"] = "cell_ids.parquet"
    if coordinate_resolution is not None:
        params["coordinate_resolution"] = float(coordinate_resolution)
    return params


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
    use_int_index: bool | None = None,
    coordinate_resolution: float | None = None,
    compression: str = "snappy",
    compression_level: int | None = None,
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

    use_int_index : bool, optional
        Store original observation IDs once in ``cell_ids.parquet``; use uint32
        row positions in geometry, clustering and per-gene files. Defaults to
        False for a new dataset, or inherits the existing dataset on append.
        Appending requires exactly the same cells and preserves their original
        order even when the new AnnData is reordered.
    coordinate_resolution : float, optional
        Round coordinates to this step in their physical units. Use 1.0 for
        nearest-micron positions (at most 0.5 microns of error on each axis).
        Integral steps use int32 coordinates; the default keeps float32. An
        appended alignment inherits the existing resolution.
    compression : str
        Parquet compression codec; defaults to ``"snappy"``. ``"zstd"`` with
        ``compression_level=6`` provides compact storage. Integer IDs also use
        delta encoding.
    compression_level : int, optional
        Compression level, when supported by the chosen codec.

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

    # Canonical integer IDs always refer to the original cell order. A named
    # alignment may arrive reordered, but must contain exactly the same cells.
    names = _cell_names(adata)
    if adata.n_obs > np.iinfo(np.uint32).max:
        raise ValueError("point-cloud integer indices require at most 2**32 - 1 cells")
    order = None
    if append_mode:
        manifest = params_path if params_path.exists() else dega_files_dir / "cell_cloud.json"
        params = json.loads(manifest.read_text())
        stored_index = bool(params.get("use_int_index", False))
        if use_int_index is not None and use_int_index != stored_index:
            raise ValueError("use_int_index must match the existing dataset")
        use_int_index = stored_index
        stored_resolution = params.get("coordinate_resolution")
        if coordinate_resolution is not None and coordinate_resolution != stored_resolution:
            raise ValueError("coordinate_resolution must match the existing dataset")
        coordinate_resolution = stored_resolution
        if use_int_index:
            original = pd.Index(pd.read_parquet(dega_files_dir / "cell_ids.parquet")["name"])
            if len(original) != len(names) or not original.is_unique:
                raise ValueError("alignment must contain exactly the existing cells")
            order = names.get_indexer(original)
            if np.any(order < 0):
                raise ValueError("alignment must contain exactly the existing cells")
    use_int_index = bool(use_int_index)
    # Validate everything before writing, so a failed call leaves nothing behind.
    coords = _rounded_coordinates(_build_coordinates(adata, z_key), coordinate_resolution)
    if order is not None:
        coords = coords[order]

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
    base_path = dega_files_dir / "cell_metadata.parquet"
    written = base_path
    if name is not None:
        written = dega_files_dir / f"cell_metadata_{name}.parquet"
        if written.exists() and not overwrite:
            raise FileExistsError(
                f"{written.name} already exists. Pass overwrite=True to replace it."
            )
        _write_cell_metadata(
            written,
            names,
            coords,
            use_int_index=use_int_index,
            compression=compression,
            compression_level=compression_level,
        )

    if write_base_metadata is None:
        write_base_metadata = not append_mode
    if write_base_metadata:
        _write_cell_metadata(
            base_path,
            names,
            coords,
            use_int_index=use_int_index,
            compression=compression,
            compression_level=compression_level,
        )

    if append_mode:
        if not params_path.exists():
            with (dega_files_dir / "cell_cloud.json").open() as f:
                _write_manifests(dega_files_dir, json.load(f))
        _register_variant(params_path, name)
        return written

    if use_int_index:
        _write_cell_ids(dega_files_dir / "cell_ids.parquet", names, compression, compression_level)
    if cluster_key is not None:
        if use_int_index:
            _write_indexed_clusters(
                dega_files_dir / "cell_clusters", adata, cluster_key, compression, compression_level
            )
        else:
            from celldega.pre import add_clustering_from_adata

            add_clustering_from_adata(adata, dega_files_dir, cluster_key=cluster_key)
    if write_genes:
        _write_cbg_and_meta_gene(
            dega_files_dir,
            adata,
            use_int_index=use_int_index,
            compression=compression,
            compression_level=compression_level,
        )
    # The manifest goes last: a directory without one is never mistaken for a
    # complete dataset (a retry runs in create mode again).
    _write_manifests(dega_files_dir, _new_manifest(name, use_int_index, coordinate_resolution))

    return written


def write_point_cloud_zarr(
    adata: Any,
    store: str | Path,
    *,
    z_key: str | None = "Z",
    cluster_key: str | None = None,
    alignments: Mapping[str, Any] | None = None,
    coordinate_resolution: float | None = 1.0,
    obs_columns: Sequence[str] | None = None,
    chunk_rows: int = 262_144,
    expression_chunk_size: int = 262_144,
    overwrite: bool = False,
) -> Path:
    """Write a self-contained CellCloud AnnData Zarr store for HTTP hosting.

    ``X`` is CSC, so selecting a gene reads only its sparse values and cell-row
    indices. ``obs_names`` retain the original cell IDs; expression is indexed
    by their zero-based row positions. ``obsm['spatial']`` stores default XYZ
    coordinates and ``obsm['spatial_<name>']`` stores each named alignment.
    Pass ``CellCloud(zarr_url=..., alignment='<name>')`` to choose one.

    Coordinates remain in their physical units. With the default
    ``coordinate_resolution=1.0``, micron coordinates are rounded to the
    nearest micron and saved as int32, with at most half a micron of error on
    each axis. Pass ``None`` to retain float32 positions. Original inputs are
    never modified. A new output path is required unless ``overwrite=True``.

    Parameters
    ----------
    adata : AnnData
        Cells, original observation IDs, gene IDs, and counts in
        ``layers['counts']`` or ``X``. Spatial positions follow the same rules
        as :func:`write_point_cloud_dataset`.
    store : str or Path
        New local directory; upload its complete contents to a static host.
    cluster_key : str, optional
        Cluster observation column. Its palette is retained and missing colors
        are generated. Other requested observation columns remain available.
    alignments : mapping of str to array, optional
        Additional ``(n_cells, 3)`` XYZ arrays in exactly ``adata.obs_names``
        order. These are rounded using the same coordinate resolution.
    obs_columns : sequence of str, optional
        Observation columns to keep; defaults to all columns. ``cluster_key``
        is always retained when provided.
    chunk_rows : int
        Number of cells per coordinate chunk (default 262,144).
    expression_chunk_size : int
        Number of sparse expression entries per chunk (default 262,144).
    overwrite : bool
        Replace an existing local store only when explicitly requested.

    Returns
    -------
    pathlib.Path
        The completed Zarr v2 store. Numeric arrays use Zstandard compression
        with bit shuffle; consolidated metadata reduces HTTP round trips.
    """
    import shutil
    import tempfile

    import anndata as ad
    from anndata.io import write_elem
    from numcodecs import Blosc
    import zarr

    from celldega.pre import _create_cluster_colors

    target = Path(store)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} already exists; choose a new path or pass overwrite=True")
    if chunk_rows <= 0 or expression_chunk_size <= 0:
        raise ValueError("chunk_rows and expression_chunk_size must be positive")
    names = _cell_names(adata)
    if cluster_key is not None and cluster_key not in adata.obs:
        raise ValueError(f"cluster_key {cluster_key!r} not found in adata.obs")
    if not adata.var_names.is_unique:
        raise ValueError("var_names must be unique")
    coordinates = {
        "spatial": _rounded_coordinates(_build_coordinates(adata, z_key), coordinate_resolution)
    }
    for name, values in (alignments or {}).items():
        _validate_variant_name(name)
        coords = _rounded_coordinates(values, coordinate_resolution)
        if len(coords) != adata.n_obs:
            raise ValueError(f"alignment {name!r} must contain one coordinate per cell")
        coordinates[f"spatial_{name}"] = coords
    columns = list(adata.obs.columns if obs_columns is None else obs_columns)
    if cluster_key is not None and cluster_key not in columns:
        columns.append(cluster_key)
    obs = adata.obs.loc[:, columns].copy()
    obs.index = names
    x = _expression_matrix(adata)
    if x is None:
        x = csc_matrix(adata.shape, dtype=np.float32)
    elif hasattr(x, "to_memory"):
        x = x.to_memory()
    x = x.tocsc(copy=False) if issparse(x) else csc_matrix(x)
    # CSC must be canonical: duplicate row entries otherwise change per-gene
    # coloring, even though ordinary matrix reductions would sum them.
    if not x.has_canonical_format:
        x = x.copy()
        x.sum_duplicates()
        x.sort_indices()
    var = adata.var.copy()
    statistics = _gene_statistics(x, adata.var_names)
    for name in ("mean", "max", "color"):
        var[name] = statistics[name]
    uns = {
        "cell_cloud": {
            "spatial_key": "spatial",
            "alignments": list(alignments or {}),
            "coordinate_units": "micrometers",
        }
    }
    if "provenance" in adata.uns:
        uns["provenance"] = adata.uns["provenance"]
    if coordinate_resolution is not None:
        uns["cell_cloud"]["coordinate_resolution"] = float(coordinate_resolution)
    if cluster_key is not None:
        obs[cluster_key] = pd.Categorical(obs[cluster_key])
        palette = adata.uns.get(f"{cluster_key}_colors")
        categories = obs[cluster_key].cat.categories
        if palette is None or len(palette) < len(categories):
            palette = _create_cluster_colors(list(categories.astype(str)))
        uns[f"{cluster_key}_colors"] = np.asarray(palette)
    preview = ad.AnnData(shape=adata.shape, obs=obs, var=var, uns=uns)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    compressor = Blosc(cname="zstd", clevel=5, shuffle=Blosc.BITSHUFFLE)
    try:
        with (
            ad.settings.override(zarr_write_format=2, auto_shard_zarr_v3=False),
            zarr.config.set({"array.write_empty_chunks": True}),
        ):
            preview.write_zarr(staging)
            group = zarr.open_group(staging, mode="a", use_consolidated=False)
            # AnnData's default Zarr v2 compressor is LZ4. Observation IDs are
            # a substantial part of a large cloud's first load, so compress
            # the whole observation dataframe with Zstandard as well.
            write_elem(
                group,
                "obs",
                obs,
                dataset_kwargs={
                    "compressor": Blosc(cname="zstd", clevel=5, shuffle=Blosc.NOSHUFFLE)
                },
            )
            if "X" in group:
                del group["X"]
            write_elem(
                group,
                "X",
                x,
                dataset_kwargs={"chunks": (expression_chunk_size,), "compressor": compressor},
            )
            for key, coords in coordinates.items():
                write_elem(
                    group["obsm"],
                    key,
                    coords,
                    dataset_kwargs={
                        "chunks": (min(chunk_rows, max(adata.n_obs, 1)), 3),
                        "compressor": compressor,
                    },
                )
            zarr.consolidate_metadata(group.store)
        if target.exists():
            if not overwrite:
                raise FileExistsError(f"{target} was created while the export was running")
            shutil.rmtree(target)
        staging.rename(target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target
