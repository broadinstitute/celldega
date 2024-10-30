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
import polars as pl
from tqdm import tqdm
import concurrent.futures
import geopandas as gpd
from copy import deepcopy
import hashlib
import base64
from shapely.affinity import affine_transform
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
    coarse_tile_size=2500,
    fine_tile_size=250,
    chunk_size=1000000,
    verbose=False,
    image_scale=1,
    max_workers=8
):
    """
    Processes transcript data by dividing it into coarse-grain and fine-grain tiles,
    applying transformations, and saving the results in a parallelized manner.

    Parameters
    ----------
    technology : str
        The technology used for generating the transcript data (e.g., "MERSCOPE" or "Xenium").
    path_trx : str
        Path to the file containing the transcript data.
    path_transformation_matrix : str
        Path to the file containing the transformation matrix (CSV file).
    path_trx_tiles : str
        Directory path where the output files (Parquet files) for each tile will be saved.
    coarse_tile_size : int, optional
        Size of each coarse-grain tile in microns (default is 2500).
    fine_tile_size : int, optional
        Size of each fine-grain tile in microns (default is 250).
    chunk_size : int, optional
        Number of rows to process per chunk for memory efficiency (default is 1000000).
    verbose : bool, optional
        Flag to enable verbose output (default is False).
    image_scale : float, optional
        Scale factor to apply to the transcript coordinates (default is 0.5).
    max_workers : int, optional
        Maximum number of parallel workers for processing tiles (default is 8).

    Returns
    -------
    dict
        A dictionary containing the bounds of the processed data in both x and y directions.
    """

    def process_coarse_tile(trx, i, j, coarse_tile_x_min, coarse_tile_x_max, coarse_tile_y_min, coarse_tile_y_max, fine_tile_size, path_trx_tiles, x_min, y_min, n_fine_tiles_x, n_fine_tiles_y, max_workers):
        # Filter the entire dataset for the current coarse tile
        coarse_tile = trx.filter(
            (pl.col("transformed_x") >= coarse_tile_x_min) & (pl.col("transformed_x") < coarse_tile_x_max) &
            (pl.col("transformed_y") >= coarse_tile_y_min) & (pl.col("transformed_y") < coarse_tile_y_max)
        )
    
        if not coarse_tile.is_empty():
            # Now process fine tiles using global fine tile indices
            process_fine_tiles(coarse_tile, i, j, coarse_tile_x_min, coarse_tile_x_max, coarse_tile_y_min, coarse_tile_y_max, fine_tile_size, path_trx_tiles, x_min, y_min, n_fine_tiles_x, n_fine_tiles_y, max_workers)   


    def process_fine_tiles(coarse_tile, coarse_i, coarse_j, coarse_tile_x_min, coarse_tile_x_max, coarse_tile_y_min, coarse_tile_y_max, fine_tile_size, path_trx_tiles, x_min, y_min, n_fine_tiles_x, n_fine_tiles_y, max_workers=8):

        # Use ThreadPoolExecutor for parallel processing of fine-grain tiles within the coarse tile
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # Iterate over fine-grain tiles within the global bounds
            for fine_i in range(n_fine_tiles_x):
                fine_tile_x_min = x_min + fine_i * fine_tile_size
                fine_tile_x_max = fine_tile_x_min + fine_tile_size

                # Process only if the fine tile falls within the current coarse tile's bounds
                if not (fine_tile_x_min >= coarse_tile_x_min and fine_tile_x_max <= coarse_tile_x_max):
                    continue

                for fine_j in range(n_fine_tiles_y):
                    fine_tile_y_min = y_min + fine_j * fine_tile_size
                    fine_tile_y_max = fine_tile_y_min + fine_tile_size

                    # Process only if the fine tile falls within the current coarse tile's bounds
                    if not (fine_tile_y_min >= coarse_tile_y_min and fine_tile_y_max <= coarse_tile_y_max):
                        continue

                    # Submit the task for each fine tile to process in parallel
                    futures.append(executor.submit(
                        filter_and_save_fine_tile, coarse_tile, coarse_i, coarse_j, fine_i, fine_j, 
                        fine_tile_x_min, fine_tile_x_max, fine_tile_y_min, fine_tile_y_max, path_trx_tiles
                    ))

            # Wait for all futures to complete
            for future in concurrent.futures.as_completed(futures):
                future.result()  # Raise exceptions if any occurred during execution


    def filter_and_save_fine_tile(coarse_tile, coarse_i, coarse_j, fine_i, fine_j, fine_tile_x_min, fine_tile_x_max, fine_tile_y_min, fine_tile_y_max, path_trx_tiles):
    
        # Filter the coarse tile for the current fine tile's boundaries
        fine_tile_trx = coarse_tile.filter(
            (pl.col("transformed_x") >= fine_tile_x_min) & (pl.col("transformed_x") < fine_tile_x_max) &
            (pl.col("transformed_y") >= fine_tile_y_min) & (pl.col("transformed_y") < fine_tile_y_max)
        )
        
        if not fine_tile_trx.is_empty():
            # Add geometry column as a list of [x, y] pairs
            fine_tile_trx = fine_tile_trx.with_columns(
                pl.concat_list([pl.col("transformed_x"), pl.col("transformed_y")]).alias("geometry")
            ).drop(['transformed_x', 'transformed_y'])
    
            # Define the filename based on fine tile coordinates
            filename = f"{path_trx_tiles}/transcripts_tile_{fine_i}_{fine_j}.parquet"
    
            # Save the filtered DataFrame to a Parquet file
            fine_tile_trx.to_pandas().to_parquet(filename)


    # Load transformation matrix
    transformation_matrix = np.loadtxt(path_transformation_matrix)

    # Load the transcript data based on the technology using Polars
    if technology == "MERSCOPE":
        trx_ini = pl.read_csv(path_trx, columns=["gene", "global_x", "global_y"])
        trx_ini = trx_ini.with_columns([
            pl.col("global_x").alias("x"),
            pl.col("global_y").alias("y"),
            pl.col("gene").alias("name")
        ]).select(["name", "x", "y"])

    elif technology == "Xenium":
        trx_ini = pl.read_parquet(path_trx).select([
            pl.col("feature_name").alias("name"),
            pl.col("x_location").alias("x"),
            pl.col("y_location").alias("y")
        ])

    # Process the data in chunks and apply transformations
    all_chunks = []

    for start_row in tqdm(range(0, trx_ini.height, chunk_size), desc="Processing chunks"):
        chunk = trx_ini.slice(start_row, chunk_size)

        # Apply transformation matrix to the coordinates
        points = np.hstack([chunk.select(["x", "y"]).to_numpy(), np.ones((chunk.height, 1))])
        transformed_points = np.dot(points, transformation_matrix.T)[:, :2]

        # Create new transformed columns and drop original x, y columns
        transformed_chunk = chunk.with_columns([
            (pl.Series(transformed_points[:, 0]) * image_scale).round(2).alias("transformed_x"),
            (pl.Series(transformed_points[:, 1]) * image_scale).round(2).alias("transformed_y")
        ]).drop(["x", "y"])
        all_chunks.append(transformed_chunk)

    # Concatenate all chunks after processing
    trx = pl.concat(all_chunks)

    # Ensure the output directory exists
    if not os.path.exists(path_trx_tiles):
        os.makedirs(path_trx_tiles)

    # Get min and max x, y values
    x_min, x_max = trx.select([
        pl.col("transformed_x").min().alias("x_min"),
        pl.col("transformed_x").max().alias("x_max")
    ]).row(0)

    y_min, y_max = trx.select([
        pl.col("transformed_y").min().alias("y_min"),
        pl.col("transformed_y").max().alias("y_max")
    ]).row(0)

    # Calculate the number of fine-grain tiles globally
    n_fine_tiles_x = int(np.ceil((x_max - x_min) / fine_tile_size))
    n_fine_tiles_y = int(np.ceil((y_max - y_min) / fine_tile_size))

    # Calculate the number of coarse-grain tiles
    n_coarse_tiles_x = int(np.ceil((x_max - x_min) / coarse_tile_size))
    n_coarse_tiles_y = int(np.ceil((y_max - y_min) / coarse_tile_size))

    # Use ThreadPoolExecutor for parallel processing of coarse-grain tiles
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(n_coarse_tiles_x):
            coarse_tile_x_min = x_min + i * coarse_tile_size
            coarse_tile_x_max = coarse_tile_x_min + coarse_tile_size

            for j in range(n_coarse_tiles_y):
                coarse_tile_y_min = y_min + j * coarse_tile_size
                coarse_tile_y_max = coarse_tile_y_min + coarse_tile_size

                # Submit each coarse tile for parallel processing
                futures.append(executor.submit(
                    process_coarse_tile, trx, i, j, coarse_tile_x_min, coarse_tile_x_max, coarse_tile_y_min, coarse_tile_y_max, fine_tile_size, path_trx_tiles, x_min, y_min, n_fine_tiles_x, n_fine_tiles_y, max_workers
                ))

        # Wait for all coarse tiles to complete
        for future in tqdm(concurrent.futures.as_completed(futures), desc="Processing coarse tiles", unit="tile"):
            future.result()  # Raise exceptions if any occurred during execution

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
    """
    Processes cell boundary data and divides it into spatial tiles based on the provided technology.
    
    This function reads cell boundary data, applies transformations to the geometries, and divides the 
    processed data into spatial tiles. The resulting tiles are saved as Parquet files, each containing 
    the geometries of cells in that tile.

    Parameters:
    ----------
    technology : str
        The technology used for generating the cell boundary data. It can be "MERSCOPE", "Xenium", or "custom".
    path_cell_boundaries : str
        Path to the file containing the cell boundaries (input file in Parquet format).
    path_meta_cell_micron : str
        Path to the file containing cell metadata (CSV file).
    path_transformation_matrix : str
        Path to the file containing the transformation matrix (CSV file).
    path_output : str
        Path where the output files (Parquet files) for each tile will be saved.
    tile_size : int, optional, default=1000
        Size of each tile in microns.
    tile_bounds : dict, optional
        Dictionary containing the minimum and maximum bounds for the x and y coordinates (keys: "x_min", "x_max", "y_min", "y_max").
    image_scale : float, optional, default=0.5
        Scale factor to apply to the geometry data.

    Returns:
    --------
    None
        This function saves the results to Parquet files and doesn't return any data.
    
    """
    def batch_transform_geometries(geometries, transformation_matrix, scale):
        transformed_geometries = []
        for poly in geometries:
            transformed = transform_polygon(poly, transformation_matrix)
            scaled = simple_format(transformed, scale)
            transformed_geometries.append(scaled)
        return transformed_geometries


    tile_size_x = tile_size
    tile_size_y = tile_size

    # Load the transformation matrix
    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=" ").values

    # Load cell boundary data based on the technology
    if technology == "MERSCOPE":
        df_meta = pd.read_parquet(f"{path_output.replace('cell_segmentation','cell_metadata.parquet')}")
        entity_to_cell_id_dict = pd.Series(df_meta.index.values, index=df_meta.EntityID).to_dict()
        cells_orig = gpd.read_parquet(path_cell_boundaries)
        cells_orig['cell_id'] = cells_orig['EntityID'].map(entity_to_cell_id_dict)
        cells_orig = cells_orig[cells_orig["ZIndex"] == 1]

        # Correct cell_id issues with meta_cell
        meta_cell = pd.read_csv(path_meta_cell_micron)
        meta_cell['cell_id'] = meta_cell['EntityID'].map(entity_to_cell_id_dict)
        cells_orig.index = meta_cell[meta_cell["cell_id"].isin(cells_orig['cell_id'])].index

        # Correct 'MultiPolygon' to 'Polygon'
        cells_orig["geometry"] = cells_orig["Geometry"].apply(
            lambda x: list(x.geoms)[0] if isinstance(x, MultiPolygon) else x
        )

        cells_orig.set_index('cell_id', inplace=True)

    elif technology == "Xenium":
        xenium_cells = pd.read_parquet(path_cell_boundaries)
        grouped = xenium_cells.groupby("cell_id")[["vertex_x", "vertex_y"]].agg(lambda x: x.tolist())
        grouped["geometry"] = grouped.apply(lambda row: Polygon(zip(row["vertex_x"], row["vertex_y"])), axis=1)
        cells_orig = gpd.GeoDataFrame(grouped, geometry="geometry")[["geometry"]]

    elif technology == "custom":
        cells_orig = gpd.read_parquet(path_cell_boundaries)

    cells_orig["GEOMETRY"] = batch_transform_geometries(cells_orig["geometry"], transformation_matrix, image_scale)

    # Create polygons from transformed coordinates
    cells_orig["polygon"] = cells_orig["GEOMETRY"].apply(lambda x: Polygon(x[0]))

    # Create a GeoDataFrame with polygons and centroids
    gdf_cells = gpd.GeoDataFrame(geometry=cells_orig["polygon"])
    gdf_cells["center_x"] = gdf_cells.geometry.centroid.x
    gdf_cells["center_y"] = gdf_cells.geometry.centroid.y

    # Ensure the output directory exists
    if not os.path.exists(path_output):
        os.makedirs(path_output)

    # Get tile bounds
    x_min, x_max = tile_bounds["x_min"], tile_bounds["x_max"]
    y_min, y_max = tile_bounds["y_min"], tile_bounds["y_max"]

    # Calculate the number of tiles needed
    n_tiles_x = int(np.ceil((x_max - x_min) / tile_size_x))
    n_tiles_y = int(np.ceil((y_max - y_min) / tile_size_y))

    # Convert centroids to numpy arrays for faster filtering
    center_x = gdf_cells["center_x"].values
    center_y = gdf_cells["center_y"].values
    cell_ids = gdf_cells.index.values

    # Iterate over tiles and filter data
    for i in tqdm(range(n_tiles_x), desc="Processing rows"):
        tile_x_min = x_min + i * tile_size_x
        tile_x_max = tile_x_min + tile_size_x

        for j in tqdm(range(n_tiles_y), desc="Processing tiles", leave=False):
            tile_y_min = y_min + j * tile_size_y
            tile_y_max = tile_y_min + tile_size_y

            # Combine x and y filters into one numpy filter for faster filtering
            tile_filter = (
                (center_x >= tile_x_min) & (center_x < tile_x_max) &
                (center_y >= tile_y_min) & (center_y < tile_y_max)
            )
            filtered_indices = np.where(tile_filter)[0]

            # Skip empty tiles
            if len(filtered_indices) == 0:
                continue

            # Filter the GeoDataFrame based on the filtered indices
            keep_cells = cell_ids[filtered_indices]
            inst_geo = cells_orig.loc[keep_cells, ["GEOMETRY"]]

            # Add cell names to the geometry
            inst_geo["name"] = pd.Series(keep_cells, index=keep_cells)

            # Define the filename based on tile coordinates
            filename = f"{path_output}/cell_tile_{i}_{j}.parquet"

            # Save the filtered DataFrame to a Parquet file
            inst_geo.to_parquet(filename)



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
