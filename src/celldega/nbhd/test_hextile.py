import io

import geopandas as gpd
import pandas as pd

from . import generate_hex_grid


def test_hextile():
    """Test the hextile generation."""
    data_string = """cell_id	cluster	geometry
    aaaadnje-1	4	POINT (446.32669 1701.35730)
    aaacalai-1	4	POINT (441.30783 1735.87793)
    aaacjgil-1	4	POINT (466.05319 1712.25977)
    aaacpcil-1	4	POINT (430.85809 1707.46460)
    aaadhocp-1	4	POINT (476.11115 1711.08936)
    oilopeok-1	10	POINT (6035.77051 644.97339)
    oiloppgp-1	5	POINT (6082.67578 555.14288)
    oimacfoj-1	5	POINT (6080.99121 626.74213)
    oimaiaae-1	10	POINT (6030.59473 536.50342)
    oimajkkk-1	5	POINT (6022.63721 573.78430)
    """

    df = pd.read_csv(io.StringIO(data_string), sep="\t", index_col=0)
    gdf_cell = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df["geometry"]))
    gdf_nbhd = generate_hex_grid(gdf_cell, radius=200)  # fedault=50

    assert len(gdf_nbhd) == 28
