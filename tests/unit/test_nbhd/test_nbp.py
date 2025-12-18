import importlib.util
from pathlib import Path
import sys
import types

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon


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
    """Create synthetic neighborhood and cell data for testing."""
    nbhd_polys = [
        Polygon([(0, 0), (0, 10), (10, 10), (10, 0)]),
        Polygon([(10, 0), (10, 10), (20, 10), (20, 0)]),
    ]
    gdf_nbhd = gpd.GeoDataFrame({"name": ["A", "B"], "geometry": nbhd_polys})

    # Create AnnData with spatial coordinates
    # 6 cells in neighborhood A, 4 cells in neighborhood B
    coords = [(1, 1)] * 6 + [(11, 1)] * 4
    clusters = ["X", "Y", "X", "X", "Y", "Y", "X", "X", "Y", "Y"]

    adata = AnnData(X=np.ones((len(coords), 1)))
    adata.obsm["spatial"] = np.array(coords)
    adata.obs["leiden"] = clusters

    return gdf_nbhd, adata


def test_calc_nbp_basic(synthetic_data):
    """Test basic calc_nbp functionality with AnnData input."""
    gdf_nbhd, adata = synthetic_data

    # Only neighborhood A has >= 5 cells (min_cells default)
    adata_nbp = calc_nbp(adata, gdf_nbhd, category="leiden")

    # Should only include neighborhood A (has 6 cells, B only has 4)
    assert adata_nbp.shape[0] == 1, "Only 1 neighborhood should pass min_cells filter"
    assert "A" in adata_nbp.obs.index, "Neighborhood A should be included"
    assert isinstance(adata_nbp, AnnData)
    assert adata_nbp.shape[1] == 2, "Should have 2 categories (X and Y)"
    np.testing.assert_array_equal(sorted(adata_nbp.var.index), ["X", "Y"])

    # Check filtered gdf is stored in uns
    assert "gdf_nbhd" in adata_nbp.uns
    filtered_nbhd = adata_nbp.uns["gdf_nbhd"]
    assert filtered_nbhd.shape[0] == 1
    assert filtered_nbhd.iloc[0]["name"] == "A"


def test_calc_nbp_with_lower_min_cells(synthetic_data):
    """Test calc_nbp with lower min_cells threshold to include both neighborhoods."""
    gdf_nbhd, adata = synthetic_data

    # Lower min_cells to 3 so both neighborhoods are included
    adata_nbp = calc_nbp(adata, gdf_nbhd, category="leiden", min_cells=3)

    assert adata_nbp.shape[0] == 2, "Both neighborhoods should be included"
    assert isinstance(adata_nbp, AnnData)


def test_calc_nbp_raises_on_missing_columns(synthetic_data):
    """Test that calc_nbp raises appropriate errors for missing columns."""
    gdf_nbhd, adata = synthetic_data

    # Test missing nbhd_col in gdf_nbhd
    bad_nbhd = gdf_nbhd.drop(columns="name")
    with pytest.raises(ValueError, match="gdf_nbhd missing required columns"):
        calc_nbp(adata, bad_nbhd, category="leiden")

    # Test missing category in adata.obs
    bad_adata = adata.copy()
    del bad_adata.obs["leiden"]
    with pytest.raises(ValueError, match="adata.obs missing required 'leiden' column"):
        calc_nbp(bad_adata, gdf_nbhd, category="leiden")

    # Test missing spatial coordinates
    bad_adata2 = adata.copy()
    del bad_adata2.obsm["spatial"]
    with pytest.raises(ValueError, match="adata.obsm missing 'spatial' coordinates"):
        calc_nbp(bad_adata2, gdf_nbhd, category="leiden")
