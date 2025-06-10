"""Module for hexatile computing."""

from pathlib import Path
import xml.etree.ElementTree as ET

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.affinity import affine_transform, translate
from shapely.geometry import Polygon, box


def create_hextile(
    radius: float,
    path_landscape_files: str | None = None,
    img_height: int = 100,
    img_width: int = 100,
    pixel_size: float = 0.2125,
) -> gpd.GeoDataFrame:
    """
    Create a grid of hexagonal tiles for an image or landscape.
    """
    if isinstance(path_landscape_files, str):
        # Use pathlib for modern, robust path handling
        base_path = Path(path_landscape_files)
        tree = ET.parse(base_path / "pyramid_images/bound.dzi")
        root = tree.getroot()
        img_width = int(root[0].attrib["Width"])
        img_height = int(root[0].attrib["Height"])

        transformation_matrix = pd.read_csv(
            base_path / "micron_to_image_transform.csv",
            sep=" ",
            header=None,
        ).values[:3, :3]
    else:
        transformation_matrix = np.eye(3)

    hex_height = 2 * radius
    hex_width = np.sqrt(3) * radius
    vert_spacing = 3 / 4 * hex_height
    horiz_spacing = hex_width

    n_cols = int(np.ceil(img_width / horiz_spacing)) + 2
    n_rows = int(np.ceil(img_height / vert_spacing)) + 2

    angles = np.radians(np.arange(0, 360, 60))
    unit_hex = Polygon([(radius * np.sin(a), radius * np.cos(a)) for a in angles])

    hexagons = []
    for row in range(n_rows):
        for col in range(n_cols):
            x = col * horiz_spacing
            y = row * vert_spacing
            if row % 2 == 1:
                x += horiz_spacing / 2
            hexagons.append(translate(unit_hex, xoff=x, yoff=y))

    image_bounds = box(0, 0, img_width, img_height)
    clipped_hexes = [
        hex.intersection(image_bounds) for hex in hexagons if hex.intersects(image_bounds)
    ]

    gdf_hextile = gpd.GeoDataFrame(geometry=clipped_hexes)
    gdf_hextile.rename(columns={"geometry": "geometry_image_space"}, inplace=True)
    gdf_hextile.set_geometry("geometry_image_space", inplace=True)

    transformation_matrix_inv = np.linalg.inv(transformation_matrix)
    a = transformation_matrix_inv[0, 0]
    b = transformation_matrix_inv[0, 1]
    d = transformation_matrix_inv[1, 0]
    e = transformation_matrix_inv[1, 1]
    xoff = transformation_matrix_inv[0, 2]
    yoff = transformation_matrix_inv[1, 2]
    inverse_affine_params = [a, b, d, e, xoff, yoff]

    gdf_hextile["geometry"] = gdf_hextile["geometry_image_space"].apply(
        lambda geom: affine_transform(geom, inverse_affine_params)
    )
    gdf_hextile.set_geometry("geometry", inplace=True)

    radius_in_microns = pixel_size * radius

    if isinstance(path_landscape_files, str):
        # Use pathlib for the output path as well
        base_path = Path(path_landscape_files)
        gdf_hextile.to_parquet(base_path / "hextiles.parquet")
        print(f"Hextiles saved at '{path_landscape_files}' as 'hextiles.parquet'\n")

        fig, ax = plt.subplots(1, 1, figsize=(60, 80))
        gdf_hextile.plot(ax=ax, alpha=1, linewidth=1, facecolor="none", edgecolor="black")
        ax.set_title(f"Hextiles (hexagon radius: {radius_in_microns} microns)", fontsize=50)
        ax.set_xlabel("x (pixels)", fontsize=25)
        ax.set_ylabel("y (pixels)", fontsize=25)
        plt.xticks(fontsize=20)
        plt.yticks(fontsize=20)
        plt.gca().invert_yaxis()
        plt.show()
        plt.close()

    return gdf_hextile


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
