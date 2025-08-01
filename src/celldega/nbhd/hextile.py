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
    nbhd_type: str,
    radius: float = 75,
    path_landscape_files: str = None
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Prepare nbhd geometries for clustering based on cell type composition.
    Also returns cell-type proportions in each nbhd."""
    import pandas as pd
    from .neighborhoods import calc_nbp
    from .utils import _get_df_cell, _get_gdf_cell
    from .alpha_shapes import alpha_shape_cell_clusters
    from .gradient import calc_grad_nbhd_from_roi

    if not isinstance(adata, AnnData):
        raise TypeError("adata must be an AnnData object")

    if nbhd_type == 'HEX':
        gdf_object = _get_gdf_cell(adata)
        gdf_nbhd = generate_hex_grid(gdf_object, radius=radius)

    elif nbhd_type == 'ALPH':
        alphas_list = range(30, 60, 5)
        gdf_object = alpha_shape_cell_clusters(adata, cat='cluster', alphas=alphas_list)
        gdf_nbhd = gdf_object.loc[gdf_object['inv_alpha']==35]

    elif nbhd_type == 'SKTCH':
        gdf_nbhd = gpd.read_parquet(f'{path_landscape_files}/spatial_regions/sketched_regions_micron.parquet')
        gdf_nbhd['name'] = gdf_nbhd['roi']

    elif nbhd_type == 'GRAD':
        gdf_object = _get_gdf_cell(adata)
        gdf_micron = gpd.read_parquet(f'{path_landscape_files}/spatial_regions/sketched_regions_micron.parquet')
        gdf_roi = gdf_micron.loc[gdf_micron['roi'] == 'region_1']
        gdf_nbhd = calc_grad_nbhd_from_roi(gdf_roi, gdf_object, 200)
        gdf_nbhd['name'] = gdf_nbhd['band']

    # Calculate cell-type counts per nbhd tile
    counts, population_distribution = calc_nbp(gdf_object, gdf_nbhd)

    # Prepare AnnData for clustering
    ad_tiles = AnnData(
        X=population_distribution.values,
        obs=pd.DataFrame(index=population_distribution.index),
        var=pd.DataFrame(index=population_distribution.columns),
    )

    return ad_tiles, gdf_nbhd