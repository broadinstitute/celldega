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

def create_cell_polygon(df: pd.DataFrame) -> Polygon:
    """
    Constructs a Shapely Polygon from a DataFrame containing 'vertex_x' and 'vertex_y' columns.

    This function is intended to be used with groupby().apply() on a DataFrame where each group
    represents the vertices of a single cell boundary. It validates that the input contains at least
    three coordinate pairs before creating the polygon.

    Parameters:
        df (pd.DataFrame): A DataFrame with 'vertex_x' and 'vertex_y' columns for one cell.

    Returns:
        shapely.geometry.Polygon: A polygon representing the cell boundary.

    Raises:
        ValueError: If fewer than three coordinate pairs are provided.
        KeyError: If 'vertex_x' or 'vertex_y' columns are missing.
    """
    required_columns = {"vertex_x", "vertex_y"}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise KeyError(f"Missing required columns: {', '.join(missing)}")

    if len(df) < 3:
        raise ValueError("At least three vertices are required to construct a polygon.")

    return Polygon(zip(df["vertex_x"], df["vertex_y"]))

@pytest.fixture
def make_synthetic_data(tmp_path):
    def _make(technology):
        return _generate_synthetic_data(tmp_path, technology)
    return _make

def _generate_synthetic_data(tmp_path: Path, technology: str) -> dict[str, Path]:

    """
    Generate synthetic spatial transcriptomics data for testing purposes.

    This function creates synthetic cell boundary data, transcript data, gene metadata,
    and transformation matrices. It supports multiple input formats depending on the
    specified `technology` and writes the generated data to the given temporary path.

    Args:
        tmp_path (Path): Directory path where synthetic data files will be written.
        technology (str): The spatial transcriptomics technology name.
                         Supported: "MERSCOPE" or "Xenium"

    Returns:
        dict[str, Path]: A dictionary mapping data types to the corresponding file paths:
            - 'trx_path': Path to transcript data (.parquet)
            - 'transform_path': Path to the 3x3 identity transform CSV
            - 'boundaries_path': Path to cell boundary data (.parquet)
            - 'meta_cell_path': Path to meta cell CSV (only for MERSCOPE)
            - 'landscape_path': Path to Landscape Files directory
            - 'trx_tiles_path': Placeholder path for transcript tiles
            - 'cell_tiles_path': Placeholder path for cell segmentation tiles

    Notes:
        - Geometry data is stored as Shapely polygons (GeoDataFrame) for MERSCOPE.
        - For Xenium, boundaries are represented as vertex tables.
        - Transcript fields differ slightly based on the technology.
        - Metadata files for cells and genes are also created.
    """

    rng = np.random.default_rng(42)

    cell_boundaries_path = tmp_path / "cell_boundaries.parquet"
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
        gdf.to_parquet(cell_boundaries_path, index=False)

        meta_cell_path = tmp_path / "meta_cell.csv"
        pd.DataFrame({"EntityID": entity_ids}).to_csv(meta_cell_path, index=False)

    elif technology == "Xenium":
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
        pd.DataFrame(records).to_parquet(cell_boundaries_path, index=False)

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
    elif technology == "Xenium":
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
        "trx_path": trx_file,
        "transform_path": trans_path,
        "boundaries_path": cell_boundaries_path,
        "meta_cell_path": meta_cell_path,
        "landscape_path": tmp_path,
        "trx_tiles_path": tmp_path / "transcript_tiles",
        "cell_tiles_path": tmp_path / "cell_segmentation",
    }


@pytest.mark.parametrize("technology", ["MERSCOPE", "Xenium"])
def test_tiles(make_synthetic_data, technology) -> None:
    """
    Unit test for verifying the correctness of transcript and cell boundary tiling.

    This test performs an end-to-end simulation of spatial transcriptomics data tiling.
    It verifies that:
        - Transcript data is correctly split into spatial tiles.
        - Tile boundaries are well-formed and consistent.
        - All transcripts are represented in the output.
        - Cell boundaries are correctly tiled based on centroids.
        - Cell geometry and metadata are preserved and valid across tiles.

    The function supports multiple technologies (e.g., MERSCOPE, Xenium),
    each of which may differ slightly in file format or metadata layout.

    Args:
        tmp_path (Path): Temporary output directory for synthetic test files.
        technology (str): Name of the spatial transcriptomics technology.
    """
    # Step 1: Generate synthetic input data
    paths = make_synthetic_data(technology)

    # Step 2: Tile the transcript data into fixed-size square tiles
    bounds = make_trx_tiles(
        technology=technology,
        path_trx=str(paths["trx_path"]),
        path_transformation_matrix=str(paths["transform_path"]),
        path_trx_tiles=str(paths["trx_tiles_path"]),
        coarse_tile_factor=2,
        tile_size=TILE_SIZE,
        chunk_size=50,
        image_scale=1,
        max_workers=1,
    )

    # Verify transcript tile outputs: file presence and bounding box logic
    trx_tile_files = list(paths["trx_tiles_path"].glob("transcripts_tile_*.parquet"))
    assert trx_tile_files, "Transcript tiles missing"
    assert bounds["x_min"] < bounds["x_max"]
    assert bounds["y_min"] < bounds["y_max"]

    # Verify the number of transcript tiles does not exceed the theoretical maximum
    expected_tiles = math.ceil((bounds["x_max"] - bounds["x_min"]) / TILE_SIZE) * math.ceil(
        (bounds["y_max"] - bounds["y_min"]) / TILE_SIZE
    )
    assert len(trx_tile_files) <= expected_tiles

    # Validate each transcript tile: non-empty, expected schema, and count transcripts
    total_trx = 0
    for p in trx_tile_files:
        assert p.stat().st_size > 0
        df = pd.read_parquet(p)
        assert not df.empty
        assert "name" in df.columns and "geometry" in df.columns
        total_trx += len(df)

    # Ensure total number of transcripts matches the expected synthetic count
    assert total_trx == N_TRX

    # Step 3: Ensure that every transcript maps to one of the generated transcript tile coordinates
    produced_trx_tiles = {
        tuple(map(int, p.stem.split("_")[-2:])) for p in trx_tile_files
    }

    if technology == "MERSCOPE":
        df_trx = pl.read_parquet(paths["trx_path"]).to_pandas()
        xcol, ycol = "global_x", "global_y"
    elif technology == "Xenium":
        df_trx = pl.read_parquet(paths["trx_path"]).to_pandas()
        xcol, ycol = "x_location", "y_location"

    for x, y in zip(df_trx[xcol], df_trx[ycol]):
        i = int((x - bounds["x_min"]) // TILE_SIZE)
        j = int((y - bounds["y_min"]) // TILE_SIZE)
        assert (i, j) in produced_trx_tiles

    # Step 4: Tile the cell boundaries based on centroid position and technology-specific format
    make_cell_boundary_tiles(
        technology=technology,
        path_cell_boundaries=str(paths["boundaries_path"]),
        path_output=str(paths["cell_tiles_path"]),
        path_meta_cell_micron=str(paths["meta_cell_path"]) if technology == "MERSCOPE" else None,
        path_transformation_matrix=str(paths["transform_path"]),
        tile_size=TILE_SIZE,
        coarse_tile_factor=2,
        tile_bounds={"x_min": BBOX[0], "x_max": BBOX[1], "y_min": BBOX[2], "y_max": BBOX[3]},
        image_scale=1,
        max_workers=1,
    )

    # Verify output cell tile files exist and are within expected count
    cell_tile_files = list(paths["cell_tiles_path"].glob("cell_tile_*.parquet"))
    assert cell_tile_files, "Cell tiles missing"
    expected_cell_tiles = math.ceil((BBOX[1] - BBOX[0]) / TILE_SIZE) * math.ceil(
        (BBOX[3] - BBOX[2]) / TILE_SIZE
    )
    assert len(cell_tile_files) <= expected_cell_tiles

    # Collect cell names from all cell tile files, ensuring data is present and valid
    all_cells = set()
    for p in cell_tile_files:
        assert p.stat().st_size > 0
        df = pd.read_parquet(p)
        assert not df.empty
        assert "geometry" in df.columns or "GEOMETRY" in df.columns
        all_cells.update(df.get("name", df.index).tolist())

    # Step 5: Load and re-compute expected polygons from the full boundary dataset
    if technology == "MERSCOPE":
        df_cells = gpd.read_parquet(paths["boundaries_path"])
        polygons = df_cells["Geometry"]
    elif technology == "Xenium":
        df_cells = pd.read_parquet(paths["boundaries_path"])
        polygons = (
            df_cells.groupby("cell_id")[["vertex_x", "vertex_y"]]
            .apply(create_cell_polygon)
        )

    # Count how many cells have centroids that fall within the image bounding box
    expected_cells = sum(
        BBOX[0] <= poly.centroid.x < BBOX[1] and BBOX[2] <= poly.centroid.y < BBOX[3]
        for poly in polygons
    )
    assert len(all_cells) >= expected_cells

    # Verify that each expected cell polygon maps to a cell tile by centroid location
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