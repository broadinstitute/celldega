"""Build a DegaFiles WebP pyramid from a SpatialData image element.

This lives here rather than in spatialdata-io on purpose. An 8-bit WebP pyramid is a
*viewer* artefact -- lossy, display-ranged, and ~100x smaller than the canonical uint16
OME-Zarr it is derived from (25 MB vs 2.9 GB for Xenium pancreas). SpatialData's job is to
hold the canonical image; deciding how to make it fast to look at is Celldega's.

Uses Pillow rather than pyvips, unlike the rest of :mod:`celldega.pre`, so no libvips
install is needed and the DeepZoom level numbering is produced directly. The numbering is
verified against ``vips dzsave`` in the tests.
"""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import shutil
from typing import Any

import numpy as np
from numpy.typing import NDArray
import pyarrow as pa
import pyarrow.parquet as pq


__all__ = ["DEFAULT_IMAGE_TILE_SIZE", "spatialdata_to_dega_images", "write_webp_pyramid"]

#: DeepZoom tile size used by Celldega's image pipeline.
DEFAULT_IMAGE_TILE_SIZE = 512

#: Image tiles are numerous and individually small, so more fit comfortably per file
#: than for transcripts.
DEFAULT_IMAGE_ROW_GROUPS_PER_FILE = 2000


def _require_pillow() -> Any:
    try:
        from PIL import Image, features
    except ImportError as exc:
        raise RuntimeError(
            "writing a WebP pyramid requires Pillow: pip install 'Pillow>=10'"
        ) from exc
    if not features.check("webp"):
        raise RuntimeError(
            "this Pillow build has no WebP support; reinstall Pillow with WebP enabled"
        )
    return Image


def _select_channel(array: Any, channel: int | str | None) -> Any:
    """Reduce one multiscale level to a 2D (y, x) plane."""
    if hasattr(array, "data_vars"):
        array = array[next(iter(array.data_vars))]
    dims = getattr(array, "dims", None)
    if dims and "c" in dims:
        if channel is None:
            array = array.isel(c=0)
        elif isinstance(channel, str):
            array = array.sel(c=channel)
        else:
            array = array.isel(c=channel)
    return array


def _as_2d(image: Any, channel: int | str | None) -> tuple[Any, Any]:
    """Return ``(full_resolution_plane, coarse_plane)`` for a SpatialData image element.

    The coarse plane is the smallest available multiscale level, used only to choose the
    display intensity window cheaply. For a single-scale image both are the same array.
    """
    if hasattr(image, "children") and len(image.children):
        levels = list(image.children)
        return (
            _select_channel(image[levels[0]], channel),
            _select_channel(image[levels[-1]], channel),
        )
    plane = _select_channel(image, channel)
    return plane, plane


def _display_window(
    sample_source: Any, display_min: float | None, display_max: float | None
) -> tuple[float, float]:
    """Choose the intensity window.

    The default is the *full dtype range* for integer images, which is a linear mapping
    and no stretch at all. That deliberately matches Celldega's own image pipeline, which
    saves raw values and leaves brightening to the viewer's intensity slider. A percentile
    stretch here would be applied on top of that slider and blow out the mid-tones -- on
    Xenium DAPI it took a tile from mean 1.3 to mean 37.4 with 1.2% of pixels saturated.

    Pass ``display_min``/``display_max`` to window explicitly; both are recorded in the
    manifest so the choice is reproducible and invalidatable.
    """
    if display_min is not None and display_max is not None:
        lo, hi = float(display_min), float(display_max)
    else:
        sample = np.asarray(sample_source)
        if sample.dtype.kind in "ui":
            info = np.iinfo(sample.dtype)
            default_lo, default_hi = float(info.min), float(info.max)
        else:
            finite = sample[np.isfinite(sample)]
            default_lo = float(finite.min()) if finite.size else 0.0
            default_hi = float(finite.max()) if finite.size else 1.0
        lo = float(display_min) if display_min is not None else default_lo
        hi = float(display_max) if display_max is not None else default_hi
    return (lo, hi if hi > lo else lo + 1.0)


def _to_uint8(
    plane: NDArray[Any], lo: float, hi: float, gamma: float, block_rows: int = 2048
) -> NDArray[np.uint8]:
    """Window a plane to 8-bit in row blocks, avoiding a float copy of the whole image."""
    height = plane.shape[0]
    out = np.empty(plane.shape, dtype=np.uint8)
    inv_gamma = 1.0 / gamma
    for start in range(0, height, block_rows):
        stop = min(start + block_rows, height)
        block = np.asarray(plane[start:stop], dtype=np.float32)
        block -= lo
        block /= hi - lo
        np.clip(block, 0.0, 1.0, out=block)
        if gamma != 1.0:
            block **= inv_gamma
        block *= 255.0
        block += 0.5
        out[start:stop] = block.astype(np.uint8)
    return out


def _downsample_half(a: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Box-filter by 2 in both axes, padding odd edges by replication."""
    h, w = a.shape
    if h % 2:
        a = np.vstack([a, a[-1:]])
    if w % 2:
        a = np.hstack([a, a[:, -1:]])
    return a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2).mean(axis=(1, 3)).astype(np.uint8)


def write_webp_pyramid(
    image: Any,
    output_dir: str | Path,
    *,
    channel: int | str | None = None,
    tile_size: int = DEFAULT_IMAGE_TILE_SIZE,
    display_min: float | None = None,
    display_max: float | None = None,
    gamma: float = 1.0,
    quality: int = 85,
    lossless: bool = False,
    max_row_groups_per_file: int = DEFAULT_IMAGE_ROW_GROUPS_PER_FILE,
    source_element: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a DeepZoom-numbered WebP pyramid as Parquet row groups.

    Parameters
    ----------
    image
        A SpatialData image element (``DataTree`` or ``DataArray``).
    output_dir
        Directory to write chunk files into. Written atomically.
    channel
        Channel index or name to render. Defaults to the first channel.
    tile_size
        Tile edge length in pixels.
    display_min, display_max
        Intensity window. Defaults to the 1st and 99.9th percentiles of the full-resolution
        plane, which is a display choice and is recorded in the returned metadata.
    gamma
        Display gamma applied after windowing.
    quality
        WebP quality when ``lossless`` is False.
    lossless
        Whether to encode losslessly.
    max_row_groups_per_file
        Tiles per chunk file.
    source_element
        Name of the canonical image element, recorded for invalidation.
    overwrite
        Replace ``output_dir`` if it exists.

    Returns
    -------
    The manifest fragment describing the written pyramid.
    """
    Image = _require_pillow()

    output_dir = Path(output_dir)
    if output_dir.exists() and not overwrite:
        raise FileExistsError(f"{output_dir} exists; pass overwrite=True to replace it")

    plane, coarse = _as_2d(image, channel)
    if plane.ndim != 2:
        raise ValueError(f"expected a 2D plane after channel selection, got shape {plane.shape}")
    source_dtype = str(plane.dtype)

    applied_min, applied_max = _display_window(coarse, display_min, display_max)
    full = _to_uint8(plane, applied_min, applied_max, gamma)
    height, width = full.shape

    # DeepZoom numbering: level max_zoom is full resolution and each level below halves
    # both dimensions, down to level 0 (a single pixel). Every level is generated so the
    # numbering matches `vips dzsave` output exactly.
    max_zoom = max(1, math.ceil(math.log2(max(width, height))))
    levels: dict[int, NDArray[np.uint8]] = {max_zoom: full}
    current = full
    for zoom in range(max_zoom - 1, -1, -1):
        current = _downsample_half(current)
        levels[zoom] = current

    schema = pa.schema(
        [
            pa.field("zoom", pa.int32()),
            pa.field("tile_x", pa.int32()),
            pa.field("tile_y", pa.int32()),
            pa.field("image_data", pa.binary()),
        ]
    )

    # Enumerate tiles in the reader's order: zoom ascending, then column-major within zoom.
    ordered: list[tuple[int, int, int]] = []
    zoom_info: dict[str, dict[str, int]] = {}
    for zoom in sorted(levels):
        lh, lw = levels[zoom].shape
        nx = max(1, math.ceil(lw / tile_size))
        ny = max(1, math.ceil(lh / tile_size))
        zoom_info[str(zoom)] = {
            "num_tiles_x": nx,
            "num_tiles_y": ny,
            "num_tiles": nx * ny,
            "row_group_offset": len(ordered),
        }
        ordered.extend((zoom, tx, ty) for tx in range(nx) for ty in range(ny))

    n_files = max(1, -(-len(ordered) // max_row_groups_per_file))
    width_digits = len(str(n_files - 1)) if n_files > 1 else 1
    filenames = [f"chunk_{i:0{width_digits}d}.parquet" for i in range(n_files)]

    schema = schema.with_metadata(
        {
            b"zoom_info": json.dumps(zoom_info).encode(),
            b"storage_mode": b"row_groups_image_chunked",
            b"max_row_groups_per_file": str(max_row_groups_per_file).encode(),
            b"tile_size": str(tile_size).encode(),
            b"profile": b"grid_files_v1",
        }
    )

    staging = output_dir.with_name(output_dir.name + ".tmp")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    encode_kwargs: dict[str, Any] = {"format": "WEBP", "lossless": lossless}
    if not lossless:
        encode_kwargs["quality"] = quality

    try:
        writer: pq.ParquetWriter | None = None
        current_file = -1
        for index, (zoom, tx, ty) in enumerate(ordered):
            file_index = index // max_row_groups_per_file
            if file_index != current_file:
                if writer is not None:
                    writer.close()
                writer = pq.ParquetWriter(
                    staging / filenames[file_index], schema, write_statistics=False
                )
                current_file = file_index

            level = levels[zoom]
            crop = level[
                ty * tile_size : (ty + 1) * tile_size, tx * tile_size : (tx + 1) * tile_size
            ]
            buf = io.BytesIO()
            Image.fromarray(crop, mode="L").save(buf, **encode_kwargs)

            assert writer is not None
            writer.write_table(
                pa.table(
                    {
                        "zoom": pa.array([zoom], pa.int32()),
                        "tile_x": pa.array([tx], pa.int32()),
                        "tile_y": pa.array([ty], pa.int32()),
                        "image_data": pa.array([buf.getvalue()], pa.binary()),
                    },
                    schema=schema,
                )
            )
        if writer is not None:
            writer.close()
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    if output_dir.exists():
        shutil.rmtree(output_dir)
    staging.rename(output_dir)

    return {
        "directory": output_dir.name,
        "files": filenames,
        "max_row_groups_per_file": max_row_groups_per_file,
        "total_row_groups": len(ordered),
        "zoom_info": zoom_info,
        "min_zoom": min(levels),
        "max_zoom": max_zoom,
        "tile_size": tile_size,
        "image_format": ".webp",
        # Recorded so the display cache can be invalidated when any of it changes.
        "source_element": source_element,
        "source_width": int(width),
        "source_height": int(height),
        "source_dtype": source_dtype,
        "channel": channel,
        "display_min": applied_min,
        "display_max": applied_max,
        "gamma": gamma,
        "downsampling": "box-2x2-mean",
        "webp_lossless": lossless,
        "webp_quality": None if lossless else quality,
    }


# Channel colours used when the caller does not supply any. Ordered so the first channels
# of a typical Xenium morphology stack (DAPI, membrane, RNA) come out blue/green/red.
_DEFAULT_CHANNEL_COLORS = [
    (0, 0, 255),
    (0, 255, 0),
    (255, 0, 0),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
]


def _channels_of(element: Any) -> list[Any]:
    """List an image element's channel names, falling back to indices."""
    level = element[next(iter(element.children))] if hasattr(element, "children") else element
    array = level[next(iter(level.data_vars))] if hasattr(level, "data_vars") else level
    coords = getattr(array, "coords", {})
    if "c" in coords:
        return [str(c) for c in coords["c"].values]
    size = dict(zip(array.dims, array.shape, strict=True)).get("c", 1)
    return list(range(size))


def _channel_label(channel: Any, index: int) -> str:
    """A filesystem- and URL-safe label for a channel.

    Xenium channel names contain slashes ('ATP1A1/CD45/E-Cadherin'), which would otherwise
    create nested directories and break relative paths in the manifest.
    """
    if isinstance(channel, int):
        return f"channel_{channel}"
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(channel)).strip("_").lower()
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe or f"channel_{index}"


def spatialdata_to_dega_images(
    store: str | Path,
    output_dir: str | Path,
    *,
    image_element: str,
    channels: list[Any] | None = None,
    colors: dict[str, tuple[int, int, int]] | None = None,
    tile_size: int = DEFAULT_IMAGE_TILE_SIZE,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a WebP pyramid per channel of a SpatialData image element.

    This is the 8-bit path for a store that already exists. The canonical OME-Zarr in the
    store stays untouched and remains the source of truth; this produces the small, fast
    representation a browser wants.

    Parameters
    ----------
    store
        Path to the ``.zarr`` store.
    output_dir
        Directory to write ``<label>/`` pyramids into, e.g. a DegaFiles ``pyramid_images``.
    image_element
        Name of the image element under ``images/``.
    channels
        Channels to write; defaults to every channel of the element.
    colors
        Optional per-label RGB, keyed by the sanitised channel label.
    tile_size
        Tile edge in pixels. 512 keeps tiles small enough to stream individually.

    Returns
    -------
    dict
        ``{"images": {...}, "image_info": [...], "image_dimensions": {...},
        "max_pyramid_zoom": int}`` -- the fragments a landscape manifest needs.
    """
    import spatialdata as sd

    sdata = sd.read_zarr(str(store))
    if image_element not in sdata.images:
        raise ValueError(f"image element {image_element!r} not found; have {list(sdata.images)}")

    element = sdata.images[image_element]
    selected = channels if channels is not None else _channels_of(element)

    output_dir = Path(output_dir)
    images: dict[str, Any] = {}
    image_info: list[dict[str, Any]] = []
    image_dimensions: dict[str, Any] | None = None
    max_pyramid_zoom: int | None = None

    for index, channel in enumerate(selected):
        label = _channel_label(channel, index)
        pyramid = write_webp_pyramid(
            element,
            output_dir / label,
            channel=channel,
            tile_size=tile_size,
            source_element=image_element,
            overwrite=overwrite,
        )
        pyramid["directory"] = label
        images[label] = pyramid

        colour = (colors or {}).get(label) or _DEFAULT_CHANNEL_COLORS[
            index % len(_DEFAULT_CHANNEL_COLORS)
        ]
        image_info.append({"name": label, "button_name": str(channel), "color": list(colour)})

        # Every channel of one element shares its dimensions and pyramid depth.
        image_dimensions = {
            "width": pyramid["source_width"],
            "height": pyramid["source_height"],
            "tile_size": tile_size,
        }
        max_pyramid_zoom = pyramid["max_zoom"]

    return {
        "images": images,
        "image_info": image_info,
        "image_dimensions": image_dimensions,
        "max_pyramid_zoom": max_pyramid_zoom,
    }
