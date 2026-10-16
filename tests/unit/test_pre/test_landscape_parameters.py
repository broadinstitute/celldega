"""``landscape_parameters.json`` is the contract between Python pre-processing and the
JavaScript viewer, so ``save_landscape_parameters`` emits one of exactly three shapes:
an ``h&e`` manifest with placeholder ``"N.A."`` fields, a per-technology manifest that
grows ``row_group_files`` / ``image_dimensions`` / ``tile_grid`` only in row-group mode,
and — for ``technology="custom"`` — the manifest already on disk with one more
segmentation approach appended. ``get_max_zoom_level`` reports the highest-numbered
pyramid directory, compared as an integer."""

import json
from pathlib import Path

import pytest

from celldega.pre.image_info import get_image_info
from celldega.pre.landscape_parameters import get_max_zoom_level, save_landscape_parameters


def _make_pyramid(root: Path, image_name: str, zoom_levels: list[int]) -> Path:
    """Create ``root/pyramid_images/<image_name>/<level>`` directories."""
    pyramid = root / "pyramid_images" / image_name
    for level in zoom_levels:
        (pyramid / str(level)).mkdir(parents=True)
    return pyramid


def _make_chunked_channel(root: Path, channel: str, chunk_indices: list[int]) -> Path:
    """Create ``root/pyramid_images/<channel>/chunk_<i>.parquet`` files."""
    channel_dir = root / "pyramid_images" / channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    for index in chunk_indices:
        (channel_dir / f"chunk_{index}.parquet").write_bytes(b"")
    return channel_dir


def _tile_grid_info() -> dict:
    return {
        "tile_size": 250,
        "num_tiles_x": 4,
        "num_tiles_y": 3,
        "x_min": 0.0,
        "x_max": 1000.0,
        "y_min": -5.0,
        "y_max": 750.0,
    }


def _image_tile_info() -> dict:
    return {
        "dapi": {
            "zoom_levels": [0, 1, 2, 3],
            "zoom_info": {"0": {"num_tiles": 1}},
            "max_row_groups_per_file": 1500,
            "total_row_groups": 37,
            "image_width": 2048,
            "image_height": 1024,
            "tile_size": 256,
        }
    }


def _read_manifest(root: Path) -> dict:
    return json.loads((root / "landscape_parameters.json").read_text())


# --- get_max_zoom_level -----------------------------------------------------


def test_get_max_zoom_level_returns_highest_level(tmp_path: Path) -> None:
    pyramid = _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3])

    assert get_max_zoom_level(pyramid) == 3


def test_get_max_zoom_level_compares_numerically_not_lexicographically(tmp_path: Path) -> None:
    # A string sort over {"2", "9", "10"} would answer "9".
    pyramid = _make_pyramid(tmp_path, "dapi_files", [2, 9, 10])

    assert get_max_zoom_level(pyramid) == 10


def test_get_max_zoom_level_ignores_files_and_non_numeric_directories(tmp_path: Path) -> None:
    pyramid = _make_pyramid(tmp_path, "dapi_files", [0, 1])
    (pyramid / "99").write_text("a file named like a zoom level")
    (pyramid / "tmp_7").mkdir()

    assert get_max_zoom_level(pyramid) == 1


def test_get_max_zoom_level_returns_none_when_no_numeric_directories(tmp_path: Path) -> None:
    pyramid = tmp_path / "pyramid_images" / "dapi_files"
    (pyramid / "scratch").mkdir(parents=True)

    assert get_max_zoom_level(pyramid) is None


def test_get_max_zoom_level_accepts_a_string_path(tmp_path: Path) -> None:
    pyramid = _make_pyramid(tmp_path, "dapi_files", [0, 5])

    assert get_max_zoom_level(str(pyramid)) == 5


# --- branch 1: technology == "h&e" ------------------------------------------


def test_h_and_e_manifest_shape(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "h_and_e_files", [0, 1, 2])
    # A decoy pyramid under the *default* image_name: the h&e branch must not read it.
    _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3, 4, 5, 6])

    save_landscape_parameters("h&e", str(tmp_path))
    manifest = _read_manifest(tmp_path)

    assert set(manifest) == {
        "technology",
        "segmentation_approach",
        "max_pyramid_zoom",
        "tile_size",
        "image_info",
        "image_format",
        "use_int_index",
    }
    assert manifest["technology"] == "h&e"
    assert manifest["segmentation_approach"] == ["N.A."]
    assert manifest["max_pyramid_zoom"] == 2
    assert manifest["tile_size"] == "N.A."
    assert manifest["use_int_index"] == "N.A."
    assert manifest["image_format"] == ".webp"
    assert manifest["image_info"] == [{"name": "h&e", "button_name": "H&E", "color": [0, 0, 255]}]


def test_h_and_e_overrides_caller_supplied_image_name_and_image_info(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "h_and_e_files", [0, 1])

    save_landscape_parameters(
        "h&e",
        str(tmp_path),
        image_name="caller_choice_files",
        image_info=[{"name": "caller", "button_name": "CALLER", "color": [1, 2, 3]}],
        image_format=".png",
        tile_size=512,
        use_int_index=False,
        segmentation_approach="cellpose",
    )
    manifest = _read_manifest(tmp_path)

    # image_name and image_info are both replaced; the pyramid read follows the override
    # (no "caller_choice_files" directory exists, yet the call succeeds with zoom 1).
    assert manifest["max_pyramid_zoom"] == 1
    assert manifest["image_info"][0]["name"] == "h&e"
    assert manifest["segmentation_approach"] == ["N.A."]
    assert manifest["tile_size"] == "N.A."
    # image_format is the one caller-supplied field this branch honours.
    assert manifest["image_format"] == ".png"


def test_h_and_e_image_info_color_contradicts_get_image_info(tmp_path: Path) -> None:
    """BUG (pinned, not fixed): the h&e branch hardcodes blue for the h&e layer while
    ``get_image_info(..., "h&e")`` returns red for the same layer. Behaviour-preserving
    refactor, so this asserts the disagreement rather than a fix."""
    _make_pyramid(tmp_path, "h_and_e_files", [0])

    save_landscape_parameters("h&e", str(tmp_path))
    manifest = _read_manifest(tmp_path)

    assert manifest["image_info"][0]["color"] == [0, 0, 255]
    assert get_image_info("Xenium", "h&e")[0]["color"] == [255, 0, 0]
    assert manifest["image_info"][0]["color"] != get_image_info("Xenium", "h&e")[0]["color"]


# --- branch 2: technology != "custom" ---------------------------------------


def test_technology_manifest_shape_without_row_groups(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3])
    image_info = get_image_info("Xenium", "dapi")

    save_landscape_parameters(
        "Xenium",
        str(tmp_path),
        tile_size=250,
        image_info=image_info,
        segmentation_approach="cellpose",
    )
    manifest = _read_manifest(tmp_path)

    assert set(manifest) == {
        "technology",
        "segmentation_approach",
        "max_pyramid_zoom",
        "tile_size",
        "image_info",
        "image_format",
        "use_int_index",
        "use_row_groups",
    }
    assert manifest["technology"] == "Xenium"
    assert manifest["segmentation_approach"] == ["cellpose"]
    assert manifest["max_pyramid_zoom"] == 3
    assert manifest["tile_size"] == 250
    assert manifest["image_info"] == image_info
    assert manifest["image_format"] == ".webp"
    assert manifest["use_int_index"] is True
    assert manifest["use_row_groups"] is False


def test_technology_manifest_defaults_image_info_to_empty_mapping(tmp_path: Path) -> None:
    # Not a list: the default is an empty dict, which round-trips through JSON as {}.
    _make_pyramid(tmp_path, "dapi_files", [0])

    save_landscape_parameters("MERSCOPE", str(tmp_path))

    assert _read_manifest(tmp_path)["image_info"] == {}


def test_row_group_mode_emits_grid_dimensions_and_chunk_manifests(tmp_path: Path) -> None:
    # Numbered pyramid directories that would answer 6; image_tile_info must win instead.
    _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3, 4, 5, 6])
    _make_chunked_channel(tmp_path, "dapi", [0, 2, 9, 10])

    save_landscape_parameters(
        "Xenium",
        str(tmp_path),
        tile_size=1000,
        use_row_groups=True,
        tile_grid_info=_tile_grid_info(),
        image_tile_info=_image_tile_info(),
        trx_chunk_info={
            "files": ["transcripts_0.parquet"],
            "max_row_groups_per_file": 5000,
            "total_row_groups": 12,
        },
        cell_chunk_info={
            "files": ["cell_segmentation_0.parquet"],
            "max_row_groups_per_file": 4000,
            "total_row_groups": 9,
        },
        cbg_chunk_info={
            "directory": "cbg_chunks",
            "files": ["cbg_0.parquet"],
            "max_row_groups_per_file": 1000,
            "total_row_groups": 4,
            "gene_to_row_group": {"GeneA": 0},
        },
    )
    manifest = _read_manifest(tmp_path)

    assert set(manifest) == {
        "technology",
        "segmentation_approach",
        "max_pyramid_zoom",
        "tile_size",
        "image_info",
        "image_format",
        "use_int_index",
        "use_row_groups",
        "row_group_files",
        "image_dimensions",
        "tile_grid",
    }
    # zoom comes from image_tile_info["dapi"]["zoom_levels"], not the 0..6 directories.
    assert manifest["max_pyramid_zoom"] == 3

    assert set(manifest["row_group_files"]) == {
        "cbg",
        "transcripts",
        "cell_segmentation",
        "images",
    }
    assert manifest["row_group_files"]["cbg"] == {
        "directory": "cbg_chunks",
        "files": ["cbg_0.parquet"],
        "max_row_groups_per_file": 1000,
        "total_row_groups": 4,
        "gene_to_row_group": {"GeneA": 0},
    }
    assert manifest["row_group_files"]["transcripts"] == {
        "directory": "transcripts",
        "files": ["transcripts_0.parquet"],
        "max_row_groups_per_file": 5000,
        "total_row_groups": 12,
    }
    assert manifest["row_group_files"]["cell_segmentation"] == {
        "directory": "cell_segmentation",
        "files": ["cell_segmentation_0.parquet"],
        "max_row_groups_per_file": 4000,
        "total_row_groups": 9,
    }

    # Only the chunked channel appears; dapi_files holds zoom dirs, not chunk parquets.
    assert set(manifest["row_group_files"]["images"]) == {"dapi"}
    assert manifest["row_group_files"]["images"]["dapi"] == {
        "directory": "pyramid_images/dapi",
        # chunk_10 sorts after chunk_9 — numeric, not lexicographic.
        "files": [
            "chunk_0.parquet",
            "chunk_2.parquet",
            "chunk_9.parquet",
            "chunk_10.parquet",
        ],
        "zoom_info": {"0": {"num_tiles": 1}},
        "zoom_levels": [0, 1, 2, 3],
        "max_row_groups_per_file": 1500,
        "total_row_groups": 37,
    }

    assert manifest["image_dimensions"] == {"width": 2048, "height": 1024, "tile_size": 256}
    assert manifest["tile_grid"] == {
        "tile_size": 250,
        "num_tiles_x": 4,
        "num_tiles_y": 3,
        "x_min": 0.0,
        "x_max": 1000.0,
        "y_min": -5.0,
        "y_max": 750.0,
    }


def test_row_group_mode_falls_back_to_legacy_single_file_names(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1])
    # A legacy flat parquet rather than a chunked channel directory.
    (tmp_path / "pyramid_images" / "dapi.parquet").write_bytes(b"")

    save_landscape_parameters(
        "Xenium",
        str(tmp_path),
        use_row_groups=True,
        tile_grid_info={"num_tiles_x": 2, "num_tiles_y": 2},
        image_tile_info=_image_tile_info(),
    )
    manifest = _read_manifest(tmp_path)

    assert manifest["row_group_files"]["cbg"] == "cbg.parquet"
    assert manifest["row_group_files"]["transcripts"] == "transcripts.parquet"
    assert manifest["row_group_files"]["cell_segmentation"] == "cell_segmentation.parquet"
    assert manifest["row_group_files"]["images"] == {
        "dapi": {
            "path": "pyramid_images/dapi.parquet",
            "zoom_info": {"0": {"num_tiles": 1}},
            "zoom_levels": [0, 1, 2, 3],
        }
    }
    # tile_grid falls back to the tile_size argument and None for absent extents.
    assert manifest["tile_grid"] == {
        "tile_size": 1000,
        "num_tiles_x": 2,
        "num_tiles_y": 2,
        "x_min": None,
        "x_max": None,
        "y_min": None,
        "y_max": None,
    }


def test_row_group_mode_without_tile_grid_info_omits_all_extras(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1])
    _make_chunked_channel(tmp_path, "dapi", [0, 1])

    save_landscape_parameters(
        "Xenium",
        str(tmp_path),
        use_row_groups=True,
        image_tile_info=_image_tile_info(),
    )
    manifest = _read_manifest(tmp_path)

    assert manifest["use_row_groups"] is True
    # image_dimensions is nested inside the tile_grid_info guard, so it is dropped too.
    assert not {"row_group_files", "image_dimensions", "tile_grid"} & set(manifest)


def test_row_group_mode_without_image_tile_info_reads_zoom_from_directories(
    tmp_path: Path,
) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3, 4])

    save_landscape_parameters(
        "Xenium",
        str(tmp_path),
        use_row_groups=True,
        tile_grid_info=_tile_grid_info(),
    )
    manifest = _read_manifest(tmp_path)

    assert manifest["max_pyramid_zoom"] == 4
    # No image_tile_info means no image_dimensions, even though tile_grid_info is present.
    assert "image_dimensions" not in manifest
    assert manifest["tile_grid"]["num_tiles_x"] == 4


def test_missing_pyramid_directory_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "pyramid_images").mkdir()

    # Matched on the path so this cannot be satisfied by some other FileNotFoundError.
    with pytest.raises(FileNotFoundError, match="dapi_files"):
        save_landscape_parameters("Xenium", str(tmp_path))


# --- branch 3: technology == "custom" ---------------------------------------


def _seed_existing_manifest(root: Path) -> dict:
    existing = {
        "technology": "Xenium",
        "segmentation_approach": ["default"],
        "max_pyramid_zoom": 3,
        "tile_size": 250,
        "image_info": [{"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]}],
        "image_format": ".webp",
        "use_int_index": True,
        "use_row_groups": False,
    }
    (root / "landscape_parameters.json").write_text(json.dumps(existing, indent=4))
    return existing


def test_custom_appends_segmentation_approach_to_existing_manifest(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3])
    existing = _seed_existing_manifest(tmp_path)

    save_landscape_parameters("custom", str(tmp_path), segmentation_approach="cellpose")
    manifest = _read_manifest(tmp_path)

    assert manifest["segmentation_approach"] == ["default", "cellpose"]
    # Every other field is carried through untouched, including "technology": the custom
    # branch never stamps "custom" onto the manifest it updates.
    assert manifest == {**existing, "segmentation_approach": ["default", "cellpose"]}


def test_custom_appends_repeatedly_without_deduplicating(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0])
    _seed_existing_manifest(tmp_path)

    save_landscape_parameters("custom", str(tmp_path), segmentation_approach="cellpose")
    save_landscape_parameters("custom", str(tmp_path), segmentation_approach="cellpose")

    assert _read_manifest(tmp_path)["segmentation_approach"] == [
        "default",
        "cellpose",
        "cellpose",
    ]


def test_custom_ignores_caller_supplied_manifest_fields(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1, 2, 3])
    _seed_existing_manifest(tmp_path)

    save_landscape_parameters(
        "custom",
        str(tmp_path),
        tile_size=9999,
        image_format=".jpg",
        use_int_index=False,
        image_info=[{"name": "ignored", "button_name": "IGNORED", "color": [9, 9, 9]}],
        segmentation_approach="cellpose",
    )
    manifest = _read_manifest(tmp_path)

    assert manifest["tile_size"] == 250
    assert manifest["image_format"] == ".webp"
    assert manifest["use_int_index"] is True
    assert manifest["image_info"][0]["name"] == "dapi"


def test_custom_requires_a_pyramid_directory_it_never_uses(tmp_path: Path) -> None:
    """BUG (pinned, not fixed): the custom branch discards ``max_pyramid_zoom``, yet the
    unconditional pyramid scan that computes it still raises when the directory is
    absent — so updating a manifest fails on datasets whose tiles were cleaned up."""
    _seed_existing_manifest(tmp_path)
    (tmp_path / "pyramid_images").mkdir()

    # "dapi_files", not "landscape_parameters.json": it is the pyramid scan that fails,
    # even though this branch discards the zoom level it computes.
    with pytest.raises(FileNotFoundError, match="dapi_files"):
        save_landscape_parameters("custom", str(tmp_path), segmentation_approach="cellpose")

    # The manifest is left untouched by the failed call.
    assert _read_manifest(tmp_path)["segmentation_approach"] == ["default"]

    # Row-group mode short-circuits the scan, so the same call then succeeds.
    save_landscape_parameters(
        "custom",
        str(tmp_path),
        segmentation_approach="cellpose",
        use_row_groups=True,
        image_tile_info=_image_tile_info(),
    )

    assert _read_manifest(tmp_path)["segmentation_approach"] == ["default", "cellpose"]


def test_custom_without_an_existing_manifest_is_an_error(tmp_path: Path) -> None:
    _make_pyramid(tmp_path, "dapi_files", [0, 1])

    # The pyramid is present, so the only thing left to be missing is the manifest itself.
    with pytest.raises(FileNotFoundError, match=r"landscape_parameters\.json"):
        save_landscape_parameters("custom", str(tmp_path))
