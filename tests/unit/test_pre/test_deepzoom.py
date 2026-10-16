"""The Pillow DeepZoom writer is layout-compatible with ``vips dzsave``.

``make_deepzoom_pyramid`` switched from pyvips to Pillow so the image pipeline no longer
needs libvips installed. Downstream -- ``pack_image_tiles_to_parquet`` and the JavaScript
viewer -- reads the pyramid by position: level numbering, tile grid, ``{col}_{row}``
filenames and the ``.dzi`` dimensions. All of that has to be identical.

The tests below assert the convention directly, and then assert it *again* against real
``dzsave`` output whenever pyvips is importable, so the two engines cannot drift.

Tiles are deliberately not compared bytewise: the engines use different downsampling
kernels, and the pyramid is a display artefact.
"""

from __future__ import annotations

import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import pytest

from celldega.pre.deepzoom import (
    deepzoom_level_size,
    deepzoom_max_level,
    parse_vips_suffix,
    write_deepzoom_pyramid,
)
from celldega.pre.image_tiles import make_deepzoom_pyramid


TILE = 128
# Deliberately non-square and not a power of two, so edge tiles and the level count are
# both non-trivial.
WIDTH, HEIGHT = 500, 300


def _pyvips():
    try:
        import pyvips as _mod
    except ImportError:  # pragma: no cover - depends on host libvips
        return None
    return _mod


def _source_image(tmp_path: Path, width: int = WIDTH, height: int = HEIGHT) -> Path:
    """A deterministic non-uniform greyscale PNG."""
    columns = np.mgrid[0:height, 0:width][1]
    array = (columns % 251).astype(np.uint8)
    path = tmp_path / "src.png"
    Image.fromarray(array, mode="L").save(path)
    return path


def _tile_names(tiles_root: Path, level: int) -> set[str]:
    return {p.name for p in (tiles_root / str(level)).iterdir() if p.is_file()}


def _levels(tiles_root: Path) -> list[int]:
    # Mirrors pack_image_tiles_to_parquet's own discovery, which filters to directories.
    return sorted(int(d.name) for d in tiles_root.iterdir() if d.is_dir())


# --- the DeepZoom convention -------------------------------------------------


def test_max_level_is_ceil_log2_of_the_longest_edge() -> None:
    assert deepzoom_max_level(WIDTH, HEIGHT) == math.ceil(math.log2(WIDTH))
    assert deepzoom_max_level(1024, 10) == 10
    # A 1x1 source is a single level, not two. Clamping this to 1 is the natural mistake
    # and desynchronises the level set from dzsave.
    assert deepzoom_max_level(1, 1) == 0


def test_level_sizes_halve_down_to_one_pixel() -> None:
    max_level = deepzoom_max_level(WIDTH, HEIGHT)
    assert deepzoom_level_size(WIDTH, HEIGHT, max_level, max_level) == (WIDTH, HEIGHT)
    assert deepzoom_level_size(WIDTH, HEIGHT, max_level - 1, max_level) == (250, 150)
    assert deepzoom_level_size(WIDTH, HEIGHT, 0, max_level) == (1, 1)


def test_every_level_from_zero_to_max_is_written(tmp_path: Path) -> None:
    write_deepzoom_pyramid(_source_image(tmp_path), tmp_path / "out", "dapi", tile_size=TILE)
    tiles_root = tmp_path / "out" / "dapi_files"
    assert _levels(tiles_root) == list(range(deepzoom_max_level(WIDTH, HEIGHT) + 1))


def test_edge_tiles_are_cropped_not_padded(tmp_path: Path) -> None:
    """The viewer relies on the last tile carrying the true remainder."""
    write_deepzoom_pyramid(
        _source_image(tmp_path), tmp_path / "out", "dapi", tile_size=TILE, suffix=".png"
    )
    max_level = deepzoom_max_level(WIDTH, HEIGHT)
    level_dir = tmp_path / "out" / "dapi_files" / str(max_level)

    # 500 = 3*128 + 116, 300 = 2*128 + 44
    assert Image.open(level_dir / "0_0.png").size == (TILE, TILE)
    assert Image.open(level_dir / "3_0.png").size == (WIDTH - 3 * TILE, TILE)
    assert Image.open(level_dir / "0_2.png").size == (TILE, HEIGHT - 2 * TILE)
    assert Image.open(level_dir / "3_2.png").size == (WIDTH - 3 * TILE, HEIGHT - 2 * TILE)


def test_dzi_records_the_source_dimensions(tmp_path: Path) -> None:
    dzi = write_deepzoom_pyramid(
        _source_image(tmp_path), tmp_path / "out", "dapi", tile_size=TILE, suffix=".webp[Q=100]"
    )
    root = ET.parse(dzi).getroot()
    size = next(child for child in root if child.tag.endswith("Size"))
    assert int(size.get("Width")) == WIDTH
    assert int(size.get("Height")) == HEIGHT
    assert root.get("TileSize") == str(TILE)
    assert root.get("Overlap") == "0"
    assert root.get("Format") == "webp"


def test_overlap_is_rejected(tmp_path: Path) -> None:
    """The parquet packer indexes tiles positionally and assumes they do not overlap."""
    with pytest.raises(ValueError, match="overlap"):
        write_deepzoom_pyramid(_source_image(tmp_path), tmp_path / "out", "dapi", overlap=1)


# --- vips suffix parsing -----------------------------------------------------


@pytest.mark.parametrize(
    ("suffix", "ext", "opts"),
    [
        (".jpeg", ".jpeg", {}),
        (".png", ".png", {}),
        (".webp[Q=100]", ".webp", {"Q": "100"}),
        (".webp[Q=75,lossless=false]", ".webp", {"Q": "75", "lossless": "false"}),
    ],
)
def test_vips_suffix_is_understood(suffix: str, ext: str, opts: dict[str, str]) -> None:
    assert parse_vips_suffix(suffix) == (ext, opts)


def test_unparseable_suffix_is_rejected() -> None:
    with pytest.raises(ValueError, match="suffix"):
        parse_vips_suffix("webp")


def test_unsupported_tile_format_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="format"):
        write_deepzoom_pyramid(_source_image(tmp_path), tmp_path / "out", "dapi", suffix=".gif")


# --- engine selection --------------------------------------------------------


def test_make_deepzoom_pyramid_defaults_to_pillow(tmp_path: Path) -> None:
    make_deepzoom_pyramid(
        str(_source_image(tmp_path)), str(tmp_path / "out"), "dapi", tile_size=TILE
    )
    assert (tmp_path / "out" / "dapi.dzi").is_file()
    assert _levels(tmp_path / "out" / "dapi_files")


def test_unknown_engine_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown engine"):
        make_deepzoom_pyramid(
            str(_source_image(tmp_path)), str(tmp_path / "out"), "dapi", engine="imagemagick"
        )


# --- equivalence with vips dzsave --------------------------------------------

requires_pyvips = pytest.mark.skipif(_pyvips() is None, reason="libvips/pyvips not installed")


@requires_pyvips
@pytest.mark.parametrize(("width", "height"), [(500, 300), (1, 1), (129, 128), (640, 640)])
def test_level_and_tile_layout_matches_dzsave(tmp_path: Path, width: int, height: int) -> None:
    """Same levels, same tile grid, same filenames as the engine being replaced."""
    source = _source_image(tmp_path, width, height)
    suffix = ".webp[Q=100]"

    _pyvips().Image.new_from_file(str(source), access="sequential").dzsave(
        str(tmp_path / "ref"), tile_size=TILE, overlap=0, suffix=suffix
    )
    write_deepzoom_pyramid(source, tmp_path / "new", "img", tile_size=TILE, suffix=suffix)

    ref_root = tmp_path / "ref_files"
    new_root = tmp_path / "new" / "img_files"

    assert _levels(new_root) == _levels(ref_root)
    for level in _levels(ref_root):
        assert _tile_names(new_root, level) == _tile_names(ref_root, level), f"level {level}"


@requires_pyvips
def test_tile_pixel_dimensions_match_dzsave(tmp_path: Path) -> None:
    source = _source_image(tmp_path)
    suffix = ".webp[Q=100]"

    _pyvips().Image.new_from_file(str(source), access="sequential").dzsave(
        str(tmp_path / "ref"), tile_size=TILE, overlap=0, suffix=suffix
    )
    write_deepzoom_pyramid(source, tmp_path / "new", "img", tile_size=TILE, suffix=suffix)

    ref_root = tmp_path / "ref_files"
    new_root = tmp_path / "new" / "img_files"

    for level in _levels(ref_root):
        for name in sorted(_tile_names(ref_root, level)):
            ref_size = Image.open(ref_root / str(level) / name).size
            new_size = Image.open(new_root / str(level) / name).size
            assert new_size == ref_size, f"level {level} tile {name}"


@requires_pyvips
def test_dzi_matches_dzsave(tmp_path: Path) -> None:
    source = _source_image(tmp_path)
    _pyvips().Image.new_from_file(str(source), access="sequential").dzsave(
        str(tmp_path / "ref"), tile_size=TILE, overlap=0, suffix=".webp[Q=100]"
    )
    write_deepzoom_pyramid(source, tmp_path / "new", "img", tile_size=TILE, suffix=".webp[Q=100]")

    def described(path: Path) -> dict[str, str]:
        root = ET.parse(path).getroot()
        size = next(child for child in root if child.tag.endswith("Size"))
        return {
            "Format": root.get("Format"),
            "Overlap": root.get("Overlap"),
            "TileSize": root.get("TileSize"),
            "Width": size.get("Width"),
            "Height": size.get("Height"),
        }

    assert described(tmp_path / "new" / "img.dzi") == described(tmp_path / "ref.dzi")


@requires_pyvips
def test_both_engines_feed_the_parquet_packer_identically(tmp_path: Path) -> None:
    """The real downstream consumer agrees on grid shape and row-group offsets."""
    from celldega.pre.image_parquet import pack_image_tiles_to_parquet

    source = _source_image(tmp_path)
    suffix = ".webp[Q=100]"

    vips_dir = tmp_path / "vips"
    vips_dir.mkdir()
    _pyvips().Image.new_from_file(str(source), access="sequential").dzsave(
        str(vips_dir / "dapi"), tile_size=TILE, overlap=0, suffix=suffix
    )
    make_deepzoom_pyramid(str(source), str(tmp_path / "pil"), "dapi", tile_size=TILE, suffix=suffix)

    from_vips = pack_image_tiles_to_parquet(
        str(vips_dir), "dapi", str(tmp_path / "out_vips"), delete_source_tiles=False
    )
    from_pillow = pack_image_tiles_to_parquet(
        str(tmp_path / "pil"), "dapi", str(tmp_path / "out_pil"), delete_source_tiles=False
    )

    assert from_pillow["zoom_info"] == from_vips["zoom_info"]
    assert from_pillow["image_width"] == from_vips["image_width"]
    assert from_pillow["image_height"] == from_vips["image_height"]
