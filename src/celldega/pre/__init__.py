"""
Module for pre-processing data
"""

try:
    import pyvips
except ImportError:
    pyvips = None

from pathlib import Path
import numpy as np
import pandas as pd
import os
from tqdm import tqdm
import geopandas as gpd
from copy import deepcopy
import hashlib
import base64
from shapely.affinity import affine_transform
# from shapely import Point, Polygon, MultiPolygon
from shapely.geometry import Polygon, MultiPolygon

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

import json

from .landscape import *

def convert_long_id_to_short(df):
    """
    Converts a column of long integer cell IDs in a DataFrame to a shorter, hash-based representation.
    
    Args:
        df (pd.DataFrame): The DataFrame containing the EntityID.
    Returns:
        pd.DataFrame: The original DataFrame with an additional column named `cell_id`
                      containing the shortened cell IDs.
    
    The function applies a SHA-256 hash to each cell ID, encodes the hash using base64, and truncates
    it to create a shorter identifier that is added as a new column to the DataFrame.
    """
    # Function to hash and encode the cell ID
    def hash_and_shorten_id(cell_id):
        # Create a hash of the cell ID
        cell_id_bytes = str(cell_id).encode('utf-8')
        hash_object = hashlib.sha256(cell_id_bytes)
        hash_digest = hash_object.digest()
        
        # Encode the hash to a base64 string to mix letters and numbers, truncate to 9 characters
        short_id = base64.urlsafe_b64encode(hash_digest).decode('utf-8')[:9]
        return short_id
    
    # Apply the hash_and_shorten_id function to each cell ID in the specified column
    df['cell_id'] = df['EntityID'].apply(hash_and_shorten_id)

    return df


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
    new_image_path = f"{path_landscape_files}/{new_image_name}"
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
    image.pngsave(new_image_path)

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
        meta_cell = pd.read_csv(path_meta_cell_micron, usecols=["EntityID", "center_x", "center_y"])
        meta_cell = convert_long_id_to_short(meta_cell)
        meta_cell["name"] =  meta_cell["cell_id"]
        meta_cell = meta_cell.set_index('cell_id')
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

    if technology == "MERSCOPE":
        meta_cell = meta_cell[["name", "geometry", "EntityID"]]
    else:
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
    image_scale=0.5
):
    """Function to process transcript data and divide into spatial tiles."""
    
    # Load transformation matrix
    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

    # Load the transcript data based on the technology
    if technology == "MERSCOPE":
        trx_ini = pd.read_csv(path_trx, usecols=["gene", "global_x", "global_y"], engine='pyarrow')
        trx_ini.columns = [x.replace("global_", "") for x in trx_ini.columns.tolist()]
        trx_ini.rename(columns={"gene": "name"}, inplace=True)

    elif technology == "Xenium":
        trx_ini = pd.read_parquet(path_trx, columns=["feature_name", "x_location", "y_location"], engine='pyarrow')
        trx_ini.columns = [x.replace("_location", "") for x in trx_ini.columns.tolist()]
        trx_ini.rename(columns={"feature_name": "name"}, inplace=True)

    # Initialize a list to store transformed chunks (avoiding pd.concat inside the loop)
    all_chunks = []

    # Process the data in chunks
    for start_row in tqdm(range(0, trx_ini.shape[0], chunk_size), desc="Processing chunks"):
        chunk = trx_ini.iloc[start_row:start_row + chunk_size].copy()

        # Apply transformation matrix to the coordinates in a vectorized way
        points = np.hstack((chunk[["x", "y"]], np.ones((chunk.shape[0], 1))))
        transformed_points = np.dot(points, transformation_matrix.T)[:, :2]
        chunk[["x", "y"]] = transformed_points

        # Apply image scaling and rounding in one step
        chunk[["x", "y"]] = (chunk[["x", "y"]] * image_scale).round(2)

        all_chunks.append(chunk)

    # Concatenate all chunks after processing
    trx = pd.concat(all_chunks, ignore_index=True)

    # Ensure the output directory exists
    if not os.path.exists(path_trx_tiles):
        os.makedirs(path_trx_tiles)

    # Get min and max x, y values
    x_min, x_max = 0, trx["x"].max()
    y_min, y_max = 0, trx["y"].max()

    # Convert pandas DataFrame to numpy arrays for faster filtering
    x_values = trx["x"].values
    y_values = trx["y"].values
    gene_values = trx["name"].values

    # Calculate the number of tiles
    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size))

    # Iterate over tiles and process the data
    for i in tqdm(range(n_tiles_x)[:10], desc="Processing rows", unit="row"):
        tile_x_min = x_min + i * tile_size
        tile_x_max = tile_x_min + tile_size

        for j in tqdm(range(n_tiles_y)[:10], desc="Processing tiles", unit="tile", leave=False):
            tile_y_min = y_min + j * tile_size
            tile_y_max = tile_y_min + tile_size

            # Combine the x and y filters into a single boolean filter
            tile_filter = (
                (x_values >= tile_x_min) & (x_values < tile_x_max) &
                (y_values >= tile_y_min) & (y_values < tile_y_max)
            )
            filtered_indices = np.where(tile_filter)[0]

            # Skip empty tiles
            if len(filtered_indices) == 0:
                continue

            # Create the filtered DataFrame
            tile_trx = pd.DataFrame({
                "name": gene_values[filtered_indices],
                "x": x_values[filtered_indices],
                "y": y_values[filtered_indices]
            })

            # Create the 'geometry' column
            tile_trx["geometry"] = [[x, y] for x, y in zip(tile_trx["x"], tile_trx["y"])]

            # Define the filename based on the tile coordinates
            filename = f"{path_trx_tiles}/transcripts_tile_{i}_{j}.parquet"

            # Save the filtered DataFrame to a Parquet file
            tile_trx[["name", "geometry"]].to_parquet(filename)

    # Return the tile bounds
    tile_bounds = {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
    }

    return tile_bounds



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

    # if the polygon is a MultiPolygon, we only take the first polygon
    if isinstance(polygon, MultiPolygon):
        polygon = list(polygon.geoms)[0]

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

    df_meta = pd.read_parquet(f"{path_output.replace('cell_segmentation','cell_metadata.parquet')}")
    entity_to_cell_id_dict = pd.Series(df_meta.index.values,index=df_meta.EntityID).to_dict()

    tile_size_x = tile_size
    tile_size_y = tile_size

    transformation_matrix = pd.read_csv(
        path_transformation_matrix, header=None, sep=" "
    ).values

    if technology == "MERSCOPE":
        cells_orig = gpd.read_parquet(path_cell_boundaries)
        cells_orig['cell_id'] = cells_orig['EntityID'].apply(lambda x: loaded_dict[x])

        z_index = 1
        cells_orig = cells_orig[cells_orig["ZIndex"] == z_index]

        # fix the id issue with the cell bounary parquet files (probably can be dropped)
        meta_cell = pd.read_csv(path_meta_cell_micron)
        meta_cell['cell_id'] = meta_cell['EntityID'].apply(lambda x: loaded_dict[x])

        fixed_names = []
        for inst_cell in cells_orig.index.tolist():
            inst_id = cells_orig.loc[inst_cell, "cell_id"]
            new_id = meta_cell[meta_cell["cell_id"] == inst_id].index.tolist()[0]
            fixed_names.append(new_id)

        cells = deepcopy(cells_orig)
        cells.index = fixed_names

        # Corrected approach to convert 'MultiPolygon' to 'Polygon'
        cells["geometry"] = cells["Geometry"].apply(
            lambda x: list(x.geoms)[0] if isinstance(x, MultiPolygon) else x
        )

    elif technology == "Xenium":
        xenium_cells = pd.read_parquet(path_cell_boundaries)

        # Group by 'cell_id' and aggregate the coordinates into lists
        grouped = xenium_cells.groupby("cell_id").agg(list)

        # Create a new column for polygons
        grouped["geometry"] = grouped.apply(
            lambda row: Polygon(zip(row["vertex_x"], row["vertex_y"])), axis=1
        )

        # Convert the DataFrame with polygon data into a GeoDataFrame
        cells = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]

    elif technology == "custom":
        import geopandas as gpd
        cells = gpd.read_parquet(path_cell_boundaries)


    # Apply the transformation to each polygon
    cells["NEW_GEOMETRY"] = cells["geometry"].apply(

        lambda poly: transform_polygon(poly, transformation_matrix)
    )

    cells["GEOMETRY"] = cells["NEW_GEOMETRY"].apply(lambda x: simple_format(x, image_scale))


    from shapely.geometry import Polygon

    cells["polygon"] = cells["GEOMETRY"].apply(lambda x: Polygon(x[0]))
    cells = cells.set_index('cell_id')

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

        if i % 2 == 0:
            print('row', i)

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
    technology, path_landscape_files, image_name="dapi_files", tile_size=1000, image_info={}, image_format='.webp'
):

    path_image_pyramid = f"{path_landscape_files}/pyramid_images/{image_name}"

    print(path_image_pyramid)

    max_pyramid_zoom = get_max_zoom_level(path_image_pyramid)

    landscape_parameters = {
        "technology": technology,
        "max_pyramid_zoom": max_pyramid_zoom,
        "tile_size": tile_size,
        "image_info": image_info,
        "image_format": image_format
    }

    path_landscape_parameters = f"{path_landscape_files}/landscape_parameters.json"

    with open(path_landscape_parameters, "w") as file:
        json.dump(landscape_parameters, file, indent=4)


__all__ = ["landscape"]
