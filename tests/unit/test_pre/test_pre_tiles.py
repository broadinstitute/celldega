import importlib.util
import math
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

try:
    import geopandas as gpd
    import polars as pl
    from shapely.geometry import Polygon
except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover - skip if deps missing
    pytest.skip(f"Required libraries missing: {e}", allow_module_level=True)

# Dynamically load modules to avoid heavy imports
ROOT_DIR = Path(__file__).resolve().parents[3]
PRE_ROOT = ROOT_DIR / "src" / "celldega" / "pre"
CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)
PREPKG = types.ModuleType("celldega.pre")
PREPKG.__path__ = [str(PRE_ROOT)]
sys.modules.setdefault("celldega.pre", PREPKG)

spec_b = importlib.util.spec_from_file_location(
    "celldega.pre.boundary_tile", PRE_ROOT / "boundary_tile.py"
)
boundary_tile = importlib.util.module_from_spec(spec_b)
boundary_tile.__package__ = "celldega.pre"
sys.modules["celldega.pre.boundary_tile"] = boundary_tile
spec_b.loader.exec_module(boundary_tile)

spec_t = importlib.util.spec_from_file_location(
    "celldega.pre.trx_tile", PRE_ROOT / "trx_tile.py"
)
trx_tile = importlib.util.module_from_spec(spec_t)
trx_tile.__package__ = "celldega.pre"
sys.modules["celldega.pre.trx_tile"] = trx_tile
spec_t.loader.exec_module(trx_tile)

make_trx_tiles = trx_tile.make_trx_tiles
make_cell_boundary_tiles = boundary_tile.make_cell_boundary_tiles


N_CELLS = 10
N_TRX = 100
TILE_SIZE = 250
BBOX = (0, 500, 0, 500)


def _build_paths(tmp_path: Path, technology: str) -> dict[str, Path]:
    """Create synthetic transcript and cell boundary data."""
    rng = np.random.default_rng(42)

    cell_boundaries = tmp_path / "cell_boundaries.parquet"
    meta_cell_path = None

    if technology == "MERSCOPE":
        polys = []
        entity_ids = []
        for i in range(N_CELLS):
            x0, y0 = rng.uniform(BBOX[0], BBOX[1]), rng.uniform(BBOX[2], BBOX[3])
            size = rng.uniform(20, 50)
            poly = Polygon(
                [
                    (x0, y0),
                    (x0 + size, y0),
                    (x0 + size, y0 + size),
                    (x0, y0 + size),
                    (x0, y0),
                ]
            )
            polys.append(poly)
            entity_ids.append(i)

        gdf = gpd.GeoDataFrame(
            {
                "EntityID": entity_ids,
                "ZIndex": [1] * N_CELLS,
                "Geometry": polys,
            },
            geometry="Geometry",
        )
        gdf.to_parquet(cell_boundaries, index=False)

        meta_cell_path = tmp_path / "meta_cell.csv"
        pd.DataFrame({"EntityID": entity_ids}).to_csv(meta_cell_path, index=False)
    else:
        records = []
        for i in range(N_CELLS):
            cell_id = f"cell_{i}"
            label_id = 1000 + i
            x0, y0 = rng.uniform(BBOX[0], BBOX[1]), rng.uniform(BBOX[2], BBOX[3])
            size = rng.uniform(20, 50)
            verts = [
                (x0, y0),
                (x0 + size, y0),
                (x0 + size, y0 + size),
                (x0, y0 + size),
                (x0, y0),
            ]
            for x, y in verts:
                records.append(
                    {
                        "cell_id": cell_id,
                        "vertex_x": x,
                        "vertex_y": y,
                        "label_id": label_id,
                    }
                )
        pd.DataFrame(records).to_parquet(cell_boundaries, index=False)

    df_meta_cell = pd.DataFrame({"name": [f"cell_{i}" for i in range(N_CELLS)]})
    df_meta_cell.to_parquet(tmp_path / "cell_metadata.parquet", index=False)

    points = [
        (rng.uniform(BBOX[0], BBOX[1]), rng.uniform(BBOX[2], BBOX[3]))
        for _ in range(N_TRX)
    ]
    genes = [f"G{i%3}" for i in range(N_TRX)]
    if technology == "MERSCOPE":
        df_trx = pl.DataFrame(
            {
                "gene": genes,
                "global_x": [p[0] for p in points],
                "global_y": [p[1] for p in points],
                "cell_id": [f"cell_{i%N_CELLS}" for i in range(N_TRX)],
                "transcript_id": list(range(N_TRX)),
            }
        )
    else:
        df_trx = pl.DataFrame(
            {
                "feature_name": genes,
                "x_location": [p[0] for p in points],
                "y_location": [p[1] for p in points],
                "cell_id": [f"cell_{i%N_CELLS}" for i in range(N_TRX)],
                "transcript_id": list(range(N_TRX)),
            }
        )
    trx_file = tmp_path / "transcripts.parquet"
    df_trx.write_parquet(trx_file)

    pd.DataFrame(index=sorted(set(genes))).to_parquet(tmp_path / "meta_gene.parquet")

    trans_path = tmp_path / "micron_to_image_transform.csv"
    np.savetxt(trans_path, np.eye(3))

    return {
        "trx": trx_file,
        "transform": trans_path,
        "boundaries": cell_boundaries,
        "meta_cell": meta_cell_path,
        "landscape": tmp_path,
        "trx_tiles": tmp_path / "transcript_tiles",
        "cell_tiles": tmp_path / "cell_segmentation",
    }


@pytest.mark.parametrize("technology", ["MERSCOPE", "Xenium"])
def test_tiles(tmp_path: Path, technology: str) -> None:
    paths = _build_paths(tmp_path, technology)

    bounds = make_trx_tiles(
        technology=technology,
        path_trx=str(paths["trx"]),
        path_transformation_matrix=str(paths["transform"]),
        path_trx_tiles=str(paths["trx_tiles"]),
        coarse_tile_factor=2,
        tile_size=TILE_SIZE,
        chunk_size=50,
        image_scale=1,
        max_workers=1,
    )

    trx_tile_files = list(paths["trx_tiles"].glob("transcripts_tile_*.parquet"))
    assert trx_tile_files, "Transcript tiles missing"
    assert bounds["x_min"] < bounds["x_max"]
    assert bounds["y_min"] < bounds["y_max"]

    expected_tiles = math.ceil((bounds["x_max"] - bounds["x_min"]) / TILE_SIZE) * math.ceil(
        (bounds["y_max"] - bounds["y_min"]) / TILE_SIZE
    )
    assert len(trx_tile_files) <= expected_tiles

    total_trx = 0
    for p in trx_tile_files:
        assert p.stat().st_size > 0
        df = pd.read_parquet(p)
        assert not df.empty
        assert "name" in df.columns and "geometry" in df.columns
        total_trx += len(df)

    assert total_trx == N_TRX

    produced_trx_tiles = {
        tuple(map(int, p.stem.split("_")[-2:])) for p in trx_tile_files
    }
    if technology == "MERSCOPE":
        df_trx = pl.read_parquet(paths["trx"]).to_pandas()
        xcol, ycol = "global_x", "global_y"
    else:
        df_trx = pl.read_parquet(paths["trx"]).to_pandas()
        xcol, ycol = "x_location", "y_location"
    for x, y in zip(df_trx[xcol], df_trx[ycol]):
        i = int((x - bounds["x_min"]) // TILE_SIZE)
        j = int((y - bounds["y_min"]) // TILE_SIZE)
        assert (i, j) in produced_trx_tiles

    make_cell_boundary_tiles(
        technology=technology,
        path_cell_boundaries=str(paths["boundaries"]),
        path_output=str(paths["cell_tiles"]),
        path_meta_cell_micron=str(paths["meta_cell"]) if technology == "MERSCOPE" else None,
        path_transformation_matrix=str(paths["transform"]),
        tile_size=TILE_SIZE,
        coarse_tile_factor=2,
        tile_bounds={"x_min": BBOX[0], "x_max": BBOX[1], "y_min": BBOX[2], "y_max": BBOX[3]},
        image_scale=1,
        max_workers=1,
    )

    cell_tile_files = list(paths["cell_tiles"].glob("cell_tile_*.parquet"))
    assert cell_tile_files, "Cell tiles missing"
    expected_cell_tiles = math.ceil((BBOX[1] - BBOX[0]) / TILE_SIZE) * math.ceil(
        (BBOX[3] - BBOX[2]) / TILE_SIZE
    )
    assert len(cell_tile_files) <= expected_cell_tiles

    all_cells = set()
    for p in cell_tile_files:
        assert p.stat().st_size > 0
        df = pd.read_parquet(p)
        assert not df.empty
        assert "geometry" in df.columns or "GEOMETRY" in df.columns
        all_cells.update(df.get("name", df.index).tolist())

    if technology == "MERSCOPE":
        df_cells = gpd.read_parquet(paths["boundaries"])
        polygons = df_cells["Geometry"]
    else:
        df_cells = pd.read_parquet(paths["boundaries"])
        polygons = (
            df_cells.groupby("cell_id")[["vertex_x", "vertex_y"]]
            .apply(lambda df: Polygon(zip(df["vertex_x"], df["vertex_y"], strict=False)))
        )

    expected_cells = sum(
        BBOX[0] <= poly.centroid.x < BBOX[1] and BBOX[2] <= poly.centroid.y < BBOX[3]
        for poly in polygons
    )
    assert len(all_cells) >= expected_cells

    produced_cell_tiles = {
        tuple(map(int, p.stem.split("_")[-2:])) for p in cell_tile_files
    }
    for poly in polygons:
        if not (
            BBOX[0] <= poly.centroid.x < BBOX[1]
            and BBOX[2] <= poly.centroid.y < BBOX[3]
        ):
            continue
        i = int((poly.centroid.x - bounds["x_min"]) // TILE_SIZE)
        j = int((poly.centroid.y - bounds["y_min"]) // TILE_SIZE)
        assert (i, j) in produced_cell_tiles
