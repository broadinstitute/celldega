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
import hashlib
import base64
from shapely.geometry import Point, Polygon

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

import json

from .landscape import *
from .trx_tile import *
from .boundary_tile import *
from ..clust import *

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
    image_scale=1
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
    ...     path_transformation_matrix='data/transformation_matrix.csv',
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

    elif technology == "custom":
        meta_cell = gpd.read_parquet(path_meta_cell_micron)
        meta_cell['center_x'] = meta_cell.centroid.x
        meta_cell['center_y'] = meta_cell.centroid.y
        meta_cell["name"] = pd.Series(meta_cell.index, index=meta_cell.index)
        meta_cell.drop(['area', 'centroid'], axis=1, inplace=True)

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
    elif technology == "custom":
        cbg = pd.read_parquet(path_cbg)
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

    # Identify sparse columns
    sparse_cols = [col for col in meta_gene.columns if pd.api.types.is_sparse(meta_gene[col])]

    # Convert sparse columns to dense
    for col in sparse_cols:
        meta_gene[col] = meta_gene[col].sparse.to_dense()

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
    technology, path_landscape_files, image_name="dapi_files", tile_size=1000, image_info={}, image_format='.webp', segmentation_approach="default"):
    """
    Save the landscape parameters to a JSON file.
    """

    if os.path.isdir(path_landscape_files) and os.path.exists(f"{path_landscape_files}/landscape_parameters.json"):

        with open(f"{path_landscape_files}/landscape_parameters.json", "r") as file:
            landscape_parameters = json.load(file)

        landscape_parameters["segmentation_approach"].append(segmentation_approach)
        
        path_landscape_parameters = f"{path_landscape_files}/landscape_parameters.json"

        with open(path_landscape_parameters, "w") as file:
            json.dump(landscape_parameters, file, indent=4)
    
    else:
        path_image_pyramid = f"{path_landscape_files}/pyramid_images/{image_name}"

        print(path_image_pyramid)

        max_pyramid_zoom = get_max_zoom_level(path_image_pyramid)

        landscape_parameters = {
                "technology": technology,
                "segmentation_approach": [segmentation_approach],
                "max_pyramid_zoom": max_pyramid_zoom,
                "tile_size": tile_size,
                "image_info": image_info,
                "image_format": image_format
            }

        path_landscape_parameters = f"{path_landscape_files}/landscape_parameters.json"

        with open(path_landscape_parameters, "w") as file:
            json.dump(landscape_parameters, file, indent=4)

def add_custom_segmentation(path_landscape_files, path_segmentation_files, image_scale=1, tile_size=250):

    with open(f"{path_segmentation_files}/segmentation_parameters.json", "r") as file:
        segmentation_parameters = json.load(file)

    make_meta_gene(technology=segmentation_parameters['technology'], 
                   path_cbg=os.path.join(path_segmentation_files, "cell_by_gene_matrix.parquet"), 
                   path_output=os.path.join(path_landscape_files, f"meta_gene_{segmentation_parameters['segmentation_approach']}.parquet"))
    
    cbg_custom = pd.read_parquet(os.path.join(path_segmentation_files, "cell_by_gene_matrix.parquet"))

    cbg = read_cbg_mtx(os.path.join(os.path.dirname(path_landscape_files), "cell_feature_matrix"))

    save_cbg_gene_parquets(path_landscape_files, 
                           cbg=cbg_custom, 
                           verbose=True, 
                           custom_segmentation_approach=f"_{segmentation_parameters['segmentation_approach']}")

    make_meta_cell_image_coord(technology = segmentation_parameters['technology'], 
                            path_transformation_matrix = os.path.join(path_landscape_files, 'transformation_matrix.csv'), 
                            path_meta_cell_micron = os.path.join(path_segmentation_files, 'cell_metadata_micron_space.parquet'), 
                            path_meta_cell_image = os.path.join(path_landscape_files, f"cell_metadata_{segmentation_parameters['segmentation_approach']}.parquet"),
                            image_scale=image_scale)

    tile_bounds = make_trx_tiles(technology = segmentation_parameters['technology'], 
                                path_trx = os.path.join(path_segmentation_files, 'transcripts.parquet'),
                                path_transformation_matrix = os.path.join(path_landscape_files, 'transformation_matrix.csv'), 
                                path_trx_tiles = os.path.join(path_landscape_files, 'transcript_tiles'),
                                tile_size=tile_size,
                                image_scale=image_scale)

    make_cell_boundary_tiles(technology = segmentation_parameters['technology'],
                path_cell_boundaries = os.path.join(path_segmentation_files, "cell_polygons.parquet"),
                path_meta_cell_micron = os.path.join(path_segmentation_files, 'cell_metadata_micron_space.parquet'),
                path_transformation_matrix = os.path.join(path_landscape_files, 'transformation_matrix.csv'),
                path_output = os.path.join(path_landscape_files, f"cell_segmentation_{segmentation_parameters['segmentation_approach']}"),
                tile_size=tile_size,
                tile_bounds=tile_bounds,
                image_scale=image_scale)
    
    calc_cluster_signatures(path_landscape_files=path_landscape_files, 
               segmentation_parameters=segmentation_parameters, 
               cbg=cbg)
    
    save_landscape_parameters(technology=segmentation_parameters['technology'], 
                              path_landscape_files=path_landscape_files, 
                              image_name="dapi_files", 
                              tile_size=1000, image_format='.webp',
                              segmentation_approach=segmentation_parameters['segmentation_approach'])

def to_geometry(coord_list):
    """
    Convert coordinates list to shapely geometry used in GeoDataFrame
    """
    # If already a Point or Polygon, return it directly
    if isinstance(coord_list, (Point, Polygon)):
        return coord_list
    
    # If it’s a single coordinate pair, create a Point
    if isinstance(coord_list[0], (int, float)):  # Single coordinate pair
        return Point(coord_list)
    
    # If it's a list of coordinate pairs, create a Polygon
    return Polygon(coord_list)

__all__ = ["landscape", "trx_tile", "boundary_tile"]


"""
This has three checklist items:

The files meta_gene.parquet and gene_metadata.parquet are the same and that's a bug that they're being saved twice

You'll need a new cell_metadata.parquet, df_sig.parquet, meta_gene.parquet, cbg directory (maybe cbg_my-seg-method)
But not transcript tiles

the cell_clusters directory and files too - 
I would do something like cell_clusters_my-seg-method and leave the files within the same.

1 make a dega.pre method for adding custom segmentation results into the LandscapeFiles 
(you can decide where to save them - there will be a new cbg file for instance called cbg_some-custom-segmentation-name), 

2 decide on the organization of the LandscapeFiles (just create new adjacent files so we don't break any backwards compatability - 
we can reorganize this when we do a 1.0 release), and 

3 make an argument in the Landscape method that lets the user select 
which segmentation approach to visualize (the landscape_parameters.json can also have a default segmentation result set up to 
establish a default behavior when no argument is given)

"""