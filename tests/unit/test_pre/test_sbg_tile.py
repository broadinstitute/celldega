import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.sparse import csr_matrix

ROOT_DIR = Path(__file__).resolve().parents[3]
PRE_ROOT = ROOT_DIR / "src" / "celldega" / "pre"

CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)
PREPKG = types.ModuleType("celldega.pre")
PREPKG.__path__ = [str(PRE_ROOT)]
sys.modules.setdefault("celldega.pre", PREPKG)

spec = importlib.util.spec_from_file_location("celldega.pre.sbg_tile", PRE_ROOT / "sbg_tile.py")
sbg_tile = importlib.util.module_from_spec(spec)
sbg_tile.__package__ = "celldega.pre"
sys.modules["celldega.pre.sbg_tile"] = sbg_tile
spec.loader.exec_module(sbg_tile)

write_pseudotranscripts_from_sbg = sbg_tile.write_pseudotranscripts_from_sbg


@pytest.fixture
def sbg_test_data():
    spots = pd.DataFrame(
        {
            "x": [10.0, 10.0, 60.0, 60.0],
            "y": [10.0, 60.0, 10.0, 60.0],
        },
        index=["s0", "s1", "s2", "s3"],
    )

    matrix = csr_matrix(
        [
            [2, 0, 1],
            [0, 1, 0],
            [1, 1, 0],
            [0, 0, 0],
        ]
    )

    sbg = pd.DataFrame.sparse.from_spmatrix(
        matrix,
        index=spots.index,
        columns=["G0", "G1", "G2"],
    )

    gene_map = {f"G{i}": i for i in range(3)}
    tile_bounds = {"x_min": 0.0, "x_max": 100.0, "y_min": 0.0, "y_max": 100.0}

    return spots, sbg, gene_map, tile_bounds


def test_pseudotranscript_tiles_created(tmp_path, sbg_test_data):
    spots, sbg, gene_map, tile_bounds = sbg_test_data

    rng = np.random.default_rng(0)
    write_pseudotranscripts_from_sbg(
        spots,
        sbg,
        gene_map,
        tile_bounds,
        tile_size=50.0,
        path_output=tmp_path,
        jitter=0.5,
        coarse_tile_factor=2,
        rng=rng,
    )

    files = sorted(tmp_path.glob("transcripts_tile_*.parquet"))
    assert len(files) == 3  # three tiles contain data, tile (1, 1) should be skipped

    tile_00 = pd.read_parquet(tmp_path / "transcripts_tile_0_0.parquet")
    assert len(tile_00) == 3
    assert set(tile_00["name"].unique()) <= {0, 2}

    coords = np.array(tile_00["geometry"].tolist())
    assert np.all(np.abs(coords[:, 0] - 10.0) <= 0.26)
    assert np.all(np.abs(coords[:, 1] - 10.0) <= 0.26)

    # Ensure other tiles are written with the expected counts
    tile_01 = pd.read_parquet(tmp_path / "transcripts_tile_0_1.parquet")
    assert len(tile_01) == 1
    assert tile_01.iloc[0]["name"] == 1

    tile_10 = pd.read_parquet(tmp_path / "transcripts_tile_1_0.parquet")
    assert len(tile_10) == 2
    assert set(tile_10["name"].unique()) <= {0, 1}


def test_empty_tiles_skip_output(tmp_path, sbg_test_data):
    spots, sbg, gene_map, tile_bounds = sbg_test_data

    zero_sbg = pd.DataFrame.sparse.from_spmatrix(
        csr_matrix(sbg.shape), index=sbg.index, columns=sbg.columns
    )

    write_pseudotranscripts_from_sbg(
        spots,
        zero_sbg,
        gene_map,
        tile_bounds,
        tile_size=50.0,
        path_output=tmp_path,
        jitter=0.0,
        coarse_tile_factor=4,
        rng=np.random.default_rng(1),
    )

    assert list(tmp_path.glob("transcripts_tile_*.parquet")) == []
