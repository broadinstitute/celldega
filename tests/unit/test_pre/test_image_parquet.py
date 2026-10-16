"""Packing a DeepZoom pyramid into chunked parquet writes one row group per tile,
in column-major order within each zoom level, so that a reader can address any tile by
``row_group_offset[zoom] + tile_x * num_tiles_y + tile_y`` and then split that global
index across the ``chunk_N.parquet`` files by ``max_row_groups_per_file``.

Tile payloads are copied verbatim as opaque bytes (no image decoding), image dimensions
come from the sidecar ``.dzi``, and the source tile directory is removed only when
``delete_source_tiles`` is set.
"""

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from celldega.pre.image_parquet import pack_image_tiles_to_parquet


_DZI_NS = "http://schemas.microsoft.com/deepzoom/2008"


# --- builders ---------------------------------------------------------------


def _tile_payload(channel: str, zoom: int, tile_x: int, tile_y: int) -> bytes:
    """Deliberately not a valid image: the packer must copy raw bytes, not decode them."""
    return f"{channel}|{zoom}|{tile_x}|{tile_y}".encode()


def _write_dzi(
    pyramid_dir: Path,
    channel: str,
    width: int,
    height: int,
    tile_size: int = 512,
    namespaced: bool = True,
) -> Path:
    xmlns = f' xmlns="{_DZI_NS}"' if namespaced else ""
    dzi = pyramid_dir / f"{channel}.dzi"
    dzi.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Image{xmlns} Format="webp" Overlap="0" TileSize="{tile_size}">\n'
        f'  <Size Width="{width}" Height="{height}"/>\n'
        "</Image>\n"
    )
    return dzi


def _make_pyramid(
    root: Path,
    channel: str = "dapi",
    grids: tuple[tuple[int, int, int], ...] = ((8, 1, 1), (9, 2, 3)),
    image_format: str = ".webp",
) -> dict[tuple[int, int, int], bytes]:
    """Fabricate ``<root>/<channel>_files/<zoom>/<x>_<y><ext>``; returns the tile payloads."""
    tiles_dir = root / f"{channel}_files"
    payloads: dict[tuple[int, int, int], bytes] = {}
    for zoom, num_x, num_y in grids:
        zoom_dir = tiles_dir / str(zoom)
        zoom_dir.mkdir(parents=True)
        for tile_x in range(num_x):
            for tile_y in range(num_y):
                data = _tile_payload(channel, zoom, tile_x, tile_y)
                (zoom_dir / f"{tile_x}_{tile_y}{image_format}").write_bytes(data)
                payloads[(zoom, tile_x, tile_y)] = data
    return payloads


def _read_row_group(output_dir: Path, manifest: dict, global_index: int) -> dict:
    """Resolve a global row-group index the way the frontend reader does."""
    per_file = manifest["max_row_groups_per_file"]
    file_name = manifest["files"][global_index // per_file]
    pf = pq.ParquetFile(output_dir / file_name)
    return pf.read_row_group(global_index % per_file).to_pylist()[0]


# --- tile counts and cumulative offsets -------------------------------------


def test_row_count_matches_tile_count_and_offsets_are_cumulative(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    grids = ((8, 1, 1), (9, 2, 3), (10, 3, 4))
    payloads = _make_pyramid(pyramid, grids=grids)
    assert len(payloads) == 1 + 6 + 12

    out = tmp_path / "out"
    manifest = pack_image_tiles_to_parquet(pyramid, "dapi", out, delete_source_tiles=False)

    assert manifest["num_tiles"] == 19
    assert manifest["total_row_groups"] == 19
    assert manifest["zoom_levels"] == [8, 9, 10]

    zoom_info = manifest["zoom_info"]
    assert zoom_info[8] == {
        "num_tiles_x": 1,
        "num_tiles_y": 1,
        "num_tiles": 1,
        "row_group_offset": 0,
    }
    assert zoom_info[9]["row_group_offset"] == 1
    assert zoom_info[10]["row_group_offset"] == 7
    assert [zoom_info[z]["num_tiles"] for z in (8, 9, 10)] == [1, 6, 12]

    written = sum(pq.ParquetFile(out / name).num_row_groups for name in manifest["files"])
    assert written == 19


def test_schema_metadata_records_zoom_info_and_channel(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, channel="bound", grids=((0, 2, 2),))

    out = tmp_path / "out"
    manifest = pack_image_tiles_to_parquet(pyramid, "bound", out, delete_source_tiles=False)

    metadata = pq.ParquetFile(out / manifest["files"][0]).schema_arrow.metadata
    assert metadata[b"storage_mode"] == b"row_groups_image_chunked"
    assert metadata[b"channel_name"] == b"bound"
    assert metadata[b"image_format"] == b".webp"
    # zoom_info round-trips through JSON, so its keys become strings on the way out.
    assert json.loads(metadata[b"zoom_info"]) == {
        "0": {"num_tiles_x": 2, "num_tiles_y": 2, "num_tiles": 4, "row_group_offset": 0}
    }


# --- .dzi dimensions --------------------------------------------------------


@pytest.mark.parametrize("namespaced", [True, False])
def test_image_dimensions_read_from_dzi(tmp_path: Path, namespaced: bool) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 1, 1),))
    _write_dzi(pyramid, "dapi", width=4321, height=765, tile_size=256, namespaced=namespaced)

    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", tmp_path / "out", delete_source_tiles=False
    )

    assert manifest["image_width"] == 4321
    assert manifest["image_height"] == 765
    assert manifest["tile_size"] == 256


def test_missing_dzi_leaves_dimensions_null_with_default_tile_size(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 1, 1),))

    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", tmp_path / "out", delete_source_tiles=False
    )

    assert manifest["image_width"] is None
    assert manifest["image_height"] is None
    assert manifest["tile_size"] == 512


def test_malformed_dzi_is_swallowed_and_yields_null_dimensions(tmp_path: Path) -> None:
    """BUG (pinned, not fixed): the .dzi parse sits inside a bare ``except Exception``
    that only prints. A truncated/corrupt .dzi therefore produces a manifest with
    ``image_width``/``image_height`` of None, which downstream is written out as JSON
    nulls instead of failing loudly."""
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 1, 1),))
    (pyramid / "dapi.dzi").write_text('<Image TileSize="256"><Size Width="10"')  # truncated

    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", tmp_path / "out", delete_source_tiles=False
    )

    assert manifest["image_width"] is None
    assert manifest["image_height"] is None
    # TileSize was present in the text but never applied: the parse died before reading it.
    assert manifest["tile_size"] == 512


def test_dzi_without_size_element_yields_null_dimensions_but_keeps_tile_size(
    tmp_path: Path,
) -> None:
    """No exception here -- the Size lookup just fails all four fallbacks, so the
    dimensions stay None while TileSize is still picked up off the root element."""
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 1, 1),))
    (pyramid / "dapi.dzi").write_text('<Image TileSize="128"><Format>webp</Format></Image>')

    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", tmp_path / "out", delete_source_tiles=False
    )

    assert manifest["image_width"] is None
    assert manifest["image_height"] is None
    assert manifest["tile_size"] == 128


# --- the row-group index formula the reader relies on -----------------------


def test_row_group_index_formula_addresses_every_tile(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    grids = ((8, 1, 1), (9, 2, 3), (10, 3, 4))
    payloads = _make_pyramid(pyramid, grids=grids)

    out = tmp_path / "out"
    manifest = pack_image_tiles_to_parquet(
        pyramid,
        "dapi",
        out,
        delete_source_tiles=False,
        # Small enough that the formula has to survive being split across files.
        max_row_groups_per_file=4,
    )
    assert len(manifest["files"]) > 1

    zoom_info = manifest["zoom_info"]
    seen = 0
    for zoom, num_x, num_y in grids:
        info = zoom_info[zoom]
        for tile_x in range(num_x):
            for tile_y in range(num_y):
                index = info["row_group_offset"] + tile_x * info["num_tiles_y"] + tile_y
                row = _read_row_group(out, manifest, index)
                assert (row["zoom"], row["tile_x"], row["tile_y"]) == (zoom, tile_x, tile_y)
                assert row["image_data"] == payloads[(zoom, tile_x, tile_y)]
                seen += 1

    assert seen == len(payloads) == 19


# --- multi-file chunking ----------------------------------------------------


@pytest.mark.parametrize(
    ("max_per_file", "expected_sizes"),
    [
        (4, [4, 4, 4, 4, 3]),  # 19 tiles, ragged last chunk
        (19, [19]),  # exact fit, single chunk
        (10, [10, 9]),
        (100, [19]),  # cap larger than the dataset
    ],
)
def test_chunking_splits_tiles_across_files(
    tmp_path: Path, max_per_file: int, expected_sizes: list[int]
) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((8, 1, 1), (9, 2, 3), (10, 3, 4)))

    out = tmp_path / "out"
    manifest = pack_image_tiles_to_parquet(
        pyramid,
        "dapi",
        out,
        delete_source_tiles=False,
        max_row_groups_per_file=max_per_file,
    )

    assert manifest["files"] == [f"chunk_{i}.parquet" for i in range(len(expected_sizes))]
    assert manifest["max_row_groups_per_file"] == max_per_file
    assert [pq.ParquetFile(out / n).num_row_groups for n in manifest["files"]] == expected_sizes
    assert sorted(p.name for p in out.glob("*.parquet")) == sorted(manifest["files"])


def test_chunk_boundaries_preserve_global_tile_order(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((8, 1, 1), (9, 2, 3)))

    out = tmp_path / "out"
    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", out, delete_source_tiles=False, max_row_groups_per_file=3
    )
    assert len(manifest["files"]) == 3

    order = []
    for name in manifest["files"]:
        pf = pq.ParquetFile(out / name)
        for i in range(pf.num_row_groups):
            row = pf.read_row_group(i).to_pylist()[0]
            order.append((row["zoom"], row["tile_x"], row["tile_y"]))

    # Zoom-major, then column-major within a zoom level.
    assert order == [
        (8, 0, 0),
        (9, 0, 0),
        (9, 0, 1),
        (9, 0, 2),
        (9, 1, 0),
        (9, 1, 1),
        (9, 1, 2),
    ]


# --- source tile deletion ---------------------------------------------------


def test_delete_source_tiles_removes_tiles_but_keeps_dzi(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 2, 2),))
    dzi = _write_dzi(pyramid, "dapi", width=1024, height=1024)
    tiles_dir = pyramid / "dapi_files"
    assert tiles_dir.exists()

    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", tmp_path / "out", delete_source_tiles=True
    )

    assert not tiles_dir.exists()
    assert dzi.exists()
    assert manifest["num_tiles"] == 4


def test_delete_source_tiles_false_leaves_tiles_in_place(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    payloads = _make_pyramid(pyramid, grids=((0, 2, 2),))
    tiles_dir = pyramid / "dapi_files"

    pack_image_tiles_to_parquet(pyramid, "dapi", tmp_path / "out", delete_source_tiles=False)

    assert tiles_dir.exists()
    assert sorted(p.name for p in (tiles_dir / "0").glob("*.webp")) == [
        "0_0.webp",
        "0_1.webp",
        "1_0.webp",
        "1_1.webp",
    ]
    assert (tiles_dir / "0" / "1_1.webp").read_bytes() == payloads[(0, 1, 1)]


# --- error paths ------------------------------------------------------------


def test_missing_tiles_directory_raises(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()

    with pytest.raises(FileNotFoundError, match="Tiles directory not found"):
        pack_image_tiles_to_parquet(pyramid, "dapi", tmp_path / "out")


def test_tiles_directory_without_zoom_levels_raises(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    (pyramid / "dapi_files").mkdir(parents=True)

    with pytest.raises(ValueError, match="No zoom levels found"):
        pack_image_tiles_to_parquet(pyramid, "dapi", tmp_path / "out")


def test_zoom_levels_without_matching_image_format_raises(tmp_path: Path) -> None:
    """An empty zoom level is tolerated in the loop but leaves ``all_tiles`` empty,
    so the packer bails before creating the output directory."""
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 1, 1),), image_format=".png")

    out = tmp_path / "out"
    with pytest.raises(ValueError, match="No tiles found to pack"):
        pack_image_tiles_to_parquet(pyramid, "dapi", out, image_format=".webp")

    assert not out.exists()


def test_non_default_image_format_is_honoured(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    payloads = _make_pyramid(pyramid, grids=((0, 2, 1),), image_format=".png")

    out = tmp_path / "out"
    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", out, image_format=".png", delete_source_tiles=False
    )

    assert manifest["num_tiles"] == 2
    metadata = pq.ParquetFile(out / manifest["files"][0]).schema_arrow.metadata
    assert metadata[b"image_format"] == b".png"
    assert _read_row_group(out, manifest, 1)["image_data"] == payloads[(0, 1, 0)]


def test_tile_filenames_that_are_not_x_y_are_skipped(tmp_path: Path) -> None:
    """Only two-part ``<x>_<y>`` stems are packed; anything else is silently ignored."""
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    _make_pyramid(pyramid, grids=((0, 1, 2),))
    (pyramid / "dapi_files" / "0" / "thumbnail.webp").write_bytes(b"nope")
    (pyramid / "dapi_files" / "0" / "0_1_extra.webp").write_bytes(b"also-nope")

    manifest = pack_image_tiles_to_parquet(
        pyramid, "dapi", tmp_path / "out", delete_source_tiles=False
    )

    assert manifest["num_tiles"] == 2
    assert manifest["zoom_info"][0]["num_tiles_x"] == 1
    assert manifest["zoom_info"][0]["num_tiles_y"] == 2
