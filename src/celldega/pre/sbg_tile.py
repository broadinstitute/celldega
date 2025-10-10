"""Utilities for generating pseudo-transcripts from sparse spot-by-gene matrices."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


__all__ = ["write_pseudotranscripts_from_sbg"]


def _validate_tile_bounds(tile_bounds: Mapping[str, float]) -> tuple[float, float, float, float]:
    try:
        x_min = float(tile_bounds["x_min"])
        x_max = float(tile_bounds["x_max"])
        y_min = float(tile_bounds["y_min"])
        y_max = float(tile_bounds["y_max"])
    except KeyError as exc:  # pragma: no cover - defensive programming
        missing = getattr(exc, "args", ("unknown",))[0]
        raise KeyError(f"Missing '{missing}' in tile_bounds") from exc

    if not (x_max > x_min and y_max > y_min):
        raise ValueError("tile_bounds must define a positive width and height")

    return x_min, x_max, y_min, y_max


def _prepare_gene_codes(columns: Iterable[str], mapping: Mapping[str, int]) -> np.ndarray:
    gene_codes = np.empty(len(columns), dtype=np.int32)
    for idx, gene in enumerate(columns):
        try:
            gene_codes[idx] = mapping[gene]
        except KeyError as exc:  # pragma: no cover - easier debugging for missing genes
            raise KeyError(f"Gene '{gene}' missing from gene_str_to_int mapping") from exc
    return gene_codes


def _coerce_mapping(
    gene_str_to_int: Mapping[str, int] | pd.Series | dict[str, int],
) -> Mapping[str, int]:
    if isinstance(gene_str_to_int, Mapping):
        return gene_str_to_int
    return dict(gene_str_to_int)


def _group_rows_by_tile(
    tile_i: np.ndarray,
    tile_j: np.ndarray,
    row_positions: np.ndarray,
    n_tiles_x: int,
    n_tiles_y: int,
) -> tuple[np.ndarray, dict[int, tuple[int, int]]]:
    if tile_i.size == 0:
        return np.empty(0, dtype=np.int64), {}

    # Sort tiles lexicographically for deterministic processing
    order = np.lexsort((tile_j, tile_i))
    tile_i_sorted = tile_i[order]
    tile_j_sorted = tile_j[order]
    row_positions_sorted = row_positions[order]

    tile_keys_sorted = tile_i_sorted * n_tiles_y + tile_j_sorted
    unique_keys, key_start = np.unique(tile_keys_sorted, return_index=True)
    key_end = np.concatenate([key_start[1:], np.array([tile_keys_sorted.size], dtype=np.int64)])

    tile_slices = dict(
        zip(
            unique_keys.tolist(),
            zip(key_start.tolist(), key_end.tolist(), strict=False),
            strict=False,
        )
    )

    return row_positions_sorted, tile_slices


def _write_tile_pseudotranscripts(
    sbg_csr: csr_matrix,
    row_indices: np.ndarray,
    tile_i: int,
    tile_j: int,
    gene_codes: np.ndarray,
    spot_x: np.ndarray,
    spot_y: np.ndarray,
    rng: np.random.Generator,
    jitter: float,
    output_dir: Path,
) -> None:
    if row_indices.size == 0:
        return

    tile_matrix = sbg_csr[row_indices]
    if tile_matrix.nnz == 0:
        return

    tile_coo = tile_matrix.tocoo()
    if tile_coo.nnz == 0:
        return

    counts = np.rint(tile_coo.data).astype(np.int64, copy=False)
    positive_mask = counts > 0
    if not np.any(positive_mask):
        return

    counts = counts[positive_mask]
    local_rows = tile_coo.row[positive_mask]
    global_rows = row_indices[local_rows]
    gene_indices = tile_coo.col[positive_mask]

    total_transcripts = int(counts.sum())
    if total_transcripts == 0:
        return

    repeats = np.repeat(np.arange(counts.size, dtype=np.int64), counts)
    names = gene_codes[gene_indices][repeats]
    x_coords = spot_x[global_rows][repeats]
    y_coords = spot_y[global_rows][repeats]

    if jitter != 0:
        jitter_radius = jitter / 2.0
        jitter_x = rng.uniform(-jitter_radius, jitter_radius, size=total_transcripts)
        jitter_y = rng.uniform(-jitter_radius, jitter_radius, size=total_transcripts)
        x_coords = x_coords + jitter_x
        y_coords = y_coords + jitter_y

    x_coords = np.round(x_coords, 2)
    y_coords = np.round(y_coords, 2)

    geometry = np.column_stack((x_coords, y_coords)).tolist()

    df_out = pd.DataFrame(
        {
            "name": names.astype(np.int32, copy=False),
            "geometry": geometry,
        }
    )

    filename = output_dir / f"transcripts_tile_{tile_i}_{tile_j}.parquet"
    df_out.to_parquet(filename, index=False)


def write_pseudotranscripts_from_sbg(
    spots: pd.DataFrame,
    sbg: pd.DataFrame,
    gene_str_to_int: Mapping[str, int] | pd.Series | dict[str, int],
    tile_bounds: Mapping[str, float],
    tile_size: float,
    path_output: str | Path,
    jitter: float,
    coarse_tile_factor: int = 10,
    rng: np.random.Generator | None = None,
) -> None:
    """Generate pseudo-transcripts from a sparse spot-by-gene matrix.

    Parameters
    ----------
    spots
        DataFrame containing ``x`` and ``y`` columns indexed by spot identifiers.
    sbg
        Sparse pandas DataFrame of spot-by-gene counts. The index should match the
        ``spots`` DataFrame.
    gene_str_to_int
        Mapping from gene name to the integer identifier expected by the frontend.
    tile_bounds
        Dictionary containing ``x_min``, ``x_max``, ``y_min`` and ``y_max``.
    tile_size
        Size of the fine tiles in the same coordinate system as ``spots``.
    path_output
        Directory where tile Parquet files will be written.
    jitter
        Total jitter range that will be split equally in the positive and negative
        direction when perturbing coordinates.
    coarse_tile_factor
        Number of fine tiles grouped into a coarse tile along each axis. This is used
        to chunk processing similar to transcript preprocessing.
    rng
        Optional numpy random Generator. If ``None`` a new generator is created.
    """

    if tile_size <= 0:
        raise ValueError("tile_size must be positive")

    coarse_tile_factor = max(1, int(coarse_tile_factor))

    x_min, x_max, y_min, y_max = _validate_tile_bounds(tile_bounds)

    n_tiles_x = math.ceil((x_max - x_min) / tile_size)
    n_tiles_y = math.ceil((y_max - y_min) / tile_size)

    if n_tiles_x <= 0 or n_tiles_y <= 0:
        return

    output_dir = Path(path_output)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = rng if rng is not None else np.random.default_rng()

    gene_map = _coerce_mapping(gene_str_to_int)
    gene_codes = _prepare_gene_codes(sbg.columns.to_numpy(), gene_map)

    sbg_csr = sbg.sparse.to_coo().tocsr()
    if sbg_csr.nnz == 0:
        return

    aligned_spots = spots.reindex(sbg.index)
    spot_x = aligned_spots["x"].to_numpy(dtype=float, copy=False)
    spot_y = aligned_spots["y"].to_numpy(dtype=float, copy=False)

    valid_mask = np.isfinite(spot_x) & np.isfinite(spot_y)
    if not np.any(valid_mask):
        return

    spot_x = spot_x.astype(float, copy=False)
    spot_y = spot_y.astype(float, copy=False)

    tile_i = np.floor((spot_x - x_min) / tile_size).astype(np.int64, copy=False)
    tile_j = np.floor((spot_y - y_min) / tile_size).astype(np.int64, copy=False)

    valid_mask &= (tile_i >= 0) & (tile_i < n_tiles_x) & (tile_j >= 0) & (tile_j < n_tiles_y)

    if not np.any(valid_mask):
        return

    tile_i_valid = tile_i[valid_mask]
    tile_j_valid = tile_j[valid_mask]
    row_positions = np.nonzero(valid_mask)[0]

    row_positions_sorted, tile_slices = _group_rows_by_tile(
        tile_i_valid, tile_j_valid, row_positions, n_tiles_x, n_tiles_y
    )
    if not tile_slices:
        return

    coarse_step = coarse_tile_factor
    n_coarse_tiles_x = math.ceil(n_tiles_x / coarse_step)
    n_coarse_tiles_y = math.ceil(n_tiles_y / coarse_step)

    for coarse_i in range(n_coarse_tiles_x):
        coarse_i_start = coarse_i * coarse_step
        coarse_i_end = min(coarse_i_start + coarse_step, n_tiles_x)

        if coarse_i % 10 == 0:
            print("coarse row", coarse_i)

        for coarse_j in range(n_coarse_tiles_y):
            coarse_j_start = coarse_j * coarse_step
            coarse_j_end = min(coarse_j_start + coarse_step, n_tiles_y)

            for tile_i_idx in range(coarse_i_start, coarse_i_end):
                for tile_j_idx in range(coarse_j_start, coarse_j_end):
                    tile_key = tile_i_idx * n_tiles_y + tile_j_idx
                    slice_bounds = tile_slices.get(tile_key)
                    if slice_bounds is None:
                        continue

                    start, end = slice_bounds
                    row_subset = row_positions_sorted[start:end]

                    _write_tile_pseudotranscripts(
                        sbg_csr,
                        row_subset,
                        tile_i_idx,
                        tile_j_idx,
                        gene_codes,
                        spot_x,
                        spot_y,
                        rng,
                        jitter,
                        output_dir,
                    )
