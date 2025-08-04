import importlib.util
import io
from pathlib import Path
import sys
import types

from anndata import AnnData
import geopandas as gpd
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[3]
NBHD_ROOT = ROOT_DIR / "src" / "celldega" / "nbhd"

CELLPKG = types.ModuleType("celldega")
CELLPKG.__path__ = [str(ROOT_DIR / "src" / "celldega")]
sys.modules.setdefault("celldega", CELLPKG)
NBHDPKG = types.ModuleType("celldega.nbhd")
NBHDPKG.__path__ = [str(NBHD_ROOT)]
sys.modules.setdefault("celldega.nbhd", NBHDPKG)

spec = importlib.util.spec_from_file_location("celldega.nbhd.hextile", NBHD_ROOT / "hextile.py")
hextile = importlib.util.module_from_spec(spec)
hextile.__package__ = "celldega.nbhd"
sys.modules["celldega.nbhd.hextile"] = hextile
spec.loader.exec_module(hextile)
cluster_hex_tiles_leiden = hextile.cluster_hex_tiles_leiden


def test_cluster_hex_tiles_leiden_basic():
    data_string = """cell_id\tcluster\tgeometry
    aaaadnje-1\t4\tPOINT (446.32669 1701.35730)
    aaacalai-1\t4\tPOINT (441.30783 1735.87793)
    aaacjgil-1\t4\tPOINT (466.05319 1712.25977)
    aaacpcil-1\t4\tPOINT (430.85809 1707.46460)
    aaadhocp-1\t4\tPOINT (476.11115 1711.08936)
    oilopeok-1\t10\tPOINT (6035.77051 644.97339)
    oiloppgp-1\t5\tPOINT (6082.67578 555.14288)
    oimacfoj-1\t5\tPOINT (6080.99121 626.74213)
    oimaiaae-1\t10\tPOINT (6030.59473 536.50342)
    oimajkkk-1\t5\tPOINT (6022.63721 573.78430)
    """

    df = pd.read_csv(io.StringIO(data_string), sep="\t", index_col=0)
    points = gpd.GeoSeries.from_wkt(df["geometry"])
    adata = AnnData(np.zeros((len(df), 1)))
    adata.obs["leiden"] = df["cluster"].astype(str)
    adata.obsm["spatial"] = np.vstack([points.x, points.y]).T

    gdf_niche, gdf_hex = cluster_hex_tiles_leiden(adata, radius=200, resolution=0.5, n_neighbors=5)

    assert len(gdf_hex) > 0
    assert len(gdf_niche) <= len(gdf_hex)
    assert {"name", "geometry"}.issubset(gdf_niche.columns)
