"""Morphology-image discovery and image-layer metadata for the supported technologies.

``resolve_xenium_morphology_ome_path`` walks a four-step precedence chain over a Xenium
bundle -- classic ``morphology_focus/morphology_focus_0000.ome.tif``, then the first
numbered ``morphology_focus_*.ome.tif``, then any ``*.ome.tif`` under ``morphology_focus/``,
then ``morphology.ome.tif`` at the bundle root -- and raises ``FileNotFoundError`` naming
the candidates it tried when none exist.

``get_image_info`` is a pure lookup from (technology, image_tile_layer) to the viewer's
channel list, including the RGB colour each channel is drawn with.
"""

import json
from pathlib import Path

import pytest

from celldega.pre.image_info import get_image_info, resolve_xenium_morphology_ome_path
from celldega.pre.landscape_parameters import save_landscape_parameters


def _touch(path: Path) -> Path:
    """Create a zero-byte file, making parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def _xenium_bundle(root: Path, *focus_names: str, root_morphology: bool = False) -> Path:
    """Build a Xenium-shaped bundle: named files under ``morphology_focus/``.

    Passing no ``focus_names`` leaves ``morphology_focus/`` absent entirely.
    """
    for name in focus_names:
        _touch(root / "morphology_focus" / name)
    if root_morphology:
        _touch(root / "morphology.ome.tif")
    return root


# --- resolve_xenium_morphology_ome_path: precedence chain --------------------


def test_classic_focus_file_beats_earlier_sorting_siblings(tmp_path: Path) -> None:
    """Step 1 short-circuits: the classic name wins even though ``morphology_focus_.ome.tif``
    sorts ahead of it ('.' < '0') under step 2's own ``morphology_focus_*.ome.tif`` glob, and
    ``aaa_alpha.ome.tif`` sorts ahead of both under step 3's ``*.ome.tif`` glob."""
    _xenium_bundle(
        tmp_path,
        "aaa_alpha.ome.tif",
        "morphology_focus_.ome.tif",
        "morphology_focus_0000.ome.tif",
        "morphology_focus_9999.ome.tif",
        root_morphology=True,
    )

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology_focus" / "morphology_focus_0000.ome.tif"


def test_numbered_focus_file_beats_unnumbered_sibling(tmp_path: Path) -> None:
    """Step 2 over step 3: no classic ``_0000`` file, and the unnumbered candidate sorts
    before the numbered one, so a plain lexicographic scan would pick the wrong file."""
    _xenium_bundle(
        tmp_path,
        "aaa_alpha.ome.tif",
        "morphology_focus_0001.ome.tif",
        root_morphology=True,
    )

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology_focus" / "morphology_focus_0001.ome.tif"


def test_lowest_numbered_focus_file_wins(tmp_path: Path) -> None:
    _xenium_bundle(tmp_path, "morphology_focus_0003.ome.tif", "morphology_focus_0002.ome.tif")

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology_focus" / "morphology_focus_0002.ome.tif"


def test_unnumbered_focus_file_used_when_no_numbered_match(tmp_path: Path) -> None:
    """Step 3 over step 4: first ``*.ome.tif`` lexicographically, in preference to the
    root ``morphology.ome.tif`` that also exists."""
    _xenium_bundle(tmp_path, "zzz_omega.ome.tif", "aaa_alpha.ome.tif", root_morphology=True)

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology_focus" / "aaa_alpha.ome.tif"


def test_root_morphology_used_when_focus_dir_absent(tmp_path: Path) -> None:
    _xenium_bundle(tmp_path, root_morphology=True)
    assert not (tmp_path / "morphology_focus").exists()

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology.ome.tif"


def test_root_morphology_used_when_focus_dir_empty(tmp_path: Path) -> None:
    (tmp_path / "morphology_focus").mkdir()
    _touch(tmp_path / "morphology.ome.tif")

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology.ome.tif"


def test_root_morphology_used_when_focus_dir_holds_no_ome_tif(tmp_path: Path) -> None:
    """A ``morphology_focus/`` full of non-OME files does not trap the search."""
    _xenium_bundle(tmp_path, "morphology_focus_0000.tif", "notes.txt", root_morphology=True)

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology.ome.tif"


def test_accepts_str_path_and_returns_path(tmp_path: Path) -> None:
    _xenium_bundle(tmp_path, "morphology_focus_0000.ome.tif")

    resolved = resolve_xenium_morphology_ome_path(str(tmp_path))

    assert isinstance(resolved, Path)
    assert resolved == tmp_path / "morphology_focus" / "morphology_focus_0000.ome.tif"


# --- resolve_xenium_morphology_ome_path: failure -----------------------------


def test_missing_morphology_raises_with_candidates_named(tmp_path: Path) -> None:
    (tmp_path / "morphology_focus").mkdir()
    _touch(tmp_path / "experiment.xenium")

    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_xenium_morphology_ome_path(tmp_path)

    message = str(excinfo.value)
    assert str(tmp_path) in message
    assert "morphology_focus/morphology_focus_0000.ome.tif" in message
    assert "morphology_focus/*.ome.tif" in message
    assert "morphology.ome.tif" in message


def test_root_directory_named_like_the_tiff_is_not_accepted(tmp_path: Path) -> None:
    """Step 4 is guarded by ``is_file()``, so a *directory* called ``morphology.ome.tif``
    does not satisfy the search."""
    (tmp_path / "morphology.ome.tif").mkdir()

    with pytest.raises(FileNotFoundError, match="No Xenium-compatible morphology OME-TIFF"):
        resolve_xenium_morphology_ome_path(tmp_path)


def test_focus_directory_entry_is_returned_even_when_it_is_a_directory(tmp_path: Path) -> None:
    """BUG (pinned, not fixed): steps 2 and 3 use ``glob`` without an ``is_file()`` check,
    so a subdirectory named ``*.ome.tif`` inside ``morphology_focus/`` is returned as if it
    were an image -- even though step 1 rejects that exact name for not being a file, and
    a real ``morphology.ome.tif`` at the root is available."""
    (tmp_path / "morphology_focus" / "morphology_focus_0000.ome.tif").mkdir(parents=True)
    _touch(tmp_path / "morphology.ome.tif")

    resolved = resolve_xenium_morphology_ome_path(tmp_path)

    assert resolved == tmp_path / "morphology_focus" / "morphology_focus_0000.ome.tif"
    assert resolved.is_dir()


# --- get_image_info: supported lookups ---------------------------------------

_DAPI_ONLY = [{"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]}]
_ALL_XENIUM = [
    {"name": "dapi", "button_name": "DAPI", "color": [0, 0, 255]},
    {"name": "bound", "button_name": "BOUND", "color": [0, 255, 0]},
    {"name": "rna", "button_name": "RNA", "color": [255, 0, 0]},
    {"name": "prot", "button_name": "PROT", "color": [255, 255, 255]},
]


@pytest.mark.parametrize(
    ("technology", "layer", "expected"),
    [
        ("Xenium", "dapi", _DAPI_ONLY),
        ("MERSCOPE", "dapi", _DAPI_ONLY),
        ("Xenium", "h&e", [{"name": "h&e", "button_name": "H&E", "color": [255, 0, 0]}]),
        ("MERSCOPE", "h&e", [{"name": "h&e", "button_name": "H&E", "color": [255, 0, 0]}]),
        ("Xenium", "all", _ALL_XENIUM),
    ],
)
def test_get_image_info_returns_channel_list(
    technology: str, layer: str, expected: list[dict]
) -> None:
    assert get_image_info(technology, layer) == expected


def test_get_image_info_defaults_to_dapi() -> None:
    assert get_image_info("Xenium") == _DAPI_ONLY


def test_all_layer_order_is_dapi_bound_rna_prot() -> None:
    """The viewer renders channels in list order, so order is part of the contract."""
    assert [entry["name"] for entry in get_image_info("Xenium", "all")] == [
        "dapi",
        "bound",
        "rna",
        "prot",
    ]


# --- get_image_info: rejected lookups ----------------------------------------


@pytest.mark.parametrize("technology", ["CosMx", "xenium", "", "Xenium "])
def test_unsupported_technology_raises(technology: str) -> None:
    with pytest.raises(ValueError, match="Unsupported technology"):
        get_image_info(technology, "dapi")


def test_all_layer_rejected_for_merscope() -> None:
    with pytest.raises(ValueError, match="only supported for 'Xenium'"):
        get_image_info("MERSCOPE", "all")


def test_unknown_layer_falls_through_to_the_all_list_for_xenium() -> None:
    """BUG (pinned, not fixed): the docstring promises ValueError for an invalid
    ``image_tile_layer``, but there is no final validation -- any unrecognised layer name
    falls through to the four-channel 'all' list for Xenium."""
    assert get_image_info("Xenium", "not-a-layer") == _ALL_XENIUM


def test_unknown_layer_raises_the_all_message_for_merscope() -> None:
    """BUG (pinned, not fixed): same missing validation, seen from the other side -- a
    MERSCOPE request for an unrecognised layer is reported as if the caller had asked for
    ``image_tile_layer='all'``."""
    with pytest.raises(ValueError, match="image_tile_layer='all' is only supported"):
        get_image_info("MERSCOPE", "not-a-layer")


# --- h&e colour divergence across modules ------------------------------------


def test_h_and_e_colour_differs_between_get_image_info_and_saved_parameters(
    tmp_path: Path,
) -> None:
    """Pinned inconsistency, deliberately NOT reconciled here: ``get_image_info`` colours
    the h&e layer red, while ``save_landscape_parameters`` overwrites ``image_info`` with
    a blue h&e entry for ``technology='h&e'``. Both are current behaviour."""
    (tmp_path / "pyramid_images" / "h_and_e_files").mkdir(parents=True)

    save_landscape_parameters("h&e", tmp_path)
    saved = json.loads((tmp_path / "landscape_parameters.json").read_text())

    assert get_image_info("Xenium", "h&e")[0]["color"] == [255, 0, 0]
    assert saved["image_info"] == [{"name": "h&e", "button_name": "H&E", "color": [0, 0, 255]}]
