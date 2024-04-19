import pyvips
from pathlib import Path
import numpy as np
import pandas as pd
import os

# function for pre-processing landscape data
def landscape(data):

    print('landscape: ' + data) 

    return data


def reduce_image_size(image_path, scale_image=0.5):
    """
    Reduce the size of an image by a factor of 0.5

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

    new_image_path = image_path.replace(".tif", "_downsize.tif")
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


def make_deepzoom_pyramid(image_path, output_path, pyramid_name, tile_size=512, overlap=0):
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
    image.dzsave(output_path, tile_size=tile_size, overlap=overlap)


def make_meta_cell_image_coord( 
        path_transformation_matrix,  
        path_meta_cell_micron,
        path_meta_cell_image
    ):
    """
    Apply an affine transformation to the cell coordinates in microns and save 
    the transformed coordinates in pixels

    Parameters
    ----------
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
    ...     path_transformation_matrix='data/transformation_matrix.txt',
    ...     path_meta_cell_micron='data/meta_cell_micron.csv',
    ...     path_meta_cell_image='data/meta_cell_image.parquet'
    ... )

    """
    
    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=' ').values

    meta_cell = pd.read_csv(path_meta_cell_micron, usecols=['center_x', 'center_y'])
    meta_cell['name'] = pd.Series(meta_cell.index, index=meta_cell.index)


    # Adding a ones column to accommodate for affine transformation
    meta_cell['ones'] = 1

    # Preparing the data for matrix multiplication
    points = meta_cell[['center_x', 'center_y', 'ones']].values

    # Applying the transformation matrix
    transformed_points = np.dot(transformation_matrix, points.T).T

    # Updating the DataFrame with transformed coordinates
    meta_cell['center_x'] = transformed_points[:, 0]
    meta_cell['center_y'] = transformed_points[:, 1]

    # Dropping the ones column as it's no longer needed
    meta_cell.drop(columns=['ones'], inplace=True)

    meta_cell['center_x'] = meta_cell['center_x'] / 2
    meta_cell['center_y'] = meta_cell['center_y'] / 2

    meta_cell['geometry'] = meta_cell.apply(lambda row: [row['center_x'], row['center_y']], axis=1)

    meta_cell[['name', 'geometry']].to_parquet(path_meta_cell_image)   


def make_trx_tiles(path_trx, path_transformation_matrix, path_trx_tiles):


    transformation_matrix = pd.read_csv(path_transformation_matrix, header=None, sep=' ').values

    trx_ini = pd.read_csv(
        path_trx, 
        usecols=['gene', 'global_x', 'global_y']
    )

    trx_ini.columns = [x.replace('global_','') for x in trx_ini.columns.tolist()]
    trx_ini.rename(columns={'gene':'name'}, inplace=True)
    trx_ini.head()

    chunk_size = 1000000

    trx = pd.DataFrame()  # Initialize empty DataFrame for results

    for start_row in range(0, trx_ini.shape[0], chunk_size):
        # print(start_row/1e6)
        chunk = trx_ini.iloc[start_row:start_row + chunk_size].copy()
        points = np.hstack((chunk[['x', 'y']], np.ones((chunk.shape[0], 1))))
        transformed_points = np.dot(points, transformation_matrix.T)[:, :2]
        chunk[['x', 'y']] = transformed_points  # Update chunk with transformed coordinates
        chunk['x'] = chunk['x'] / 2  # Adjust for downsampling
        chunk['y'] = chunk['y'] / 2

        chunk['x'] = chunk['x'].round(2)
        chunk['y'] = chunk['y'].round(2)
        trx = pd.concat([trx, chunk], ignore_index=True)    


    if not os.path.exists(path_trx_tiles):
        os.mkdir(path_trx_tiles)

    tile_size_x = 1000
    tile_size_y = 1000

    x_min = 0
    x_max = trx['x'].max()
    y_min = 0
    y_max = trx['y'].max()

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
            
            # Filter trx to get only the data within the current tile's bounds
            tile_trx = trx[(trx.x >= tile_x_min) & (trx.x < tile_x_max) & 
                        (trx.y >= tile_y_min) & (trx.y < tile_y_max)].copy()


            # make 'geometry' column
            tile_trx = tile_trx.assign(geometry=tile_trx.apply(lambda row: [row['x'], row['y']], axis=1))

            # Define the filename based on the tile's coordinates
            filename = f'{path_trx_tiles}/transcripts_tile_{i}_{j}.parquet'        

            # Save the filtered DataFrame to a Parquet file
            tile_trx[['name', 'geometry']].to_parquet(filename)


__all__ = ["landscape"]
