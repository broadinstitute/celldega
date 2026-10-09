"""Tests for Xenium LUT-max image scaling and channel guards."""

import json
from unittest.mock import patch

import numpy as np
import pytest
import tifffile

import celldega.pre as pre


OME_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06">
  <Image ID="Image:0">
    <Pixels ID="Pixels:0" DimensionOrder="XYCZT" Type="uint16" SizeX="8" SizeY="8" SizeZ="1" SizeC="2" SizeT="1">
      <Channel ID="Channel:0" Name="DAPI" SamplesPerPixel="1"/>
      <Channel ID="Channel:1" Name="ATP1A1/CD45/E-Cadherin" SamplesPerPixel="1"/>
      <TiffData/>
    </Pixels>
  </Image>
  <StructuredAnnotations>
    <MapAnnotation ID="Annotation:0">
      <Value>
        <M K="Long name">DAPI</M>
        <M K="Suggested LUT max">5000</M>
      </Value>
    </MapAnnotation>
    <MapAnnotation ID="Annotation:1">
      <Value>
        <M K="Long name">ATP1A1/CD45/E-Cadherin</M>
        <M K="Suggested LUT max">2500.5</M>
      </Value>
    </MapAnnotation>
  </StructuredAnnotations>
</OME>
"""


def test_parse_lut_max_by_channel_index():
    assert pre._parse_xenium_lut_max(OME_XML) == {0: 5000.0, 1: 2500.5}


@pytest.mark.parametrize("xml", [None, "", "<not xml", "<OME/>"])
def test_parse_lut_max_missing_or_invalid(xml):
    assert pre._parse_xenium_lut_max(xml) == {}


def _run_channel(tmp_path, img, lut_max, lut_max_scale=1.0):
    captured = {}

    def fake_pyramid(image_png, *_args, **_kwargs):
        captured["tif"] = tifffile.imread(tmp_path / "dapi_output_regular.tif")

    with (
        patch.object(pre, "_convert_to_png", return_value="x.png"),
        patch.object(pre, "make_deepzoom_pyramid", side_effect=fake_pyramid),
    ):
        pre._process_image_channel(
            tmp_path,
            {"name": "dapi", "index": 0},
            img,
            lut_max=lut_max,
            lut_max_scale=lut_max_scale,
        )
    return captured["tif"]


def test_process_channel_lut_scaling(tmp_path):
    img = np.array([[0, 1000, 5000, 60000]], dtype=np.uint16)
    out = _run_channel(tmp_path, img, lut_max=5000)
    assert out.dtype == np.uint8
    assert out.tolist() == [[0, 51, 255, 255]]


def test_process_channel_legacy_without_lut(tmp_path):
    img = np.array([[0, 10000, 30000]], dtype=np.uint16)
    out = _run_channel(tmp_path, img, lut_max=None)
    assert out.dtype == np.uint16
    assert out.tolist() == [[0, 10000, 30000]]


def _write_ome(path, data, description=None):
    tifffile.imwrite(path, data, photometric="minisblack", metadata={"axes": "CYX"})
    if description is not None:
        tifffile.tiffcomment(path, description)


def test_all_layers_rejected_for_single_channel_image(tmp_path):
    focus = tmp_path / "morphology_focus"
    focus.mkdir()
    _write_ome(focus / "morphology_focus_0000.ome.tif", np.ones((1, 8, 8), dtype=np.uint16))
    with pytest.raises(ValueError, match="needs 4 channels"):
        pre.create_image_tiles_xenium(str(tmp_path), str(tmp_path / "out"), image_tile_layer="all")


def test_all_layers_rejected_for_root_morphology(tmp_path):
    _write_ome(tmp_path / "morphology.ome.tif", np.ones((4, 8, 8), dtype=np.uint16))
    with pytest.raises(ValueError, match=r"morphology\.ome\.tif"):
        pre.create_image_tiles_xenium(str(tmp_path), str(tmp_path / "out"), image_tile_layer="all")


def test_process_channel_lut_max_scale_adds_headroom(tmp_path):
    img = np.array([[0, 2500, 5000]], dtype=np.uint16)
    out = _run_channel(tmp_path, img, lut_max=5000, lut_max_scale=2.0)
    assert out.tolist() == [[0, 63, 127]]


def test_invalid_lut_max_scale_rejected(tmp_path):
    with pytest.raises(ValueError, match="lut_max_scale"):
        pre.create_image_tiles_xenium(str(tmp_path), str(tmp_path), lut_max_scale=0)


def test_xenium_tiles_return_scaling_record(tmp_path):
    focus = tmp_path / "morphology_focus"
    focus.mkdir()
    path = focus / "morphology_focus_0000.ome.tif"
    tifffile.imwrite(path, np.ones((2, 8, 8), dtype=np.uint16), metadata={"axes": "CYX"})
    tifffile.tiffcomment(path, OME_XML)
    out = tmp_path / "out"
    out.mkdir()
    with (
        patch.object(pre, "_convert_to_png", return_value="x.png"),
        patch.object(pre, "make_deepzoom_pyramid"),
    ):
        record = pre.create_image_tiles_xenium(str(tmp_path), str(out), lut_max_scale=1.5)
    assert record["source_image"] == "morphology_focus_0000.ome.tif"
    assert record["channels"]["dapi"] == {
        "method": "lut_max",
        "lut_max": 5000.0,
        "lut_max_scale": 1.5,
    }
    assert not list(out.glob("*.json"))


def test_landscape_parameters_include_image_scaling(tmp_path):
    scaling = {"source_image": "a.ome.tif", "channels": {"dapi": {"method": "legacy"}}}
    (tmp_path / "pyramid_images" / "dapi_files" / "0").mkdir(parents=True)
    pre.save_landscape_parameters("Xenium", tmp_path, image_info=[], image_scaling=scaling)
    params = json.loads((tmp_path / "landscape_parameters.json").read_text())
    assert params["image_scaling"] == scaling
