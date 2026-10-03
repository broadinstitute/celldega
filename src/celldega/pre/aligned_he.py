"""Add an externally aligned RGB H&E image to existing DegaFiles."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import numpy as np
import tifffile


def _reference_dimensions(path, params):
    if not params.get("image_info"):
        raise ValueError("DegaFiles must contain a reference image before adding H&E.")
    name = params["image_info"][0]["name"]
    dzi = path / "pyramid_images" / f"{name}.dzi"
    if dzi.exists():
        root = ET.parse(dzi).getroot()
        size = next(child for child in root if child.tag.endswith("Size"))
        if int(root.attrib.get("Overlap", 0)) != 0:
            raise ValueError("The reference image must use tiles without overlap.")
        return int(size.attrib["Width"]), int(size.attrib["Height"]), int(root.attrib["TileSize"])
    dims = params["image_dimensions"]
    return int(dims["width"]), int(dims["height"]), int(dims["tile_size"])


def _load_rgb(image_path, pyvips):
    image = pyvips.Image.new_from_file(str(image_path), access="random")
    # OME-TIFF can store R, G and B as separate grayscale pages.
    if image.bands == 1 and image_path.suffix.lower() in {".tif", ".tiff"}:
        with tifffile.TiffFile(image_path) as tif:
            series = tif.series[0]
            if series.axes == "CYX" and series.shape[0] == 3:
                image = image.bandjoin(
                    [pyvips.Image.new_from_file(str(image_path), page=i) for i in (1, 2)]
                )
    if image.bands not in (3, 4) or image.format != "uchar":
        raise ValueError("H&E must be an 8-bit RGB or RGBA image.")
    image = image.copy(interpretation="srgb")
    return image.flatten(background=[255, 255, 255]) if image.bands == 4 else image


def add_aligned_he(path_dega_files, image_path, *, alignment=None):
    """Tile H&E in the existing image coordinate system and register it in the manifest.

    Run after ``pre.main()`` or on an existing DegaFiles directory. Without
    ``alignment``, the RGB image must already have exactly the reference image's
    width, height, origin and pixel scale. No alignment is estimated here.

    ``alignment`` may be a 3x3 array or a headerless CSV path. It maps H&E pixel
    coordinates to the existing DegaFiles image pixels: ``[x, y, 1]`` (column
    vectors). Xenium Explorer imagealignment.csv files use this convention.
    Translation, rotation, reflection, shear and scale are supported. The image
    is resampled onto the reference canvas; outside pixels are white.

    Existing fluorescence, cells and transcripts are preserved. The new pyramid
    uses WebP and the reference tile size, with Parquet packing when DegaFiles
    use row groups. Requires the optional ``celldega[pre]`` dependency and libvips.
    An existing H&E pyramid is never overwritten. Returns the H&E manifest entry.
    """
    from . import pack_image_tiles_to_parquet, pyvips

    if pyvips is None:
        raise ImportError("Install celldega[pre] and libvips to add an H&E image.")
    path = Path(path_dega_files)
    image_path = Path(image_path)
    manifest = path / "landscape_parameters.json"
    params = json.loads(manifest.read_text())
    pyramid = path / "pyramid_images"
    name = "h_and_e"
    if params.get("aligned_he") or any(
        (pyramid / item).exists() for item in (name, f"{name}.dzi", f"{name}_files")
    ):
        raise FileExistsError("DegaFiles already contain an H&E image.")
    width, height, tile_size = _reference_dimensions(path, params)
    transform = np.eye(3)
    if alignment is not None:
        transform = (
            np.loadtxt(alignment, delimiter=",")
            if isinstance(alignment, str | Path)
            else np.asarray(alignment, dtype=float)
        )
        if (
            transform.shape != (3, 3)
            or not np.isfinite(transform).all()
            or not np.allclose(transform[2], [0, 0, 1])
            or abs(np.linalg.det(transform[:2, :2])) < 1e-12
        ):
            raise ValueError("alignment must be a finite, invertible 3x3 affine matrix.")

    image = _load_rgb(image_path, pyvips)
    if alignment is None and (image.width, image.height) != (width, height):
        raise ValueError(
            f"Aligned H&E must match the reference canvas ({width} x {height}); "
            "supply an alignment matrix for a different pixel grid."
        )
    if alignment is not None:
        image = image.affine(
            transform[:2, :2].ravel().tolist(),
            odx=float(transform[0, 2]),
            ody=float(transform[1, 2]),
            oarea=[0, 0, width, height],
            interpolate=pyvips.Interpolate.new("bilinear"),
            background=[255, 255, 255],
        )

    entry = {
        "name": name,
        "button_name": "H&E",
        "image_format": ".webp",
        "alignment": transform.tolist(),
    }
    pyramid.mkdir(exist_ok=True)
    # Publish metadata only after all tiles have been successfully generated.
    with TemporaryDirectory(prefix=".aligned-he-", dir=pyramid) as tmp:
        staging = Path(tmp)
        image.dzsave(str(staging / name), tile_size=tile_size, overlap=0, suffix=".webp[Q=95]")
        if params.get("use_row_groups"):
            info = pack_image_tiles_to_parquet(staging, name, staging / name)
            info["directory"] = f"pyramid_images/{name}"
            params.setdefault("row_group_files", {}).setdefault("images", {})[name] = info
        for item in staging.iterdir():
            item.rename(pyramid / item.name)
        params["aligned_he"] = entry
        staged_manifest = staging / "landscape_parameters.json"
        staged_manifest.write_text(json.dumps(params, indent=2) + "\n")
        staged_manifest.replace(manifest)
    return entry
