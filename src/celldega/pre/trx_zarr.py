"""Read transcripts from the 10x ``transcripts.zarr.zip`` spatial grid format.

Modern 10x instruments (Xenium Onboard Analysis, and the Atera whole-transcriptome
preview) ship transcripts as ``transcripts.zarr.zip`` in addition to the flat
``transcripts.parquet``. The Zarr bundle stores transcripts in a ``/grids`` pyramid:
level ``0`` holds every transcript, split into spatial grid positions named
``"<col>,<row>"`` (e.g. ``grids/0/0,0``), with coarser, subsampled levels above it.

Because the grid already partitions transcripts spatially, we can stream one grid
position at a time and feed it straight into the tiling pipeline. This avoids reading
the entire flat parquet into memory and avoids a global ``partition_by`` over every
transcript, which is the main cost of :func:`celldega.pre.trx_tile.make_trx_tiles`
on large panels.

Reference: https://www.10xgenomics.com/support/software/xenium-onboard-analysis/latest/advanced/xoa-output-zarr
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
import shutil

import numpy as np
import polars as pl
from scipy.sparse import csr_matrix
import zarr

from .boundary_tile import _get_name_mapping
from .trx_tile import (
    _apply_gene_mapping,
    _spill_one_transform_shard_to_tiles,
    _transform_batch,
    _write_tiles_as_row_groups_streaming,
    _write_traditional_transcript_tiles_from_spill,
)


# ``gene_identity`` is uint16; this sentinel marks a "no-call" (absence of a codeword).
NO_CALL_GENE_INDEX = 65535


@contextmanager
def open_zarr(path: str | Path):
    """Open a ``.zarr`` directory or ``.zarr.zip`` archive as a Zarr group.

    The underlying store is closed on exit, which matters for ``ZipStore`` archives
    that hold an open file handle.

    Parameters
    ----------
    path : str or Path
        Path to a ``.zarr`` directory or ``.zarr.zip`` file.

    Yields
    ------
    zarr.hierarchy.Group
        The root Zarr group.
    """
    path = str(path)
    store = zarr.ZipStore(path, mode="r") if path.endswith(".zip") else zarr.DirectoryStore(path)
    try:
        yield zarr.group(store=store)
    finally:
        close = getattr(store, "close", None)
        if close is not None:
            close()


def is_zarr_transcript_path(path: str | Path) -> bool:
    """Return ``True`` if ``path`` points at a Zarr transcript bundle."""
    return str(path).endswith((".zarr", ".zarr.zip"))


def _level_position_keys(grids_group, level: int, level_group) -> list[str]:
    """Return the ``"col,row"`` grid-position keys for one pyramid level.

    Prefer the ``grid_keys`` attribute (authoritative ordering) and fall back to
    listing the level group's subgroups for bundles that omit the attribute.
    """
    grid_keys = grids_group.attrs.get("grid_keys")
    if grid_keys is not None and level < len(grid_keys):
        keys = [str(k) for k in grid_keys[level]]
        if keys:
            return keys
    return sorted(level_group.group_keys())


def read_zarr_transcript_metadata(path: str | Path, level: int = 0) -> dict:
    """Read summary metadata from a ``transcripts.zarr.zip`` bundle.

    Parameters
    ----------
    path : str or Path
        Path to the Zarr transcript bundle.
    level : int, optional
        Pyramid level to inspect for grid positions (default ``0``, full resolution).

    Returns
    -------
    dict
        Keys: ``gene_names`` (list[str]), ``number_rnas`` (int or None),
        ``number_levels`` (int), ``grid_size`` (list), ``position_keys`` (list[str])
        for the requested level, and ``spatial_units`` (str or None).
    """
    with open_zarr(path) as root:
        root_attrs = dict(root.attrs)
        grids = root["grids"]
        grid_attrs = dict(grids.attrs)
        level_group = grids[str(level)]
        position_keys = _level_position_keys(grids, level, level_group)

        return {
            "gene_names": list(root_attrs.get("gene_names", [])),
            "number_rnas": root_attrs.get("number_rnas"),
            "number_levels": grid_attrs.get("number_levels", 1),
            "grid_size": grid_attrs.get("grid_size"),
            "position_keys": position_keys,
            "spatial_units": root_attrs.get("spatial_units"),
        }


def _first_column(array: np.ndarray, n_rows: int) -> np.ndarray:
    """Return the first column of a possibly 2D per-transcript array."""
    values = np.asarray(array)
    if values.ndim == 1:
        return values
    return values.reshape(n_rows, -1)[:, 0]


def iter_zarr_transcript_batches(
    path: str | Path,
    *,
    level: int = 0,
    drop_no_call: bool = True,
    min_quality: float | None = None,
    gene_names: Sequence[str] | None = None,
) -> Iterator[pl.DataFrame]:
    """Yield one ``name``/``x``/``y`` batch per spatial grid position.

    Each yielded frame corresponds to a single ``grids/<level>/<col>,<row>`` position
    and therefore covers a contiguous region of space, which keeps downstream tile
    assignment local and memory bounded.

    Parameters
    ----------
    path : str or Path
        Path to the Zarr transcript bundle.
    level : int, optional
        Pyramid level to read (default ``0``, every transcript).
    drop_no_call : bool, optional
        Drop transcripts whose ``gene_identity`` is the no-call sentinel
        (:data:`NO_CALL_GENE_INDEX`). Defaults to ``True``.
    min_quality : float, optional
        If given, drop transcripts with ``quality_score`` below this threshold.
    gene_names : sequence of str, optional
        Override the gene-name lookup table. Defaults to the bundle's ``gene_names``
        root attribute.

    Yields
    ------
    polars.DataFrame
        Columns ``name`` (gene name, str), ``x`` and ``y`` (micron space, float).
        Empty positions are skipped.
    """
    with open_zarr(path) as root:
        lookup = np.asarray(
            list(root.attrs.get("gene_names", [])) if gene_names is None else list(gene_names)
        )
        grids = root["grids"]
        level_group = grids[str(level)]

        for key in _level_position_keys(grids, level, level_group):
            position = level_group[key]
            location = np.asarray(position["location"][:])
            n_rows = location.shape[0]
            if n_rows == 0:
                continue

            gene_idx = _first_column(position["gene_identity"][:], n_rows).astype(np.int64)

            mask = np.ones(n_rows, dtype=bool)
            if drop_no_call:
                mask &= gene_idx != NO_CALL_GENE_INDEX
            if min_quality is not None and "quality_score" in position:
                quality = _first_column(position["quality_score"][:], n_rows)
                mask &= quality >= min_quality
            # Guard against out-of-range gene indices (e.g. control codewords).
            mask &= gene_idx < lookup.shape[0]

            if not mask.any():
                continue

            yield pl.DataFrame(
                {
                    "name": lookup[gene_idx[mask]],
                    "x": location[mask, 0].astype(np.float64),
                    "y": location[mask, 1].astype(np.float64),
                }
            )


def load_zarr_transcripts(
    path: str | Path,
    *,
    level: int = 0,
    drop_no_call: bool = True,
    min_quality: float | None = None,
    gene_names: Sequence[str] | None = None,
) -> pl.DataFrame:
    """Load all transcripts from a Zarr bundle into a single ``name``/``x``/``y`` frame.

    This is a convenience wrapper over :func:`iter_zarr_transcript_batches` that mirrors
    the output schema of
    :func:`celldega.pre.trx_tile._load_transcript_data_by_technology` for Xenium, so it
    can be used as a drop-in transcript source. For large datasets prefer the streaming
    tiling entry points, which never materialize the full frame.

    Parameters
    ----------
    path : str or Path
        Path to the Zarr transcript bundle.
    level, drop_no_call, min_quality, gene_names
        See :func:`iter_zarr_transcript_batches`.

    Returns
    -------
    polars.DataFrame
        Columns ``name``, ``x``, ``y``. Empty if the bundle has no transcripts.
    """
    batches = list(
        iter_zarr_transcript_batches(
            path,
            level=level,
            drop_no_call=drop_no_call,
            min_quality=min_quality,
            gene_names=gene_names,
        )
    )
    if not batches:
        return pl.DataFrame(
            {"name": [], "x": [], "y": []},
            schema={"name": pl.Utf8, "x": pl.Float64, "y": pl.Float64},
        )
    return pl.concat(batches)


def _resolve_gene_mapping(gene_str_to_int_mapping, path_dega_files):
    """Return an explicit gene name -> int mapping, loading it if not supplied."""
    if gene_str_to_int_mapping is not None:
        return gene_str_to_int_mapping
    if path_dega_files is not None:
        return _get_name_mapping(str(path_dega_files), layer="transcript")
    return {}


def make_trx_tiles_from_zarr(
    path_trx_zarr: str | Path,
    path_transformation_matrix: str | Path,
    path_output_dir: str | Path,
    *,
    tile_size: float = 250,
    image_scale: float = 1,
    use_row_groups: bool = False,
    max_row_groups_per_file: int = 400,
    path_dega_files: str | Path | None = None,
    gene_str_to_int_mapping=None,
    level: int = 0,
    drop_no_call: bool = True,
    min_quality: float | None = None,
):
    """Tile transcripts directly from a ``transcripts.zarr.zip`` spatial grid.

    Streams one grid position at a time: apply the gene-name mapping, affine-transform
    the coordinates, and spill per-tile parquet parts to disk. Because grid positions
    are spatially local and processed one at a time, peak memory stays bounded and the
    global ``partition_by`` used by the parquet path is avoided.

    The output layout matches the parquet-based entry points:

    * ``use_row_groups=False`` -> one ``transcripts_tile_{i}_{j}.parquet`` per non-empty
      tile (same as :func:`celldega.pre.trx_tile.make_trx_tiles`).
    * ``use_row_groups=True`` -> chunked row-group parquet files (same as
      :func:`celldega.pre.trx_tile.make_trx_tiles_row_groups`).

    Parameters
    ----------
    path_trx_zarr : str or Path
        Path to the ``transcripts.zarr.zip`` bundle.
    path_transformation_matrix : str or Path
        Path to the whitespace-delimited micron -> image affine matrix.
    path_output_dir : str or Path
        Directory that will hold the tile parquet files.
    tile_size : float, optional
        Fine tile size in image space (default 250).
    image_scale : float, optional
        Scale factor applied after the affine transform (default 1).
    use_row_groups : bool, optional
        Write chunked row-group parquet files instead of individual tile files.
    max_row_groups_per_file : int, optional
        Row groups per chunk file when ``use_row_groups`` is ``True`` (default 400).
    path_dega_files : str or Path, optional
        Landscape files directory used to load the gene mapping when
        ``gene_str_to_int_mapping`` is not supplied.
    gene_str_to_int_mapping : mapping, optional
        Explicit gene name -> integer mapping. Overrides ``path_dega_files``.
    level, drop_no_call, min_quality
        See :func:`iter_zarr_transcript_batches`.

    Returns
    -------
    tuple
        ``(tile_bounds, tile_grid_info, chunk_info)``. ``chunk_info`` is ``None`` when
        ``use_row_groups`` is ``False``.
    """
    output_path = Path(path_output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    transformation_matrix = np.loadtxt(str(path_transformation_matrix))
    sparse_matrix = csr_matrix(transformation_matrix)
    gene_mapping = _resolve_gene_mapping(gene_str_to_int_mapping, path_dega_files)

    tmp_root = output_path / "_tmp_trx_zarr_build"
    shards_dir = tmp_root / "shards"
    spill_dir = tmp_root / "spill"
    shards_dir.mkdir(parents=True, exist_ok=True)
    spill_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Pass 1: transform each grid-position batch to a shard and track the extent.
        max_x = 0.0
        max_y = 0.0
        shard_idx = 0
        for batch in iter_zarr_transcript_batches(
            path_trx_zarr,
            level=level,
            drop_no_call=drop_no_call,
            min_quality=min_quality,
        ):
            batch = _apply_gene_mapping(batch, gene_mapping)
            transformed = _transform_batch(batch, sparse_matrix, image_scale)

            extent = transformed.select(
                [
                    pl.col("transformed_x").max().alias("mx"),
                    pl.col("transformed_y").max().alias("my"),
                ]
            ).row(0)
            max_x = max(max_x, float(extent[0]))
            max_y = max(max_y, float(extent[1]))

            transformed.write_parquet(shards_dir / f"shard_{shard_idx:06d}.parquet")
            shard_idx += 1

        x_min, y_min = 0.0, 0.0
        x_max, y_max = max_x, max_y
        n_tiles_x = int(np.ceil((x_max - x_min) / tile_size)) if x_max > x_min else 0
        n_tiles_y = int(np.ceil((y_max - y_min) / tile_size)) if y_max > y_min else 0

        tile_grid_info = {
            "tile_size": tile_size,
            "num_tiles_x": n_tiles_x,
            "num_tiles_y": n_tiles_y,
            "x_min": float(x_min),
            "x_max": float(x_max),
            "y_min": float(y_min),
            "y_max": float(y_max),
        }
        tile_bounds = {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max}

        chunk_info = None
        if shard_idx > 0 and n_tiles_x > 0 and n_tiles_y > 0:
            # Pass 2: spill each shard into per-tile parts.
            for i, shard_path in enumerate(sorted(shards_dir.glob("shard_*.parquet"))):
                _spill_one_transform_shard_to_tiles(
                    shard_path, i, x_min, y_min, n_tiles_x, n_tiles_y, tile_size, spill_dir
                )
            shutil.rmtree(shards_dir, ignore_errors=True)

            if use_row_groups:
                chunk_info = _write_tiles_as_row_groups_streaming(
                    str(output_path), tile_grid_info, spill_dir, max_row_groups_per_file
                )
            else:
                _write_traditional_transcript_tiles_from_spill(
                    spill_dir, n_tiles_x, n_tiles_y, str(output_path)
                )

        return tile_bounds, tile_grid_info, chunk_info
    finally:
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)
