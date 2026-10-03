"""
Row-group writers emit a deterministic, index-addressable parquet layout.

`make_trx_tiles_row_groups` and `make_cell_boundary_tiles_row_groups` are
TILE-indexed: every cell of the ``num_tiles_x x num_tiles_y`` grid gets exactly one
row group -- empty tiles included -- at global index ``tile_x * num_tiles_y + tile_y``,
and each chunk file carries ``storage_mode=row_groups_chunked`` plus the JSON
``tile_grid_info`` needed to invert that formula.

`save_cbg_gene_parquets_row_groups` is GENE-indexed instead: one row group per gene
that has any non-zero expression, ``storage_mode=row_groups_cbg_chunked``, a
``gene_to_row_group`` mapping and ``num_genes`` -- and deliberately no tile grid.

For all three the global row-group index is FILE-LOCAL once written:
``file_index = idx // max_row_groups_per_file`` and ``local = idx % max_row_groups_per_file``.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from celldega.pre.boundary_tile import make_cell_boundary_tiles_row_groups
from celldega.pre.landscape import save_cbg_gene_parquets_row_groups
from celldega.pre.trx_tile import make_trx_tiles_row_groups


# --- synthetic dataset geometry -------------------------------------------------
#
# A 4x4 grid of 100-unit tiles. Transcript bounds are derived from the DATA
# (x_min/y_min are pinned to 0, x_max/y_max to the observed maximum), so the
# furthest transcript sits at 350 to force ceil(350/100) == 4 tiles per axis.
# Boundary bounds are supplied explicitly instead, hence the 400 below.

TILE_SIZE = 100
NUM_TILES_X = 4
NUM_TILES_Y = 4
TOTAL_TILES = NUM_TILES_X * NUM_TILES_Y
BOUNDARY_BOUNDS = {"x_min": 0, "x_max": 400, "y_min": 0, "y_max": 400}

# Deliberately not alphabetical: the gene -> int mapping is positional in
# meta_gene.parquet, not sorted.
META_GENE_ORDER = ("GC", "GA", "GB")
TRX_GENES = ("GA", "GB", "GC")

# One tile is left without transcripts so the empty-row-group path is exercised.
EMPTY_TRX_TILE = (1, 2)

N_BOUNDARY_CELLS = 8


def _tile_gene(tile_x: int, tile_y: int) -> str:
    return TRX_GENES[(tile_x + tile_y) % len(TRX_GENES)]


def _expected_trx_points(tile_x: int, tile_y: int) -> list[list[float]]:
    """The transcript geometries `_write_transcripts` places in one tile."""
    if (tile_x, tile_y) == EMPTY_TRX_TILE:
        return []
    points = [
        [float(tile_x * TILE_SIZE + 10), float(tile_y * TILE_SIZE + 10)],
        [float(tile_x * TILE_SIZE + 11), float(tile_y * TILE_SIZE + 11)],
    ]
    if (tile_x, tile_y) == (NUM_TILES_X - 1, NUM_TILES_Y - 1):
        points.append([350.0, 350.0])
    return points


# --- input builders -------------------------------------------------------------


def _write_dega_metadata(tmp_path: Path) -> None:
    """meta_gene.parquet / cell_metadata.parquet drive the name -> int mappings."""
    pd.DataFrame(index=pd.Index(list(META_GENE_ORDER))).to_parquet(tmp_path / "meta_gene.parquet")
    pd.DataFrame({"name": [f"cell_{i}" for i in range(N_BOUNDARY_CELLS)]}).to_parquet(
        tmp_path / "cell_metadata.parquet"
    )


def _write_transformation_matrix(tmp_path: Path) -> Path:
    path = tmp_path / "micron_to_image_transform.csv"
    np.savetxt(path, np.eye(3))
    return path


def _write_transcripts(tmp_path: Path) -> Path:
    """Xenium-shaped transcripts, two per tile, one tile left empty."""
    names: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for tile_x in range(NUM_TILES_X):
        for tile_y in range(NUM_TILES_Y):
            for x, y in _expected_trx_points(tile_x, tile_y):
                names.append(_tile_gene(tile_x, tile_y))
                xs.append(x)
                ys.append(y)

    path = tmp_path / "transcripts.parquet"
    pl.DataFrame(
        {
            "feature_name": names,
            "x_location": xs,
            "y_location": ys,
            "cell_id": [f"cell_{i % N_BOUNDARY_CELLS}" for i in range(len(names))],
            "transcript_id": list(range(len(names))),
        }
    ).write_parquet(path)
    return path


def _write_cell_boundaries(tmp_path: Path) -> Path:
    """Square Xenium cells; cell ``i`` has its centroid in tile ``(i % 4, i // 4)``."""
    records = []
    for i in range(N_BOUNDARY_CELLS):
        tile_x, tile_y = _boundary_tile_of_cell(i)
        x0 = tile_x * TILE_SIZE + 20.0
        y0 = tile_y * TILE_SIZE + 20.0
        size = 20.0
        for x, y in [
            (x0, y0),
            (x0 + size, y0),
            (x0 + size, y0 + size),
            (x0, y0 + size),
            (x0, y0),
        ]:
            records.append(
                {"cell_id": f"cell_{i}", "vertex_x": x, "vertex_y": y, "label_id": 1000 + i}
            )

    path = tmp_path / "cell_boundaries.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path


def _boundary_tile_of_cell(cell_index: int) -> tuple[int, int]:
    return cell_index % NUM_TILES_X, cell_index // NUM_TILES_X


def _make_cbg() -> pd.DataFrame:
    """Cell-by-gene frame whose column order is not alphabetical and holds a dead gene."""
    return pd.DataFrame(
        {
            "GB": [5.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "GZERO": [0.0] * 6,
            "GA": [0.0, 2.0, 4.0, 0.0, 0.0, 7.0],
            "GC": [0.0, 0.0, 0.0, 0.0, 9.0, 0.0],
        },
        index=[f"cell_{i}" for i in range(6)],
    )


# --- row-group readers ----------------------------------------------------------


def _row_group_counts(output_dir: Path, chunk_info: dict) -> list[int]:
    """Row groups held by each chunk file, in ``chunk_info['files']`` order."""
    return [
        pq.ParquetFile(output_dir / name).metadata.num_row_groups for name in chunk_info["files"]
    ]


def _read_row_group(output_dir: Path, chunk_info: dict, global_index: int) -> pd.DataFrame:
    """Resolve a global row-group index through the file-local addressing scheme."""
    per_file = chunk_info["max_row_groups_per_file"]
    file_name = chunk_info["files"][global_index // per_file]
    parquet_file = pq.ParquetFile(output_dir / file_name)
    return parquet_file.read_row_group(global_index % per_file).to_pandas()


def _expected_file_layout(total_row_groups: int, per_file: int) -> list[int]:
    full, remainder = divmod(total_row_groups, per_file)
    return [per_file] * full + ([remainder] if remainder else [])


def _schema_metadata(output_dir: Path, file_name: str) -> dict[bytes, bytes]:
    return dict(pq.ParquetFile(output_dir / file_name).schema_arrow.metadata)


# --- transcript row groups ------------------------------------------------------


@pytest.mark.parametrize("max_row_groups_per_file", [2, 3])
@pytest.mark.parametrize("streaming", [False, True])
def test_trx_row_groups_are_tile_indexed(
    tmp_path: Path, max_row_groups_per_file: int, streaming: bool
) -> None:
    # The in-memory and the disk-backed (spill-to-parquet) tile assignment paths are two
    # independent implementations of the same layout; forcing the flag covers the streaming
    # one, which the 500k-row auto-threshold would otherwise never select here.
    _write_dega_metadata(tmp_path)
    output_dir = tmp_path / "transcript_tiles"

    tile_bounds, tile_grid_info, chunk_info = make_trx_tiles_row_groups(
        technology="Xenium",
        path_trx=str(_write_transcripts(tmp_path)),
        path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
        path_output_dir=str(output_dir),
        tile_size=TILE_SIZE,
        image_scale=1,
        path_dega_files=str(tmp_path),
        max_row_groups_per_file=max_row_groups_per_file,
        streaming_tile_assignment=streaming,
    )

    assert tile_bounds == {"x_min": 0, "x_max": 350.0, "y_min": 0, "y_max": 350.0}
    assert tile_grid_info["num_tiles_x"] == NUM_TILES_X
    assert tile_grid_info["num_tiles_y"] == NUM_TILES_Y

    # One row group per grid cell, including the tile with no transcripts.
    assert chunk_info["total_row_groups"] == TOTAL_TILES
    assert chunk_info["max_row_groups_per_file"] == max_row_groups_per_file
    assert _row_group_counts(output_dir, chunk_info) == _expected_file_layout(
        TOTAL_TILES, max_row_groups_per_file
    )
    assert sorted(p.name for p in output_dir.glob("*.parquet")) == sorted(chunk_info["files"])

    for tile_x in range(NUM_TILES_X):
        for tile_y in range(NUM_TILES_Y):
            global_index = tile_x * NUM_TILES_Y + tile_y
            group = _read_row_group(output_dir, chunk_info, global_index)
            expected_points = _expected_trx_points(tile_x, tile_y)

            assert len(group) == len(expected_points), (tile_x, tile_y)
            if not expected_points:
                continue
            assert group["tile_x"].tolist() == [tile_x] * len(expected_points)
            assert group["tile_y"].tolist() == [tile_y] * len(expected_points)
            assert sorted(list(point) for point in group["geometry"]) == sorted(expected_points)


def test_trx_row_groups_map_gene_names_through_meta_gene(tmp_path: Path) -> None:
    _write_dega_metadata(tmp_path)
    output_dir = tmp_path / "transcript_tiles"

    _, _, chunk_info = make_trx_tiles_row_groups(
        technology="Xenium",
        path_trx=str(_write_transcripts(tmp_path)),
        path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
        path_output_dir=str(output_dir),
        tile_size=TILE_SIZE,
        image_scale=1,
        path_dega_files=str(tmp_path),
        max_row_groups_per_file=3,
    )

    seen_codes = set()
    for tile_x in range(NUM_TILES_X):
        for tile_y in range(NUM_TILES_Y):
            expected_points = _expected_trx_points(tile_x, tile_y)
            if not expected_points:
                continue
            group = _read_row_group(output_dir, chunk_info, tile_x * NUM_TILES_Y + tile_y)
            expected_code = META_GENE_ORDER.index(_tile_gene(tile_x, tile_y))
            assert group["name"].tolist() == [expected_code] * len(expected_points)
            seen_codes.add(expected_code)

    # Positional, not alphabetical: all three meta_gene slots were actually hit.
    assert seen_codes == {0, 1, 2}


def test_trx_row_groups_preserve_every_transcript(tmp_path: Path) -> None:
    _write_dega_metadata(tmp_path)
    trx_path = _write_transcripts(tmp_path)
    expected_total = pl.read_parquet(trx_path).height
    output_dir = tmp_path / "transcript_tiles"

    _, _, chunk_info = make_trx_tiles_row_groups(
        technology="Xenium",
        path_trx=str(trx_path),
        path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
        path_output_dir=str(output_dir),
        tile_size=TILE_SIZE,
        image_scale=1,
        path_dega_files=str(tmp_path),
        max_row_groups_per_file=3,
    )

    assert expected_total == 31
    written = sum(
        pq.ParquetFile(output_dir / name).metadata.num_rows for name in chunk_info["files"]
    )
    assert written == expected_total


@pytest.mark.parametrize("streaming", [False, True])
def test_trx_chunk_files_each_carry_tile_grid_metadata(tmp_path: Path, streaming: bool) -> None:
    """Metadata is repeated in every chunk so a reader can start from any file.

    The streaming writer builds its own metadata block, so both paths are checked.
    """
    _write_dega_metadata(tmp_path)
    output_dir = tmp_path / "transcript_tiles"

    _, tile_grid_info, chunk_info = make_trx_tiles_row_groups(
        technology="Xenium",
        path_trx=str(_write_transcripts(tmp_path)),
        path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
        path_output_dir=str(output_dir),
        tile_size=TILE_SIZE,
        image_scale=1,
        path_dega_files=str(tmp_path),
        max_row_groups_per_file=3,
        streaming_tile_assignment=streaming,
    )

    assert len(chunk_info["files"]) == 6
    for name in chunk_info["files"]:
        metadata = _schema_metadata(output_dir, name)
        assert metadata[b"storage_mode"] == b"row_groups_chunked"
        assert metadata[b"max_row_groups_per_file"] == b"3"
        assert json.loads(metadata[b"tile_grid_info"]) == tile_grid_info
        assert b"gene_to_row_group" not in metadata


# --- cell boundary row groups ---------------------------------------------------


@pytest.mark.parametrize("max_row_groups_per_file", [2, 3])
def test_boundary_row_groups_are_tile_indexed(tmp_path: Path, max_row_groups_per_file: int) -> None:
    _write_dega_metadata(tmp_path)
    output_dir = tmp_path / "cell_segmentation"

    chunk_info = make_cell_boundary_tiles_row_groups(
        technology="Xenium",
        path_cell_boundaries=str(_write_cell_boundaries(tmp_path)),
        path_output_dir=str(output_dir),
        path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
        tile_size=TILE_SIZE,
        tile_bounds=BOUNDARY_BOUNDS,
        image_scale=1,
        path_dega_files=str(tmp_path),
        max_row_groups_per_file=max_row_groups_per_file,
    )

    assert chunk_info["total_row_groups"] == TOTAL_TILES
    assert _row_group_counts(output_dir, chunk_info) == _expected_file_layout(
        TOTAL_TILES, max_row_groups_per_file
    )
    assert sorted(p.name for p in output_dir.glob("*.parquet")) == sorted(chunk_info["files"])

    # cell_i -> integer i via cell_metadata.parquet, landing in tile (i % 4, i // 4).
    expected_by_tile = {_boundary_tile_of_cell(i): i for i in range(N_BOUNDARY_CELLS)}
    assert len(expected_by_tile) == N_BOUNDARY_CELLS

    occupied = 0
    for tile_x in range(NUM_TILES_X):
        for tile_y in range(NUM_TILES_Y):
            group = _read_row_group(output_dir, chunk_info, tile_x * NUM_TILES_Y + tile_y)
            expected_name = expected_by_tile.get((tile_x, tile_y))
            if expected_name is None:
                assert len(group) == 0, (tile_x, tile_y)
                continue
            occupied += 1
            assert group["name"].tolist() == [expected_name]
            assert group["tile_x"].tolist() == [tile_x]
            assert group["tile_y"].tolist() == [tile_y]
            # GEOMETRY is a rounded nested ring, not a shapely object.
            (ring,) = group["GEOMETRY"].tolist()
            assert [list(coord) for coord in ring[0]] == [
                [tile_x * TILE_SIZE + 20.0, tile_y * TILE_SIZE + 20.0],
                [tile_x * TILE_SIZE + 40.0, tile_y * TILE_SIZE + 20.0],
                [tile_x * TILE_SIZE + 40.0, tile_y * TILE_SIZE + 40.0],
                [tile_x * TILE_SIZE + 20.0, tile_y * TILE_SIZE + 40.0],
                [tile_x * TILE_SIZE + 20.0, tile_y * TILE_SIZE + 20.0],
            ]

    assert occupied == N_BOUNDARY_CELLS


def test_boundary_tile_grid_info_comes_from_tile_bounds_not_data(tmp_path: Path) -> None:
    """Cells only reach x=340, but the declared bounds (0..400) set the grid."""
    _write_dega_metadata(tmp_path)
    output_dir = tmp_path / "cell_segmentation"

    chunk_info = make_cell_boundary_tiles_row_groups(
        technology="Xenium",
        path_cell_boundaries=str(_write_cell_boundaries(tmp_path)),
        path_output_dir=str(output_dir),
        path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
        tile_size=TILE_SIZE,
        tile_bounds=BOUNDARY_BOUNDS,
        image_scale=1,
        path_dega_files=str(tmp_path),
        max_row_groups_per_file=3,
    )

    assert len(chunk_info["files"]) == 6
    for name in chunk_info["files"]:
        metadata = _schema_metadata(output_dir, name)
        assert metadata[b"storage_mode"] == b"row_groups_chunked"
        assert metadata[b"max_row_groups_per_file"] == b"3"
        grid = json.loads(metadata[b"tile_grid_info"])
        assert grid == {
            "tile_size": TILE_SIZE,
            "num_tiles_x": NUM_TILES_X,
            "num_tiles_y": NUM_TILES_Y,
            "x_min": 0.0,
            "x_max": 400.0,
            "y_min": 0.0,
            "y_max": 400.0,
        }


def test_boundary_row_groups_reject_unsupported_technology(tmp_path: Path) -> None:
    _write_dega_metadata(tmp_path)

    with pytest.raises(NotImplementedError, match="Row group mode"):
        make_cell_boundary_tiles_row_groups(
            technology="custom",
            path_cell_boundaries=str(_write_cell_boundaries(tmp_path)),
            path_output_dir=str(tmp_path / "cell_segmentation"),
            path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
            tile_bounds=BOUNDARY_BOUNDS,
        )

    with pytest.raises(ValueError, match="Unsupported technology: Visium"):
        make_cell_boundary_tiles_row_groups(
            technology="Visium",
            path_cell_boundaries=str(_write_cell_boundaries(tmp_path)),
            path_output_dir=str(tmp_path / "cell_segmentation"),
            path_transformation_matrix=str(_write_transformation_matrix(tmp_path)),
            tile_bounds=BOUNDARY_BOUNDS,
        )


# --- cell-by-gene row groups ----------------------------------------------------


@pytest.mark.parametrize("max_row_groups_per_file", [2, 3])
def test_cbg_row_groups_are_gene_indexed(tmp_path: Path, max_row_groups_per_file: int) -> None:
    """CBG indexes by gene, not by tile: no tile_grid_info, one row group per live gene."""
    _write_dega_metadata(tmp_path)
    cbg = _make_cbg()

    chunk_info = save_cbg_gene_parquets_row_groups(
        "Xenium", str(tmp_path), cbg, max_row_groups_per_file=max_row_groups_per_file
    )

    output_dir = tmp_path / "cbg"
    assert chunk_info["directory"] == "cbg"
    assert chunk_info["total_row_groups"] == 3
    assert chunk_info["gene_to_row_group"] == {"GB": 0, "GA": 1, "GC": 2}
    assert _row_group_counts(output_dir, chunk_info) == _expected_file_layout(
        3, max_row_groups_per_file
    )
    assert sorted(p.name for p in output_dir.glob("*.parquet")) == sorted(chunk_info["files"])

    expected_rows = {
        "GB": {0: 5.0, 3: 1.0},
        "GA": {1: 2.0, 2: 4.0, 5: 7.0},
        "GC": {4: 9.0},
    }
    for gene, global_index in chunk_info["gene_to_row_group"].items():
        group = _read_row_group(output_dir, chunk_info, global_index)
        assert group["gene"].tolist() == [gene] * len(expected_rows[gene])
        assert dict(zip(group["cell_id"], group["expression"], strict=True)) == expected_rows[gene]

    for name in chunk_info["files"]:
        metadata = _schema_metadata(output_dir, name)
        assert metadata[b"storage_mode"] == b"row_groups_cbg_chunked"
        assert metadata[b"num_genes"] == b"3"
        assert metadata[b"max_row_groups_per_file"] == str(max_row_groups_per_file).encode()
        assert b"tile_grid_info" not in metadata
        assert json.loads(metadata[b"gene_to_row_group"]) == {
            "GB": 0,
            "GA": 1,
            "GC": 2,
        }


def test_cbg_drops_genes_with_no_expression(tmp_path: Path) -> None:
    """The all-zero column is skipped and the surviving indices stay dense."""
    _write_dega_metadata(tmp_path)
    cbg = _make_cbg()
    assert "GZERO" in cbg.columns

    chunk_info = save_cbg_gene_parquets_row_groups("Xenium", str(tmp_path), cbg)

    assert "GZERO" not in chunk_info["gene_to_row_group"]
    assert sorted(chunk_info["gene_to_row_group"].values()) == [0, 1, 2]

    all_genes = set()
    for name in chunk_info["files"]:
        all_genes.update(pq.read_table(tmp_path / "cbg" / name)["gene"].to_pylist())
    assert all_genes == {"GA", "GB", "GC"}


def test_cbg_returns_empty_chunk_info_when_nothing_is_expressed(tmp_path: Path) -> None:
    _write_dega_metadata(tmp_path)
    cbg = pd.DataFrame(
        0.0, index=[f"cell_{i}" for i in range(6)], columns=["GA", "GB", "GC"], dtype=float
    )

    chunk_info = save_cbg_gene_parquets_row_groups("Xenium", str(tmp_path), cbg)

    assert chunk_info == {}
    # The directory is still created, it is just left empty.
    assert (tmp_path / "cbg").is_dir()
    assert list((tmp_path / "cbg").glob("*.parquet")) == []


def test_cbg_segmentation_approach_suffixes_the_output_directory(tmp_path: Path) -> None:
    _write_dega_metadata(tmp_path)
    # Reversed order, so the suffixed file is demonstrably the one that wins.
    pd.DataFrame({"name": [f"cell_{i}" for i in reversed(range(6))]}).to_parquet(
        tmp_path / "cell_metadata_cellpose2.parquet"
    )

    chunk_info = save_cbg_gene_parquets_row_groups(
        "Xenium", str(tmp_path), _make_cbg(), segmentation_approach="cellpose2"
    )

    assert chunk_info["directory"] == "cbg_cellpose2"
    assert (tmp_path / "cbg_cellpose2" / "chunk_0.parquet").exists()
    assert not (tmp_path / "cbg").exists()

    # cell_metadata_cellpose2.parquet lists cell_5..cell_0, so cell_0 maps to 5.
    table = pq.read_table(tmp_path / "cbg_cellpose2" / "chunk_0.parquet")
    gb_rows = table.filter(pc.equal(table["gene"], "GB")).to_pydict()
    assert sorted(gb_rows["cell_id"]) == [2, 5]


# --- pinned current behaviour (not endorsements) --------------------------------


def test_cbg_ignores_its_technology_argument(tmp_path: Path) -> None:
    """PINNED: `technology` is accepted but never read; any value yields the same bytes."""
    _write_dega_metadata(tmp_path)
    cbg = _make_cbg()

    xenium_dir = tmp_path / "as_xenium"
    nonsense_dir = tmp_path / "as_nonsense"
    xenium_dir.mkdir()
    nonsense_dir.mkdir()
    for target in (xenium_dir, nonsense_dir):
        (target / "cell_metadata.parquet").write_bytes(
            (tmp_path / "cell_metadata.parquet").read_bytes()
        )

    save_cbg_gene_parquets_row_groups("Xenium", str(xenium_dir), cbg.copy())
    save_cbg_gene_parquets_row_groups("not-a-technology", str(nonsense_dir), cbg.copy())

    assert (xenium_dir / "cbg" / "chunk_0.parquet").read_bytes() == (
        nonsense_dir / "cbg" / "chunk_0.parquet"
    ).read_bytes()


def test_cbg_keeps_cells_missing_from_cell_metadata_as_null_ids(tmp_path: Path) -> None:
    """PINNED BUG: unmapped barcodes are not dropped or raised on.

    `cbg.index.map(cell_str_to_int_mapping)` yields NaN for a barcode absent from
    cell_metadata.parquet. The row survives into the row group with a null cell_id,
    and the NaN promotes the whole cell_id column from int64 to double.
    """
    pd.DataFrame(index=pd.Index(list(META_GENE_ORDER))).to_parquet(tmp_path / "meta_gene.parquet")
    pd.DataFrame({"name": ["cell_0", "cell_1"]}).to_parquet(tmp_path / "cell_metadata.parquet")
    cbg = pd.DataFrame({"GA": [1.0, 2.0, 3.0]}, index=["cell_0", "cell_1", "ghost_cell"])

    chunk_info = save_cbg_gene_parquets_row_groups("Xenium", str(tmp_path), cbg)

    table = pq.read_table(tmp_path / "cbg" / chunk_info["files"][0])
    assert table.schema.field("cell_id").type == "double"
    assert table["cell_id"].to_pylist() == [0.0, 1.0, None]
    assert table["expression"].to_pylist() == [1.0, 2.0, 3.0]


def test_trx_row_groups_reject_custom_technology(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match="Row group mode"):
        make_trx_tiles_row_groups(
            technology="custom",
            path_trx=str(tmp_path / "missing.parquet"),
            path_transformation_matrix=str(tmp_path / "missing.csv"),
            path_output_dir=str(tmp_path / "out"),
        )
