"""Module for hexatile computing."""

from typing import TYPE_CHECKING

import geopandas as gpd
import numpy as np
from shapely.affinity import translate
from shapely.geometry import Polygon

if TYPE_CHECKING:
    from anndata import AnnData


def generate_hextile(
    adata: "AnnData",
    diameter: float = 100,
) -> gpd.GeoDataFrame:
    """
    Generate a hexagonal grid over the bounding box of cell spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        AnnData object with spatial coordinates in `obsm["spatial"]`.
    diameter : float, default 100
        Diameter of each hexagon in the same units as the spatial coordinates
        (typically microns).

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with hexagon geometries covering the spatial extent.
        Columns: "name" (hex_0, hex_1, ...), "geometry" (Polygon).

    Examples
    --------
    >>> gdf_hex = dega.nbhd.generate_hextile(adata, diameter=100)
    >>> gdf_hex.shape
    (1234, 2)
    """
    # Get bounding box directly from spatial coordinates
    coords = adata.obsm["spatial"]
    minx, miny = coords[:, 0].min(), coords[:, 1].min()
    maxx, maxy = coords[:, 0].max(), coords[:, 1].max()

    radius = diameter / 2
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
            hexagons.append(hex_tile)

    return gpd.GeoDataFrame(
        {"name": [f"hex_{i}" for i in range(len(hexagons))], "geometry": hexagons},
    )
