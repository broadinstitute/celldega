import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

try:
    import geopandas as gpd
    import polars as pl
    from shapely.geometry import Polygon, Point
except Exception as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"Required libraries missing: {e}", allow_module_level=True)

# Load modules directly to avoid heavy package imports
ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT = ROOT_DIR / "src" / "celldega" / "pre"
CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)
PREPKG = types.ModuleType("celldega.pre")
PREPKG.__path__ = [str(ROOT)]
sys.modules.setdefault("celldega.pre", PREPKG)

spec_b = importlib.util.spec_from_file_location(
    "celldega.pre.boundary_tile", ROOT / "boundary_tile.py"
)
boundary_tile = importlib.util.module_from_spec(spec_b)
boundary_tile.__package__ = "celldega.pre"
sys.modules["celldega.pre.boundary_tile"] = boundary_tile
spec_b.loader.exec_module(boundary_tile)

spec_t = importlib.util.spec_from_file_location(
    "celldega.pre.trx_tile", ROOT / "trx_tile.py"
)
trx_tile = importlib.util.module_from_spec(spec_t)
trx_tile.__package__ = "celldega.pre"
sys.modules["celldega.pre.trx_tile"] = trx_tile
spec_t.loader.exec_module(trx_tile)

make_trx_tiles = trx_tile.make_trx_tiles
make_cell_boundary_tiles = boundary_tile.make_cell_boundary_tiles


@pytest.fixture
def synthetic_paths(tmp_path: Path) -> dict[str, Path]:
    """Create synthetic transcript and cell boundary data."""
    rng = np.random.default_rng(42)

    n_cells = 10
    cell_size = 10
    transcripts = 100
    bbox = (0, 50, 0, 50)

    # Generate square polygons for cells
    cells = []
    for _ in range(n_cells):
        x = rng.uniform(bbox[0], bbox[1] - cell_size)
        y = rng.uniform(bbox[2], bbox[3] - cell_size)
        square = Polygon([(x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)])
        cells.append(square)

    gdf_cells = gpd.GeoDataFrame({"geometry_image_space": cells}, geometry="geometry_image_space")
    gdf_cells.index = [str(i) for i in range(n_cells)]
    cell_boundaries = tmp_path / "cell_boundaries.parquet"
    gdf_cells.to_parquet(cell_boundaries, index=True)

    df_meta_cell = pd.DataFrame({"name": [str(i) for i in range(n_cells)]})
    df_meta_cell.to_parquet(tmp_path / "cell_metadata.parquet")
    df_meta_cell.to_parquet(tmp_path / "cell_metadata_custom.parquet")

    # Generate transcripts
    points = [(rng.uniform(bbox[0], bbox[1]), rng.uniform(bbox[2], bbox[3])) for _ in range(transcripts)]
    genes = [f"G{i%3}" for i in range(transcripts)]
    df_trx = pl.DataFrame(
        {
            "gene": genes,
            "global_x": [p[0] for p in points],
            "global_y": [p[1] for p in points],
            "cell_id": [str(i % n_cells) for i in range(transcripts)],
            "transcript_id": list(range(transcripts)),
        }
    )
    trx_file = tmp_path / "transcripts.parquet"
    df_trx.write_parquet(trx_file)

    pd.DataFrame(index=sorted(set(genes))).to_parquet(tmp_path / "meta_gene.parquet")

    trans_mat = np.eye(3)
    trans_path = tmp_path / "micron_to_image_transform.csv"
    np.savetxt(trans_path, trans_mat)

    return {
        "trx": trx_file,
        "transform": trans_path,
        "boundaries": cell_boundaries,
        "landscape": tmp_path,
        "trx_tiles": tmp_path / "transcript_tiles",
        "cell_tiles": tmp_path / "cell_segmentation_custom",
    }


def test_make_tiles_functions(synthetic_paths: dict[str, Path]) -> None:
    bounds = make_trx_tiles(
        technology="MERSCOPE",
        path_trx=str(synthetic_paths["trx"]),
        path_transformation_matrix=str(synthetic_paths["transform"]),
        path_trx_tiles=str(synthetic_paths["trx_tiles"]),
        coarse_tile_factor=2,
        tile_size=10,
        chunk_size=50,
        image_scale=1,
        max_workers=1,
    )

    assert list(synthetic_paths["trx_tiles"].glob("transcripts_tile_*.parquet")), "Transcript tiles missing"

    make_cell_boundary_tiles(
        technology="custom",
        path_cell_boundaries=str(synthetic_paths["boundaries"]),
        path_output=str(synthetic_paths["cell_tiles"]),
        tile_size=10,
        coarse_tile_factor=2,
        tile_bounds=bounds,
        image_scale=1,
        max_workers=1,
    )

    assert list(synthetic_paths["cell_tiles"].glob("cell_tile_*.parquet")), "Cell tiles missing"
