"""Module for gradient polygon(s) generation."""

import geopandas as gpd


def calc_grad_nbhd_from_roi(
    polygon: gpd.GeoDataFrame,
    gdf_reference: gpd.GeoDataFrame,
    band_width: float = 300,
) -> gpd.GeoDataFrame:
    """
    Generate concentric rings (neighborhood bands) from a polygon,
    clipped to the convex hull of a reference GeoDataFrame.

    Parameters
    ----------
    polygon : GeoDataFrame
        GeoDataFrame containing a single polygon.
    gdf_reference : GeoDataFrame
        Reference GeoDataFrame used to calculate the boundary area (convex hull).
    band_width : float
        Width of each band in microns (default: 300).

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with columns for band (index of ring) and geometry (polygon).
    """
    if len(polygon) != 1:
        raise ValueError("Input polygon GeoDataFrame must contain exactly one polygon.")

    roi_polygon = polygon.geometry.iloc[0]
    boundary = gdf_reference.unary_union.convex_hull

    bands = []
    current_polygon = roi_polygon
    band_idx = 0

    # Add the original polygon as band 0
    bands.append({"band": f"grad_{band_idx}", "geometry": roi_polygon})

    while True:
        band_idx += 1
        # Generate next ring
        next_buffer = current_polygon.buffer(band_width)
        ring = next_buffer.difference(current_polygon)

        # Clip the ring to the convex hull boundary
        ring_clipped = ring.intersection(boundary)

        # Stop if no part of the ring remains within boundary
        if ring_clipped.is_empty:
            break

        bands.append({"band": f"grad_{band_idx}", "geometry": ring_clipped})
        current_polygon = next_buffer

    gdf = gpd.GeoDataFrame(bands, crs=polygon.crs)
    gdf["band_width"] = band_width

    return gdf
