import importlib.util
from pathlib import Path
import sys
import types

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, Polygon


# --- Dynamic Import Setup ---
ROOT_DIR = Path(__file__).resolve().parents[3]
NBHD_ROOT = ROOT_DIR / "src" / "celldega" / "nbhd"

CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)

NBHDPKG = types.ModuleType("celldega.nbhd")
NBHDPKG.__path__ = [str(NBHD_ROOT)]
sys.modules.setdefault("celldega.nbhd", NBHDPKG)

spec = importlib.util.spec_from_file_location(
    "celldega.nbhd.neighborhoods", NBHD_ROOT / "neighborhoods.py"
)
neighborhoods = importlib.util.module_from_spec(spec)
neighborhoods.__package__ = "celldega.nbhd"
sys.modules["celldega.nbhd.neighborhoods"] = neighborhoods
spec.loader.exec_module(neighborhoods)

# --- Load function ---
calc_nbp = neighborhoods.calc_nbp


# --- Fixtures and Tests ---
@pytest.fixture
def synthetic_data():
    nbhd_polys = [
        Polygon([(0, 0), (0, 10), (10, 10), (10, 0)]),
        Polygon([(10, 0), (10, 10), (20, 10), (20, 0)]),
    ]
    gdf_nbhd = gpd.GeoDataFrame({"name": ["A", "B"], "geometry": nbhd_polys}, crs="EPSG:4326")

    coords = [(1, 1)] * 6 + [(11, 1)] * 4
    clusters = ["X", "Y", "X", "X", "Y", "Y", "X", "X", "Y", "Y"]
    gdf_cells = gpd.GeoDataFrame(
        {"cluster": clusters, "geometry": [Point(xy) for xy in coords]}, crs="EPSG:4326"
    )

    return gdf_nbhd, gdf_cells


def test_calc_nbp_basic(synthetic_data):
    gdf_nbhd, gdf_cells = synthetic_data
    adata, filtered_nbhd = calc_nbp(data=gdf_cells, gdf_nbhd=gdf_nbhd)

    assert filtered_nbhd.shape[0] == 1
    assert filtered_nbhd.iloc[0]["name"] == "A"
    assert isinstance(adata, AnnData)
    assert adata.shape[0] == 1
    assert adata.shape[1] == 2
    np.testing.assert_array_equal(sorted(adata.var.index), ["X", "Y"])


def test_calc_nbp_with_anndata_input(synthetic_data):
    gdf_nbhd, gdf_cells = synthetic_data
    adata_input = AnnData(X=np.ones((gdf_cells.shape[0], 1)))
    adata_input.obsm["spatial"] = np.array([[p.x, p.y] for p in gdf_cells.geometry])
    adata_input.obs["geometry"] = gdf_cells.geometry
    adata_input.obs["leiden"] = gdf_cells["cluster"]

    adata, filtered_nbhd = calc_nbp(data=adata_input, gdf_nbhd=gdf_nbhd, category="cluster")
    assert filtered_nbhd.shape[0] == 1
    assert isinstance(adata, AnnData)


def test_calc_nbp_raises_on_missing_columns(synthetic_data):
    gdf_nbhd, gdf_cells = synthetic_data

    bad_nbhd = gdf_nbhd.drop(columns="name")
    with pytest.raises(ValueError, match="gdf_nbhd missing required columns"):
        calc_nbp(data=gdf_cells, gdf_nbhd=bad_nbhd)

    bad_cells = gdf_cells.drop(columns="cluster")
    with pytest.raises(ValueError, match="gdf_cell missing required 'geometry' or cluster column"):
        calc_nbp(data=bad_cells, gdf_nbhd=gdf_nbhd)
