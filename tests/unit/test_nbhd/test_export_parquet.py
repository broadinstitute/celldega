import pytest

try:
    import geopandas as gpd
    from shapely.geometry import Polygon
    from anndata import AnnData
    from celldega.nbhd.neighborhoods import NBHD
except Exception as e:  # pragma: no cover - if deps missing skip
    pytest.skip(f"celldega modules unavailable: {e}", allow_module_level=True)


def test_export_parquet_returns_bytes():
    gdf = gpd.GeoDataFrame({
        "name": ["a"],
        "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
    })
    ad = AnnData()
    nb = NBHD(gdf, nbhd_type="hex", adata=ad, data_dir="", path_landscape_files="")
    data = nb.export_parquet()
    assert isinstance(data, (bytes, bytearray))
    assert data
