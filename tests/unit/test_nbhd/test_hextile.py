import io

from anndata import AnnData
import numpy as np
import pandas as pd

from celldega.nbhd import generate_hextile


def _toy_adata():
    """Small AnnData with spatial coordinates in obsm['spatial']."""
    data_string = """cell_id\tcluster\tx\ty
aaaadnje-1\t4\t446.32669\t1701.35730
aaacalai-1\t4\t441.30783\t1735.87793
aaacjgil-1\t4\t466.05319\t1712.25977
aaacpcil-1\t4\t430.85809\t1707.46460
aaadhocp-1\t4\t476.11115\t1711.08936
oilopeok-1\t10\t6035.77051\t644.97339
oiloppgp-1\t5\t6082.67578\t555.14288
oimacfoj-1\t5\t6080.99121\t626.74213
oimaiaae-1\t10\t6030.59473\t536.50342
oimajkkk-1\t5\t6022.63721\t573.78430"""

    df = pd.read_csv(io.StringIO(data_string), sep="\t", index_col=0)
    adata = AnnData(X=np.zeros((len(df), 1), dtype="float32"), obs=df[["cluster"]].astype(str))
    adata.obsm["spatial"] = df[["x", "y"]].to_numpy()
    return adata


def test_hextile():
    """generate_hextile tiles the spatial bounding box with hexagons."""
    adata = _toy_adata()
    gdf_nbhd = generate_hextile(adata, diameter=800)

    # Deterministic count for this bounding box / diameter.
    assert len(gdf_nbhd) == 44
    assert {"name", "geometry"}.issubset(gdf_nbhd.columns)
    # Names are hex_0, hex_1, ... and every geometry is a hexagonal polygon.
    assert gdf_nbhd["name"].str.startswith("hex_").all()
    assert (gdf_nbhd.geometry.geom_type == "Polygon").all()
