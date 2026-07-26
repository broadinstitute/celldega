"""Tests for reading and tiling transcripts from the 10x ``transcripts.zarr.zip`` format.

These cover:

* metadata + batch reading of the ``/grids`` spatial pyramid,
* the no-call / quality filters,
* streaming tiling directly from the Zarr grid (traditional + row-group layouts), and
* parity between the Zarr tiling path and the flat-parquet ``make_trx_tiles`` path.
"""

import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pandas as pd
import pytest


try:
    import polars as pl
    import pyarrow.parquet as pq
    import zarr
except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"Required libraries missing: {e}", allow_module_level=True)


# Dynamically load the pre submodules to avoid importing the heavy celldega.pre package.
ROOT_DIR = Path(__file__).resolve().parents[3]
PRE_ROOT = ROOT_DIR / "src" / "celldega" / "pre"
CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)
PREPKG = types.ModuleType("celldega.pre")
PREPKG.__path__ = [str(PRE_ROOT)]
sys.modules.setdefault("celldega.pre", PREPKG)


def _load(name):
    spec = importlib.util.spec_from_file_location(f"celldega.pre.{name}", PRE_ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "celldega.pre"
    sys.modules[f"celldega.pre.{name}"] = module
    spec.loader.exec_module(module)
    return module


boundary_tile = _load("boundary_tile")
trx_tile = _load("trx_tile")
trx_zarr = _load("trx_zarr")

make_trx_tiles = trx_tile.make_trx_tiles


GENE_NAMES = ["G0", "G1", "G2"]
GENE_MAP = {name: idx for idx, name in enumerate(GENE_NAMES)}
NO_CALL = trx_zarr.NO_CALL_GENE_INDEX


def _write_zarr_transcripts(path, positions, *, gene_names=GENE_NAMES, as_zip=False):
    """Write a synthetic ``transcripts.zarr`` mirroring the 10x /grids schema.

    ``positions`` maps a ``"col,row"`` key to a dict with ``x``, ``y``, ``gene`` (uint16
    gene indices) and optional ``quality`` lists.
    """
    store = zarr.ZipStore(str(path), mode="w") if as_zip else zarr.DirectoryStore(str(path))
    root = zarr.group(store=store, overwrite=True)
    total = sum(len(p["x"]) for p in positions.values())
    root.attrs["gene_names"] = list(gene_names)
    root.attrs["number_rnas"] = total
    root.attrs["spatial_units"] = "micron"

    grids = root.create_group("grids")
    grids.attrs["number_levels"] = 1
    grids.attrs["grid_size"] = [100.0]
    grids.attrs["grid_keys"] = [list(positions.keys())]
    grids.attrs["grid_key_names"] = ["grid_x_loc", "grid_y_loc"]

    level0 = grids.create_group("0")
    for key, data in positions.items():
        group = level0.create_group(key)
        n = len(data["x"])
        location = np.column_stack(
            [np.asarray(data["x"]), np.asarray(data["y"]), np.zeros(n)]
        ).astype("float32")
        group.create_dataset("location", data=location)
        group.create_dataset("gene_identity", data=np.asarray(data["gene"], dtype="uint16"))
        quality = data.get("quality", [40.0] * n)
        group.create_dataset("quality_score", data=np.asarray(quality, dtype="float32"))

    if as_zip:
        store.close()
    return path


@pytest.fixture
def simple_zarr(tmp_path):
    positions = {
        "0,0": {"x": [50.0, 120.0], "y": [50.0, 120.0], "gene": [0, 1]},
        "1,1": {"x": [300.0, 320.0], "y": [60.0, 320.0], "gene": [2, 0]},
    }
    return _write_zarr_transcripts(tmp_path / "transcripts.zarr", positions)


def test_is_zarr_transcript_path():
    assert trx_zarr.is_zarr_transcript_path("foo/transcripts.zarr.zip")
    assert trx_zarr.is_zarr_transcript_path("foo/transcripts.zarr")
    assert not trx_zarr.is_zarr_transcript_path("foo/transcripts.parquet")


def test_read_metadata(simple_zarr):
    meta = trx_zarr.read_zarr_transcript_metadata(simple_zarr)
    assert meta["gene_names"] == GENE_NAMES
    assert meta["number_rnas"] == 4
    assert meta["number_levels"] == 1
    assert set(meta["position_keys"]) == {"0,0", "1,1"}


def test_iter_batches_yields_per_position(simple_zarr):
    batches = list(trx_zarr.iter_zarr_transcript_batches(simple_zarr))
    assert len(batches) == 2
    for batch in batches:
        assert batch.columns == ["name", "x", "y"]
        assert batch.height == 2

    combined = pl.concat(batches)
    assert sorted(combined["name"].to_list()) == ["G0", "G0", "G1", "G2"]


def test_load_full_frame(simple_zarr):
    frame = trx_zarr.load_zarr_transcripts(simple_zarr)
    assert frame.height == 4
    assert set(frame["name"].to_list()) == {"G0", "G1", "G2"}


def test_drop_no_call(tmp_path):
    positions = {
        "0,0": {"x": [10.0, 20.0, 30.0], "y": [10.0, 20.0, 30.0], "gene": [0, NO_CALL, 2]},
    }
    path = _write_zarr_transcripts(tmp_path / "transcripts.zarr", positions)

    kept = trx_zarr.load_zarr_transcripts(path, drop_no_call=True)
    assert kept.height == 2
    assert sorted(kept["name"].to_list()) == ["G0", "G2"]

    all_rows = trx_zarr.load_zarr_transcripts(path, drop_no_call=False)
    # The no-call index is out of range for gene_names, so it is filtered regardless.
    assert all_rows.height == 2


def test_min_quality_filter(tmp_path):
    positions = {
        "0,0": {
            "x": [10.0, 20.0, 30.0],
            "y": [10.0, 20.0, 30.0],
            "gene": [0, 1, 2],
            "quality": [10.0, 25.0, 40.0],
        },
    }
    path = _write_zarr_transcripts(tmp_path / "transcripts.zarr", positions)

    kept = trx_zarr.load_zarr_transcripts(path, min_quality=20.0)
    assert sorted(kept["name"].to_list()) == ["G1", "G2"]


def test_zip_roundtrip(tmp_path):
    positions = {"0,0": {"x": [1.0, 2.0], "y": [3.0, 4.0], "gene": [0, 2]}}
    path = _write_zarr_transcripts(tmp_path / "transcripts.zarr.zip", positions, as_zip=True)

    meta = trx_zarr.read_zarr_transcript_metadata(path)
    assert meta["number_rnas"] == 2
    frame = trx_zarr.load_zarr_transcripts(path)
    assert sorted(frame["name"].to_list()) == ["G0", "G2"]


def _identity_transform(tmp_path):
    path = tmp_path / "micron_to_image_transform.csv"
    np.savetxt(path, np.eye(3))
    return path


def test_make_trx_tiles_from_zarr_traditional(tmp_path, simple_zarr):
    transform = _identity_transform(tmp_path)
    out_dir = tmp_path / "transcript_tiles"
    tile_size = 250

    tile_bounds, _tile_grid_info, chunk_info = trx_zarr.make_trx_tiles_from_zarr(
        simple_zarr,
        transform,
        out_dir,
        tile_size=tile_size,
        use_row_groups=False,
        gene_str_to_int_mapping=GENE_MAP,
    )

    assert chunk_info is None
    assert tile_bounds["x_min"] == 0.0
    assert tile_bounds["x_max"] >= 320.0

    tile_files = list(out_dir.glob("transcripts_tile_*.parquet"))
    assert tile_files, "expected transcript tile files"

    total = 0
    for path in tile_files:
        df = pd.read_parquet(path)
        assert list(df.columns) == ["name", "geometry"] or set(df.columns) >= {"name", "geometry"}
        # Gene names must be mapped to their integer codes.
        assert set(df["name"].unique()) <= set(GENE_MAP.values())
        total += len(df)
    assert total == 4


def test_make_trx_tiles_from_zarr_row_groups(tmp_path, simple_zarr):
    transform = _identity_transform(tmp_path)
    out_dir = tmp_path / "transcripts"
    tile_size = 250

    _tile_bounds, tile_grid_info, chunk_info = trx_zarr.make_trx_tiles_from_zarr(
        simple_zarr,
        transform,
        out_dir,
        tile_size=tile_size,
        use_row_groups=True,
        max_row_groups_per_file=400,
        gene_str_to_int_mapping=GENE_MAP,
    )

    assert chunk_info is not None
    n_tiles = tile_grid_info["num_tiles_x"] * tile_grid_info["num_tiles_y"]
    assert chunk_info["total_row_groups"] == n_tiles

    chunk_files = sorted(out_dir.glob("chunk_*.parquet"))
    assert chunk_files

    # Metadata identifies the chunked row-group storage mode and grid dimensions.
    pf = pq.ParquetFile(chunk_files[0])
    md = pf.schema_arrow.metadata
    assert md[b"storage_mode"] == b"row_groups_chunked"
    grid = json.loads(md[b"tile_grid_info"])
    assert grid["num_tiles_x"] == tile_grid_info["num_tiles_x"]

    # All transcripts are recoverable across the row groups.
    total = 0
    for path in chunk_files:
        file = pq.ParquetFile(path)
        for rg in range(file.metadata.num_row_groups):
            total += file.read_row_group(rg).num_rows
    assert total == 4


def test_empty_zarr_produces_no_tiles(tmp_path):
    positions = {"0,0": {"x": [], "y": [], "gene": []}}
    path = _write_zarr_transcripts(tmp_path / "transcripts.zarr", positions)
    transform = _identity_transform(tmp_path)
    out_dir = tmp_path / "transcript_tiles"

    _tile_bounds, _tile_grid_info, chunk_info = trx_zarr.make_trx_tiles_from_zarr(
        path, transform, out_dir, tile_size=250, gene_str_to_int_mapping=GENE_MAP
    )

    assert chunk_info is None
    assert list(out_dir.glob("transcripts_tile_*.parquet")) == []


def test_zarr_matches_parquet_tiling(tmp_path):
    """The Zarr grid tiler and the flat-parquet tiler must agree tile-for-tile."""
    # Interior coordinates (well away from 250 um tile boundaries) so both the
    # floor-based Zarr assignment and the coarse/fine parquet filters agree exactly.
    points = [
        (50.0, 50.0, "G0"),
        (120.0, 120.0, "G1"),
        (300.0, 60.0, "G2"),
        (320.0, 320.0, "G0"),
        (60.0, 300.0, "G1"),
        (420.0, 420.0, "G2"),
    ]
    tile_size = 250

    # meta_gene.parquet drives the gene->int mapping for the parquet path.
    pd.DataFrame(index=GENE_NAMES).to_parquet(tmp_path / "meta_gene.parquet")
    transform = _identity_transform(tmp_path)

    # Flat Xenium-style parquet source.
    trx_parquet = tmp_path / "transcripts.parquet"
    pl.DataFrame(
        {
            "feature_name": [g for _, _, g in points],
            "x_location": [x for x, _, _ in points],
            "y_location": [y for _, y, _ in points],
            "cell_id": [f"c{i}" for i in range(len(points))],
            "transcript_id": list(range(len(points))),
        }
    ).write_parquet(trx_parquet)

    # Equivalent Zarr source (two grid positions).
    positions = {
        "0,0": {
            "x": [p[0] for p in points[:3]],
            "y": [p[1] for p in points[:3]],
            "gene": [GENE_MAP[p[2]] for p in points[:3]],
        },
        "1,1": {
            "x": [p[0] for p in points[3:]],
            "y": [p[1] for p in points[3:]],
            "gene": [GENE_MAP[p[2]] for p in points[3:]],
        },
    }
    zarr_path = _write_zarr_transcripts(tmp_path / "transcripts.zarr", positions)

    parquet_out = tmp_path / "transcript_tiles"
    make_trx_tiles(
        technology="Xenium",
        path_trx=str(trx_parquet),
        path_transformation_matrix=str(transform),
        path_trx_tiles=str(parquet_out),
        coarse_tile_factor=2,
        tile_size=tile_size,
        chunk_size=50,
        image_scale=1,
        max_workers=1,
    )

    zarr_out = tmp_path / "transcript_tiles_zarr"
    trx_zarr.make_trx_tiles_from_zarr(
        zarr_path,
        transform,
        zarr_out,
        tile_size=tile_size,
        use_row_groups=False,
        path_dega_files=tmp_path,
    )

    def _tile_counts(directory):
        counts = {}
        for path in directory.glob("transcripts_tile_*.parquet"):
            key = tuple(map(int, path.stem.split("_")[-2:]))
            counts[key] = len(pd.read_parquet(path))
        return counts

    parquet_counts = _tile_counts(parquet_out)
    zarr_counts = _tile_counts(zarr_out)

    assert parquet_counts == zarr_counts
    assert sum(zarr_counts.values()) == len(points)
