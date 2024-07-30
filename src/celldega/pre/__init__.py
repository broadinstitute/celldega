try:
    import pyvips
except ImportError:
    pyvips = None

from pathlib import Path
import numpy as np
import pandas as pd
import os
import geopandas as gpd
from copy import deepcopy
from shapely.affinity import affine_transform
from shapely import Point, Polygon, MultiPolygon

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

import json

from .landscape import *


def reduce_image_size(image_path, scale_image=0.5, path_landscape_files=""):
    """

    Parameters
    ----------
    image_path : str
        Path to the image file
    scale_image : float (default=0.5)
        Scale factor for the image resize

    Returns
    -------
    new_image_path : str
        Path to the resized image file
    """

    image = pyvips.Image.new_from_file(image_path, access="sequential")

    resized_image = image.resize(scale_image)

    new_image_name = image_path.split("/")[-1].replace(".tif", "_downsize.tif")
    new_image_path = path_landscape_files + new_image_name
    resized_image.write_to_file(new_image_path)

    return new_image_path


def convert_to_jpeg(image_path, quality=80):
    """
    Convert a TIFF image to a JPEG image with a quality of score

    Parameters
    ----------
    image_path : str
        Path to the image file
    quality : int (default=80)
        Quality score for the JPEG image

    Returns
    -------
    new_image_path : str
        Path to the JPEG image file

    """

    # Load the TIFF image
    image = pyvips.Image.new_from_file(image_path, access="sequential")

    # Save the image as a JPEG with a quality of 80
    new_image_path = image_path.replace(".tif", ".jpeg")
    image.jpegsave(new_image_path, Q=quality)

    return new_image_path

def convert_to_png(image_path):
    """
    Convert a TIFF image to a JPEG image with a quality of score

    Parameters
    ----------
    image_path : str
        Path to the image file
    quality : int (default=80)
        Quality score for the JPEG image

    Returns
    -------
    new_image_path : str
        Path to the JPEG image file

    """

    # Load the TIFF image
    image = pyvips.Image.new_from_file(image_path, access="sequential")

    # Save the image as a JPEG with a quality of 80
    new_image_path = image_path.replace(".tif", ".png")
    image.pngsave(new_image_path, Q=quality)

    return new_image_path



def convert_to_webp(image_path, quality=100):
    """
    Convert a TIFF image to a WEBP image with a specified quality score.

    Parameters
    ----------
    image_path : str
        Path to the image file
    quality : int (default=100)
        Quality score for the WEBP image (higher is better quality)

    Returns
    -------
    new_image_path : str
        Path to the WEBP image file
    """
    # Load the TIFF image
    image = pyvips.Image.new_from_file(image_path, access="sequential")

    # Save the image as a WEBP with specified quality
    new_image_path = image_path.replace(".tif", ".webp")
    image.webpsave(new_image_path, Q=quality)

    return new_image_path



def make_deepzoom_pyramid(
    image_path, output_path, pyramid_name, tile_size=512, overlap=0, suffix=".jpeg"
):
    """
    Create a DeepZoom image pyramid from a JPEG image

    Parameters
    ----------
    image_path : str
        Path to the JPEG image file
    tile_size : int (default=512)
        Tile size for the DeepZoom pyramid
    overlap : int (default=0)
        Overlap size for the DeepZoom pyramid
    suffix : str (default='jpeg')
        Suffix for the DeepZoom pyramid tiles

    Returns
    -------
    None

    """

    # Define the output path
    output_path = Path(output_path)

    # Load the JPEG image
    image = pyvips.Image.new_from_file(image_path, access="sequential")

    # check if the output path exists and create it if it does not
    output_path.mkdir(parents=True, exist_ok=True)

    # append the pyramid name to the output path
    output_path = output_path / pyramid_name

    # Save the image as a DeepZoom image pyramid
    image.dzsave(output_path, tile_size=tile_size, overlap=overlap, suffix=suffix)


def make_meta_cell_image_coord(
    technology,
    path_transformation_matrix,
    path_meta_cell_micron,
    path_meta_cell_image,
    image_scale
):
    """
    Apply an affine transformation to the cell coordinates in microns and save
    the transformed coordinates in pixels

    Parameters
    ----------
    technology : str
        The technology used to generate the data, Xenium and MERSCOPE are supported.
    path_transformation_matrix : str
        Path to the transformation matrix file
    path_meta_cell_micron : str
        Path to the meta cell file with coordinates in microns
    path_meta_cell_image : str
        Path to save the meta cell file with coordinates in pixels

    Returns
    -------
    None

    Examples
    --------
    >>> make_meta_cell_image_coord(
    ...     technology='Xenium',
    ...     path_transformation_matrix='data/transformation_matrix.txt',
    ...     path_meta_cell_micron='data/meta_cell_micron.csv',
    ...     path_meta_cell_image='data/meta_cell_image.parquet'
    ... )

    """

    transformation_matrix = pd.read_csv(
        path_transformation_matrix, header=None, sep=" "
    ).values

    if technology == "MERSCOPE":
        meta_cell = pd.read_csv(path_meta_cell_micron, usecols=["center_x", "center_y"])
        meta_cell["name"] = pd.Series(meta_cell.index, index=meta_cell.index)
    elif technology == "Xenium":
        usecols = ["cell_id", "x_centroid", "y_centroid"]
        meta_cell = pd.read_csv(path_meta_cell_micron, index_col=0, usecols=usecols)
        meta_cell.columns = ["center_x", "center_y"]
        meta_cell["name"] = pd.Series(meta_cell.index, index=meta_cell.index)

    # Adding a ones column to accommodate for affine transformation
    meta_cell["ones"] = 1

    # Preparing the data for matrix multiplication
    points = meta_cell[["center_x", "center_y", "ones"]].values

    # Applying the transformation matrix
    transformed_points = np.dot(transformation_matrix, points.T).T

    # Updating the DataFrame with transformed coordinates
    meta_cell["center_x"] = transformed_points[:, 0]
    meta_cell["center_y"] = transformed_points[:, 1]

    # Dropping the ones column as it's no longer needed
    meta_cell.drop(columns=["ones"], inplace=True)

    meta_cell["center_x"] = meta_cell["center_x"] / image_scale
    meta_cell["center_y"] = meta_cell["center_y"] / image_scale

    meta_cell["geometry"] = meta_cell.apply(
        lambda row: [row["center_x"], row["center_y"]], axis=1
    )

    meta_cell = meta_cell[["name", "geometry"]]


    meta_cell.to_parquet(path_meta_cell_image)


def make_trx_tiles(
    technology,
    path_trx,
    path_transformation_matrix,
    path_trx_tiles,
    tile_size=1000,
    chunk_size=1000000,
    verbose=False,
    image_scale = 0.5
):
    """ """

    tile_size_x = tile_size
    tile_size_y = tile_size

    transformation_matrix = pd.read_csv(
        path_transformation_matrix, header=None, sep=" "
    ).values

    if technology == "MERSCOPE":
        trx_ini = pd.read_csv(path_trx, usecols=["gene", "global_x", "global_y"])

        trx_ini.columns = [x.replace("global_", "") for x in trx_ini.columns.tolist()]
        trx_ini.rename(columns={"gene": "name"}, inplace=True)

    elif technology == "Xenium":
        trx_ini = pd.read_parquet(
            path_trx, columns=["feature_name", "x_location", "y_location"]
        )

        # trx_ini['feature_name'] = trx_ini['feature_name'].apply(lambda x: x.decode('utf-8'))
        trx_ini.columns = [x.replace("_location", "") for x in trx_ini.columns.tolist()]
        trx_ini.rename(columns={"feature_name": "name"}, inplace=True)

    trx = pd.DataFrame()  # Initialize empty DataFrame for results

    for start_row in range(0, trx_ini.shape[0], chunk_size):
        # print(start_row/1e6)
        chunk = trx_ini.iloc[start_row : start_row + chunk_size].copy()
        points = np.hstack((chunk[["x", "y"]], np.ones((chunk.shape[0], 1))))
        transformed_points = np.dot(points, transformation_matrix.T)[:, :2]
        chunk[["x", "y"]] = (
            transformed_points  # Update chunk with transformed coordinates
        )

        # add this as an argument that can be modified
        chunk["x"] = chunk["x"] * image_scale
        chunk["y"] = chunk["y"] * image_scale

        chunk["x"] = chunk["x"].round(2)
        chunk["y"] = chunk["y"].round(2)
        trx = pd.concat([trx, chunk], ignore_index=True)

    if not os.path.exists(path_trx_tiles):
        os.mkdir(path_trx_tiles)

    x_min = 0
    x_max = trx["x"].max()
    y_min = 0
    y_max = trx["y"].max()

    # Calculate the number of tiles needed
    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size_x))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size_y))

    for i in range(n_tiles_x):

        if i % 2 == 0 and verbose:
            print("row", i)

        for j in range(n_tiles_y):
            # calculate polygon from these bounds
            tile_x_min = x_min + i * tile_size_x
            tile_x_max = tile_x_min + tile_size_x
            tile_y_min = y_min + j * tile_size_y
            tile_y_max = tile_y_min + tile_size_y

            # Filter trx to get only the data within the current tile's bounds
            # We need to make this more efficient
            # option 1: make a GeoDataFrame and filter using sindex and the tile polygon
            # option 2: remove transcripts that have been assigned to a tile from the DataFrame
            tile_trx = trx[
                (trx.x >= tile_x_min)
                & (trx.x < tile_x_max)
                & (trx.y >= tile_y_min)
                & (trx.y < tile_y_max)
            ].copy()

            # this actually slows things down - will try to move to Polars later
            # # drop trx that have been assigned to a tile from the original trx DataFrame
            # trx = trx[~trx.index.isin(tile_trx.index)]

            # make 'geometry' column
            tile_trx = tile_trx.assign(
                geometry=tile_trx.apply(lambda row: [row["x"], row["y"]], axis=1)
            )

            # add some logic to skip tiles where there are no transcripts

            # Define the filename based on the tile's coordinates
            filename = f"{path_trx_tiles}/transcripts_tile_{i}_{j}.parquet"

            # Save the filtered DataFrame to a Parquet file
            if tile_trx.shape[0] > 0:
                tile_trx[["name", "geometry"]].to_parquet(filename)

    tile_bonds = {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
    }

    return tile_bonds



# Function to apply transformation to a polygon
def transform_polygon(polygon, matrix):
    # Extracting the affine transformation components from the matrix
    a, b, d, e, xoff, yoff = (
        matrix[0, 0],
        matrix[0, 1],
        matrix[1, 0],
        matrix[1, 1],
        matrix[0, 2],
        matrix[1, 2],
    )
    # Constructing the affine transformation formula for shapely
    affine_params = [a, b, d, e, xoff, yoff]
    # Applying the transformation
    transformed_polygon = affine_transform(polygon, affine_params)

    exterior_coords = transformed_polygon.exterior.coords

    # Creating the original structure by directly using numpy array for each coordinate pair
    original_format_coords = np.array([np.array(coord) for coord in exterior_coords])

    return np.array([original_format_coords], dtype=object)


def simple_format(geometry, image_scale):
    # factor in scaling
    return [[[coord[0] / image_scale, coord[1] / image_scale] for coord in polygon] for polygon in geometry]


def make_cell_boundary_tiles(
    technology,
    path_cell_boundaries,
    path_meta_cell_micron,
    path_transformation_matrix,
    path_output,
    tile_size=1000,
    tile_bounds=None,
    image_scale=0.5
):
    """ """

    tile_size_x = tile_size
    tile_size_y = tile_size

    transformation_matrix = pd.read_csv(
        path_transformation_matrix, header=None, sep=" "
    ).values

    if technology == "MERSCOPE":
        cells_orig = gpd.read_parquet(path_cell_boundaries)
        cells_orig.shape

        z_index = 1
        cells_orig = cells_orig[cells_orig["ZIndex"] == z_index]

        # fix the id issue with the cell bounary parquet files (probably can be dropped)
        meta_cell = pd.read_csv(path_meta_cell_micron)

        fixed_names = []
        for inst_cell in cells_orig.index.tolist():
            inst_id = cells_orig.loc[inst_cell, "EntityID"]
            new_id = meta_cell[meta_cell["EntityID"] == inst_id].index.tolist()[0]
            fixed_names.append(new_id)

        cells = deepcopy(cells_orig)
        cells.index = fixed_names

        # Corrected approach to convert 'MultiPolygon' to 'Polygon'
        cells["geometry"] = cells["Geometry"].apply(
            lambda x: list(x.geoms)[0] if isinstance(x, MultiPolygon) else x
        )

    elif technology == "Xenium":
        xenium_cells = pd.read_parquet(path_cell_boundaries)

        from shapely.geometry import Polygon
        import geopandas as gpd

        # Group by 'cell_id' and aggregate the coordinates into lists
        grouped = xenium_cells.groupby("cell_id").agg(list)

        # Create a new column for polygons
        grouped["geometry"] = grouped.apply(
            lambda row: Polygon(zip(row["vertex_x"], row["vertex_y"])), axis=1
        )

        # Convert the DataFrame with polygon data into a GeoDataFrame
        cells = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]

    # Apply the transformation to each polygon
    cells["NEW_GEOMETRY"] = cells["geometry"].apply(
        lambda poly: transform_polygon(poly, transformation_matrix)
    )

    cells["GEOMETRY"] = cells["NEW_GEOMETRY"].apply(lambda x: simple_format(x, image_scale))

    cells["polygon"] = cells["GEOMETRY"].apply(lambda x: Polygon(x[0]))

    gdf_cells = gpd.GeoDataFrame(geometry=cells["polygon"])

    gdf_cells["center_x"] = gdf_cells.centroid.x
    gdf_cells["center_y"] = gdf_cells.centroid.y

    if not os.path.exists(path_output):
        os.mkdir(path_output)

    x_min = tile_bounds["x_min"]
    x_max = tile_bounds["x_max"]
    y_min = tile_bounds["y_min"]
    y_max = tile_bounds["y_max"]

    # Calculate the number of tiles needed
    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size_x))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size_y))

    for i in range(n_tiles_x):

        # if i % 2 == 0:
        #     print('row', i)

        for j in range(n_tiles_y):
            tile_x_min = x_min + i * tile_size_x
            tile_x_max = tile_x_min + tile_size_x
            tile_y_min = y_min + j * tile_size_y
            tile_y_max = tile_y_min + tile_size_y

            # find cell polygons with centroids in the tile
            keep_cells = gdf_cells[
                (gdf_cells.center_x >= tile_x_min)
                & (gdf_cells.center_x < tile_x_max)
                & (gdf_cells.center_y >= tile_y_min)
                & (gdf_cells.center_y < tile_y_max)
            ].index.tolist()

            inst_geo = cells.loc[keep_cells, ["GEOMETRY"]]

            # try adding cell name to geometry
            inst_geo["name"] = pd.Series(
                inst_geo.index.tolist(), index=inst_geo.index.tolist()
            )

            filename = f"{path_output}/cell_tile_{i}_{j}.parquet"

            # Save the filtered DataFrame to a Parquet file
            if inst_geo.shape[0] > 0:
                inst_geo[["GEOMETRY", "name"]].to_parquet(filename)


def make_meta_gene(technology, path_cbg, path_output):
    """
    Create a DataFrame with genes and their assigned colors

    Parameters
    ----------
    technology : str
        The technology used to generate the data, Xenium and MERSCOPE are supported.
    path_cbg : str
        Path to the cell-by-gene matrix data (the data format can vary based on technology)
    path_output : str
        Path to save the meta gene file

    Returns
    -------
    None

    Examples
    --------
    >>> make_meta_gene(
    ...     technology='Xenium',
    ...     path_cbg='data/',
    ...     path_output='data/meta_gene.parquet'
    ... )
    """

    if technology == "MERSCOPE":
        cbg = pd.read_csv(path_cbg, index_col=0)
        genes = cbg.columns.tolist()
    elif technology == "Xenium":
        # genes = pd.read_csv(path_cbg + 'features.tsv.gz', sep='\t', header=None)[1].values.tolist()
        cbg = read_cbg_mtx(path_cbg)
        genes = cbg.columns.tolist()

    # Get all categorical color palettes from Matplotlib and flatten them into a single list of colors
    palettes = [plt.get_cmap(name).colors for name in plt.colormaps() if "tab" in name]
    flat_colors = [color for palette in palettes for color in palette]

    # Convert RGB tuples to hex codes
    flat_colors_hex = [to_hex(color) for color in flat_colors]

    # Use modular arithmetic to assign a color to each gene, white for genes with "Blank"
    colors = [
        flat_colors_hex[i % len(flat_colors_hex)] if "Blank" not in gene else "#FFFFFF"
        for i, gene in enumerate(genes)
    ]

    # Create a DataFrame with genes and their assigned colors
    ser_color = pd.Series(colors, index=genes)

    # calculate gene expression metadata
    meta_gene = calc_meta_gene_data(cbg)
    meta_gene['color'] = ser_color

    meta_gene.to_parquet(path_output)


def get_max_zoom_level(path_image_pyramid):
    """
    Returns the maximum zoom level based on the highest-numbered directory
    in the specified path_image_pyramid.

    Parameters:
        path_image_pyramid (str): The path to the directory containing zoom level directories.

    Returns:
        max_pyramid_zoom (int): The maximum zoom level.
    """
    # List all entries in the path_image_pyramid that are directories and can be converted to integers
    zoom_levels = [
        entry
        for entry in os.listdir(path_image_pyramid)
        if os.path.isdir(os.path.join(path_image_pyramid, entry)) and entry.isdigit()
    ]

    # Convert to integer and find the maximum value
    max_pyramid_zoom = max(map(int, zoom_levels)) if zoom_levels else None

    return max_pyramid_zoom


def save_landscape_parameters(
    technology, path_landscape_files, image_name="dapi_files", tile_size=1000, image_info={}
):

    path_image_pyramid = path_landscape_files + "pyramid_images/" + image_name + "/"

    print(path_image_pyramid)

    max_pyramid_zoom = get_max_zoom_level(path_image_pyramid)

    landscape_parameters = {
        "technology": technology,
        "max_pyramid_zoom": max_pyramid_zoom,
        "tile_size": tile_size,
        "image_info": image_info
    }

    path_landscape_parameters = path_landscape_files + "landscape_parameters.json"

    with open(path_landscape_parameters, "w") as file:
        json.dump(landscape_parameters, file, indent=4)


__all__ = ["landscape"]
