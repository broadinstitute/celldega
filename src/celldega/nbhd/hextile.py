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


def prepare_nbhd_for_clustering(
    adata: AnnData,
    radius: float = 75,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Prepare nbhd geometries for clustering based on cell type composition.
    Also returns cell-type proportions in each tile."""
    import pandas as pd
    from .neighborhoods import calc_nbp
    from .utils import _get_gdf_cell

    if not isinstance(adata, AnnData):
        raise TypeError("adata must be an AnnData object")

    gdf_cell = _get_gdf_cell(adata)
    gdf_hex = generate_hex_grid(gdf_cell, radius=radius)

    # Calculate cell-type counts per hex tile
    counts, population_distribution = calc_nbp(gdf_cell, gdf_hex)

    # Prepare AnnData for clustering
    ad_tiles = AnnData(
        X=population_distribution.values,
        obs=pd.DataFrame(index=population_distribution.index),
        var=pd.DataFrame(index=population_distribution.columns),
    )

    return ad_tiles, gdf_hex