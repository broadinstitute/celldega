"""The raw-bundle pre-flight accepts a vendor directory only when every entry the
technology declares is present.

``_check_required_files`` is the gate ``run_pre_processing`` passes through before any
DegaFiles are written: a complete Xenium or MERSCOPE layout is accepted silently, any
missing entry raises ``FileNotFoundError`` naming it, and an unknown technology raises
``ValueError``. Xenium additionally requires a morphology OME-TIFF, which is resolved by
name pattern rather than by the flat file list.

The two transform writers round-trip a matrix to disk: ``write_identity_transform`` emits a
3x3 identity, ``write_xenium_transform`` emits the top-left 3x3 block of the homogeneous
transform stored in ``cells.zarr.zip`` while returning the full matrix.
"""

from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest
import zarr

from celldega.pre.raw_bundle import (
    _check_required_files,
    write_identity_transform,
    write_xenium_transform,
)


# Mirrors the table inside _check_required_files. Kept separate on purpose: if the
# production list changes, the "complete bundle passes" tests here start failing instead of
# silently tracking the change.
XENIUM_FILES = (
    "cells.csv",
    "cells.csv.gz",
    "cells.parquet",
    "transcripts.parquet",
    "cell_boundaries.parquet",
)
XENIUM_DIRS = ("cells.zarr", "cell_feature_matrix", "analysis")
XENIUM_MORPHOLOGY = "morphology_focus/morphology_focus_0000.ome.tif"

MERSCOPE_FILES = (
    "images/mosaic_DAPI_z3.tif",
    "images/micron_to_mosaic_pixel_transform.csv",
    "cell_metadata.csv",
    "detected_transcripts.csv",
    "cell_boundaries.parquet",
    "cell_by_gene.csv",
)


# --- bundle builders --------------------------------------------------------


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _make_xenium_bundle(root: Path) -> Path:
    """A minimally complete Xenium ``outs`` layout: empty placeholders are enough,
    the checker only tests for existence."""
    root.mkdir(parents=True, exist_ok=True)
    for name in XENIUM_FILES:
        _touch(root / name)
    for name in XENIUM_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    _touch(root / XENIUM_MORPHOLOGY)
    return root


def _make_merscope_bundle(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in MERSCOPE_FILES:
        _touch(root / name)
    return root


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _missing_entries(excinfo) -> list[str]:
    """The comma-separated tail of the FileNotFoundError message, as a list.

    Compared exactly rather than by substring, so that a report naming ``cells.csv.gz``
    cannot satisfy an expectation of ``cells.csv``.
    """
    return str(excinfo.value).rsplit(": ", 1)[1].split(", ")


# --- _check_required_files: Xenium ------------------------------------------


def test_xenium_complete_bundle_passes(tmp_path: Path) -> None:
    _check_required_files("Xenium", str(_make_xenium_bundle(tmp_path / "outs")))


@pytest.mark.parametrize("entry", [*XENIUM_FILES, *XENIUM_DIRS])
def test_xenium_missing_entry_raises_and_names_it(tmp_path: Path, entry: str) -> None:
    """Also proves _make_xenium_bundle is not creating dead weight: every entry it
    creates is load-bearing for the passing case above."""
    data_dir = _make_xenium_bundle(tmp_path / "outs")
    _remove(data_dir / entry)

    with pytest.raises(FileNotFoundError) as excinfo:
        _check_required_files("Xenium", str(data_dir))

    assert _missing_entries(excinfo) == [entry]
    assert "Xenium" in str(excinfo.value)


def test_xenium_missing_morphology_tiff_is_reported_separately(tmp_path: Path) -> None:
    """The morphology TIFF is not in the flat file list -- it is resolved by pattern, so
    its absence travels through resolve_xenium_morphology_ome_path, not the list scan."""
    data_dir = _make_xenium_bundle(tmp_path / "outs")
    shutil.rmtree(data_dir / "morphology_focus")

    with pytest.raises(FileNotFoundError) as excinfo:
        _check_required_files("Xenium", str(data_dir))

    # Nothing from the flat list is missing, so it is the only complaint.
    (missing,) = _missing_entries(excinfo)
    assert missing.startswith("morphology OME-TIFF")


def test_xenium_accepts_root_level_morphology_ome_tif(tmp_path: Path) -> None:
    """The resolver's root-level fallback is a real acceptance path, not just an
    error path -- a bundle with morphology.ome.tif at the root and no
    morphology_focus/ directory still passes."""
    data_dir = _make_xenium_bundle(tmp_path / "outs")
    shutil.rmtree(data_dir / "morphology_focus")
    _touch(data_dir / "morphology.ome.tif")

    _check_required_files("Xenium", str(data_dir))


def test_xenium_reports_every_missing_entry_at_once(tmp_path: Path) -> None:
    data_dir = _make_xenium_bundle(tmp_path / "outs")
    _remove(data_dir / "cells.parquet")
    _remove(data_dir / "analysis")
    shutil.rmtree(data_dir / "morphology_focus")

    with pytest.raises(FileNotFoundError) as excinfo:
        _check_required_files("Xenium", str(data_dir))

    # Exactly these three, and the morphology complaint is appended last.
    missing = _missing_entries(excinfo)
    assert missing[:2] == ["cells.parquet", "analysis"]
    assert len(missing) == 3
    assert missing[2].startswith("morphology OME-TIFF")


def test_xenium_rejects_an_empty_directory(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        _check_required_files("Xenium", str(empty))

    missing = _missing_entries(excinfo)
    assert set(missing[:-1]) == {*XENIUM_FILES, *XENIUM_DIRS}
    assert missing[-1].startswith("morphology OME-TIFF")


# --- _check_required_files: MERSCOPE ----------------------------------------


def test_merscope_complete_bundle_passes(tmp_path: Path) -> None:
    _check_required_files("MERSCOPE", str(_make_merscope_bundle(tmp_path / "region_0")))


def test_merscope_does_not_require_a_morphology_tiff(tmp_path: Path) -> None:
    """The morphology resolution is Xenium-only; a MERSCOPE bundle has no
    morphology_focus/ directory and must still pass."""
    data_dir = _make_merscope_bundle(tmp_path / "region_0")
    assert not (data_dir / "morphology_focus").exists()

    _check_required_files("MERSCOPE", str(data_dir))


@pytest.mark.parametrize("entry", MERSCOPE_FILES)
def test_merscope_missing_entry_raises_and_names_it(tmp_path: Path, entry: str) -> None:
    data_dir = _make_merscope_bundle(tmp_path / "region_0")
    _remove(data_dir / entry)

    with pytest.raises(FileNotFoundError) as excinfo:
        _check_required_files("MERSCOPE", str(data_dir))

    assert _missing_entries(excinfo) == [entry]
    assert "MERSCOPE" in str(excinfo.value)


# --- _check_required_files: technology dispatch -----------------------------


@pytest.mark.parametrize("technology", ["CosMx", "xenium", "", "MERFISH"])
def test_unsupported_technology_raises_value_error(tmp_path: Path, technology: str) -> None:
    """Matching is exact and case-sensitive -- "xenium" is not "Xenium"."""
    data_dir = _make_xenium_bundle(tmp_path / "outs")

    with pytest.raises(ValueError) as excinfo:
        _check_required_files(technology, str(data_dir))

    assert "Unsupported technology" in str(excinfo.value)


def test_unsupported_technology_is_checked_before_the_directory(tmp_path: Path) -> None:
    """The technology table is consulted first, so a nonexistent data_dir still yields
    ValueError rather than FileNotFoundError."""
    with pytest.raises(ValueError, match="Unsupported technology"):
        _check_required_files("CosMx", str(tmp_path / "does_not_exist"))


# --- write_identity_transform -----------------------------------------------


def _read_transform(path: Path) -> np.ndarray:
    return pd.read_csv(path, sep=" ", header=None).to_numpy()


def test_write_identity_transform_writes_a_3x3_identity(tmp_path: Path) -> None:
    write_identity_transform(str(tmp_path))

    written = tmp_path / "micron_to_image_transform.csv"
    assert written.is_file()
    matrix = _read_transform(written)
    assert matrix.shape == (3, 3)
    np.testing.assert_allclose(matrix, np.eye(3))


def test_write_identity_transform_leaves_an_existing_file_alone(tmp_path: Path) -> None:
    """Current behaviour: the writer is a no-op when the transform already exists, so a
    real Xenium-derived transform is never clobbered by the IST fallback."""
    existing = tmp_path / "micron_to_image_transform.csv"
    pd.DataFrame(np.full((3, 3), 7.0)).to_csv(existing, sep=" ", header=False, index=False)

    write_identity_transform(str(tmp_path))

    np.testing.assert_allclose(_read_transform(existing), np.full((3, 3), 7.0))


# --- write_xenium_transform --------------------------------------------------


def _make_cells_zarr_zip(data_dir: Path, matrix: np.ndarray | None = None) -> np.ndarray:
    """Write the smallest cells.zarr.zip that write_xenium_transform can read:
    a ``masks`` group holding a ``homogeneous_transform`` array."""
    data_dir.mkdir(parents=True, exist_ok=True)
    if matrix is None:
        matrix = np.arange(16, dtype="float64").reshape(4, 4)
    store = zarr.storage.ZipStore(str(data_dir / "cells.zarr.zip"), mode="w")
    root = zarr.open_group(store=store, mode="w")
    masks = root.create_group("masks")
    masks.create_array("homogeneous_transform", shape=matrix.shape, dtype=matrix.dtype)
    masks["homogeneous_transform"][:] = matrix
    store.close()
    return matrix


def test_write_xenium_transform_writes_the_top_left_3x3_block(tmp_path: Path) -> None:
    data_dir = tmp_path / "outs"
    dega_files = tmp_path / "dega"
    dega_files.mkdir()
    matrix = _make_cells_zarr_zip(data_dir)

    returned = write_xenium_transform(str(data_dir), str(dega_files))

    written = dega_files / "micron_to_image_transform.csv"
    assert written.is_file()
    # The full 4x4 comes back, but only the upper-left 3x3 is persisted.
    np.testing.assert_allclose(returned, matrix)
    np.testing.assert_allclose(_read_transform(written), matrix[:3, :3])


def test_write_xenium_transform_honours_a_custom_filename(tmp_path: Path) -> None:
    data_dir = tmp_path / "outs"
    dega_files = tmp_path / "dega"
    dega_files.mkdir()
    _make_cells_zarr_zip(data_dir)

    write_xenium_transform(str(data_dir), str(dega_files), transform_fname="custom.csv")

    assert (dega_files / "custom.csv").is_file()
    assert not (dega_files / "micron_to_image_transform.csv").exists()


def test_write_xenium_transform_overwrites_an_existing_transform(tmp_path: Path) -> None:
    """Unlike write_identity_transform, this writer is unconditional."""
    data_dir = tmp_path / "outs"
    dega_files = tmp_path / "dega"
    dega_files.mkdir()
    matrix = _make_cells_zarr_zip(data_dir)
    stale = dega_files / "micron_to_image_transform.csv"
    pd.DataFrame(np.zeros((3, 3))).to_csv(stale, sep=" ", header=False, index=False)

    write_xenium_transform(str(data_dir), str(dega_files))

    np.testing.assert_allclose(_read_transform(stale), matrix[:3, :3])


def test_write_xenium_transform_missing_zip_raises_file_not_found(tmp_path: Path) -> None:
    data_dir = tmp_path / "outs"
    data_dir.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        write_xenium_transform(str(data_dir), str(tmp_path))

    assert "cells.zarr.zip" in str(excinfo.value)


def test_write_xenium_transform_missing_matrix_raises_key_error(tmp_path: Path) -> None:
    data_dir = tmp_path / "outs"
    data_dir.mkdir()
    store = zarr.storage.ZipStore(str(data_dir / "cells.zarr.zip"), mode="w")
    root = zarr.open_group(store=store, mode="w")
    root.create_group("masks")
    store.close()

    with pytest.raises(KeyError) as excinfo:
        write_xenium_transform(str(data_dir), str(tmp_path))

    assert "Could not find the transformation matrix" in str(excinfo.value)
    assert not (tmp_path / "micron_to_image_transform.csv").exists()
