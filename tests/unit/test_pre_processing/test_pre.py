import pytest
import pandas as pd
import numpy as np
import geopandas as gpd
from pathlib import Path
import shutil

try:
    from celldega.pre.boundary_tile import make_cell_boundary_tiles
    from celldega.pre.trx_tile import make_trx_tiles
except ImportError:
    pytest.skip("celldega module not available", allow_module_level=True)

SCRIPT_DIR = Path(__file__).parent.resolve()


def create_vertex_style_cell_boundaries(path, n_cells=10, min_size=20, max_size=50):
    """Generate vertex-style cell boundary data and save as Parquet."""
    records = []
    for i in range(n_cells):
        cell_id = f"cell_{i}"
        label_id = 1000 + i
        x0, y0 = np.random.uniform(0, 500), np.random.uniform(0, 500)
        size = np.random.uniform(min_size, max_size)
        vertices = [
            (x0, y0),
            (x0 + size, y0),
            (x0 + size, y0 + size),
            (x0, y0 + size),
            (x0, y0)
        ]
        for x, y in vertices:
            records.append({
                "cell_id": cell_id,
                "vertex_x": x,
                "vertex_y": y,
                "label_id": label_id
            })
    df = pd.DataFrame(records)
    df.to_parquet(path, index=False)
    return df


def create_identity_matrix_csv(path, size=3):
    """Save a square identity matrix as a space-delimited CSV."""
    identity = np.identity(size)
    np.savetxt(path, identity, fmt="%.1f", delimiter=" ")


@pytest.fixture
def tile_test_environment_with_metadata():
    """
    Prepare synthetic boundary input + identity matrix + metadata.
    Uses ./test_output directory which will be deleted after test.
    """
    workspace_dir = SCRIPT_DIR / "test_output"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    landscape_dir = workspace_dir / "landscape"
    cell_segmentation_dir = landscape_dir / "cell_segmentation"
    output_dir = cell_segmentation_dir
    input_file = workspace_dir / "cell_boundaries.parquet"
    matrix_file = workspace_dir / "identity_transform.csv"

    df = create_vertex_style_cell_boundaries(input_file)
    cell_metadata = pd.DataFrame({"name": df["cell_id"].unique()})
    landscape_dir.mkdir(parents=True, exist_ok=True)
    cell_metadata.to_parquet(landscape_dir / "cell_metadata.parquet", index=False)

    meta_gene = pd.DataFrame(index=["Actb", "Gapdh", "Snap25"])
    meta_gene.to_parquet(landscape_dir / "meta_gene.parquet")

    create_identity_matrix_csv(matrix_file)

    return {
        "workspace_dir": workspace_dir,
        "input_file": input_file,
        "output_dir": output_dir,
        "matrix_file": matrix_file,
        "tile_bounds": {
            "x_min": 0,
            "x_max": 500,
            "y_min": 0,
            "y_max": 500
        }
    }


def test_make_cell_boundary_tiles_with_identity_matrix(tile_test_environment_with_metadata):
    env = tile_test_environment_with_metadata

    make_cell_boundary_tiles(
        technology="Xenium",
        path_cell_boundaries=env["input_file"],
        path_output=str(env["output_dir"]),
        path_meta_cell_micron=None,
        path_transformation_matrix=env["matrix_file"],
        tile_bounds=env["tile_bounds"],
        tile_size=250,
        coarse_tile_factor=2,
        image_scale=1,
        max_workers=2
    )

    output_files = list(env["output_dir"].glob("*.parquet"))
    assert len(output_files) > 0, "No tile output files were created."

    for path in output_files:
        df = pd.read_parquet(path)
        assert not df.empty
        assert "geometry" in df.columns or "GEOMETRY" in df.columns

    shutil.rmtree(env["workspace_dir"])


def create_xenium_style_transcripts(path, n=100, genes=None):
    """Create a Xenium-style transcript file and save as Parquet."""
    if genes is None:
        genes = ["EPCAM", "Gapdh", "ARFGEF3", "TFPI", "GPRC5A", "VCAN"]
    df = pd.DataFrame({
        "transcript_id": [str(1000000000000000 + i) for i in range(n)],
        "cell_id": [f"cell-{i % 5}" for i in range(n)],
        "overlaps_nucleus": np.random.choice([0, 1], n),
        "feature_name": np.random.choice(genes, n),
        "x_location": np.random.uniform(0, 500, n),
        "y_location": np.random.uniform(0, 500, n),
        "z_location": np.random.uniform(10, 25, n),
        "qv": np.full(n, 40.0),
        "fov_name": np.random.choice(["P12", "Q13", "R5"], n),
        "nucleus_distance": np.random.exponential(1.5, n),
        "codeword_index": np.random.randint(100, 400, n)
    })
    df.to_parquet(path, index=False)
    return df


@pytest.fixture
def trx_test_environment():
    """
    Prepare synthetic transcript data, meta_gene file, and transform matrix.
    Uses ./test_output_trx which is removed after test.
    """
    trx_dir = SCRIPT_DIR / "test_output_trx"
    trx_dir.mkdir(exist_ok=True)

    trx_file = trx_dir / "transcripts.parquet"
    transform_file = trx_dir / "identity_transform.csv"
    meta_gene_file = trx_dir / "meta_gene.parquet"
    output_dir = trx_dir / "transcript_tiles"
    output_dir.mkdir(exist_ok=True)

    genes = ["Actb", "Gapdh", "Snap25"]
    df = create_xenium_style_transcripts(trx_file, n=100, genes=genes)

    meta_gene_df = pd.DataFrame(index=pd.Index(genes, name="name"))
    meta_gene_df.to_parquet(meta_gene_file)

    create_identity_matrix_csv(transform_file)

    return {
        "trx_file": trx_file,
        "transform_file": transform_file,
        "meta_gene_file": meta_gene_file,
        "output_dir": output_dir,
        "workspace_dir": trx_dir,
    }


def test_make_trx_tiles_with_identity_matrix(trx_test_environment):
    env = trx_test_environment

    result = make_trx_tiles(
        technology="Xenium",
        path_trx=str(env["trx_file"]),
        path_transformation_matrix=str(env["transform_file"]),
        path_trx_tiles=str(env["output_dir"]),
        tile_size=250,
        coarse_tile_factor=2,
        image_scale=1,
        max_workers=2
    )

    assert "x_min" in result and "x_max" in result
    assert "y_min" in result and "y_max" in result
    assert result["x_max"] > result["x_min"]
    assert result["y_max"] > result["y_min"]

    output_files = list(env["output_dir"].glob("*.parquet"))
    assert len(output_files) > 0, "No transcript tile files were created."

    for path in output_files:
        df = pd.read_parquet(path)
        assert not df.empty
        assert "name" in df.columns and "geometry" in df.columns

    shutil.rmtree(env["workspace_dir"])
