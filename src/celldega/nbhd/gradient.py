"""Module for gradient polygon(s) generation."""

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm


def gradient_from_gdf(
    gdf,
    scale_um_per_pixel=0.2125,  # This is for Xenium data
    bin_width=10,
    max_dist_um=50,
    is_pixel_space=True,  # New flag: False if GDF is already in microns
):
    """
    Generates concentric rings. Works with GDFs in pixel or micron units.
    """
    # 1. Determine effective scale
    # If already in microns, 1 unit = 1 um. If in pixels, use the provided scale.
    effective_scale = scale_um_per_pixel if is_pixel_space else 1.0

    # Get the merged geometry
    geometry = gdf.geometry.unary_union

    # 2. Define distances in microns for labels
    rings_um = list(range(0, max_dist_um + 1, bin_width))

    # Define distances in GDF units (px or um) for geometric buffering
    # d_gdf = d_um / scale_um_per_unit
    rings_gdf_units = [r / effective_scale for r in rings_um]

    # --- Label & Order Generation ---
    outward_labels = [
        f"out (+{rings_um[i]}~+{rings_um[i + 1]}) µm" for i in range(len(rings_um) - 1)
    ]
    inward_labels = [
        f"in ({0 if rings_um[i] == 0 else -rings_um[i]}~-{rings_um[i + 1]}) µm"
        for i in range(len(rings_um) - 1)
    ]
    bin_order = inward_labels[::-1] + outward_labels

    def get_colors(cmap_name, n):
        cmap = plt.get_cmap(cmap_name)
        return [mcolors.to_hex(cmap(i)) for i in np.linspace(0.8, 0.3, n)]

    dynamic_color_map = {
        **dict(zip(outward_labels, get_colors("Blues", len(outward_labels)), strict=True)),
        **dict(zip(inward_labels, get_colors("Reds", len(inward_labels)), strict=True)),
    }

    # --- Geometric Processing ---
    global_ring_geoms = []
    global_ring_labels = []

    for direction in ["outward", "inward"]:
        desc = f"Generating {direction} rings"
        for i in tqdm(range(len(rings_gdf_units) - 1), desc=desc):
            if direction == "outward":
                d1, d2 = rings_gdf_units[i], rings_gdf_units[i + 1]
                label = outward_labels[i]
            else:
                d1, d2 = -rings_gdf_units[i], -rings_gdf_units[i + 1]
                label = inward_labels[i]

            # Buffer based on native GDF units
            geom_1 = geometry.buffer(d1)
            geom_2 = geometry.buffer(d2)

            if geom_1.is_empty and geom_2.is_empty:
                continue

            ring = (
                geom_2.difference(geom_1) if direction == "outward" else geom_1.difference(geom_2)
            )

            if not ring.is_empty:
                global_ring_geoms.append(ring)
                global_ring_labels.append({"mode": direction, "ring_range_um": label})

    # --- Build GeoDataFrame ---
    gdf_rings = gpd.GeoDataFrame(global_ring_labels, geometry=global_ring_geoms, crs=gdf.crs)
    gdf_rings["color"] = gdf_rings["ring_range_um"].map(dynamic_color_map).fillna("#cccccc")

    # Calculate Area
    area_native = gdf_rings.geometry.area
    if is_pixel_space:
        gdf_rings["area_px2"] = area_native
        gdf_rings["area_um2"] = area_native * (scale_um_per_pixel**2)
    else:
        gdf_rings["area_um2"] = area_native
        gdf_rings["area_px2"] = area_native / (scale_um_per_pixel**2)

    gdf_rings["area"] = gdf_rings["area_um2"]
    gdf_rings["name"] = gdf_rings["ring_range_um"]

    return gdf_rings, bin_order


def _calc_grad_nbhd_from_roi(
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
