"""Exercise real libvips tiles, affine coordinates and Parquet round trips."""

import importlib.util
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pyarrow.parquet as pq
import pytest
import tifffile


pyvips = pytest.importorskip("pyvips")
# Other preprocessing tests install lightweight celldega stubs. Load this package
# independently so these integration tests exercise the real tiler in either order.
root = Path(__file__).resolve().parents[3] / "src/celldega/pre"
spec = importlib.util.spec_from_file_location("_aligned_he_test_pre", root / "__init__.py")
pre = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pre
spec.loader.exec_module(pre)


def setup_dega(tmp_path, row_groups=False):
    pyramid = tmp_path / "pyramid_images"
    pyramid.mkdir()
    pyvips.Image.black(64, 48).dzsave(str(pyramid / "dapi"), tile_size=32, overlap=0)
    params = {
        "technology": "Xenium",
        "image_info": [{"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]}],
        "max_pyramid_zoom": 6,
        "tile_size": 250,
        "image_format": ".jpeg",
        "use_row_groups": row_groups,
        "row_group_files": {"images": {"dapi": {"directory": "pyramid_images/dapi"}}},
        "segmentation_approach": ["default"],
    }
    (tmp_path / "landscape_parameters.json").write_text(json.dumps(params))
    (tmp_path / "cell_metadata.parquet").write_bytes(b"preserve me")
    return params


def read_tile(tmp_path, x=0, y=0):
    return np.array(Image.open(tmp_path / f"pyramid_images/h_and_e_files/6/{x}_{y}.webp"))


@pytest.mark.parametrize("row_groups", [False, True])
def test_identity_rgb_and_manifest_preservation(tmp_path, row_groups):
    before = setup_dega(tmp_path, row_groups)
    image = np.full((48, 64, 3), [170, 60, 100], dtype=np.uint8)
    source = tmp_path / "he.tif"
    tifffile.imwrite(source, image, photometric="rgb")
    entry = pre.add_aligned_he(tmp_path, source)
    after = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert after["aligned_he"] == entry
    for key, value in before.items():
        if key != "row_group_files":
            assert after[key] == value
    assert after["row_group_files"]["images"]["dapi"] == before["row_group_files"]["images"]["dapi"]
    assert (tmp_path / "cell_metadata.parquet").read_bytes() == b"preserve me"
    if row_groups:
        info = after["row_group_files"]["images"]["h_and_e"]
        table = pq.read_table(tmp_path / info["directory"] / info["files"][0])
        rows = table.to_pylist()
        tile = next(row for row in rows if row["zoom"] == 6 and row["tile_x"] == row["tile_y"] == 0)
        pixels = np.array(Image.open(io.BytesIO(tile["image_data"])))
        assert not (tmp_path / "pyramid_images/h_and_e_files").exists()
    else:
        pixels = read_tile(tmp_path)
    np.testing.assert_allclose(pixels[8, 8], image[8, 8], atol=4)
    with pytest.raises(FileExistsError):
        pre.add_aligned_he(tmp_path, source)


def test_affine_rotation_translation_and_white_padding(tmp_path):
    setup_dega(tmp_path)
    image = np.full((16, 24, 3), [180, 30, 90], dtype=np.uint8)
    source = tmp_path / "he.tif"
    tifffile.imwrite(source, image, photometric="rgb")
    # Rotate (x,y) -> (28-y, 4+x); the red rectangle occupies x=13..28,y=4..27.
    matrix = np.array([[0, -1, 28], [1, 0, 4], [0, 0, 1]])
    csv = tmp_path / "alignment.csv"
    np.savetxt(csv, matrix, delimiter=",")
    pre.add_aligned_he(tmp_path, source, alignment=csv)
    pixels = read_tile(tmp_path)
    np.testing.assert_allclose(pixels[15, 20], [180, 30, 90], atol=5)
    np.testing.assert_allclose(pixels[5, 5], [255, 255, 255], atol=5)


@pytest.mark.parametrize(
    "matrix", [np.zeros((3, 3)), np.eye(2), [[1, 0, 0], [0, 1, 0], [1, 0, 1]], np.eye(3) * np.nan]
)
def test_invalid_alignment_does_not_publish(tmp_path, matrix):
    setup_dega(tmp_path)
    before = (tmp_path / "landscape_parameters.json").read_bytes()
    with pytest.raises(ValueError, match="affine"):
        pre.add_aligned_he(tmp_path, tmp_path / "missing.tif", alignment=matrix)
    assert (tmp_path / "landscape_parameters.json").read_bytes() == before
    assert not (tmp_path / "pyramid_images/h_and_e.dzi").exists()


def test_reject_wrong_grid_and_grayscale(tmp_path):
    setup_dega(tmp_path)
    source = tmp_path / "he.tif"
    tifffile.imwrite(source, np.zeros((10, 10, 3), dtype=np.uint8), photometric="rgb")
    with pytest.raises(ValueError, match="reference canvas"):
        pre.add_aligned_he(tmp_path, source)
    source = tmp_path / "grayscale.tif"
    tifffile.imwrite(source, np.zeros((48, 64), dtype=np.uint8))
    with pytest.raises(ValueError, match="RGB"):
        pre.add_aligned_he(tmp_path, source)


def test_planar_ome_rgb(tmp_path):
    setup_dega(tmp_path)
    source = tmp_path / "he.ome.tif"
    pixels = np.full((3, 48, 64), 0, dtype=np.uint8)
    pixels[:] = np.array([170, 60, 100])[:, None, None]
    tifffile.imwrite(source, pixels, photometric="minisblack", metadata={"axes": "CYX"})
    pre.add_aligned_he(tmp_path, source)
    np.testing.assert_allclose(read_tile(tmp_path)[8, 8], [170, 60, 100], atol=4)


def test_failed_tiling_leaves_existing_dataset_unchanged(tmp_path, monkeypatch):
    setup_dega(tmp_path)
    before = (tmp_path / "landscape_parameters.json").read_bytes()
    source = tmp_path / "he.tif"
    tifffile.imwrite(source, np.zeros((48, 64, 3), dtype=np.uint8), photometric="rgb")

    def fail(*args, **kwargs):
        raise RuntimeError("simulated tile write failure")

    monkeypatch.setattr(pyvips.Image, "dzsave", fail)
    with pytest.raises(RuntimeError, match="tile write failure"):
        pre.add_aligned_he(tmp_path, source)
    assert (tmp_path / "landscape_parameters.json").read_bytes() == before
    assert sorted(p.name for p in (tmp_path / "pyramid_images").iterdir()) == [
        "dapi.dzi",
        "dapi_files",
    ]
