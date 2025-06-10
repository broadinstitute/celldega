"""Module for hexatile computing."""

import geopandas as gpd
import numpy as np
from shapely.affinity import translate
from shapely.geometry import Polygon


def generate_hex_grid(
    gdf_cell: gpd.GeoDataFrame,
    radius: float = 20,
) -> gpd.GeoDataFrame:
    """
    Generate a hexagonal grid over the convex hull of a GeoDataFrame using affine translation.
    """
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
        {
            "name": [f"hex_{i}" for i in range(len(hexagons))],
            "geometry": hexagons,
        },
        crs=gdf_cell.crs,
    )
