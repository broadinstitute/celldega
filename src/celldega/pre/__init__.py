"""
Module for pre-processing to generate LandscapeFiles from ST data.
"""

try:
    import pyvips
except ImportError:
    pyvips = None

from pathlib import Path
import numpy as np
import pandas as pd
import os
import subprocess
import hashlib
import base64
from shapely.geometry import Point, Polygon

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

import json

from .landscape import *
from .trx_tile import *
from .boundary_tile import *


def convert_long_id_to_short(df):
    """Converts a column of long integer cell IDs in a DataFrame to a shorter, hash-based representation.

    Args:
        df (pd.DataFrame): The DataFrame containing the `EntityID` column.

    Returns:
        pd.DataFrame: The original DataFrame with an additional column named `cell_id`
                      containing the shortened cell IDs.

    The function applies a SHA-256 hash to each cell ID, encodes the hash using base64, and truncates
    it to create a shorter identifier that is added as a new column to the DataFrame.
    """
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
    """Reduces the size of an image by a specified scale factor.

    Args:
        image_path (str): Path to the image file.
        scale_image (float, optional): Scale factor for the image resize. Defaults to 0.5.
        path_landscape_files (str, optional): Directory to save the resized image. Defaults to "".

    Returns:
        str: Path to the resized image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    resized_image = image.resize(scale_image)

    new_image_name = image_path.split("/")[-1].replace(".tif", "_downsize.tif")
    new_image_path = f"{path_landscape_files}/{new_image_name}"
    resized_image.write_to_file(new_image_path)

    return new_image_path


def convert_to_jpeg(image_path, quality=80):
    """Converts a TIFF image to a JPEG image with a specified quality score.

    Args:
        image_path (str): Path to the image file.
        quality (int, optional): Quality score for the JPEG image. Defaults to 80.

    Returns:
        str: Path to the JPEG image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    new_image_path = image_path.replace(".tif", ".jpeg")
    image.jpegsave(new_image_path, Q=quality)

    return new_image_path


def convert_to_png(image_path):
    """Converts a TIFF image to a PNG image.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: Path to the PNG image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    new_image_path = image_path.replace(".tif", ".png")
    image.pngsave(new_image_path)

    return new_image_path


def convert_to_webp(image_path, quality=100):
    """Converts a TIFF image to a WEBP image with a specified quality score.

    Args:
        image_path (str): Path to the image file.
        quality (int, optional): Quality score for the WEBP image. Defaults to 100.

    Returns:
        str: Path to the WEBP image file.
    """
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    new_image_path = image_path.replace(".tif", ".webp")
    image.webpsave(new_image_path, Q=quality)

    return new_image_path


def make_deepzoom_pyramid(image_path, output_path, pyramid_name, tile_size=512, overlap=0, suffix=".jpeg"):
    """Creates a DeepZoom image pyramid from a JPEG image.

    Args:
        image_path (str): Path to the JPEG image file.
        output_path (str): Directory to save the DeepZoom pyramid.
        pyramid_name (str): Name of the pyramid directory.
        tile_size (int, optional): Tile size for the DeepZoom pyramid. Defaults to 512.
        overlap (int, optional): Overlap size for the DeepZoom pyramid. Defaults to 0.
        suffix (str, optional): Suffix for the DeepZoom pyramid tiles. Defaults to ".jpeg".

    Returns:
        None
    """
    output_path = Path(output_path)
    image = pyvips.Image.new_from_file(image_path, access="sequential")
    output_path.mkdir(parents=True, exist_ok=True)
    output_path = output_path / pyramid_name
    image.dzsave(output_path, tile_size=tile_size, overlap=overlap, suffix=suffix)


def make_meta_cell_image_coord(
    technology, path_transformation_matrix, path_meta_cell_micron, path_meta_cell_image, image_scale
):
    """Applies an affine transformation to cell coordinates in microns and saves the transformed coordinates in pixels.

    Args:
        technology (str): The technology used to generate the data (e.g., "Xenium" or "MERSCOPE").
        path_transformation_matrix (str): Path to the transformation matrix file.
        path_meta_cell_micron (str): Path to the meta cell file with coordinates in microns.
        path_meta_cell_image (str): Path to save the meta cell file with coordinates in pixels.
        image_scale (float): Scaling factor to convert micron coordinates to pixel coordinates.

    Returns:
        None
    """
    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

    if technology == "MERSCOPE":
        meta_cell = pd.read_csv(path_meta_cell_micron, usecols=["EntityID", "center_x", "center_y"])
        meta_cell = convert_long_id_to_short(meta_cell)
        meta_cell["name"] = meta_cell["cell_id"]
        meta_cell = meta_cell.set_index('cell_id')
    elif technology == "Xenium":
        usecols = ["cell_id", "x_centroid", "y_centroid"]
        meta_cell = pd.read_csv(path_meta_cell_micron, index_col=0, usecols=usecols)
        meta_cell.columns = ["center_x", "center_y"]
        meta_cell["name"] = pd.Series(meta_cell.index, index=meta_cell.index)

    meta_cell["ones"] = 1
    points = meta_cell[["center_x", "center_y", "ones"]].values
    transformed_points = np.dot(transformation_matrix, points.T).T

    meta_cell["center_x"] = transformed_points[:, 0]
    meta_cell["center_y"] = transformed_points[:, 1]
    meta_cell.drop(columns=["ones"], inplace=True)

    meta_cell["center_x"] = meta_cell["center_x"] / image_scale
    meta_cell["center_y"] = meta_cell["center_y"] / image_scale

    meta_cell["geometry"] = meta_cell.apply(lambda row: [row["center_x"], row["center_y"]], axis=1)

    if technology == "MERSCOPE":
        meta_cell = meta_cell[["name", "geometry", "EntityID"]]
    else:
        meta_cell = meta_cell[["name", "geometry"]]

    meta_cell.to_parquet(path_meta_cell_image)


def make_meta_gene(technology, path_cbg, path_output):
    """Creates a DataFrame with genes and their assigned colors.

    Args:
        technology (str): The technology used to generate the data (e.g., "Xenium" or "MERSCOPE").
        path_cbg (str): Path to the cell-by-gene matrix data.
        path_output (str): Path to save the meta gene file.

    Returns:
        None
    """
    if technology == "MERSCOPE":
        cbg = pd.read_csv(path_cbg, index_col=0)
        genes = cbg.columns.tolist()
    elif technology == "Xenium":
        cbg = read_cbg_mtx(path_cbg)
        genes = cbg.columns.tolist()

    palettes = [plt.get_cmap(name).colors for name in plt.colormaps() if "tab" in name]
    flat_colors = [color for palette in palettes for color in palette]
    flat_colors_hex = [to_hex(color) for color in flat_colors]

    colors = [
        flat_colors_hex[i % len(flat_colors_hex)] if "Blank" not in gene else "#FFFFFF"
        for i, gene in enumerate(genes)
    ]

    ser_color = pd.Series(colors, index=genes)
    meta_gene = calc_meta_gene_data(cbg)
    meta_gene['color'] = ser_color

    sparse_cols = [col for col in meta_gene.columns if pd.api.types.is_sparse(meta_gene[col])]
    for col in sparse_cols:
        meta_gene[col] = meta_gene[col].sparse.to_dense()

    meta_gene.to_parquet(path_output)


def get_max_zoom_level(path_image_pyramid):
    """Returns the maximum zoom level based on the highest-numbered directory in the specified path.

    Args:
        path_image_pyramid (str): Path to the directory containing zoom level directories.

    Returns:
        int: The maximum zoom level.
    """
    zoom_levels = [
        entry
        for entry in os.listdir(path_image_pyramid)
        if os.path.isdir(os.path.join(path_image_pyramid, entry)) and entry.isdigit()
    ]
    max_pyramid_zoom = max(map(int, zoom_levels)) if zoom_levels else None
    return max_pyramid_zoom


def save_landscape_parameters(
    technology, path_landscape_files, image_name="dapi_files", tile_size=1000, image_info={}, image_format='.webp'
):
    """Saves the landscape parameters to a JSON file.

    Args:
        technology (str): The technology used to generate the data.
        path_landscape_files (str): Path to the directory where landscape files are stored.
        image_name (str, optional): Name of the image directory. Defaults to "dapi_files".
        tile_size (int, optional): Tile size for the image pyramid. Defaults to 1000.
        image_info (dict, optional): Additional image metadata. Defaults to {}.
        image_format (str, optional): Format of the image files. Defaults to ".webp".

    Returns:
        None
    """
    path_image_pyramid = f"{path_landscape_files}/pyramid_images/{image_name}"
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


def to_geometry(coord_list):
    """Converts a coordinates list to a Shapely geometry object (Point or Polygon).

    Args:
        coord_list (list or Point or Polygon): Input coordinates or geometry object.

    Returns:
        Point or Polygon: Shapely geometry object.
    """
    if isinstance(coord_list, (Point, Polygon)):
        return coord_list
    if isinstance(coord_list[0], (int, float)):
        return Point(coord_list)
    return Polygon(coord_list)


def _xenium_unzipper(target_dir):
    """
    Unzips and extracts Xenium-related files in the specified directory.
    If the unzipped files already exist, the function skips those steps.

    Args:
        target_dir (str): Path to the directory containing the compressed files.

    Raises:
        subprocess.CalledProcessError: If any of the commands fail to execute.
        FileNotFoundError: If the target directory does not exist.
    """
    # Check if the target directory exists
    if not os.path.exists(target_dir):
        raise FileNotFoundError(f"The directory '{target_dir}' does not exist.")

    # Save the current working directory
    original_dir = os.getcwd()

    try:
        # Change to the target directory
        os.chdir(target_dir)

        # Check if cells.csv already exists
        if not os.path.exists("cells.csv"):
            print("Decompressing cells.csv.gz...")
            subprocess.run(["gzip", "-dk", "cells.csv.gz"], check=True)
        else:
            print("cells.csv already exists. Skipping decompression.")

        # Check if cells.zarr directory already exists
        if not os.path.exists("cells.zarr"):
            print("Unzipping cells.zarr.zip...")
            subprocess.run(["unzip", "cells.zarr.zip", "-d", "cells.zarr"], check=True)
        else:
            print("cells.zarr directory already exists. Skipping unzipping.")

        # Check if analysis directory already exists
        if not os.path.exists("analysis"):
            print("Extracting analysis.tar.gz...")
            subprocess.run(["tar", "-xvzf", "analysis.tar.gz"], check=True)
        else:
            print("analysis directory already exists. Skipping extraction.")

        # Check if cell_feature_matrix directory already exists
        if not os.path.exists("cell_feature_matrix"):
            print("Extracting cell_feature_matrix.tar.gz...")
            subprocess.run(["tar", "-xvzf", "cell_feature_matrix.tar.gz"], check=True)
        else:
            print("cell_feature_matrix directory already exists. Skipping extraction.")

        print("All files have been successfully extracted or skipped.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing a command: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise
    finally:
        # Restore the original working directory
        os.chdir(original_dir)
        print(f"Restored working directory to '{original_dir}'.")


__all__ = ["landscape", "trx_tile", "boundary_tile"]