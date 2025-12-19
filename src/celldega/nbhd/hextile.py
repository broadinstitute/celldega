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

    names = [f"hex_{i}" for i in range(len(hexagons))]
    gdf_hex = gpd.GeoDataFrame(
        {"name": names, "geometry": hexagons},
    )
    gdf_hex = gdf_hex.set_index("name")
    gdf_hex["name"] = names  # Keep name as both index and column

    return gdf_hex


def hextile_niche(
    gdf_hex: gpd.GeoDataFrame,
    adata_hex: "AnnData",
    category: str = "leiden",
    dissolve: bool = True,
) -> gpd.GeoDataFrame:
    """
    Create niche polygons from hextiles based on clustering results.

    Takes hexagon geometries and assigns them to niches based on clustering
    (e.g., Leiden clustering of hexagon population distributions). Optionally
    dissolves adjacent hexagons of the same niche into unified polygons.

    Parameters
    ----------
    gdf_hex : gpd.GeoDataFrame
        GeoDataFrame of hexagon geometries. Must be indexed by hexagon name
        (matching `adata_hex.obs.index`).
    adata_hex : AnnData
        AnnData object containing clustering results in `obs[category]`.
        The index must match the hexagon names in `gdf_hex`.
        Colors can be provided in `uns[f"{category}_colors"]`.
    category : str, default "leiden"
        Column name in `adata_hex.obs` containing the niche/cluster assignment.
    dissolve : bool, default True
        If True, dissolve adjacent hexagons of the same niche into unified
        MultiPolygon geometries. If False, return individual hexagons with
        their niche assignment.

    Returns
    -------
    gpd.GeoDataFrame
        If dissolve=True:
            GeoDataFrame with dissolved niche polygons.
            Columns: "name", "cat", "geometry", "color", "area".
        If dissolve=False:
            GeoDataFrame with individual hexagons and niche assignment.
            Columns: "name", "cat", "geometry", "color".

    Examples
    --------
    >>> # Generate hexagons and compute population distribution
    >>> gdf_hex = dega.nbhd.generate_hextile(adata, diameter=100)
    >>> adata_hex = dega.nbhd.calc_nbhd_by_pop(adata, gdf_hex, category="leiden")
    >>>
    >>> # Cluster hexagons by population similarity (e.g., using scanpy)
    >>> import scanpy as sc
    >>> sc.pp.pca(adata_hex)
    >>> sc.pp.neighbors(adata_hex)
    >>> sc.tl.leiden(adata_hex)
    >>>
    >>> # Create dissolved niche polygons
    >>> gdf_niche = dega.nbhd.hextile_niche(gdf_hex, adata_hex, category="leiden")
    >>>
    >>> # Or keep individual hexagons with niche assignment
    >>> gdf_hex_niche = dega.nbhd.hextile_niche(gdf_hex, adata_hex, dissolve=False)
    """
    # Validate inputs
    if category not in adata_hex.obs.columns:
        raise ValueError(f"adata_hex.obs missing '{category}' column")

    # Get niche assignments aligned with hexagon index
    hex_names = gdf_hex.index.tolist()
    adata_names = adata_hex.obs.index.tolist()

    # Check alignment
    common_names = set(hex_names) & set(adata_names)
    if len(common_names) == 0:
        raise ValueError("No matching names between gdf_hex index and adata_hex.obs.index")

    # Filter to common hexagons
    gdf_result = gdf_hex.loc[gdf_hex.index.isin(common_names)].copy()
    niche_values = adata_hex.obs.loc[gdf_result.index, category].astype(str)
    gdf_result["cat"] = niche_values.values

    # Get colors from adata.uns if available
    color_key = f"{category}_colors"
    color_dict: dict[str, str] = {}
    if color_key in adata_hex.uns:
        src_colors = adata_hex.uns[color_key]
        if hasattr(adata_hex.obs[category], "cat"):
            src_categories = list(adata_hex.obs[category].cat.categories.astype(str))
        else:
            src_categories = sorted(adata_hex.obs[category].unique().astype(str))

        color_dict = {
            str(cat): src_colors[i] for i, cat in enumerate(src_categories) if i < len(src_colors)
        }

    # Assign colors
    gdf_result["color"] = [color_dict.get(c, "#808080") for c in gdf_result["cat"]]

    if dissolve:
        # Dissolve hexagons by niche category
        gdf_dissolved = gdf_result.dissolve(by="cat", as_index=False)

        # Clean up and add metadata
        gdf_dissolved["name"] = gdf_dissolved["cat"]
        gdf_dissolved["area"] = gdf_dissolved.geometry.area

        # Reorder columns
        return gdf_dissolved[["name", "cat", "geometry", "color", "area"]]

    # Return individual hexagons with niche assignment
    gdf_result = gdf_result.reset_index()
    return gdf_result[["name", "cat", "geometry", "color"]]
