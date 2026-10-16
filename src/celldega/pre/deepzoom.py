"""DeepZoom pyramid generation with Pillow, replacing ``pyvips.Image.dzsave``.

Pillow is a pure-wheel dependency; pyvips needs libvips installed on the host, which is
why it sits behind the optional ``celldega[pre]`` extra and why
``import celldega.pre`` has historically been fragile on machines without it.

The output is layout-compatible with ``vips dzsave`` -- same level numbering, same tile
grid, same ``{col}_{row}.{ext}`` filenames, same ``.dzi`` -- so
:func:`celldega.pre.image_parquet.pack_image_tiles_to_parquet` and the JavaScript viewer
consume it unchanged. ``tests/unit/test_pre/test_deepzoom.py`` asserts that equivalence
against real ``dzsave`` output whenever pyvips is importable.

Tiles are *not* expected to be pixel-identical to vips': the two use different
downsampling kernels (vips defaults to a Lanczos-family reduction, this uses Pillow's
``LANCZOS`` over a halving chain). The pyramid is a display artefact, so the difference is
not meaningful -- but it does mean a byte-comparison against previously generated tiles
will differ.

Memory: pyvips streams with ``access="sequential"``; Pillow decodes the whole image. For
the multi-gigabyte morphology images some Xenium runs produce, pass ``engine="pyvips"`` to
:func:`celldega.pre.image_tiles.make_deepzoom_pyramid` to keep the streaming path.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any


#: DeepZoom tile edge length, matching the pipeline's historical pyvips default.
DEFAULT_TILE_SIZE = 512

#: ``.dzi`` descriptor. vips emits this exact shape; the viewer parses Width/Height.
_DZI_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
  Format="{fmt}"
  Overlap="{overlap}"
  TileSize="{tile_size}"
  >
  <Size
    Height="{height}"
    Width="{width}"
  />
</Image>
"""

#: vips encodes save options in the suffix, e.g. ``.webp[Q=100]``.
_SUFFIX_RE = re.compile(r"^(?P<ext>\.[A-Za-z0-9]+)(?:\[(?P<opts>.*)\])?$")


def _require_pillow() -> Any:
    """Import Pillow, or explain how to get it.

    Deliberately a runtime check rather than a module-level ``pyvips = None`` sentinel:
    the latter defers the failure to an ``AttributeError: 'NoneType' object has no
    attribute ...`` at the call site, which tells the caller nothing.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a hard dependency
        raise RuntimeError(
            "building an image pyramid requires Pillow: pip install 'Pillow>=10'"
        ) from exc
    return Image


def parse_vips_suffix(suffix: str) -> tuple[str, dict[str, str]]:
    """Split a vips-style suffix into an extension and its options.

    ``".webp[Q=100]"`` -> ``(".webp", {"Q": "100"})``. Callers in this package pass the
    vips spelling, so it is understood rather than rejected.
    """
    match = _SUFFIX_RE.match(suffix.strip())
    if not match:
        raise ValueError(f"unrecognised tile suffix: {suffix!r}")
    ext = match.group("ext").lower()
    opts: dict[str, str] = {}
    for part in (match.group("opts") or "").split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            opts[key.strip()] = value.strip()
    return ext, opts


def _save_kwargs(ext: str, opts: dict[str, str]) -> dict[str, Any]:
    """Translate vips save options to Pillow's."""
    quality = opts.get("Q") or opts.get("quality")
    kwargs: dict[str, Any] = {}
    if ext == ".webp":
        kwargs["format"] = "WEBP"
        kwargs["quality"] = int(quality) if quality else 100
        # vips treats Q=100 on webp as lossless; match that so round-tripping a
        # ".webp[Q=100]" suffix does not silently start losing data.
        if kwargs["quality"] >= 100:
            kwargs["lossless"] = True
    elif ext in {".jpeg", ".jpg"}:
        kwargs["format"] = "JPEG"
        kwargs["quality"] = int(quality) if quality else 75
    elif ext == ".png":
        kwargs["format"] = "PNG"
    else:
        raise ValueError(f"unsupported tile format: {ext!r}")
    return kwargs


def deepzoom_max_level(width: int, height: int) -> int:
    """Number of the full-resolution DeepZoom level.

    Level ``max`` is full resolution and each level below halves both dimensions, down to
    level 0 at a single pixel. Matches ``vips dzsave``.

    No lower bound of 1: a 1x1 source has ``max_level == 0``, and dzsave emits exactly one
    level for it. Clamping to 1 here produces a spurious extra level, which the
    differential test against dzsave catches.
    """
    return math.ceil(math.log2(max(width, height)))


def deepzoom_level_size(width: int, height: int, level: int, max_level: int) -> tuple[int, int]:
    """Pixel dimensions of one DeepZoom level."""
    scale = 2 ** (max_level - level)
    return max(1, math.ceil(width / scale)), max(1, math.ceil(height / scale))


def write_deepzoom_pyramid(
    image_path: str | Path,
    output_path: str | Path,
    pyramid_name: str,
    *,
    tile_size: int = DEFAULT_TILE_SIZE,
    overlap: int = 0,
    suffix: str = ".jpeg",
) -> Path:
    """Write a DeepZoom pyramid with Pillow.

    Produces ``<output_path>/<pyramid_name>.dzi`` and
    ``<output_path>/<pyramid_name>_files/<level>/<col>_<row><ext>``.

    Parameters
    ----------
    image_path
        Source image, in any format Pillow can open.
    output_path
        Directory to write the pyramid into. Created if absent.
    pyramid_name
        Base name for the ``.dzi`` and the ``_files`` directory.
    tile_size
        Tile edge in pixels.
    overlap
        DeepZoom tile overlap. Only 0 is supported; the pipeline has always passed 0 and
        the parquet packer assumes non-overlapping tiles.
    suffix
        Tile format, in vips spelling -- ``".webp[Q=100]"``, ``".jpeg"``, ``".png"``.

    Returns
    -------
    Path
        The ``.dzi`` descriptor that was written.
    """
    if overlap != 0:
        raise ValueError(
            f"overlap={overlap} is not supported; the DegaFiles tile packer assumes "
            "non-overlapping tiles"
        )

    Image = _require_pillow()
    ext, opts = parse_vips_suffix(suffix)
    save_kwargs = _save_kwargs(ext, opts)

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    tiles_root = output_dir / f"{pyramid_name}_files"

    # Pillow refuses very large images by default as a decompression-bomb guard. Morphology
    # images legitimately exceed it, and the path is a local file the caller chose.
    Image.MAX_IMAGE_PIXELS = None

    with Image.open(image_path) as opened:
        full = opened.convert("L" if opened.mode in {"L", "I;16", "I"} else "RGB")
        width, height = full.size
        max_level = deepzoom_max_level(width, height)

        current = full
        for level in range(max_level, -1, -1):
            level_w, level_h = deepzoom_level_size(width, height, level, max_level)
            if current.size != (level_w, level_h):
                current = current.resize((level_w, level_h), Image.LANCZOS)

            level_dir = tiles_root / str(level)
            level_dir.mkdir(parents=True, exist_ok=True)

            n_cols = max(1, math.ceil(level_w / tile_size))
            n_rows = max(1, math.ceil(level_h / tile_size))
            for col in range(n_cols):
                for row in range(n_rows):
                    # Edge tiles are cropped, not padded -- vips does the same, and the
                    # viewer relies on the last tile carrying the true remainder.
                    box = (
                        col * tile_size,
                        row * tile_size,
                        min((col + 1) * tile_size, level_w),
                        min((row + 1) * tile_size, level_h),
                    )
                    current.crop(box).save(level_dir / f"{col}_{row}{ext}", **save_kwargs)

    dzi_path = output_dir / f"{pyramid_name}.dzi"
    dzi_path.write_text(
        _DZI_TEMPLATE.format(
            fmt=ext.lstrip("."),
            overlap=overlap,
            tile_size=tile_size,
            height=height,
            width=width,
        )
    )
    return dzi_path
