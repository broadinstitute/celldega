"""Module for hexatile computing."""

from anndata import AnnData
import geopandas as gpd
import numpy as np
from shapely.affinity import translate
from shapely.geometry import Polygon


def generate_hex_grid(
    gdf_cell: gpd.GeoDataFrame,
    radius: float = 20,
) -> gpd.GeoDataFrame:
    """Generate a hexagonal grid over the convex hull of a GeoDataFrame."""
    bounding_geom = gdf_cell.unary_union.convex_hull
    minx, miny, maxx, maxy = bounding_geom.bounds

    dx = np.sqrt(3) * radius
    dy = 1.5 * radius

    angles_deg = [30 + i * 60 for i in range(6)]
    angles_rad = [np.radians(a) for a in angles_deg]
    unit_hex = Polygon([(radius * np.cos(a), radius * np.sin(a)) for a in angles_rad])

    n_cols = int((maxx - minx) / dx) + 3
    n_rows = int((maxy - miny) / dy) + 3

    hexagons = []
    for row in range(n_rows):
        for col in range(n_cols):
            x = col * dx
            y = row * dy
            if row % 2 == 1:
                x += dx / 2
            hex_tile = translate(unit_hex, xoff=x + minx - dx, yoff=y + miny - dy)
            if hex_tile.intersects(bounding_geom):
                hexagons.append(hex_tile)

    return gpd.GeoDataFrame(
        {"name": [f"hex_{i}" for i in range(len(hexagons))], "geometry": hexagons},
        crs=gdf_cell.crs,
    )


def cluster_hex_tiles_leiden(
    adata: AnnData,
    radius: float = 20,
    resolution: float = 1.0,
    n_neighbors: int = 15,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Cluster hexagon tiles based on cell type composition using Leiden."""
    import pandas as pd
    import scanpy as sc

    from .neighborhoods import calc_nbp
    from .utils import _get_gdf_cell

    if not isinstance(adata, AnnData):
        raise TypeError("adata must be an AnnData object")

    gdf_cell = _get_gdf_cell(adata)
    gdf_hex = generate_hex_grid(gdf_cell, radius=radius)

    counts, _ = calc_nbp(gdf_cell, gdf_hex)
    counts = counts.fillna(0)

    ad_tiles = AnnData(
        X=counts.values,
        obs=pd.DataFrame(index=counts.index),
        var=pd.DataFrame(index=counts.columns),
    )

    n_neighbors = min(n_neighbors, max(1, len(gdf_hex) - 1))
    sc.pp.neighbors(ad_tiles, n_neighbors=n_neighbors)
    sc.tl.leiden(ad_tiles, resolution=resolution, key_added="leiden")

    gdf_hex = gdf_hex.set_index("name")
    gdf_hex["leiden"] = ad_tiles.obs["leiden"].values
    gdf_hex.reset_index(inplace=True)

    gdf_niche = gdf_hex.dissolve(by="leiden", as_index=False)
    gdf_niche["name"] = [f"niche_{c}" for c in gdf_niche["leiden"]]

    return gdf_niche[["name", "geometry"]], gdf_hex
